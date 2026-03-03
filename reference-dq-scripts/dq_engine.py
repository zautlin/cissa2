"""
engine/dq_engine.py — Data Quality Engine

Transforms raw FY-aligned data into clean, float-valued data using a
7-step statistical imputation cascade per (ticker, fiscal_year, metric).

Pipeline:
    raw_data_points  →  [FY-align]  →  [optional plugs]  →  [impute]  →  dq_data_points

Imputation cascade (applied in order, first match wins):
    1. raw       — valid float value from aligned raw data
    2. plug      — user-supplied plug override (if plugs enabled)
    3. forward_fill   — carry last known value forward within ticker
    4. backward_fill  — fill early gaps from first known value
    5. interpolate    — linear interpolation between two known anchors
    6. sector_median  — same metric × same fiscal_year × same companies.sector
    7. market_median  — same metric × same fiscal_year × all tickers
    8. missing        — genuinely unresolvable; value=NULL stored
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine

from db_utils import read_sql, pg_insert
from models import DQVersion, DQDataPoint

# ---------------------------------------------------------------------------
# Metrics that go through DQ imputation
# ---------------------------------------------------------------------------
DQ_METRICS = [
    'Total Equity', 'MI', 'PAT', 'PAT XO', 'PBT',
    'Revenue', 'Op Income', 'Cash', 'FA', 'GW',
    'Total Assets', 'Div', 'Franking',
    'Share Price', 'Spot Shares', 'MC',
    'FY TSR',
    'Rf',   # Rf goes through DQ so Calc Ke always has a value
]

# Source labels
SRC_RAW    = 'raw'
SRC_PLUG   = 'plug'
SRC_FWD    = 'forward_fill'
SRC_BWD    = 'backward_fill'
SRC_INTERP = 'interpolate'
SRC_SECT   = 'sector_median'
SRC_MKT    = 'market_median'
SRC_MISS   = 'missing'


class DQEngine:
    """
    Data Quality Engine.

    Usage:
        engine = DQEngine(db_engine)
        dq_version_id = engine.run(raw_load_id=48, plug_load_id=None)
    """

    def __init__(self, db_engine: Engine):
        self.engine = db_engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        raw_load_id: int,
        plug_load_id: int | None = None,
        created_by: str = 'system',
        run_id: str | None = None,
    ) -> int:
        """
        Run the DQ pipeline and return the new dq_version_id.

        Args:
            raw_load_id:  RawDataLoad to process.
            plug_load_id: Optional plug_loads.plug_load_id to apply first.
            created_by:   Audit string.
            run_id:       Optional pipeline_runs.run_id for audit trail.
        """
        print(f"[DQEngine] Starting DQ run: raw_load_id={raw_load_id}, "
              f"plug_load_id={plug_load_id}")

        # 1. FY-align raw data
        wide = self._load_raw_wide(raw_load_id)
        print(f"  Loaded {len(wide)} (ticker, fiscal_year) rows × {wide.shape[1]-2} metrics")

        # 2. Apply plugs (if provided)
        plugs_applied = False
        if plug_load_id:
            wide = self._apply_plugs(wide, plug_load_id)
            plugs_applied = True
            print(f"  Plug overrides applied from plug_load_id={plug_load_id}")

        # 3. Load company sector for sector-median imputation
        sector_map = self._load_sector_map()

        # 4. Run imputation cascade
        wide_clean, source_wide, log = self._impute(wide, sector_map)
        print(f"  Imputation complete — log summary:")
        for metric, counts in sorted(log.items()):
            total = sum(counts.values())
            missing = counts.get(SRC_MISS, 0)
            print(f"    {metric:20s}  total={total}  missing={missing}  "
                  f"filled={total-missing}")

        # 5. Register DQ version
        dq_version_id = self._register_version(
            raw_load_id=raw_load_id,
            plug_load_id=plug_load_id,
            plugs_applied=plugs_applied,
            created_by=created_by,
            run_id=run_id,
            imputation_log=log,
        )
        print(f"  Registered dq_version_id={dq_version_id}")

        # 6. Write dq_data_points
        n = self._write(wide_clean, source_wide, dq_version_id, raw_load_id)
        print(f"  Written {n} dq_data_points rows")
        print(f"[DQEngine] Done. dq_version_id={dq_version_id}")
        return dq_version_id

    # ------------------------------------------------------------------
    # Step 1: Load raw data FY-aligned (via adj_data_points from the latest adj run,
    #          or directly from the FYAligner)
    # ------------------------------------------------------------------

    def _load_raw_wide(self, raw_load_id: int) -> pd.DataFrame:
        """
        Load FY-aligned raw data for the given raw_load_id.

        We reuse the existing FYAligner which reads from raw_data_points
        and aligns to fiscal years using fy_dates.
        """
        from engine.fy_aligner import FYAligner
        aligner = FYAligner(self.engine)

        # FYAligner returns a long DataFrame: ticker, fiscal_year, metric, value, source
        long_df = aligner.align(raw_load_id, DQ_METRICS)

        if long_df.empty:
            raise ValueError(f"No FY-aligned data for raw_load_id={raw_load_id}")

        # Treat 'NaN' strings and non-numeric values as missing
        long_df['value'] = pd.to_numeric(long_df['value'], errors='coerce')

        # Pivot to wide: index = (ticker, fiscal_year), columns = metric
        wide = long_df.pivot_table(
            index=['ticker', 'fiscal_year'],
            columns='metric',
            values='value',
            aggfunc='first',
        ).reset_index()
        wide.columns.name = None
        wide = wide.sort_values(['ticker', 'fiscal_year']).reset_index(drop=True)
        return wide

    # ------------------------------------------------------------------
    # Step 2: Apply plug overrides
    # ------------------------------------------------------------------

    def _apply_plugs(self, wide: pd.DataFrame, plug_load_id: int) -> pd.DataFrame:
        """Overlay plug override values onto the wide dataframe."""
        sql = """
            SELECT po.ticker, po.fiscal_year, po.metric, po.value
            FROM plug_overrides po
            WHERE po.plug_load_id = %(plug_load_id)s
              AND po.is_valid = TRUE
        """
        plugs = read_sql(sql, self.engine, params={'plug_load_id': plug_load_id})

        if plugs.empty:
            return wide

        plugs['value'] = pd.to_numeric(plugs['value'], errors='coerce')

        for _, row in plugs.iterrows():
            ticker, fy, metric, val = row['ticker'], int(row['fiscal_year']), row['metric'], row['value']
            if metric not in wide.columns:
                continue
            mask = (wide['ticker'] == ticker) & (wide['fiscal_year'] == fy)
            if mask.any():
                wide.loc[mask, metric] = val
        return wide

    # ------------------------------------------------------------------
    # Step 3: Load sector map
    # ------------------------------------------------------------------

    def _load_sector_map(self) -> dict[str, str]:
        """Returns {ticker: sector}."""
        df = read_sql(
            "SELECT ticker, sector FROM companies WHERE is_active = TRUE",
            self.engine
        )
        # Fill empty/null sector with a common fallback so sector median
        # still works within the 'unknown' group
        df['sector'] = df['sector'].fillna('Unknown')
        return dict(zip(df['ticker'], df['sector']))

    # ------------------------------------------------------------------
    # Step 4: Imputation cascade
    # ------------------------------------------------------------------

    def _impute(
        self,
        wide: pd.DataFrame,
        sector_map: dict[str, str],
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
        """
        Apply 7-step imputation cascade in-place.

        Returns:
            wide_clean  — values DataFrame (NaN only for source='missing')
            source_wide — same shape, string source label per cell
            log         — {metric: {source_label: count}}
        """
        metrics = [c for c in wide.columns if c not in ('ticker', 'fiscal_year')]

        # Initialise source tracking: start everything as 'raw' if non-NaN else None
        source_wide = wide[['ticker', 'fiscal_year']].copy()
        for m in metrics:
            source_wide[m] = np.where(wide[m].notna(), SRC_RAW, None)

        wide_clean = wide.copy()

        # Add sector column for group operations (dropped before return)
        wide_clean['_sector'] = wide_clean['ticker'].map(sector_map).fillna('Unknown')

        for metric in metrics:
            col = wide_clean[metric]
            src_col = source_wide[metric]
            need_fill = col.isna()

            if not need_fill.any():
                continue   # all values present for this metric — nothing to do

            # --- Steps 2-4: within-ticker operations ---
            for ticker, grp_idx in wide_clean.groupby('ticker').groups.items():
                grp = wide_clean.loc[grp_idx, metric].copy()
                src = source_wide.loc[grp_idx, metric].copy()
                nan_mask = grp.isna()
                if not nan_mask.any():
                    continue

                # Step 2: forward fill
                fwd = grp.ffill()
                fwd_filled = nan_mask & fwd.notna()
                grp[fwd_filled] = fwd[fwd_filled]
                src[fwd_filled] = SRC_FWD

                # Step 3: backward fill (only on still-missing)
                still_nan = grp.isna()
                bwd = grp.bfill()
                bwd_filled = still_nan & bwd.notna()
                grp[bwd_filled] = bwd[bwd_filled]
                src[bwd_filled] = SRC_BWD

                # Step 4: linear interpolation (only on still-missing)
                still_nan = grp.isna()
                if still_nan.any() and grp.notna().sum() >= 2:
                    interp = grp.interpolate(method='linear', limit_direction='both')
                    interp_filled = still_nan & interp.notna()
                    grp[interp_filled] = interp[interp_filled]
                    src[interp_filled] = SRC_INTERP

                wide_clean.loc[grp_idx, metric] = grp
                source_wide.loc[grp_idx, metric] = src

            # --- Step 5: sector median per fiscal year ---
            still_nan = wide_clean[metric].isna()
            if still_nan.any():
                sect_medians = (
                    wide_clean[~wide_clean[metric].isna()]
                    .groupby(['_sector', 'fiscal_year'])[metric]
                    .median()
                )
                def fill_sector(row):
                    if pd.isna(row[metric]):
                        key = (row['_sector'], row['fiscal_year'])
                        med = sect_medians.get(key)
                        if med is not None and not pd.isna(med):
                            return med, SRC_SECT
                    return row[metric], source_wide.loc[row.name, metric]

                for idx in wide_clean[still_nan].index:
                    row = wide_clean.loc[idx]
                    key = (row['_sector'], row['fiscal_year'])
                    med = sect_medians.get(key)
                    if med is not None and not pd.isna(med):
                        wide_clean.loc[idx, metric] = med
                        source_wide.loc[idx, metric] = SRC_SECT

            # --- Step 6: market median per fiscal year ---
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

            # --- Step 7: flag remaining as missing ---
            still_nan = wide_clean[metric].isna()
            source_wide.loc[still_nan, metric] = SRC_MISS

        # Drop sector helper column
        wide_clean = wide_clean.drop(columns=['_sector'])

        # Build imputation log
        log: dict[str, dict[str, int]] = {}
        for metric in metrics:
            counts: dict[str, int] = defaultdict(int)
            for src in source_wide[metric]:
                if src is not None:
                    counts[src] += 1
                else:
                    counts[SRC_MISS] += 1
            log[metric] = dict(counts)

        return wide_clean, source_wide, log

    # ------------------------------------------------------------------
    # Step 5: Register DQ version
    # ------------------------------------------------------------------

    def _register_version(
        self,
        raw_load_id: int,
        plug_load_id: int | None,
        plugs_applied: bool,
        created_by: str,
        run_id: str | None,
        imputation_log: dict,
    ) -> int:
        """Insert a dq_versions row and return the new dq_version_id."""
        from sqlalchemy import insert as sa_insert
        from models import DQVersion

        stmt = sa_insert(DQVersion).values(
            run_id=run_id,
            raw_load_id=raw_load_id,
            plug_load_id=plug_load_id,
            plugs_applied=plugs_applied,
            created_by=created_by,
            status='ACTIVE',
            imputation_log=imputation_log,
        ).returning(DQVersion.dq_version_id)

        with self.engine.begin() as conn:
            result = conn.execute(stmt)
            return result.scalar_one()

    # ------------------------------------------------------------------
    # Step 6: Write dq_data_points
    # ------------------------------------------------------------------

    def _write(
        self,
        wide_clean: pd.DataFrame,
        source_wide: pd.DataFrame,
        dq_version_id: int,
        raw_load_id: int,
    ) -> int:
        """Melt wide → long and bulk-insert into dq_data_points."""
        metrics = [c for c in wide_clean.columns if c not in ('ticker', 'fiscal_year')]

        rows: list[dict] = []
        for _, row in wide_clean.iterrows():
            ticker = row['ticker']
            fy = int(row['fiscal_year'])
            for metric in metrics:
                val = row[metric]
                src = source_wide.loc[row.name, metric] or SRC_MISS
                rows.append({
                    'dq_version_id': dq_version_id,
                    'ticker':        ticker,
                    'fiscal_year':   fy,
                    'metric':        metric,
                    'value':         None if (pd.isna(val) if val is not None else True) else float(val),
                    'source':        src,
                    'raw_load_id':   raw_load_id,
                })

        if not rows:
            return 0

        with self.engine.begin() as conn:
            conn.execute(
                pg_insert(DQDataPoint.__table__).on_conflict_do_nothing(),
                rows,
            )
        return len(rows)
