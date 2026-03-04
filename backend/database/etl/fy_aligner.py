"""
Fiscal Year Alignment Engine.

Maps raw financial data to fiscal years.

IMPORTANT: raw_data contains periods as strings (e.g., 'FY 2003').
This aligner extracts the fiscal_year from the period string and uses that
to create aligned output. No mapping to calendar dates is needed — the fiscal_year
is already encoded in the period string.
"""

from typing import Optional
import re
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text


class FYAligner:
    """
    Aligns raw data to fiscal years by extracting fiscal_year from period strings.
    
    Raw data contains periods like 'FY 2003'. We extract the year and use it directly
    as the fiscal_year, without needing calendar-year translation.
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
        Align raw data by extracting fiscal_year from period strings.
        
        Returns a DataFrame with columns:
        - ticker
        - fiscal_year
        - metric_name
        - value
        - source = 'aligned'
        
        Logic:
        For each row in raw_data (ticker, metric_name, period, numeric_value):
          1. Extract fiscal_year from period string (e.g., 'FY 2003' → 2003)
          2. If extraction successful, emit row with (ticker, fiscal_year, metric_name, value)
          3. If extraction fails, skip row (no fiscal_year to align to)
        
        Args:
            dataset_id: UUID of dataset to align (not currently used, but kept for API compatibility)
            metrics: Optional list of metric names to filter on
            
        Returns:
            DataFrame with columns: ticker, fiscal_year, metric_name, value, source
        """
        # Load raw data for this dataset
        raw = self._load_raw_data(dataset_id, metrics)
        if raw.empty:
            return pd.DataFrame(columns=['ticker', 'fiscal_year', 'metric_name', 'value', 'source'])
        
        # Extract fiscal_year from period strings
        records = []
        for _, row in raw.iterrows():
            period_str = row['period']
            fiscal_year = self._extract_fiscal_year(period_str)
            
            if fiscal_year is not None:
                records.append({
                    'ticker': row['ticker'],
                    'fiscal_year': fiscal_year,
                    'metric_name': row['metric_name'],
                    'value': float(row['numeric_value']) if row['numeric_value'] is not None and pd.notna(row['numeric_value']) else None,
                    'source': 'aligned',
                })
        
        if not records:
            return pd.DataFrame(columns=['ticker', 'fiscal_year', 'metric_name', 'value', 'source'])
        
        return pd.DataFrame(records)
    
    def _extract_fiscal_year(self, period_str: str) -> Optional[int]:
        """
        Extract fiscal year from period string.
        
        Examples:
        - 'FY 2003' → 2003
        - 'FY2003' → 2003
        - '2003-12-31 00:00:00' → None (calendar date, not fiscal year)
        - 'FY 2004' → 2004
        
        Args:
            period_str: Period string from raw_data
            
        Returns:
            Fiscal year as integer, or None if extraction fails
        """
        if not isinstance(period_str, str):
            return None
        
        match = self.fiscal_year_pattern.search(period_str)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                return None
        
        return None
    
    def _load_raw_data(self, dataset_id: str, metrics: Optional[list] = None) -> pd.DataFrame:
        """
        Load raw data points for a given dataset.
        
        Returns DataFrame with columns: ticker, period, metric_name, numeric_value
        """
        if metrics:
            placeholders = ', '.join(f"'{m}'" for m in metrics)
            sql = f"""
                SELECT ticker, period, metric_name, numeric_value
                FROM raw_data
                WHERE dataset_id = :dataset_id
                  AND metric_name IN ({placeholders})
                  AND numeric_value IS NOT NULL
            """
        else:
            sql = """
                SELECT ticker, period, metric_name, numeric_value
                FROM raw_data
                WHERE dataset_id = :dataset_id
                  AND numeric_value IS NOT NULL
            """
        
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), {"dataset_id": dataset_id})
            rows = result.fetchall()
        
        if not rows:
            return pd.DataFrame()
        
        return pd.DataFrame(rows, columns=['ticker', 'period', 'metric_name', 'numeric_value'])
