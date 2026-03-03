"""
engine/fy_aligner.py — FYAligner

Maps raw data to fiscal-year-aligned data.

The EP Database stores raw data with year labels from each sheet's header
(FY 2000, FY 2001...). All FISCAL_YEAR_SHEETS are ingested with
period_type='fiscal'. The 'FY Period' sheet maps fiscal_year → fy_period
(the source year to pull data from) and is stored in fy_dates.

For most companies fy_period = fiscal_year (June year-end). For others,
the fy_period may differ (e.g. December year-end companies).

This module replicates the Excel INDEX/MATCH logic using fy_dates.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
from db_utils import read_sql


class FYAligner:
    """
    Aligns raw calendar-year data to fiscal years using the fy_dates table.

    For each company and fiscal year, looks up which calendar year
    the data should come from (fy_period column in fy_dates).
    Then retrieves the corresponding raw value.
    """

    def __init__(self, engine: Engine):
        self.engine = engine

    def align(
        self,
        raw_load_id: int,
        metrics: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Produce a FY-aligned DataFrame from raw_data_points.

        Returns a DataFrame with columns:
            ticker, fiscal_year, metric, value, source='aligned'

        Logic (replicates Excel '(A)' sheet INDEX/MATCH):
            For each (ticker, fiscal_year, metric):
              1. Look up fy_period from fy_dates (= which calendar year to use)
              2. Find the raw value for (ticker, calendar_year=fy_period, metric)
              3. If not found → NULL
        """
        # Load FY date mapping for this load
        fy_map = self._load_fy_map(raw_load_id)
        if fy_map.empty:
            raise ValueError(
                f"No fy_dates found for load_id={raw_load_id}. "
                "Ensure FY Dates and FY Period sheets were ingested."
            )

        # Load raw data for this load
        raw = self._load_raw(raw_load_id, metrics)
        if raw.empty:
            return pd.DataFrame(columns=['ticker', 'fiscal_year', 'metric', 'value', 'source'])

        # Build lookup: (ticker, calendar_year, metric) → numeric_value
        raw_lookup = raw.set_index(['ticker', 'period_year', 'metric'])['numeric_value']

        # Align: for each (ticker, fiscal_year), find the calendar year to use
        records = []
        for _, fy_row in fy_map.iterrows():
            ticker      = fy_row['ticker']
            fiscal_year = int(fy_row['fiscal_year'])
            cal_year    = int(fy_row['fy_period'])  # calendar year to pull from

            # Get all metrics for this ticker from raw
            ticker_metrics = raw[raw['ticker'] == ticker]['metric'].unique()
            target_metrics = metrics if metrics else ticker_metrics

            for metric in target_metrics:
                key = (ticker, cal_year, metric)
                value = raw_lookup.get(key, None)
                records.append({
                    'ticker':      ticker,
                    'fiscal_year': fiscal_year,
                    'metric':      metric,
                    'value':       float(value) if value is not None and not pd.isna(value) else None,
                    'source':      'aligned',
                })

        if not records:
            return pd.DataFrame(columns=['ticker', 'fiscal_year', 'metric', 'value', 'source'])

        return pd.DataFrame(records)

    def _load_fy_map(self, raw_load_id: int) -> pd.DataFrame:
        """Load the FY period mapping for a given load."""
        sql = """
            SELECT ticker, fiscal_year, fy_period
            FROM fy_dates
            WHERE load_id = %(load_id)s
            ORDER BY ticker, fiscal_year
        """
        return read_sql(sql, self.engine, params={'load_id': raw_load_id})

    def _load_raw(self, raw_load_id: int, metrics: list[str] | None) -> pd.DataFrame:
        """
        Load raw data points for a given load, optionally filtered by metrics.
        Note: period_type is NOT filtered here — all sheets (fiscal or calendar)
        use period_year as the year label for INDEX/MATCH lookup via fy_dates.
        """
        if metrics:
            placeholders = ', '.join(f'%s' for _ in metrics)
            sql = f"""
                SELECT ticker, period_year, metric, numeric_value
                FROM raw_data_points
                WHERE load_id = %s
                  AND metric IN ({placeholders})
            """
            params = (raw_load_id, *metrics)
        else:
            sql = """
                SELECT ticker, period_year, metric, numeric_value
                FROM raw_data_points
                WHERE load_id = %s
            """
            params = (raw_load_id,)

        return read_sql(sql, self.engine, params=params)
