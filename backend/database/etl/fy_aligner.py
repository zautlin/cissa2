"""
Fiscal Year Alignment Engine.

Maps raw financial data to fiscal years.

IMPORTANT: raw_data contains periods as strings:
- FISCAL: 'FY 2003' format
- MONTHLY: '1981-11-30 00:00:00' date format

This aligner extracts fiscal_year, fiscal_month, and fiscal_day from both formats.
"""

from typing import Optional, Tuple
import re
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text


class FYAligner:
    """
    Aligns raw data to fiscal year components by extracting from period strings.
    
    Returns (fiscal_year, fiscal_month, fiscal_day) tuples:
    - FISCAL: (2003, None, None) from 'FY 2003'
    - MONTHLY: (1981, 11, 30) from '1981-11-30 00:00:00'
    """
    
    def __init__(self, db_engine: Engine):
        """
        Initialize FY aligner.
        
        Args:
            db_engine: SQLAlchemy database engine
        """
        self.engine = db_engine
        self.fiscal_year_pattern = re.compile(r'FY\s+(\d{4})')
    
    def align(
        self,
        dataset_id: str,
        metrics: Optional[list] = None,
    ) -> pd.DataFrame:
        """
        Align raw data by extracting fiscal_year, fiscal_month, fiscal_day from period strings.
        
        Returns a DataFrame with columns:
        - ticker
        - fiscal_year
        - fiscal_month (NULL for FISCAL, 1-12 for MONTHLY)
        - fiscal_day (NULL for FISCAL, 1-31 for MONTHLY)
        - metric_name
        - value
        - period_type
        - source = 'aligned'
        
        Logic:
        For each row in raw_data (ticker, metric_name, period, numeric_value, period_type):
          1. Extract (fiscal_year, fiscal_month, fiscal_day) from period string
             - FISCAL 'FY 2003' → (2003, None, None)
             - MONTHLY '1981-11-30' → (1981, 11, 30)
          2. If extraction successful, emit row with all components and period_type
          3. If extraction fails, skip row (no fiscal_year to align to)
        
        Args:
            dataset_id: UUID of dataset to align
            metrics: Optional list of metric names to filter on
            
        Returns:
            DataFrame with columns: ticker, fiscal_year, fiscal_month, fiscal_day, metric_name, value, period_type, source
        """
        # Load raw data for this dataset
        raw = self._load_raw_data(dataset_id, metrics)
        if raw.empty:
            return pd.DataFrame(columns=['ticker', 'fiscal_year', 'fiscal_month', 'fiscal_day', 'metric_name', 'value', 'period_type', 'source'])
        
        # Extract fiscal year components from period strings
        records = []
        for _, row in raw.iterrows():
            period_str = str(row['period'])
            period_type = str(row['period_type'])
            fiscal_year, fiscal_month, fiscal_day = self._extract_fiscal_year_components(period_str, period_type)
            
            if fiscal_year is not None:
                numeric_val = row['numeric_value']
                if numeric_val is not None and pd.notna(numeric_val):
                    numeric_val = float(numeric_val)
                else:
                    numeric_val = None
                
                records.append({
                    'ticker': row['ticker'],
                    'fiscal_year': fiscal_year,
                    'fiscal_month': fiscal_month,
                    'fiscal_day': fiscal_day,
                    'metric_name': row['metric_name'],
                    'value': numeric_val,
                    'period_type': period_type,
                    'source': 'aligned',
                })
        
        if not records:
            return pd.DataFrame(columns=['ticker', 'fiscal_year', 'fiscal_month', 'fiscal_day', 'metric_name', 'value', 'period_type', 'source'])
        
        return pd.DataFrame(records)
    
    def _extract_fiscal_year_components(self, period_str, period_type) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        """
        Extract (fiscal_year, fiscal_month, fiscal_day) from period string.
        
        For FISCAL periods:
          - Input: 'FY 2003', 'FY2003'
          - Output: (2003, None, None)
        
        For MONTHLY periods:
          - Input: '1981-11-30 00:00:00', '2024-01-31'
          - Output: (1981, 11, 30)
        
        Args:
            period_str: Period string from raw_data
            period_type: 'FISCAL' or 'MONTHLY'
            
        Returns:
            Tuple of (fiscal_year, fiscal_month, fiscal_day), or (None, None, None) if extraction fails
        """
        if not isinstance(period_str, str):
            return (None, None, None)
        
        # Handle FISCAL periods: "FY 2003" → (2003, None, None)
        if period_type == 'FISCAL':
            match = self.fiscal_year_pattern.search(period_str)
            if match:
                try:
                    return (int(match.group(1)), None, None)
                except (ValueError, IndexError):
                    return (None, None, None)
            return (None, None, None)
        
        # Handle MONTHLY periods: "1981-11-30 00:00:00" → (1981, 11, 30)
        if period_type == 'MONTHLY':
            try:
                date_obj = pd.to_datetime(period_str)
                return (date_obj.year, date_obj.month, date_obj.day)
            except Exception:
                return (None, None, None)
        
        return (None, None, None)
    
    def _load_raw_data(self, dataset_id: str, metrics: Optional[list] = None) -> pd.DataFrame:
        """
        Load raw data points for a given dataset.
        
        Returns DataFrame with columns: ticker, period, metric_name, numeric_value, period_type
        """
        if metrics:
            placeholders = ', '.join(f"'{m}'" for m in metrics)
            sql = f"""
                SELECT ticker, period, metric_name, numeric_value, period_type
                FROM raw_data
                WHERE dataset_id = :dataset_id
                  AND metric_name IN ({placeholders})
                  AND numeric_value IS NOT NULL
            """
        else:
            sql = """
                SELECT ticker, period, metric_name, numeric_value, period_type
                FROM raw_data
                WHERE dataset_id = :dataset_id
                  AND numeric_value IS NOT NULL
            """
        
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), {"dataset_id": dataset_id})
            rows = result.fetchall()
        
        if not rows:
            return pd.DataFrame()
        
        return pd.DataFrame(rows, columns=['ticker', 'period', 'metric_name', 'numeric_value', 'period_type'])
