"""
Fiscal Year Alignment Engine.

Maps raw calendar-year data to fiscal years using the fiscal_year_mapping table.
For each company and fiscal year, looks up which calendar year the data should
come from, then retrieves the corresponding raw value.

Refactored from reference-dq-scripts/fy_aligner.py with clean API.
"""

from typing import Optional
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text


class FYAligner:
    """
    Aligns raw calendar-year data to fiscal years.
    
    The FY mapping table stores (ticker, fiscal_year) → fy_period_date mappings,
    which tells us which calendar year's data to pull for each fiscal year.
    """
    
    def __init__(self, db_engine: Engine):
        """
        Initialize FY aligner.
        
        Args:
            db_engine: SQLAlchemy database engine
        """
        self.engine = db_engine
    
    def align(
        self,
        dataset_id: str,
        metrics: Optional[list] = None,
    ) -> pd.DataFrame:
        """
        Produce FY-aligned DataFrame from raw_data.
        
        Returns a DataFrame with columns:
        - ticker
        - fiscal_year
        - metric_name
        - value
        - source = 'aligned'
        
        Logic (INDEX/MATCH pattern):
        For each (ticker, fiscal_year, metric):
          1. Look up fiscal_year_mapping to find which calendar year to use
          2. Find raw value for (ticker, calendar_year, metric)
          3. If not found → NULL
        
        Args:
            dataset_id: UUID of dataset to align
            metrics: Optional list of metric names to filter on
            
        Returns:
            DataFrame with columns: ticker, fiscal_year, metric_name, value, source
            
        Raises:
            ValueError: If no FY mapping found for dataset
        """
        # Load FY date mapping for this dataset
        fy_map = self._load_fy_mapping(dataset_id)
        if fy_map.empty:
            raise ValueError(
                f"No fiscal_year_mapping found for dataset {dataset_id}. "
                "Ensure FY Dates.csv was loaded."
            )
        
        # Load raw data for this dataset
        raw = self._load_raw_data(dataset_id, metrics)
        if raw.empty:
            return pd.DataFrame(columns=['ticker', 'fiscal_year', 'metric_name', 'value', 'source'])
        
        # Build lookup: (ticker, period, metric) → numeric_value
        raw_lookup = raw.set_index(['ticker', 'period', 'metric_name'])['numeric_value'].to_dict()
        
        # Align: for each (ticker, fiscal_year), find the period to use
        records = []
        for _, fy_row in fy_map.iterrows():
            ticker = fy_row['ticker']
            fiscal_year = int(fy_row['fiscal_year'])
            fy_period = fy_row['fy_period_date']
            
            # Get metrics for this ticker from raw
            ticker_metrics = raw[raw['ticker'] == ticker]['metric_name'].unique()
            target_metrics = metrics if metrics else ticker_metrics
            
            for metric in target_metrics:
                # Try to find raw value for this metric
                key = (ticker, fy_period, metric)
                value = raw_lookup.get(key)
                
                records.append({
                    'ticker': ticker,
                    'fiscal_year': fiscal_year,
                    'metric_name': metric,
                    'value': float(value) if value is not None and pd.notna(value) else None,
                    'source': 'aligned',
                })
        
        if not records:
            return pd.DataFrame(columns=['ticker', 'fiscal_year', 'metric_name', 'value', 'source'])
        
        return pd.DataFrame(records)
    
    def _load_fy_mapping(self, dataset_id: str) -> pd.DataFrame:
        """
        Load the FY period mapping.
        
        Returns DataFrame with columns: ticker, fiscal_year, fy_period_date
        """
        sql = """
            SELECT ticker, fiscal_year, fy_period_date
            FROM fiscal_year_mapping
            ORDER BY ticker, fiscal_year
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
        
        if not rows:
            return pd.DataFrame()
        
        return pd.DataFrame(rows, columns=['ticker', 'fiscal_year', 'fy_period_date'])
    
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
