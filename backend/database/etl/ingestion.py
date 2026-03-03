"""
Stage 1: Data Ingestion and Validation.

Handles CSV loading, numeric validation, and insertion into raw_data table.
"""

from typing import Dict, Any
import json
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
    - metrics_catalog (reference table)
    - raw_data (staging table with validation)
    - dataset_versions (audit trail)
    """
    
    def __init__(self, db_engine: Engine):
        """
        Initialize ingester.
        
        Args:
            db_engine: SQLAlchemy database engine
        """
        self.engine = db_engine
    
    def load_reference_tables(
        self,
        base_csv: str,
        fy_dates_csv: str,
        metrics_csv: str,
    ) -> Dict[str, Any]:
        """
        Load reference tables (one-time setup).
        
        Args:
            base_csv: Path to Base.csv (companies)
            fy_dates_csv: Path to FY Dates.csv (fiscal_year_mapping)
            metrics_csv: Path to consolidated financial_metrics_fact_table.csv (metrics)
            
        Returns:
            Dict with load results
        """
        results = {}
        
        # Load companies
        results['companies'] = self._load_companies(base_csv)
        
        # Load metrics catalog
        results['metrics'] = self._load_metrics_catalog(metrics_csv)
        
        # Load FY mapping
        results['fy_dates'] = self._load_fiscal_year_mapping(fy_dates_csv)
        
        return results
    
    def load_dataset(
        self,
        dataset_id: str,
        csv_path: str,
        base_csv_path: str = None,
        fy_dates_csv_path: str = None,
    ) -> Dict[str, Any]:
        """
        Load a complete dataset (financial_metrics_fact_table.csv → raw_data).
        
        Args:
            dataset_id: UUID of dataset_versions row
            csv_path: Path to financial_metrics_fact_table.csv
            base_csv_path: Optional path to Base.csv (loads companies if provided)
            fy_dates_csv_path: Optional path to FY Dates.csv (loads fy mappings if provided)
            
        Returns:
            Dict with ingestion statistics
        """
        # Load reference tables if provided
        if base_csv_path or fy_dates_csv_path:
            self.load_reference_tables(
                base_csv=base_csv_path or "input-data/ASX/extracted-worksheets/Base.csv",
                fy_dates_csv=fy_dates_csv_path or "input-data/ASX/extracted-worksheets/FY Dates.csv",
                metrics_csv=csv_path,  # Use the metrics CSV passed in
            )
        
        # Load and validate raw data
        result = self._load_raw_data(dataset_id, csv_path)
        
        # Update dataset_versions status
        with self.engine.begin() as conn:
            conn.execute(text("""
                UPDATE dataset_versions
                SET status = 'INGESTED',
                    ingestion_completed_at = now(),
                    total_raw_rows = :total_rows,
                    validation_rejected_rows = :rejected_rows,
                    validation_reject_summary = CAST(:summary AS jsonb)
                WHERE dataset_id = :dataset_id
            """), {
                "dataset_id": dataset_id,
                "total_rows": result['total_rows'],
                "rejected_rows": result['rejected_rows'],
                "summary": json.dumps(result['validation_summary']),
            })
        
        return result
    
    def _load_companies(self, csv_path: str) -> Dict[str, Any]:
        """Load Base.csv → companies table."""
        df = pd.read_csv(csv_path)
        
        # Map columns from Base.csv
        company_rows = []
        for _, row in df.iterrows():
            company_rows.append({
                'ticker': str(row.get('Ticker', '')).strip(),
                'name': str(row.get('Name', '')).strip(),
                'sector': str(row.get('Sector', '')).strip() if 'Sector' in df.columns else None,
                'bics_level_1': str(row.get('BICS 1', '')).strip() if 'BICS 1' in df.columns else None,
                'bics_level_2': str(row.get('BICS 2', '')).strip() if 'BICS 2' in df.columns else None,
                'bics_level_3': str(row.get('BICS 3', '')).strip() if 'BICS 3' in df.columns else None,
                'bics_level_4': str(row.get('BICS 4', '')).strip() if 'BICS 4' in df.columns else None,
                'currency': str(row.get('Data FX', 'AUD')).strip(),
            })
        
        # Upsert into database
        with self.engine.begin() as conn:
            for row in company_rows:
                conn.execute(text("""
                    INSERT INTO companies (ticker, name, sector, bics_level_1, bics_level_2, bics_level_3, bics_level_4, currency)
                    VALUES (:ticker, :name, :sector, :bics_level_1, :bics_level_2, :bics_level_3, :bics_level_4, :currency)
                    ON CONFLICT (ticker) DO UPDATE SET
                        name = EXCLUDED.name,
                        sector = EXCLUDED.sector,
                        bics_level_1 = EXCLUDED.bics_level_1,
                        bics_level_2 = EXCLUDED.bics_level_2,
                        bics_level_3 = EXCLUDED.bics_level_3,
                        bics_level_4 = EXCLUDED.bics_level_4,
                        currency = EXCLUDED.currency
                """), row)
        
        return {'loaded': len(company_rows), 'path': csv_path}
    
    def _load_metrics_catalog(self, csv_path: str) -> Dict[str, Any]:
        """Extract and load unique metrics from financial_metrics_fact_table.csv."""
        df = pd.read_csv(csv_path)
        
        # Extract unique metrics
        metrics = df['Metric'].unique()
        period_types = df['Period_Type'].unique()
        
        # Upsert into metrics_catalog
        with self.engine.begin() as conn:
            for metric in metrics:
                # Determine if FISCAL or MONTHLY (assume FISCAL if not explicitly MONTHLY)
                metric_type = 'FISCAL'
                if 'MONTHLY' in str(period_types).upper():
                    metric_type = 'MONTHLY'
                
                conn.execute(text("""
                    INSERT INTO metrics_catalog (metric_name, metric_type, active)
                    VALUES (:metric_name, :metric_type, TRUE)
                    ON CONFLICT (metric_name) DO NOTHING
                """), {'metric_name': metric, 'metric_type': metric_type})
        
        return {'loaded': len(metrics), 'path': csv_path}
    
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
                        # Value is Excel date serial; convert to date
                        excel_serial = int(float(row[col]))
                        # Excel epoch: 1899-12-30
                        from datetime import datetime, timedelta
                        excel_epoch = datetime(1899, 12, 30)
                        fy_date = excel_epoch + timedelta(days=excel_serial)
                        fy_mapping_rows.append({
                            'ticker': ticker,
                            'fiscal_year': fiscal_year,
                            'fy_period_date': fy_date.date(),
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
        """Load financial_metrics_fact_table.csv → raw_data with validation."""
        df = pd.read_csv(csv_path)
        
        total_rows = 0
        rejected_rows = 0
        validation_summary = {}
        
        raw_data_rows = []
        rejected_rows_list = []
        
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
                    'validation_status': 'VALID',
                    'rejection_reason': None,
                })
            else:
                rejected_rows += 1
                rejected_rows_list.append({
                    'dataset_id': dataset_id,
                    'ticker': ticker,
                    'metric_name': metric_name,
                    'period': period,
                    'raw_string_value': raw_value,
                    'numeric_value': None,
                    'currency': currency,
                    'validation_status': 'REJECTED',
                    'rejection_reason': rejection_reason,
                })
                
                # Track rejection reasons
                if rejection_reason not in validation_summary:
                    validation_summary[rejection_reason] = 0
                validation_summary[rejection_reason] += 1
        
        # Bulk insert into raw_data
        if raw_data_rows:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO raw_data 
                    (dataset_id, ticker, metric_name, period, period_type, raw_string_value, numeric_value, currency, validation_status, rejection_reason)
                    VALUES (:dataset_id, :ticker, :metric_name, :period, :period_type, :raw_string_value, :numeric_value, :currency, :validation_status, :rejection_reason)
                    ON CONFLICT (dataset_id, ticker, metric_name, period) DO UPDATE SET
                        raw_string_value = EXCLUDED.raw_string_value,
                        numeric_value = EXCLUDED.numeric_value,
                        validation_status = EXCLUDED.validation_status
                """), raw_data_rows)
        
        # Optional: log rejected rows
        if rejected_rows_list:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO raw_data 
                    (dataset_id, ticker, metric_name, period, period_type, raw_string_value, numeric_value, currency, validation_status, rejection_reason)
                    VALUES (:dataset_id, :ticker, :metric_name, :period, :period_type, :raw_string_value, :numeric_value, :currency, :validation_status, :rejection_reason)
                """), rejected_rows_list)
        
        return {
            'status': 'INGESTED',
            'total_rows': total_rows,
            'rejected_rows': rejected_rows,
            'validation_summary': validation_summary,
            'path': csv_path,
        }
