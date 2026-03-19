# ============================================================================
# Phase 10c: Total Expense Ratio (TER) Metrics Service
# ============================================================================
# Calculates: TER_1Y, TER_3Y, TER_5Y, TER_10Y
# These are L2 metrics calculated after FV_ECF
# Uses vectorized Pandas + batch database inserts
# ============================================================================

import pandas as pd
import numpy as np
from decimal import Decimal
from uuid import UUID
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json
import time

from ..core.config import get_logger

logger = get_logger(__name__)


def to_float(value):
    """Convert Decimal or float to float, handling NaN."""
    if value is None:
        return np.nan
    if isinstance(value, Decimal):
        return float(value)
    if pd.isna(value):
        return np.nan
    return float(value)


class TERService:
    """
    Total Expense Ratio (TER) and TER-KE Service (Phase 10c)
    
    Calculates:
    - TER_1Y, TER_3Y, TER_5Y, TER_10Y: 1/3/5/10-year total expense ratio
    - TER-KE_1Y, TER-KE_3Y, TER-KE_5Y, TER-KE_10Y: 1/3/5/10-year TER-KE (wealth creation component)
    
    These are L2 metrics calculated after FV_ECF metrics, computed simultaneously for efficiency.
    
    Formulas (for each interval n):
    TER = ((WC + WP) / Open MC)^(1/n) - 1
    
    TER-KE = ((WC + WP) / Open MC)^(1/n) - (WP / Open MC)^(1/n)
    
    For 1Y (n=1): Simplifies to TER-KE = WC / Open MC
    For 3Y, 5Y, 10Y (n>1): Cannot be algebraically simplified; must compute full formula
    
    Shared components (calculated once per interval):
    - Load TRTE = Calc {interval}Y FV ECF + (Calc MC - LAG(Calc MC, 1))
    - Load TER = (Load TRTE / Open MC) - 1
    - WC = Open MC × (1 + Load TER) - Open MC × (1 + Ke)
    - WP = Open MC × (1 + Ke)
    - Open MC = LAG(Calc MC, 1)
    
    Key optimizations:
    - Calculates both TER and TER-KE from same intermediate values
    - Fetches Calc MC, Calc KE, and FV_ECF from metrics_outputs table
    - Vectorized Pandas operations (no row-by-row iteration)
    - Single batch database insert for all metrics
    - 8 metrics (4 intervals × 2 types) × ~9,189 records = ~73,512 total inserts
    
    Prerequisites:
    - Phase 10a Core L2 Metrics (Calc MC, Calc KE in metrics_outputs)
    - Phase 10b FV_ECF Metrics (all 4 intervals in metrics_outputs)
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def calculate_ter_metrics(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
    ) -> dict:
        """
        Calculate Phase 10c TER and TER-KE metrics simultaneously.
        
        Args:
            dataset_id: Dataset version ID
            param_set_id: Parameter set ID
        
        Returns:
            {
                'dataset_id': UUID,
                'param_set_id': UUID,
                'intervals': [list of intervals],
                'total_records_calculated': int,
                'total_records_with_nulls': int,
                'null_row_breakdown': {interval: count},
                'metrics_inserted': [metric names],
                'calculation_time_ms': float
            }
        """
        start_time = time.time()
        logger.info(f"[TER] Starting TER calculation for dataset={dataset_id}, param_set={param_set_id}")
        
        try:
            # Step 1: Fetch Calc MC
            logger.info("[TER] Step 1: Fetching Calc MC from metrics_outputs...")
            calc_mc = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc MC',
                param_set_id=param_set_id
            )
            logger.info(f"[TER]   - Fetched {len(calc_mc)} Calc MC records")
            
            # Step 2: Fetch Calc KE (for all intervals, we'll use the same Calc KE)
            logger.info("[TER] Step 2: Fetching Calc KE from metrics_outputs...")
            calc_ke = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc KE',
                param_set_id=param_set_id
            )
            logger.info(f"[TER]   - Fetched {len(calc_ke)} Calc KE records")
            
            # Step 3: Fetch all FV_ECF intervals
            logger.info("[TER] Step 3: Fetching FV_ECF metrics (all intervals)...")
            fv_ecf_1y = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc 1Y FV ECF',
                param_set_id=param_set_id
            )
            fv_ecf_3y = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc 3Y FV ECF',
                param_set_id=param_set_id
            )
            fv_ecf_5y = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc 5Y FV ECF',
                param_set_id=param_set_id
            )
            fv_ecf_10y = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc 10Y FV ECF',
                param_set_id=param_set_id
            )
            logger.info(f"[TER]   - Fetched FV_ECF: 1Y={len(fv_ecf_1y)}, 3Y={len(fv_ecf_3y)}, 5Y={len(fv_ecf_5y)}, 10Y={len(fv_ecf_10y)}")
            
            # Step 4: Fetch fundamentals for ticker-year coverage
            logger.info("[TER] Step 4: Fetching fundamentals for ticker-year coverage...")
            fundamentals_df = await self._fetch_fundamentals(dataset_id)
            logger.info(f"[TER]   - Fetched {len(fundamentals_df)} fundamentals records")
            
            # Step 5: Calculate TER for each interval
            logger.info("[TER] Step 5: Calculating TER for all intervals...")
            
            ter_1y = self._calculate_ter_for_interval(
                calc_mc=calc_mc,
                calc_ke=calc_ke,
                fv_ecf=fv_ecf_1y,
                interval=1
            )
            logger.info(f"[TER]   - Calculated 1Y TER: {len(ter_1y)} records")
            
            ter_3y = self._calculate_ter_for_interval(
                calc_mc=calc_mc,
                calc_ke=calc_ke,
                fv_ecf=fv_ecf_3y,
                interval=3
            )
            logger.info(f"[TER]   - Calculated 3Y TER: {len(ter_3y)} records")
            
            ter_5y = self._calculate_ter_for_interval(
                calc_mc=calc_mc,
                calc_ke=calc_ke,
                fv_ecf=fv_ecf_5y,
                interval=5
            )
            logger.info(f"[TER]   - Calculated 5Y TER: {len(ter_5y)} records")
            
            ter_10y = self._calculate_ter_for_interval(
                calc_mc=calc_mc,
                calc_ke=calc_ke,
                fv_ecf=fv_ecf_10y,
                interval=10
            )
            logger.info(f"[TER]   - Calculated 10Y TER: {len(ter_10y)} records")
            
            # Combine all intervals
            ter_combined = pd.concat([ter_1y, ter_3y, ter_5y, ter_10y], ignore_index=True)
            logger.info(f"[TER]   - Total records calculated: {len(ter_combined)}")
            
            # Step 5a: Add NULL rows for insufficient history
            logger.info("[TER] Step 5a: Adding NULL rows for insufficient history...")
            ter_combined, null_breakdown = self._add_null_rows_for_ter(ter_combined, fundamentals_df)
            logger.info(f"[TER]   - Total records after NULL rows: {len(ter_combined)}")
            
            # Step 6: Insert results in batches
            logger.info("[TER] Step 6: Inserting into metrics_outputs...")
            await self._insert_ter_batch(
                ter_df=ter_combined,
                null_breakdown=null_breakdown,
                dataset_id=dataset_id,
                param_set_id=param_set_id
            )
            logger.info(f"[TER]   - Insertion complete")
            
            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"[TER] ✓ TER calculation completed in {elapsed_ms:.0f}ms")
            
            return {
                'dataset_id': str(dataset_id),
                'param_set_id': str(param_set_id),
                'intervals': ['1Y', '3Y', '5Y', '10Y'],
                'total_records_calculated': len(ter_combined) - sum(null_breakdown.values()),
                'total_records_with_nulls': len(ter_combined),
                'null_row_breakdown': null_breakdown,
                'metrics_inserted': [
                    'Calc 1Y TER', 'Calc 1Y TER-KE',
                    'Calc 3Y TER', 'Calc 3Y TER-KE',
                    'Calc 5Y TER', 'Calc 5Y TER-KE',
                    'Calc 10Y TER', 'Calc 10Y TER-KE'
                ],
                'calculation_time_ms': elapsed_ms
            }
        
        except Exception as e:
            logger.error(f"[TER] ✗ Error in TER calculation: {str(e)}", exc_info=True)
            raise
    
    async def _fetch_metric(
        self,
        dataset_id: UUID,
        metric_name: str,
        param_set_id: UUID
    ) -> pd.DataFrame:
        """Fetch metric from metrics_outputs table."""
        query = text("""
            SELECT ticker, fiscal_year, output_metric_value
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id
              AND param_set_id = :param_set_id
              AND output_metric_name = :metric_name
            ORDER BY ticker, fiscal_year
        """)
        
        result = await self.session.execute(query, {
            'dataset_id': dataset_id,
            'param_set_id': param_set_id,
            'metric_name': metric_name
        })
        
        rows = result.fetchall()
        df = pd.DataFrame(rows, columns=['ticker', 'fiscal_year', 'value'])
        df['fiscal_year'] = df['fiscal_year'].astype(int)
        df['value'] = df['value'].apply(to_float)
        return df
    
    async def _fetch_fundamentals(self, dataset_id: UUID) -> pd.DataFrame:
        """Fetch fundamentals to get ticker-year coverage."""
        query = text("""
            SELECT DISTINCT ticker, fiscal_year
            FROM cissa.fundamentals
            WHERE dataset_id = :dataset_id
            ORDER BY ticker, fiscal_year
        """)
        
        result = await self.session.execute(query, {'dataset_id': dataset_id})
        rows = result.fetchall()
        df = pd.DataFrame(rows, columns=['ticker', 'fiscal_year'])
        df['fiscal_year'] = df['fiscal_year'].astype(int)
        return df
    
    def _calculate_ter_for_interval(
        self,
        calc_mc: pd.DataFrame,
        calc_ke: pd.DataFrame,
        fv_ecf: pd.DataFrame,
        interval: int
    ) -> pd.DataFrame:
        """
        Calculate both TER and TER-KE for a specific interval simultaneously.
        
        Formulas (for each interval n):
        TER = ((WC + WP) / Open MC)^(1/n) - 1
        
        TER-KE = ((WC + WP) / Open MC)^(1/n) - (WP / Open MC)^(1/n)
        
        For 1Y (n=1): TER-KE simplifies to WC / Open MC
        For 3Y, 5Y, 10Y (n>1): Cannot be algebraically simplified; full formula required
        
        Shared components (calculated once):
        - Load TRTE = Calc {interval}Y FV ECF + (Calc MC - LAG(Calc MC, 1))
        - Load TER = (Load TRTE / Open MC) - 1
        - WC = Open MC × (1 + Load TER) - Open MC × (1 + Ke)
        - WP = Open MC × (1 + Ke)
        - Open MC = LAG(Calc MC, 1)
        """
        
        # Rename columns for clarity
        calc_mc = calc_mc.rename(columns={'value': 'calc_mc'}).copy()
        calc_ke = calc_ke.rename(columns={'value': 'calc_ke'}).copy()
        fv_ecf = fv_ecf.rename(columns={'value': 'fv_ecf'}).copy()
        
        # Merge all data by ticker and fiscal_year
        df = calc_mc.merge(calc_ke, on=['ticker', 'fiscal_year'], how='inner')
        df = df.merge(fv_ecf, on=['ticker', 'fiscal_year'], how='inner')
        
        # Sort by ticker and fiscal_year to enable lag calculation
        df = df.sort_values(['ticker', 'fiscal_year']).reset_index(drop=True)
        
        # Calculate LAG(Calc MC, 1) within each ticker
        df['calc_mc_lag'] = df.groupby('ticker')['calc_mc'].shift(1)
        
        # Calculate Open MC
        df['open_mc'] = df['calc_mc_lag']
        
        # Step 1: Calculate Load TRTE
        # Load TRTE = Calc {interval}Y FV ECF + (Calc MC - LAG(Calc MC, 1))
        df['load_trte'] = df['fv_ecf'] + (df['calc_mc'] - df['calc_mc_lag'])
        
        # Step 2: Calculate Load TER
        # Load TER = (1 + Load TRTE / Open MC)^(1/interval) - 1
        # Guard against division by zero
        exponent_ter = 1.0 / interval
        df['load_ter'] = np.where(
            df['open_mc'].notna() & (df['open_mc'] != 0),
            np.power(1 + (df['load_trte'] / df['open_mc']), exponent_ter) - 1,
            np.nan
        )
        
        # Step 3: Calculate WC and WP
        # WC = Open MC × (1 + Load TER)^interval - Open MC × (1 + Ke)^interval
        # WP = Open MC × (1 + Ke)^interval
        df['wc'] = df['open_mc'] * np.power(1 + df['load_ter'], interval) - df['open_mc'] * np.power(1 + df['calc_ke'], interval)
        df['wp'] = df['open_mc'] * np.power(1 + df['calc_ke'], interval)
        
        # Step 4: Calculate TER (final)
        # TER = ((WC + WP) / Open MC)^(1/interval) - 1
        exponent = 1.0 / interval
        ratio_wc_wp = (df['wc'] + df['wp']) / df['open_mc']
        df['ter'] = np.where(
            df['open_mc'].notna() & (df['open_mc'] != 0),
            np.power(ratio_wc_wp, exponent) - 1,
            np.nan
        )
        
        # Step 5: Calculate TER-KE (new)
        # TER-KE = ((WC + WP) / Open MC)^(1/interval) - (WP / Open MC)^(1/interval)
        ratio_wp = df['wp'] / df['open_mc']
        df['ter_ke'] = np.where(
            df['open_mc'].notna() & (df['open_mc'] != 0),
            np.power(ratio_wc_wp, exponent) - np.power(ratio_wp, exponent),
            np.nan
        )
        
        # Build result dataframe with BOTH TER and TER-KE
        ter_results = pd.DataFrame({
            'ticker': df['ticker'],
            'fiscal_year': df['fiscal_year'],
            'TER_Y': df['ter'],
            'TER_TYPE': f'Calc {interval}Y TER'
        })
        
        ter_ke_results = pd.DataFrame({
            'ticker': df['ticker'],
            'fiscal_year': df['fiscal_year'],
            'TER_Y': df['ter_ke'],
            'TER_TYPE': f'Calc {interval}Y TER-KE'
        })
        
        return pd.concat([ter_results, ter_ke_results], ignore_index=True)
    
    def _add_null_rows_for_ter(
        self,
        ter_df: pd.DataFrame,
        fundamentals_df: pd.DataFrame
    ) -> tuple:
        """
        Add NULL rows for fiscal years with insufficient lag history.
        
        Generates NULL rows for both TER and TER-KE metrics.
        
        For each interval, we need a minimum number of prior years of data:
        - 1Y: First year (min_year) = 1 NULL row per metric type
        - 3Y: First 2 years = 2 NULL rows per metric type (fiscal_year - 1, -2)
        - 5Y: First 4 years = 4 NULL rows per metric type (fiscal_year - 1, -2, -3, -4)
        - 10Y: First 9 years = 9 NULL rows per metric type (fiscal_year - 1 through -9)
        
        Args:
            ter_df: DataFrame with calculated TER and TER-KE values
            fundamentals_df: Original fundamentals data with all ticker-year combinations
        
        Returns:
            Tuple of (DataFrame with NULL rows added, null_row_breakdown dict)
        """
        # Get unique tickers and their min/max fiscal years from fundamentals
        ticker_year_info = fundamentals_df.groupby('ticker')['fiscal_year'].agg(['min', 'max']).reset_index()
        
        null_rows = []
        null_row_breakdown = {
            '1Y_TER': 0,
            '1Y_TER-KE': 0,
            '3Y_TER': 0,
            '3Y_TER-KE': 0,
            '5Y_TER': 0,
            '5Y_TER-KE': 0,
            '10Y_TER': 0,
            '10Y_TER-KE': 0
        }
        
        for _, row in ticker_year_info.iterrows():
            ticker = row['ticker']
            min_year = int(row['min'])
            max_year = int(row['max'])
            
            # For 1Y: first year (min_year) should have NULL
            if min_year <= max_year:
                # Add NULL for TER
                null_rows.append({
                    'ticker': ticker,
                    'fiscal_year': min_year,
                    'TER_Y': np.nan,
                    'TER_TYPE': 'Calc 1Y TER'
                })
                null_row_breakdown['1Y_TER'] += 1
                # Add NULL for TER-KE
                null_rows.append({
                    'ticker': ticker,
                    'fiscal_year': min_year,
                    'TER_Y': np.nan,
                    'TER_TYPE': 'Calc 1Y TER-KE'
                })
                null_row_breakdown['1Y_TER-KE'] += 1
            
            # For 3Y: first 3 years should have NULL
            for year_offset in range(1, 3):
                target_year = min_year + year_offset
                if target_year <= max_year:
                    # Add NULL for TER
                    null_rows.append({
                        'ticker': ticker,
                        'fiscal_year': target_year,
                        'TER_Y': np.nan,
                        'TER_TYPE': 'Calc 3Y TER'
                    })
                    null_row_breakdown['3Y_TER'] += 1
                    # Add NULL for TER-KE
                    null_rows.append({
                        'ticker': ticker,
                        'fiscal_year': target_year,
                        'TER_Y': np.nan,
                        'TER_TYPE': 'Calc 3Y TER-KE'
                    })
                    null_row_breakdown['3Y_TER-KE'] += 1
            
            # For 5Y: first 5 years should have NULL
            for year_offset in range(1, 5):
                target_year = min_year + year_offset
                if target_year <= max_year:
                    # Add NULL for TER
                    null_rows.append({
                        'ticker': ticker,
                        'fiscal_year': target_year,
                        'TER_Y': np.nan,
                        'TER_TYPE': 'Calc 5Y TER'
                    })
                    null_row_breakdown['5Y_TER'] += 1
                    # Add NULL for TER-KE
                    null_rows.append({
                        'ticker': ticker,
                        'fiscal_year': target_year,
                        'TER_Y': np.nan,
                        'TER_TYPE': 'Calc 5Y TER-KE'
                    })
                    null_row_breakdown['5Y_TER-KE'] += 1
            
            # For 10Y: first 10 years should have NULL
            for year_offset in range(1, 10):
                target_year = min_year + year_offset
                if target_year <= max_year:
                    # Add NULL for TER
                    null_rows.append({
                        'ticker': ticker,
                        'fiscal_year': target_year,
                        'TER_Y': np.nan,
                        'TER_TYPE': 'Calc 10Y TER'
                    })
                    null_row_breakdown['10Y_TER'] += 1
                    # Add NULL for TER-KE
                    null_rows.append({
                        'ticker': ticker,
                        'fiscal_year': target_year,
                        'TER_Y': np.nan,
                        'TER_TYPE': 'Calc 10Y TER-KE'
                    })
                    null_row_breakdown['10Y_TER-KE'] += 1
        
        null_rows_df = pd.DataFrame(null_rows)
        
        # Remove any calculated rows that conflict with NULL rows
        # (same ticker, fiscal_year, and metric_type)
        combined = ter_df.copy()
        if len(null_rows_df) > 0:
            # Create a key to identify rows to remove
            conflict_key = null_rows_df[['ticker', 'fiscal_year', 'TER_TYPE']].copy()
            conflict_key['_conflict'] = True
            
            # Merge to identify conflicts
            combined = combined.merge(
                conflict_key,
                on=['ticker', 'fiscal_year', 'TER_TYPE'],
                how='left'
            )
            
            # Keep only rows without conflicts (where _conflict is NaN/False)
            combined = combined[combined['_conflict'].isna()].copy()
            combined = combined.drop('_conflict', axis=1)
        
        # Combine with NULL rows
        combined = pd.concat([combined, null_rows_df], ignore_index=True)
        
        return combined, null_row_breakdown
    
    async def _insert_ter_batch(
        self,
        ter_df: pd.DataFrame,
        null_breakdown: dict,
        dataset_id: UUID,
        param_set_id: UUID
    ) -> None:
        """
        Insert TER and TER-KE metrics into metrics_outputs using single multi-row INSERT.
        
        Uses PostgreSQL multi-row VALUES clause for efficiency:
        - Single INSERT statement for all metrics (TER + TER-KE + NULL rows)
        - Reduces database roundtrips significantly
        - Expected performance: <1s for insert phase
        
        Args:
            ter_df: DataFrame with both TER and TER-KE values plus NULL rows
            null_breakdown: Dictionary with NULL row counts per metric type and interval
            dataset_id: Dataset version ID
            param_set_id: Parameter set ID
        """
        try:
            # Build multi-row VALUES clause for ALL records at once
            rows_sql_parts = []
            for _, row in ter_df.iterrows():
                metric_value = row['TER_Y']
                metric_value_sql = float(metric_value) if pd.notna(metric_value) else 'NULL'
                
                metadata = {
                    'metric_level': 'L2',
                    'interval': row['TER_TYPE'].split()[1]
                }
                metadata_json = json.dumps(metadata).replace("'", "''")  # Escape single quotes for SQL
                
                row_sql = f"('{str(dataset_id)}', '{str(param_set_id)}', '{row['ticker']}', {int(row['fiscal_year'])}, '{row['TER_TYPE']}', {metric_value_sql}, '{metadata_json}')"
                rows_sql_parts.append(row_sql)
            
            rows_sql = ", ".join(rows_sql_parts)
            
            # Execute SINGLE multi-row INSERT...ON CONFLICT UPDATE for all records
            # This is the key: ONE statement instead of 49k individual INSERTs
            query = text(f"""
                INSERT INTO cissa.metrics_outputs 
                (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata)
                VALUES {rows_sql}
                ON CONFLICT (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
                DO UPDATE SET
                    output_metric_value = EXCLUDED.output_metric_value,
                    metadata = EXCLUDED.metadata
            """)
            
            await self.session.execute(query)
            logger.info(f"[TER]   - Executed single multi-row INSERT for {len(ter_df)} records")
            
            # Single commit at the end
            await self.session.commit()
            logger.info(f"[TER]   - Batch insert complete: {len(ter_df)} records committed")
        
        except Exception as e:
            logger.error(f"[TER]   - Failed to insert TER batch: {e}", exc_info=True)
            await self.session.rollback()
            raise
