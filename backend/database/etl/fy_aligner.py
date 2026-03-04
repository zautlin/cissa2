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
import logging
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text

logger = logging.getLogger(__name__)


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
        # Case-insensitive, flexible whitespace: handles "FY 2003", "fy 2003", "FY2003", etc.
        self.fiscal_year_pattern = re.compile(r'fy\s*(\d{4})', re.IGNORECASE)
        
        # Track statistics for debugging
        self.fiscal_extracted = 0
        self.fiscal_failed = 0
        self.monthly_extracted = 0
        self.monthly_failed = 0
        self.skipped_null_period_type = 0
    
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
        # Reset statistics
        self.fiscal_extracted = 0
        self.fiscal_failed = 0
        self.monthly_extracted = 0
        self.monthly_failed = 0
        self.skipped_null_period_type = 0
        
        # Load raw data for this dataset
        raw = self._load_raw_data(dataset_id, metrics)
        if raw.empty:
            logger.warning("No raw data loaded for dataset_id: %s", dataset_id)
            return pd.DataFrame(columns=['ticker', 'fiscal_year', 'fiscal_month', 'fiscal_day', 'metric_name', 'value', 'period_type', 'source'])
        
        logger.info("Loaded %d rows from raw_data for alignment", len(raw))
        
        # Extract fiscal year components from period strings
        records = []
        failed_samples = {'FISCAL': [], 'MONTHLY': []}
        
        for _, row in raw.iterrows():
            period_str = str(row['period']).strip()
            period_type_raw = row['period_type']
            
            # Handle None/null period_type
            if pd.isna(period_type_raw):
                self.skipped_null_period_type += 1
                continue
            
            period_type = str(period_type_raw).strip()
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
            else:
                # Capture failed samples for debugging
                if period_type in failed_samples and len(failed_samples[period_type]) < 5:
                    failed_samples[period_type].append({
                        'ticker': row['ticker'],
                        'period': period_str,
                        'period_type': period_type,
                        'metric': row['metric_name']
                    })
        
        # Log extraction statistics
        logger.info("✓ Alignment complete:")
        logger.info("  - FISCAL extracted: %d", self.fiscal_extracted)
        logger.info("  - FISCAL failed: %d", self.fiscal_failed)
        logger.info("  - MONTHLY extracted: %d", self.monthly_extracted)
        logger.info("  - MONTHLY failed: %d", self.monthly_failed)
        logger.info("  - Skipped (null period_type): %d", self.skipped_null_period_type)
        logger.info("  - Total successful records: %d", len(records))
        
        if failed_samples['FISCAL']:
            logger.warning("  - FISCAL extraction failures (sample): %s", failed_samples['FISCAL'][:3])
        if failed_samples['MONTHLY']:
            logger.warning("  - MONTHLY extraction failures (sample): %s", failed_samples['MONTHLY'][:3])
        
        if not records:
            logger.error("No records successfully extracted after alignment!")
            return pd.DataFrame(columns=['ticker', 'fiscal_year', 'fiscal_month', 'fiscal_day', 'metric_name', 'value', 'period_type', 'source'])
        
        return pd.DataFrame(records)
    
    def _extract_fiscal_year_components(self, period_str, period_type) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        """
        Extract (fiscal_year, fiscal_month, fiscal_day) from period string.
        
        For FISCAL periods:
          - Input: 'FY 2003', 'FY2003', 'fy 2003', etc.
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
            logger.debug("Period is not a string: type=%s, value=%s", type(period_str), period_str)
            return (None, None, None)
        
        period_str = period_str.strip()
        
        # Handle FISCAL periods: "FY 2003" → (2003, None, None)
        if period_type.upper() == 'FISCAL':
            match = self.fiscal_year_pattern.search(period_str)
            if match:
                try:
                    fiscal_year = int(match.group(1))
                    self.fiscal_extracted += 1
                    logger.debug("FISCAL extracted: %s → %d", period_str, fiscal_year)
                    return (fiscal_year, None, None)
                except (ValueError, IndexError) as e:
                    self.fiscal_failed += 1
                    logger.warning("FISCAL extraction failed for '%s': %s", period_str, str(e))
                    return (None, None, None)
            else:
                self.fiscal_failed += 1
                logger.debug("FISCAL regex no match: '%s' (pattern: %s)", period_str, self.fiscal_year_pattern.pattern)
                return (None, None, None)
        
        # Handle MONTHLY periods: "1981-11-30 00:00:00" → (1981, 11, 30)
        elif period_type.upper() == 'MONTHLY':
            try:
                date_obj = pd.to_datetime(period_str)
                self.monthly_extracted += 1
                logger.debug("MONTHLY extracted: %s → (%d, %d, %d)", period_str, date_obj.year, date_obj.month, date_obj.day)
                return (date_obj.year, date_obj.month, date_obj.day)
            except Exception as e:
                self.monthly_failed += 1
                logger.warning("MONTHLY datetime parsing failed for '%s': %s", period_str, str(e))
                return (None, None, None)
        else:
            logger.warning("Unknown period_type: '%s' (expected FISCAL or MONTHLY)", period_type)
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
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql), {"dataset_id": dataset_id})
                rows = result.fetchall()
            
            if not rows:
                logger.warning("No raw_data rows found for dataset_id: %s", dataset_id)
                return pd.DataFrame()
            
            logger.info("Loaded %d raw_data rows for dataset_id: %s", len(rows), dataset_id)
            return pd.DataFrame(rows, columns=['ticker', 'period', 'metric_name', 'numeric_value', 'period_type'])
        except Exception as e:
            logger.error("Failed to load raw_data: %s", str(e))
            raise
