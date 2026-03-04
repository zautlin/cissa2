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
        
        Handles both FISCAL and MONTHLY data separately to avoid imputation bleed-through.
        
        Args:
            dataset_id: UUID of dataset to process
            
        Returns:
            Dict with processing results and statistics
        """
        print(f"[DataQualityProcessor] Starting process_dataset: {dataset_id}")
        
        try:
            # Step 1: FY-align raw data
            print("  [1/5] FY-aligning raw data...")
            aligned_df = self.fy_aligner.align(dataset_id)
            print(f"    ✓ Aligned {len(aligned_df)} records (fiscal_year, fiscal_month, fiscal_day, metric) tuples")
            
            # Step 2: Split by period_type for separate imputation
            print("  [2/5] Separating FISCAL and MONTHLY data...")
            fiscal_df = aligned_df[aligned_df['period_type'] == 'FISCAL'].copy()
            monthly_df = aligned_df[aligned_df['period_type'] == 'MONTHLY'].copy()
            print(f"    ✓ FISCAL records: {len(fiscal_df)}, MONTHLY records: {len(monthly_df)}")
            
            # Step 3: Convert to wide format and build period_type_map for each
            print("  [3/5] Converting to wide format...")
            sector_map = self.imputation._load_sector_map()
            
            # Process FISCAL data
            fiscal_clean, fiscal_source, fiscal_imputation_log = None, None, {}
            if not fiscal_df.empty:
                print("    - Processing FISCAL data...")
                fiscal_period_type_map = self._build_period_type_map(fiscal_df, 'FISCAL')
                fiscal_wide_df = self._convert_to_wide(fiscal_df, 'FISCAL')
                print(f"      ✓ FISCAL wide format: {fiscal_wide_df.shape[0]} rows × {fiscal_wide_df.shape[1]-2} metrics (2-part index)")
                fiscal_clean, fiscal_source, fiscal_imputation_log = self.imputation.impute(fiscal_wide_df, sector_map)
            
            # Process MONTHLY data
            monthly_clean, monthly_source, monthly_imputation_log = None, None, {}
            if not monthly_df.empty:
                print("    - Processing MONTHLY data...")
                monthly_period_type_map = self._build_period_type_map(monthly_df, 'MONTHLY')
                monthly_wide_df = self._convert_to_wide(monthly_df, 'MONTHLY')
                print(f"      ✓ MONTHLY wide format: {monthly_wide_df.shape[0]} rows × {monthly_wide_df.shape[1]-4} metrics (4-part index)")
                monthly_clean, monthly_source, monthly_imputation_log = self.imputation.impute(monthly_wide_df, sector_map)
            
            # Step 4: Print imputation statistics
            print("  [4/5] Imputation complete. Statistics:")
            combined_log = {**fiscal_imputation_log, **monthly_imputation_log}
            for metric, counts in sorted(combined_log.items()):
                total = sum(counts.values())
                print(f"      {metric:30s}: {total:6d} total (raw: {counts.get('RAW', 0):5d}, missing: {counts.get('MISSING', 0):5d})")
            
            # Step 5: Write fundamentals table
            print("  [5/5] Writing fundamentals table...")
            n_rows = 0
            if fiscal_clean is not None and not fiscal_clean.empty:
                n_rows += self._write_fundamentals(dataset_id, fiscal_clean, fiscal_source, fiscal_period_type_map, 'FISCAL')
            if monthly_clean is not None and not monthly_clean.empty:
                n_rows += self._write_fundamentals(dataset_id, monthly_clean, monthly_source, monthly_period_type_map, 'MONTHLY')
            print(f"    ✓ Wrote {n_rows} fundamentals rows")
            
            # Calculate quality metadata
            quality_metadata = self._calculate_quality_metadata(combined_log, n_rows)
            
            # Update dataset_versions with success
            with self.engine.begin() as conn:
                quality_metadata_json = json.dumps(quality_metadata)
                conn.exec_driver_sql("""
                    UPDATE dataset_versions
                    SET metadata = metadata || jsonb_build_object(
                        'status', 'PROCESSED',
                        'processing_completed_at', now(),
                        'quality_metadata', %s::jsonb
                    )
                    WHERE dataset_id = %s
                """, (quality_metadata_json, str(dataset_id)))
            
            print(f"[DataQualityProcessor] ✓ Done. dataset_id={dataset_id}")
            
            return {
                'status': 'PROCESSED',
                'fundamentals_rows': n_rows,
                'imputation_stats': combined_log,
                'quality_metadata': quality_metadata,
                'dataset_id': dataset_id,
            }
        
        except Exception as e:
            print(f"[DataQualityProcessor] ✗ Error: {e}")
            raise
    
    def _build_period_type_map(self, df: pd.DataFrame, period_type: str) -> dict:
        """
        Build map from index tuple → period_type string.
        
        The index structure depends on period_type:
        - FISCAL (2-part): Maps (ticker, fiscal_year) → 'FISCAL'
        - MONTHLY (4-part): Maps (ticker, fiscal_year, fiscal_month, fiscal_day) → 'MONTHLY'
        
        This map is used during _write_fundamentals to reconstruct the period_type
        for each row based on its position after imputation.
        
        Args:
            df: Aligned DataFrame with period_type column
            period_type: 'FISCAL' or 'MONTHLY' to determine index structure
            
        Returns:
            Dict mapping index tuple → period_type string
        """
        if period_type == 'FISCAL':
            # FISCAL: 2-part index key
            period_map = df.groupby(['ticker', 'fiscal_year'])['period_type'].first().reset_index()
            period_map = period_map.set_index(['ticker', 'fiscal_year'])['period_type'].to_dict()
        else:  # period_type == 'MONTHLY'
            # MONTHLY: 4-part index key
            period_map = df.groupby(['ticker', 'fiscal_year', 'fiscal_month', 'fiscal_day'])['period_type'].first().reset_index()
            period_map = period_map.set_index(['ticker', 'fiscal_year', 'fiscal_month', 'fiscal_day'])['period_type'].to_dict()
        
        return period_map
    
    def _convert_to_wide(self, df: pd.DataFrame, period_type: str) -> pd.DataFrame:
        """
        Convert aligned DataFrame to wide format with appropriate index structure.
        
        INDEX STRATEGY:
        - FISCAL (period_type='FISCAL'): Uses (ticker, fiscal_year) as 2-part index
          * All FISCAL records have fiscal_month=NULL, fiscal_day=NULL
          * Pivoting on 4-part index would treat each NULL as a separate value
          * Result: 0 rows (pivot can't aggregate on multiple NULL values)
          * Solution: Use 2-part index to get 1 row per company per fiscal year
          * Output: ~500 companies × 22 years = ~11,000 rows
        
        - MONTHLY (period_type='MONTHLY'): Uses (ticker, fiscal_year, fiscal_month, fiscal_day) as 4-part index
          * All date components populated for monthly data
          * Each month-day is a unique observation
          * Pivoting creates 1 row per unique (ticker, year, month, day) combination
          * Output: ~500 companies × many months = ~133,000 rows
        
        Args:
            df: Aligned DataFrame with columns: ticker, fiscal_year, fiscal_month, fiscal_day, metric_name, value
            period_type: 'FISCAL' or 'MONTHLY' to determine index structure
            
        Returns:
            Wide DataFrame with appropriate index and metric columns
        """
        # Choose index based on period type
        if period_type == 'FISCAL':
            # FISCAL: 2-part index (month/day always NULL)
            index = ['ticker', 'fiscal_year']
        else:  # period_type == 'MONTHLY'
            # MONTHLY: 4-part index (all date components populated)
            index = ['ticker', 'fiscal_year', 'fiscal_month', 'fiscal_day']
        
        wide_df = df.pivot_table(
            index=index,
            columns='metric_name',
            values='value',
            aggfunc='first',
        ).reset_index()
        wide_df.columns.name = None
        return wide_df
    
    def _write_fundamentals(
        self,
        dataset_id: str,
        wide_clean: pd.DataFrame,
        source_wide: pd.DataFrame,
        period_type_map: dict,
        period_type: str,
    ) -> int:
        """
        Write cleaned data to fundamentals table with appropriate index handling.
        
        INDEX HANDLING:
        - FISCAL (period_type='FISCAL'): wide_clean has 2-part index (ticker, fiscal_year)
          * fiscal_month and fiscal_day are NOT columns (they are NULL in final output)
          * period_type_map keys are (ticker, fiscal_year) tuples
        
        - MONTHLY (period_type='MONTHLY'): wide_clean has 4-part index (ticker, fiscal_year, fiscal_month, fiscal_day)
          * fiscal_month and fiscal_day ARE present as columns
          * period_type_map keys are (ticker, fiscal_year, fiscal_month, fiscal_day) tuples
        
        Args:
            dataset_id: UUID of dataset
            wide_clean: Wide DataFrame with cleaned values
            source_wide: Wide DataFrame with imputation sources
            period_type_map: Dict mapping index tuple → period_type
            period_type: 'FISCAL' or 'MONTHLY' to determine index structure
            
        Returns:
            Number of rows written to fundamentals table
        """
        metrics = [c for c in wide_clean.columns if c not in ('ticker', 'fiscal_year', 'fiscal_month', 'fiscal_day')]
        
        rows = []
        for _, row in wide_clean.iterrows():
            ticker = str(row['ticker'])
            fiscal_year = int(row['fiscal_year'])
            
            # Handle fiscal_month and fiscal_day based on period_type
            if period_type == 'FISCAL':
                # FISCAL: month/day are NOT in the wide DataFrame
                fiscal_month = None
                fiscal_day = None
                index_key = (ticker, fiscal_year)
            else:  # period_type == 'MONTHLY'
                # MONTHLY: month/day ARE in the wide DataFrame
                fiscal_month = row['fiscal_month']
                fiscal_day = row['fiscal_day']
                
                # Convert NaN to None for nullable columns
                if pd.isna(fiscal_month):
                    fiscal_month = None
                else:
                    fiscal_month = int(fiscal_month)
                
                if pd.isna(fiscal_day):
                    fiscal_day = None
                else:
                    fiscal_day = int(fiscal_day)
                
                index_key = (ticker, fiscal_year, fiscal_month, fiscal_day)
            
            period_type_val = period_type_map.get(index_key, period_type)
            
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
                if pd.isna(val):
                    continue
                
                # Store imputation metadata as JSONB
                metadata = {
                    'imputation_source': src,
                    'confidence_level': confidence,
                }
                
                rows.append({
                    'dataset_id': dataset_id,
                    'ticker': ticker,
                    'metric_name': metric,
                    'fiscal_year': fiscal_year,
                    'fiscal_month': fiscal_month,
                    'fiscal_day': fiscal_day,
                    'numeric_value': float(val),
                    'currency': 'AUD',  # Default to AUD for ASX data
                    'period_type': period_type_val,
                    'imputed': src != 'RAW',  # True if source is anything other than RAW
                    'metadata': json.dumps(metadata),
                })
        
        # Bulk insert
        if rows:
            with self.engine.begin() as conn:
                stmt = """
                    INSERT INTO fundamentals 
                    (dataset_id, ticker, metric_name, fiscal_year, fiscal_month, fiscal_day, numeric_value, currency, period_type, imputed, metadata)
                    VALUES (%(dataset_id)s, %(ticker)s, %(metric_name)s, %(fiscal_year)s, %(fiscal_month)s, %(fiscal_day)s, %(numeric_value)s, %(currency)s, %(period_type)s, %(imputed)s, %(metadata)s::jsonb)
                """
                conn.exec_driver_sql(stmt, rows)
        
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
