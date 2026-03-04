"""
Data Quality Imputation Engine.

Transforms FY-aligned raw data into clean, float-valued data using a
7-step statistical imputation cascade per (ticker, fiscal_year, metric).

Refactored from reference-dq-scripts/dq_engine.py with clean API and structure.

Imputation cascade (applied in order, first match wins):
  1. RAW - valid float value from aligned raw data
  2. FORWARD_FILL - carry last known value forward within ticker
  3. BACKWARD_FILL - fill early gaps from first known value
  4. INTERPOLATE - linear interpolation between two known anchors
  5. SECTOR_MEDIAN - same metric × same fiscal_year × same companies.sector
  6. MARKET_MEDIAN - same metric × same fiscal_year × all tickers
  7. MISSING - genuinely unresolvable; value=NULL
"""

from collections import defaultdict
from typing import Dict, Tuple, List
import pandas as pd
import numpy as np
from sqlalchemy.engine import Engine
from sqlalchemy import text


# Source labels for imputation tracking
SRC_RAW = 'RAW'
SRC_FWD = 'FORWARD_FILL'
SRC_BWD = 'BACKWARD_FILL'
SRC_INTERP = 'INTERPOLATED'
SRC_SECT = 'SECTOR_MEDIAN'
SRC_MKT = 'MARKET_MEDIAN'
SRC_MISS = 'MISSING'


class ImputationCascade:
    """
    7-step imputation cascade for financial data.
    
    Handles missing data hierarchically:
    1. Use raw values
    2. Carry forward last known values
    3. Fill early gaps
    4. Interpolate between known anchors
    5. Use sector median
    6. Use market median
    7. Mark as missing
    """
    
    def __init__(self, db_engine: Engine):
        """
        Initialize imputation cascade.
        
        Args:
            db_engine: SQLAlchemy database engine
        """
        self.engine = db_engine
    
    def impute(
        self,
        wide_df: pd.DataFrame,
        sector_map: Dict[str, str],
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
        """
        Apply 7-step imputation cascade to wide DataFrame with temporal ordering.
        
        TEMPORAL ORDERING:
        Before imputation, data is sorted to ensure correct chronological order within each ticker.
        This is critical for forward_fill, backward_fill, and interpolation to work correctly,
        especially across year boundaries (e.g., Dec 2021 → Jan 2022 for MONTHLY data).
        
        FISCAL data: Sorted by (ticker, fiscal_year) → fills across years
        MONTHLY data: Sorted by (ticker, fiscal_year, fiscal_month, fiscal_day) → fills across months/years
        
        Args:
            wide_df: DataFrame with columns: ticker, fiscal_year, [fiscal_month, fiscal_day], metrics
                     Index structure depends on data type:
                     - FISCAL: columns (ticker, fiscal_year) + metrics
                     - MONTHLY: columns (ticker, fiscal_year, fiscal_month, fiscal_day) + metrics
            sector_map: Dictionary {ticker: sector}
            
        Returns:
            Tuple of:
            - wide_clean: Cleaned values DataFrame (sorted by temporal order)
            - source_wide: Source labels (same shape as wide_clean, same temporal order)
            - log: Imputation statistics {metric: {source: count}}
        """
        metrics = [c for c in wide_df.columns if c not in ('ticker', 'fiscal_year', 'fiscal_month', 'fiscal_day')]
        
        # Initialize source tracking - preserve all dimension columns
        dimension_cols = ['ticker', 'fiscal_year']
        if 'fiscal_month' in wide_df.columns:
            dimension_cols.extend(['fiscal_month', 'fiscal_day'])
        source_wide = wide_df[dimension_cols].copy()
        for m in metrics:
            source_wide[m] = np.where(wide_df[m].notna(), SRC_RAW, None)
        
        wide_clean = wide_df.copy()
        
        # Add sector column for group operations (dropped before return)
        wide_clean['_sector'] = wide_clean['ticker'].map(sector_map).fillna('Unknown')
        
        # === SORT BY TEMPORAL ORDER ===
        # Ensure chronological ordering within each ticker for correct ffill/bfill/interpolate
        # This is critical for filling gaps across year boundaries (e.g., Dec 2021 → Jan 2022)
        if 'fiscal_month' in wide_clean.columns:
            # MONTHLY data: Sort by (ticker, fiscal_year, fiscal_month, fiscal_day)
            # This ensures: ticker1-2021-01-31 → ticker1-2021-02-28 → ... → ticker1-2023-12-31 → ticker2-2021-01-31 ...
            sort_cols = ['ticker', 'fiscal_year', 'fiscal_month', 'fiscal_day']
        else:
            # FISCAL data: Sort by (ticker, fiscal_year)
            # This ensures: ticker1-2002 → ticker1-2003 → ... → ticker1-2023 → ticker2-2002 ...
            sort_cols = ['ticker', 'fiscal_year']
        
        wide_clean = wide_clean.sort_values(by=sort_cols).reset_index(drop=True)
        source_wide = source_wide.sort_values(by=sort_cols).reset_index(drop=True)
        # === END SORT ===
        
        # Process each metric
        for metric in metrics:
            col = wide_clean[metric]
            src_col = source_wide[metric]
            need_fill = col.isna()
            
            if not need_fill.any():
                continue  # All values present for this metric
            
            # --- STEPS 2-4: Within-ticker operations ---
            for ticker, grp_idx in wide_clean.groupby('ticker').groups.items():
                grp = wide_clean.loc[grp_idx, metric].copy()
                src = source_wide.loc[grp_idx, metric].copy()
                nan_mask = grp.isna()
                
                if not nan_mask.any():
                    continue
                
                # Step 2: FORWARD_FILL
                fwd = grp.ffill()
                fwd_filled = nan_mask & fwd.notna()
                grp[fwd_filled] = fwd[fwd_filled]
                src[fwd_filled] = SRC_FWD
                
                # Step 3: BACKWARD_FILL (only on still-missing)
                still_nan = grp.isna()
                bwd = grp.bfill()
                bwd_filled = still_nan & bwd.notna()
                grp[bwd_filled] = bwd[bwd_filled]
                src[bwd_filled] = SRC_BWD
                
                # Step 4: INTERPOLATE (only on still-missing)
                still_nan = grp.isna()
                if still_nan.any() and grp.notna().sum() >= 2:
                    interp = grp.interpolate(method='linear', limit_direction='both')
                    interp_filled = still_nan & interp.notna()
                    grp[interp_filled] = interp[interp_filled]
                    src[interp_filled] = SRC_INTERP
                
                wide_clean.loc[grp_idx, metric] = grp
                source_wide.loc[grp_idx, metric] = src
            
            # --- STEP 5: SECTOR_MEDIAN per fiscal year ---
            still_nan = wide_clean[metric].isna()
            if still_nan.any():
                sect_medians = (
                    wide_clean[~wide_clean[metric].isna()]
                    .groupby(['_sector', 'fiscal_year'])[metric]
                    .median()
                )
                for idx in wide_clean[still_nan].index:
                    row = wide_clean.loc[idx]
                    key = (row['_sector'], row['fiscal_year'])
                    med = sect_medians.get(key)
                    if med is not None and not pd.isna(med):
                        wide_clean.loc[idx, metric] = med
                        source_wide.loc[idx, metric] = SRC_SECT
            
            # --- STEP 6: MARKET_MEDIAN per fiscal year ---
            still_nan = wide_clean[metric].isna()
            if still_nan.any():
                mkt_medians = (
                    wide_clean[~wide_clean[metric].isna()]
                    .groupby('fiscal_year')[metric]
                    .median()
                )
                for idx in wide_clean[still_nan].index:
                    fy = wide_clean.loc[idx, 'fiscal_year']
                    med = mkt_medians.get(fy)
                    if med is not None and not pd.isna(med):
                        wide_clean.loc[idx, metric] = med
                        source_wide.loc[idx, metric] = SRC_MKT
            
            # --- STEP 7: MISSING ---
            still_nan = wide_clean[metric].isna()
            source_wide.loc[still_nan, metric] = SRC_MISS
        
        # Drop sector helper column
        wide_clean = wide_clean.drop(columns=['_sector'])
        
        # Build imputation log
        log: Dict[str, Dict[str, int]] = {}
        for metric in metrics:
            counts: Dict[str, int] = defaultdict(int)
            for src in source_wide[metric]:
                if src is not None:
                    counts[src] += 1
                else:
                    counts[SRC_MISS] += 1
            log[metric] = dict(counts)
        
        return wide_clean, source_wide, log
    
    def _load_sector_map(self) -> Dict[str, str]:
        """
        Load sector mapping for all companies.
        
        Returns:
            Dictionary {ticker: sector}
        """
        sql = "SELECT ticker, sector FROM companies"
        
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
        
        if not rows:
            return {}
        
        sector_map = dict(rows)
        
        # Fill empty/null sectors with fallback
        for ticker in sector_map:
            if not sector_map[ticker] or pd.isna(sector_map[ticker]):
                sector_map[ticker] = 'Unknown'
        
        return sector_map
