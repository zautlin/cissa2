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
        Apply 7-step imputation cascade to wide DataFrame.
        
        Args:
            wide_df: DataFrame with shape (ticker, fiscal_year) × metrics
            sector_map: Dictionary {ticker: sector}
            
        Returns:
            Tuple of:
            - wide_clean: Cleaned values DataFrame
            - source_wide: Source labels (same shape as wide_clean)
            - log: Imputation statistics {metric: {source: count}}
        """
        metrics = [c for c in wide_df.columns if c not in ('ticker', 'fiscal_year')]
        
        # Initialize source tracking
        source_wide = wide_df[['ticker', 'fiscal_year']].copy()
        for m in metrics:
            source_wide[m] = np.where(wide_df[m].notna(), SRC_RAW, None)
        
        wide_clean = wide_df.copy()
        
        # Add sector column for group operations (dropped before return)
        wide_clean['_sector'] = wide_clean['ticker'].map(sector_map).fillna('Unknown')
        
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
        Load sector mapping for all active companies.
        
        Returns:
            Dictionary {ticker: sector}
        """
        sql = "SELECT ticker, sector FROM companies WHERE active = TRUE"
        
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
