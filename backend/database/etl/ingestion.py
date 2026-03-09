"""
Stage 1: Data Ingestion and Validation.

Handles CSV loading, numeric validation, and insertion into raw_data table.
"""

from typing import Dict, Any, Tuple, Optional
import json
import hashlib
import pandas as pd
import asyncio
from sqlalchemy.engine import Engine
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from .validators import validate_numeric


class DuplicateDataException(Exception):
    """
    Raised when duplicate (ticker, metric_name, period) combinations are detected in raw data.
    
    Stores the list of duplicates found so they can be logged to audit trail.
    """
    def __init__(self, duplicates: list, message: str = None):
        """
        Args:
            duplicates: List of dicts with keys: ticker, metric_name, period, original_value, imputed_value
            message: Optional custom error message
        """
        self.duplicates = duplicates
        if message is None:
            message = f"Found {len(duplicates)} duplicate (ticker, metric_name, period) combinations in raw data"
        super().__init__(message)


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
        
        # Auto-trigger L1 metrics calculation
        print("Auto-calculating L1 metrics...")
        print(f"Dataset ID: {dataset_id}")
        
        # Verify raw_data exists and is committed
        with self.engine.connect() as conn:
            count_result = conn.execute(text("""
                SELECT COUNT(*) FROM raw_data WHERE dataset_id = :dataset_id
            """), {'dataset_id': dataset_id})
            raw_count = count_result.scalar()
            print(f"Raw data rows: {raw_count}")
        
        # Give the database a moment to ensure visibility
        import time
        time.sleep(0.5)
        
        l1_metrics_result = self._auto_calculate_l1_metrics(dataset_id)
        result['l1_metrics'] = l1_metrics_result
        
        return {
            'dataset_id': str(dataset_id),
            'dataset_name': dataset_name,
            'version_number': version_number,
            'source_file': csv_path,
            'total_csv_rows': result['total_csv_rows'],
            'total_rows_processed': result['total_rows_processed'],
            'rejected_rows': result['rejected_rows'],
            'duplicate_combinations': result['duplicate_combinations'],
            'unique_rows_in_db': result['unique_rows_in_db'],
            'validation_summary': result['validation_summary'],
            'l1_metrics': result.get('l1_metrics', {}),
        }
    
    def _auto_calculate_l1_metrics(self, dataset_id: str) -> Dict[str, Any]:
        """
        Auto-trigger L1 metrics calculation at the end of ingestion.
        
        This method bridges the synchronous Ingester context with the async MetricsService
        by running the async metric calculation in an event loop.
        
        Args:
            dataset_id: UUID of the dataset that was just ingested
            
        Returns:
            Dict with L1 metrics calculation results {status, calculated, failed, errors}
        """
        try:
            # Use asyncio.run() directly - it handles event loop setup/teardown
            result = asyncio.run(self._async_calculate_l1_metrics(dataset_id))
            print(f"L1 metrics result: {result}")
            return result
        except Exception as e:
            error_str = str(e) if str(e) else repr(e)
            print(f"⚠  L1 metrics calculation failed: {error_str}")
            import traceback
            traceback.print_exc()
            return {
                'status': 'error',
                'message': error_str,
                'total_metrics': 15,
                'calculated': 0,
                'failed': 15,
                'errors': [error_str]
            }
    
    async def _async_calculate_l1_metrics(self, dataset_id: str) -> Dict[str, Any]:
        """
        Async implementation of L1 metrics calculation.
        
        Creates an async engine and session, calls MetricsService.calculate_all_l1_metrics(),
        and properly cleans up resources.
        
        Args:
            dataset_id: UUID of the dataset
            
        Returns:
            Dict with calculation results
        """
        # Import inside function to avoid import issues
        import sys
        import os
        from pathlib import Path
        
        # Get the directory structure right
        # File is at: /backend/database/etl/ingestion.py
        # Need to import from /backend/app/services/metrics_service
        etl_dir = Path(__file__).parent  # /backend/database/etl
        database_dir = etl_dir.parent  # /backend/database
        backend_dir = database_dir.parent  # /backend
        
        # Add both to path to enable proper imports
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        if str(database_dir) not in sys.path:
            sys.path.insert(0, str(database_dir))
        
        # Now imports should work
        from app.services.metrics_service import MetricsService
        from etl.config import get_db_url
        
        # Create async engine from sync config
        # The sync config includes ?options=-c search_path=cissa which asyncpg doesn't handle
        # So we need to strip it and handle search_path differently
        sync_url = get_db_url()
        # Remove the options parameter which asyncpg doesn't support
        async_url = sync_url.split('?options')[0] if '?options' in sync_url else sync_url
        async_db_url = async_url.replace('postgresql://', 'postgresql+asyncpg://')
        
        async_engine = create_async_engine(
            async_db_url, 
            echo=False,
            connect_args={
                "timeout": 10,
                "command_timeout": 60,
                "server_settings": {"search_path": "cissa"}
            }
        )
        
        try:
            # Create async session
            async_session_maker = async_sessionmaker(
                async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            async with async_session_maker() as session:
                # Verify we're in the right schema
                from sqlalchemy import text as sql_text
                schema_check = await session.execute(sql_text("SELECT current_schema()"))
                schema_name = schema_check.scalar()
                print(f"[ASYNC] Current schema: {schema_name}")
                
                # Check if raw_data table is accessible
                raw_data_check = await session.execute(sql_text(f"""
                    SELECT COUNT(*) FROM raw_data WHERE dataset_id = '{dataset_id}'
                """))
                raw_count = raw_data_check.scalar()
                print(f"[ASYNC] Raw data rows in async context: {raw_count}")
                
                # Create MetricsService and call calculate_all_l1_metrics
                metrics_service = MetricsService(session)
                
                # Convert string UUID to UUID object if needed
                from uuid import UUID
                if isinstance(dataset_id, str):
                    dataset_uuid = UUID(dataset_id)
                else:
                    dataset_uuid = dataset_id
                
                result = await metrics_service.calculate_all_l1_metrics(dataset_uuid)
                return result
        
        finally:
            # Clean up async engine
            await async_engine.dispose()
    
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
        """Update dataset_versions.metadata with full ingestion reconciliation stats."""
        metadata = {
            'stage_1_ingestion': {
                'total_csv_rows': ingestion_result['total_csv_rows'],
                'total_rows_processed': ingestion_result['total_rows_processed'],
                'rows_with_valid_numbers': ingestion_result['total_rows_processed'] - ingestion_result['rejected_rows'] - ingestion_result['duplicate_combinations'],
                'rows_with_unparseable_values': ingestion_result['rejected_rows'],
                'duplicate_combinations_found': ingestion_result['duplicate_combinations'],
                'unique_rows_in_raw_data': ingestion_result['unique_rows_in_db'],
                'rejection_summary': ingestion_result['validation_summary'],
                'reconciliation': {
                    'formula': 'unique_in_db = processed - rejects - duplicates',
                    'calculated': f"{ingestion_result['total_rows_processed']} - {ingestion_result['rejected_rows']} - {ingestion_result['duplicate_combinations']} = {ingestion_result['unique_rows_in_db']}"
                }
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
        """Load Base.csv → companies table.
        
        Assigns parent_index based on market cap ordering:
        - Top 200 companies (first 200 rows, already sorted by market cap): parent_index='ASX200'
        - Remaining companies: parent_index=NULL
        """
        df = pd.read_csv(csv_path)
        
        # Map columns from Base.csv
        company_rows = []
        for row_idx, (_, row) in enumerate(df.iterrows()):
            # Extract country from Data FX column
            currency = str(row.get('Data FX', 'AUD')).strip()
            if currency == 'USD':
                country = 'United States'
            elif currency == 'GBP':
                country = 'United Kingdom'
            else:
                country = 'Australia'
            
            # Assign parent_index: ASX200 for top 200, NULL for rest
            parent_index = 'ASX200' if row_idx < 200 else None
            
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
                'parent_index': parent_index,
                'fy_report_month': fy_report_month,
                'begin_year': int(row.get('Begin Year', 2002)) if 'Begin Year' in df.columns else None,
            })
        
        # Upsert into database
        with self.engine.begin() as conn:
            for row in company_rows:
                conn.execute(text("""
                    INSERT INTO companies (ticker, name, sector, bics_level_1, bics_level_2, bics_level_3, bics_level_4, currency, country, parent_index, fy_report_month, begin_year)
                    VALUES (:ticker, :name, :sector, :bics_level_1, :bics_level_2, :bics_level_3, :bics_level_4, :currency, :country, :parent_index, :fy_report_month, :begin_year)
                    ON CONFLICT (ticker) DO UPDATE SET
                        name = EXCLUDED.name,
                        sector = EXCLUDED.sector,
                        bics_level_1 = EXCLUDED.bics_level_1,
                        bics_level_2 = EXCLUDED.bics_level_2,
                        bics_level_3 = EXCLUDED.bics_level_3,
                        bics_level_4 = EXCLUDED.bics_level_4,
                        currency = EXCLUDED.currency,
                        country = EXCLUDED.country,
                        parent_index = EXCLUDED.parent_index,
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
    
    def _validate_metrics_against_units(self, dataset_id: str) -> Dict[str, Any]:
        """
        Validate that all metrics in raw_data have corresponding entries in metric_units.
        
        Logs warnings for any metrics without defined units.
        
        Returns:
            Dict with validation results (metrics_found, metrics_with_units, unknown_metrics)
        """
        try:
            with self.engine.connect() as conn:
                # Get all unique metrics in raw_data for this dataset
                result = conn.execute(text("""
                    SELECT DISTINCT metric_name FROM raw_data WHERE dataset_id = :dataset_id
                """), {'dataset_id': dataset_id})
                
                metrics_in_data = {row[0] for row in result.fetchall()}
                
                # Get all metrics in metric_units
                result = conn.execute(text("""
                    SELECT DISTINCT metric_name FROM metric_units
                """))
                
                metrics_with_units = {row[0] for row in result.fetchall()}
            
            # Find unknown metrics
            unknown_metrics = metrics_in_data - metrics_with_units
            
            if unknown_metrics:
                print(f"⚠  Found {len(unknown_metrics)} metrics without defined units:")
                for metric in sorted(unknown_metrics):
                    print(f"   - {metric}")
            else:
                print(f"✓ All {len(metrics_in_data)} metrics have defined units")
            
            return {
                'metrics_found': len(metrics_in_data),
                'metrics_with_units': len(metrics_with_units),
                'unknown_metrics': len(unknown_metrics),
                'unknown_metric_names': sorted(unknown_metrics),
            }
        
        except Exception as e:
            print(f"⚠  Could not validate metrics against units: {e}")
            return {
                'metrics_found': 0,
                'metrics_with_units': 0,
                'unknown_metrics': 0,
                'unknown_metric_names': [],
            }
    
    def _log_duplicates_to_audit_trail(self, dataset_id: str, duplicates_found: list[Dict[str, Any]]) -> None:
        """
        Log all detected duplicates to imputation_audit_trail table.
        
        For each duplicate (ticker, metric_name, period):
        - Extracts fiscal_year from period string if possible
        - Logs with imputation_step = 'DATA_QUALITY_DUPLICATE'
        - Stores period in metadata JSONB column
        - Records first occurrence as original_value, second as imputed_value
        
        Args:
            dataset_id: The dataset_id being ingested
            duplicates_found: List of dicts with keys: ticker, metric_name, period, occurrences
                            Each duplicate has occurrences list with value/raw_value
        """
        audit_records = []
        
        for duplicate in duplicates_found:
            ticker: str = duplicate['ticker']
            metric_name: str = duplicate['metric_name']
            period: str = duplicate['period']
            occurrences: list = duplicate['occurrences']
            
            # Extract fiscal_year from period if possible (e.g., "FY 2023" → 2023)
            fiscal_year: Optional[int] = None
            if isinstance(period, str) and period.startswith('FY '):
                try:
                    fiscal_year = int(period.split()[-1])
                except (ValueError, IndexError):
                    pass
            
            # Log using first occurrence value as original, second as imputed
            original_value = str(occurrences[0]['value'])
            imputed_value = str(occurrences[1]['value']) if len(occurrences) > 1 else str(occurrences[0]['value'])
            
            audit_records.append({
                'dataset_id': dataset_id,
                'ticker': ticker,
                'metric_name': metric_name,
                'fiscal_year': fiscal_year,
                'original_value': original_value,
                'imputed_value': imputed_value,
                'imputation_step': 'DATA_QUALITY_DUPLICATE',
                'metadata': json.dumps({'period': period, 'num_occurrences': len(occurrences)}),
            })
        
        # Insert all duplicate records at once
        if audit_records:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO imputation_audit_trail 
                    (dataset_id, ticker, metric_name, fiscal_year, original_value, imputed_value, imputation_step, metadata)
                    VALUES (:dataset_id, :ticker, :metric_name, :fiscal_year, :original_value, :imputed_value, :imputation_step, :metadata)
                """), audit_records)
    
    def _load_raw_data(self, dataset_id: str, csv_path: str) -> Dict[str, Any]:
        """Load financial_metrics_fact_table.csv → raw_data with duplicate detection.
        
        Detects ALL duplicate (ticker, metric_name, period) combinations and logs them
        to imputation_audit_trail. Continues ingestion using ON CONFLICT DO NOTHING
        to keep first occurrence and skip duplicates.
        
        Tracks all rows through the ingestion pipeline:
        - total_csv_rows: All rows in CSV file
        - total_rows_processed: Rows with valid ticker/period/metric
        - rejected_rows: Rows with unparseable numeric values
        - duplicate_combinations: Duplicate (ticker, metric_name, period) combinations detected
        
        Returns:
            Dict with ingestion statistics including duplicate_combinations count
        """
        df = pd.read_csv(csv_path)
        
        total_rows = 0
        rejected_rows = 0
        validation_summary = {}
        
        raw_data_rows = []
        # Track: (ticker, metric_name, period) → list of (row_index, value, period_type)
        combination_map = {}
        duplicates_found = []
        
        for row_idx, (_, row) in enumerate(df.iterrows(), start=2):  # Start at 2 (after header)
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
                combination = (ticker, metric_name, period)
                
                # Track for duplicate detection
                if combination not in combination_map:
                    combination_map[combination] = []
                
                combination_map[combination].append({
                    'row_index': row_idx,
                    'value': numeric_val,
                    'raw_value': raw_value,
                    'period_type': period_type,
                    'currency': currency,
                })
                
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
        
        # Check for duplicates BEFORE inserting
        duplicate_count = 0
        for (ticker, metric_name, period), occurrences in combination_map.items():
            if len(occurrences) > 1:
                # Multiple occurrences = duplicate
                duplicate_count += 1
                duplicates_found.append({
                    'ticker': ticker,
                    'metric_name': metric_name,
                    'period': period,
                    'occurrences': occurrences,
                })
        
        # If duplicates found, log them but continue ingestion
        if duplicates_found:
            self._log_duplicates_to_audit_trail(dataset_id, duplicates_found)
        
        # Insert raw data with ON CONFLICT DO NOTHING (keeps first occurrence, skips duplicates)
        if raw_data_rows:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO raw_data 
                    (dataset_id, ticker, metric_name, period, period_type, raw_string_value, numeric_value, currency)
                    VALUES (:dataset_id, :ticker, :metric_name, :period, :period_type, :raw_string_value, :numeric_value, :currency)
                    ON CONFLICT (dataset_id, ticker, metric_name, period) DO NOTHING
                """), raw_data_rows)
        
        # Query to get actual rows inserted
        unique_rows_in_db = 0
        if raw_data_rows:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM raw_data WHERE dataset_id = :dataset_id
                """), {'dataset_id': dataset_id})
                unique_rows_in_db = result.scalar()
        
        # Validate metrics against metric_units
        print()
        metrics_validation = self._validate_metrics_against_units(dataset_id)
        
        return {
            'status': 'INGESTED',
            'total_csv_rows': len(df),
            'total_rows_processed': total_rows,
            'rejected_rows': rejected_rows,
            'duplicate_combinations': duplicate_count,
            'unique_rows_in_db': unique_rows_in_db,
            'validation_summary': validation_summary,
            'metrics_validation': metrics_validation,
            'path': csv_path,
        }
