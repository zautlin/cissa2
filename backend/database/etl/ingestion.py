"""
Stage 1: Data Ingestion and Validation.

Handles CSV loading, numeric validation, and insertion into raw_data table.
"""

from typing import Dict, Any, Tuple, Optional
import json
import hashlib
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text

from .validators import validate_numeric


class Ingester:
    """
    Ingestion orchestrator for Stage 1.
    
    Loads CSV files, validates numeric values, and populates:
    - companies (reference table)
    - fiscal_year_mapping (reference table)
    - raw_data (all rows, no filtering)
    - dataset_versions (audit trail with metadata)
    """
    
    def __init__(self, db_engine: Engine):
        """
        Initialize ingester.
        
        Args:
            db_engine: SQLAlchemy database engine
        """
        self.engine = db_engine
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA256 hash of a file for duplicate detection.
        
        Args:
            file_path: Path to file
            
        Returns:
            SHA256 hash hex string
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b''):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _calculate_dataset_name(self, base_csv: str, data_df: pd.DataFrame) -> Tuple[str, str, int, int]:
        """
        Calculate dataset_name from data: <country>_<start_year>_<end_year>_<num_companies>
        
        Args:
            base_csv: Path to Base.csv (contains country)
            data_df: DataFrame of financial data
            
        Returns:
            Tuple: (dataset_name, country, start_year, end_year)
        """
        # Load Base.csv to get country (default Australia)
        base_df = pd.read_csv(base_csv)
        country = base_df['Data FX'].iloc[0] if 'Data FX' in base_df.columns else 'Australia'
        # Map currency to country
        if country == 'AUD':
            country = 'Australia'
        elif country == 'USD':
            country = 'United States'
        elif country == 'GBP':
            country = 'United Kingdom'
        else:
            country = 'Australia'  # Default fallback
        
        # Extract fiscal years from data
        fiscal_years = set()
        for period_str in data_df['Period'].unique():
            # Try to extract year from "FY XXXX" format
            if isinstance(period_str, str) and period_str.startswith('FY '):
                try:
                    year = int(period_str.split()[-1])
                    fiscal_years.add(year)
                except (ValueError, IndexError):
                    pass
        
        if fiscal_years:
            start_year = min(fiscal_years)
            end_year = max(fiscal_years)
        else:
            start_year = 0
            end_year = 0
        
        # Count unique companies
        num_companies = base_df['Ticker'].nunique()
        
        dataset_name = f"{country[:2].upper()}_{start_year}_{end_year}_{num_companies}"
        return dataset_name, country, start_year, end_year
    
    def load_reference_tables(
        self,
        base_csv: str,
        fy_dates_csv: str,
    ) -> Dict[str, Any]:
        """
        Load reference tables (one-time setup).
        
        Args:
            base_csv: Path to Base.csv (companies)
            fy_dates_csv: Path to FY Dates.csv (fiscal_year_mapping)
            
        Returns:
            Dict with load results
        """
        results = {}
        
        # Load companies
        results['companies'] = self._load_companies(base_csv)
        
        # Load FY mapping
        results['fy_dates'] = self._load_fiscal_year_mapping(fy_dates_csv)
        
        return results
    
    def load_dataset(
        self,
        csv_path: str,
        base_csv_path: Optional[str] = None,
        fy_dates_csv_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Load a complete dataset (financial_metrics_fact_table.csv → raw_data).
        
        Args:
            csv_path: Path to financial_metrics_fact_table.csv
            base_csv_path: Optional path to Base.csv (loads companies if provided)
            fy_dates_csv_path: Optional path to FY Dates.csv (loads fy mappings if provided)
            
        Returns:
            Dict with ingestion statistics including dataset_id, dataset_name, version_number
        """
        # Set defaults
        if not base_csv_path:
            base_csv_path = "input-data/ASX/extracted-worksheets/Base.csv"
        if not fy_dates_csv_path:
            fy_dates_csv_path = "input-data/ASX/extracted-worksheets/FY Dates.csv"
        
        # Load reference tables if provided
        self.load_reference_tables(
            base_csv=base_csv_path,
            fy_dates_csv=fy_dates_csv_path,
        )
        
        # Calculate file hash and dataset name
        source_file_hash = self._calculate_file_hash(csv_path)
        data_df = pd.read_csv(csv_path)
        dataset_name, country, start_year, end_year = self._calculate_dataset_name(base_csv_path, data_df)
        
        # Check if dataset already ingested (same name + hash)
        existing_version = self._check_existing_dataset(dataset_name, source_file_hash)
        if existing_version:
            version_number = existing_version + 1
        else:
            version_number = 1
        
        # Create dataset_versions entry
        dataset_id = self._create_dataset_version(
            dataset_name=dataset_name,
            version_number=version_number,
            source_file=csv_path,
            source_file_hash=source_file_hash,
        )
        
        # Load and ingest raw data
        result = self._load_raw_data(dataset_id, csv_path)
        
        # Update dataset_versions with metadata
        self._update_dataset_metadata(dataset_id, result)
        
        return {
            'dataset_id': str(dataset_id),
            'dataset_name': dataset_name,
            'version_number': version_number,
            'source_file': csv_path,
            'total_rows': result['total_rows'],
            'rejected_rows': result['rejected_rows'],
            'validation_summary': result['validation_summary'],
        }
    
    def _check_existing_dataset(self, dataset_name: str, source_file_hash: str) -> Optional[int]:
        """
        Check if dataset with same name+hash already exists.
        
        Returns:
            version_number if exists, None otherwise
        """
        with self.engine.begin() as conn:
            result = conn.execute(text("""
                SELECT version_number
                FROM dataset_versions
                WHERE dataset_name = :dataset_name AND source_file_hash = :source_file_hash
                ORDER BY version_number DESC
                LIMIT 1
            """), {'dataset_name': dataset_name, 'source_file_hash': source_file_hash})
            
            row = result.fetchone()
            return row[0] if row else None
    
    def _create_dataset_version(
        self,
        dataset_name: str,
        version_number: int,
        source_file: str,
        source_file_hash: str,
    ) -> str:
        """
        Create dataset_versions entry.
        
        Returns:
            dataset_id (UUID)
        """
        with self.engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO dataset_versions (dataset_name, version_number, source_file, source_file_hash, metadata, created_by)
                VALUES (:dataset_name, :version_number, :source_file, :source_file_hash, :metadata, 'admin')
                RETURNING dataset_id
            """), {
                'dataset_name': dataset_name,
                'version_number': version_number,
                'source_file': source_file,
                'source_file_hash': source_file_hash,
                'metadata': json.dumps({}),
            })
            return result.scalar()
    
    def _update_dataset_metadata(self, dataset_id: str, ingestion_result: Dict[str, Any]):
        """Update dataset_versions.metadata with ingestion statistics."""
        metadata = {
            'stage_1_ingestion': {
                'total_rows_ingested': ingestion_result['total_rows'],
                'rows_with_valid_numbers': ingestion_result['total_rows'] - ingestion_result['rejected_rows'],
                'rows_with_unparseable_values': ingestion_result['rejected_rows'],
                'rejection_summary': ingestion_result['validation_summary'],
            }
        }
        
        with self.engine.begin() as conn:
            conn.execute(text("""
                UPDATE dataset_versions
                SET metadata = CAST(:metadata AS jsonb)
                WHERE dataset_id = :dataset_id
            """), {
                'dataset_id': dataset_id,
                'metadata': json.dumps(metadata),
            })
    
    def _load_companies(self, csv_path: str) -> Dict[str, Any]:
        """Load Base.csv → companies table."""
        df = pd.read_csv(csv_path)
        
        # Map columns from Base.csv
        company_rows = []
        for _, row in df.iterrows():
            # Extract country from Data FX column
            currency = str(row.get('Data FX', 'AUD')).strip()
            if currency == 'USD':
                country = 'United States'
            elif currency == 'GBP':
                country = 'United Kingdom'
            else:
                country = 'Australia'
            
            # Parse FY Report Month - can be a date string (e.g., "2019-06-30 00:00:00") or int
            fy_report_month = None
            if 'FY Report Month' in df.columns:
                fy_value = row.get('FY Report Month', None)
                if fy_value is not None and fy_value != '':
                    if isinstance(fy_value, str):
                        try:
                            # Parse as date string
                            from datetime import datetime
                            dt = datetime.fromisoformat(fy_value.replace(' 00:00:00', ''))
                            fy_report_month = dt.date()
                        except (ValueError, AttributeError):
                            fy_report_month = None
                    else:
                        # If it's a numeric type, return None (we only want dates)
                        fy_report_month = None
            else:
                fy_report_month = None
            
            company_rows.append({
                'ticker': str(row.get('Ticker', '')).strip(),
                'name': str(row.get('Name', '')).strip(),
                'sector': str(row.get('Sector', '')).strip() if 'Sector' in df.columns else None,
                'bics_level_1': str(row.get('BICS 1', '')).strip() if 'BICS 1' in df.columns else None,
                'bics_level_2': str(row.get('BICS 2', '')).strip() if 'BICS 2' in df.columns else None,
                'bics_level_3': str(row.get('BICS 3', '')).strip() if 'BICS 3' in df.columns else None,
                'bics_level_4': str(row.get('BICS 4', '')).strip() if 'BICS 4' in df.columns else None,
                'currency': currency,
                'country': country,
                'fy_report_month': fy_report_month,
                'begin_year': int(row.get('Begin Year', 2002)) if 'Begin Year' in df.columns else None,
            })
        
        # Upsert into database
        with self.engine.begin() as conn:
            for row in company_rows:
                conn.execute(text("""
                    INSERT INTO companies (ticker, name, sector, bics_level_1, bics_level_2, bics_level_3, bics_level_4, currency, country, fy_report_month, begin_year)
                    VALUES (:ticker, :name, :sector, :bics_level_1, :bics_level_2, :bics_level_3, :bics_level_4, :currency, :country, :fy_report_month, :begin_year)
                    ON CONFLICT (ticker) DO UPDATE SET
                        name = EXCLUDED.name,
                        sector = EXCLUDED.sector,
                        bics_level_1 = EXCLUDED.bics_level_1,
                        bics_level_2 = EXCLUDED.bics_level_2,
                        bics_level_3 = EXCLUDED.bics_level_3,
                        bics_level_4 = EXCLUDED.bics_level_4,
                        currency = EXCLUDED.currency,
                        country = EXCLUDED.country,
                        fy_report_month = EXCLUDED.fy_report_month,
                        begin_year = EXCLUDED.begin_year
                """), row)
        
        return {'loaded': len(company_rows), 'path': csv_path}
    
    def _load_fiscal_year_mapping(self, csv_path: str) -> Dict[str, Any]:
        """Load FY Dates.csv → fiscal_year_mapping."""
        df = pd.read_csv(csv_path)
        
        # Parse FY columns (FY 2002, FY 2003, etc.)
        fy_mapping_rows = []
        for _, row in df.iterrows():
            ticker = str(row.get('Ticker', '')).strip()
            if not ticker:
                continue
            
            # Find all FY columns and parse them
            for col in df.columns:
                if col.startswith('FY'):
                    try:
                        fiscal_year = int(col.split()[-1])
                        value = row[col]
                        
                        # Handle different date formats
                        if isinstance(value, str):
                            # Parse date string (e.g., "2002-06-30 00:00:00" or "2002-06-30")
                            from datetime import datetime
                            # Remove time portion if present
                            date_str = value.split()[0] if ' ' in value else value
                            fy_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        else:
                            # Handle Excel serial number (if not a string)
                            try:
                                excel_serial = int(float(value))
                                from datetime import datetime, timedelta
                                excel_epoch = datetime(1899, 12, 30)
                                fy_date = (excel_epoch + timedelta(days=excel_serial)).date()
                            except (ValueError, TypeError):
                                continue
                        
                        fy_mapping_rows.append({
                            'ticker': ticker,
                            'fiscal_year': fiscal_year,
                            'fy_period_date': fy_date,
                        })
                    except (ValueError, TypeError):
                        continue
        
        # Upsert into database
        with self.engine.begin() as conn:
            for row in fy_mapping_rows:
                conn.execute(text("""
                    INSERT INTO fiscal_year_mapping (ticker, fiscal_year, fy_period_date)
                    VALUES (:ticker, :fiscal_year, :fy_period_date)
                    ON CONFLICT (ticker, fiscal_year) DO UPDATE SET
                        fy_period_date = EXCLUDED.fy_period_date
                """), row)
        
        return {'loaded': len(fy_mapping_rows), 'path': csv_path}
    
    def _load_raw_data(self, dataset_id: str, csv_path: str) -> Dict[str, Any]:
        """Load financial_metrics_fact_table.csv → raw_data (all rows, no filtering)."""
        df = pd.read_csv(csv_path)
        
        total_rows = 0
        rejected_rows = 0
        validation_summary = {}
        
        raw_data_rows = []
        
        for _, row in df.iterrows():
            ticker = str(row.get('Ticker', '')).strip()
            period = str(row.get('Period', '')).strip()
            period_type = str(row.get('Period_Type', '')).strip()
            metric_name = str(row.get('Metric', '')).strip()
            raw_value = str(row.get('Value', '')).strip()
            currency = str(row.get('Currency', '')).strip()
            
            if not all([ticker, period, metric_name]):
                continue
            
            total_rows += 1
            
            # Validate numeric value
            numeric_val, is_valid, rejection_reason = validate_numeric(raw_value)
            
            if is_valid:
                raw_data_rows.append({
                    'dataset_id': dataset_id,
                    'ticker': ticker,
                    'metric_name': metric_name,
                    'period': period,
                    'period_type': period_type,
                    'raw_string_value': raw_value,
                    'numeric_value': numeric_val,
                    'currency': currency,
                })
            else:
                rejected_rows += 1
                # Track rejection reasons for metadata
                if rejection_reason not in validation_summary:
                    validation_summary[rejection_reason] = 0
                validation_summary[rejection_reason] += 1
        
        # Bulk insert valid rows into raw_data
        if raw_data_rows:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO raw_data 
                    (dataset_id, ticker, metric_name, period, period_type, raw_string_value, numeric_value, currency)
                    VALUES (:dataset_id, :ticker, :metric_name, :period, :period_type, :raw_string_value, :numeric_value, :currency)
                    ON CONFLICT (dataset_id, ticker, metric_name, period) DO UPDATE SET
                        raw_string_value = EXCLUDED.raw_string_value,
                        numeric_value = EXCLUDED.numeric_value
                """), raw_data_rows)
        
        return {
            'status': 'INGESTED',
            'total_rows': total_rows,
            'rejected_rows': rejected_rows,
            'validation_summary': validation_summary,
            'path': csv_path,
        }
