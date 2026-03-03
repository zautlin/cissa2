"""
Stage 2: Data Processing (FY Alignment + Imputation).

Orchestrates the quality processing pipeline:
1. FY-align raw data (calendar year → fiscal year)
2. Run 7-step imputation cascade
3. Write fundamentals table
4. Update dataset_versions with quality metadata
"""

from typing import Dict, Any
import json
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text

from .fy_aligner import FYAligner
from .imputation_engine import ImputationCascade


class DataQualityProcessor:
    """
    Stage 2 orchestrator: FY alignment + imputation.
    
    Transforms raw_data into fundamentals:
    1. Load raw_data from database
    2. FY-align using fiscal_year_mapping
    3. Run 7-step imputation cascade
    4. Track imputation sources
    5. Write to fundamentals table
    6. Update dataset_versions with quality stats
    """
    
    def __init__(self, db_engine: Engine):
        """
        Initialize processor.
        
        Args:
            db_engine: SQLAlchemy database engine
        """
        self.engine = db_engine
        self.fy_aligner = FYAligner(db_engine)
        self.imputation = ImputationCascade(db_engine)
    
    def process_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """
        Execute complete Stage 2 processing.
        
        Args:
            dataset_id: UUID of dataset to process
            
        Returns:
            Dict with processing results and statistics
        """
        print(f"[DataQualityProcessor] Starting process_dataset: {dataset_id}")
        
        # Update dataset_versions status
        with self.engine.begin() as conn:
            conn.execute(text("""
                UPDATE dataset_versions
                SET status = 'PROCESSING',
                    processing_timestamp = now()
                WHERE dataset_id = :dataset_id
            """), {"dataset_id": dataset_id})
        
        try:
            # Step 1: FY-align raw data
            print("  [1/4] FY-aligning raw data...")
            aligned_df = self.fy_aligner.align(dataset_id)
            print(f"    ✓ Aligned {len(aligned_df)} (ticker, fiscal_year, metric) tuples")
            
            # Step 2: Convert to wide format for imputation
            print("  [2/4] Converting to wide format...")
            wide_df = aligned_df.pivot_table(
                index=['ticker', 'fiscal_year'],
                columns='metric_name',
                values='value',
                aggfunc='first',
            ).reset_index()
            wide_df.columns.name = None
            print(f"    ✓ Wide format: {wide_df.shape[0]} (ticker, fiscal_year) rows × {wide_df.shape[1]-2} metrics")
            
            # Step 3: Run imputation cascade
            print("  [3/4] Running 7-step imputation cascade...")
            sector_map = self.imputation._load_sector_map()
            wide_clean, source_wide, imputation_log = self.imputation.impute(wide_df, sector_map)
            print("    ✓ Imputation complete. Statistics:")
            for metric, counts in sorted(imputation_log.items()):
                total = sum(counts.values())
                print(f"      {metric:30s}: {total:6d} total (raw: {counts.get('RAW', 0):5d}, missing: {counts.get('MISSING', 0):5d})")
            
            # Step 4: Write fundamentals table
            print("  [4/4] Writing fundamentals table...")
            n_rows = self._write_fundamentals(dataset_id, wide_clean, source_wide)
            print(f"    ✓ Wrote {n_rows} fundamentals rows")
            
            # Calculate quality metadata
            quality_metadata = self._calculate_quality_metadata(imputation_log, n_rows)
            
            # Update dataset_versions with success
            with self.engine.begin() as conn:
                conn.execute(text("""
                    UPDATE dataset_versions
                    SET status = 'PROCESSED',
                        processing_completed_at = now(),
                        quality_metadata = CAST(:quality_metadata AS jsonb)
                    WHERE dataset_id = :dataset_id
                """), {
                    "dataset_id": dataset_id,
                    "quality_metadata": json.dumps(quality_metadata),
                })
            
            print(f"[DataQualityProcessor] ✓ Done. dataset_id={dataset_id}")
            
            return {
                'status': 'PROCESSED',
                'fundamentals_rows': n_rows,
                'imputation_stats': imputation_log,
                'quality_metadata': quality_metadata,
                'dataset_id': dataset_id,
            }
        
        except Exception as e:
            print(f"[DataQualityProcessor] ✗ Error: {e}")
            
            # Update dataset_versions with error
            with self.engine.begin() as conn:
                conn.execute(text("""
                    UPDATE dataset_versions
                    SET status = 'ERROR',
                        processing_completed_at = now(),
                        notes = :error_msg
                    WHERE dataset_id = :dataset_id
                """), {
                    "dataset_id": dataset_id,
                    "error_msg": str(e),
                })
            
            raise
    
    def _write_fundamentals(
        self,
        dataset_id: str,
        wide_clean: pd.DataFrame,
        source_wide: pd.DataFrame,
    ) -> int:
        """
        Write cleaned data to fundamentals table.
        
        Args:
            dataset_id: UUID of dataset
            wide_clean: Wide DataFrame with cleaned values
            source_wide: Wide DataFrame with imputation sources
            
        Returns:
            Number of rows written
        """
        metrics = [c for c in wide_clean.columns if c not in ('ticker', 'fiscal_year')]
        
        rows = []
        for _, row in wide_clean.iterrows():
            ticker = row['ticker']
            fiscal_year = int(row['fiscal_year'])
            
            for metric in metrics:
                val = row[metric]
                src = source_wide.loc[row.name, metric]
                
                # Determine confidence level based on source
                confidence_map = {
                    'RAW': 'HIGH',
                    'FORWARD_FILL': 'MEDIUM',
                    'BACKWARD_FILL': 'MEDIUM',
                    'INTERPOLATED': 'MEDIUM',
                    'SECTOR_MEDIAN': 'LOW',
                    'MARKET_MEDIAN': 'LOW',
                    'MISSING': None,
                }
                confidence = confidence_map.get(src)
                
                # Skip missing values (val is NaN)
                if pd.isna(val) if val is not None else True:
                    continue
                
                rows.append({
                    'dataset_id': dataset_id,
                    'ticker': ticker,
                    'metric_name': metric,
                    'fiscal_year': fiscal_year,
                    'value': float(val),
                    'imputation_source': src,
                    'confidence_level': confidence,
                    'data_quality_flags': '{}',  # Empty flags initially
                })
        
        # Bulk insert
        if rows:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO fundamentals 
                    (dataset_id, ticker, metric_name, fiscal_year, value, imputation_source, confidence_level, data_quality_flags)
                    VALUES (:dataset_id, :ticker, :metric_name, :fiscal_year, :value, :imputation_source, :confidence_level, :data_quality_flags::jsonb)
                """), rows)
        
        return len(rows)
    
    def _calculate_quality_metadata(self, imputation_log: Dict, n_rows: int) -> Dict[str, Any]:
        """
        Calculate quality summary statistics.
        
        Args:
            imputation_log: Imputation stats from cascade
            n_rows: Number of rows written to fundamentals
            
        Returns:
            Dict with quality metadata
        """
        total_cells = 0
        sources_count = {}
        
        for metric, counts in imputation_log.items():
            for source, count in counts.items():
                total_cells += count
                sources_count[source] = sources_count.get(source, 0) + count
        
        # Calculate fill rate (non-missing / total)
        missing_count = sources_count.get('MISSING', 0)
        fill_rate = (total_cells - missing_count) / total_cells if total_cells > 0 else 0
        
        return {
            'total_cells': total_cells,
            'fundamentals_rows': n_rows,
            **sources_count,
            'fill_rate': round(fill_rate, 4),
        }
