# ============================================================================
# Phase 10d: TER Alpha (Risk-Adjusted Performance) Metrics Service
# ============================================================================
# Calculates: TER_Alpha_1Y, TER_Alpha_3Y, TER_Alpha_5Y, TER_Alpha_10Y
# Plus intermediate metrics: Load RA MM (portfolio), WC TERA (company)
# These are L2 metrics calculated after TER/TER-KE (Phase 10c)
# Uses vectorized Pandas + batch database inserts
# ============================================================================

import pandas as pd
import numpy as np
from decimal import Decimal
from uuid import UUID
from typing import Optional, Dict
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


class TERAlphaService:
    """
    Total Expense Ratio Alpha (TER Alpha) Service (Phase 10d)
    
    Calculates:
    - TER Alpha_1Y, TER Alpha_3Y, TER Alpha_5Y, TER Alpha_10Y: Risk-adjusted performance
    - Load RA MM_1Y, Load RA MM_3Y, Load RA MM_5Y, Load RA MM_10Y: Portfolio risk adjustment
    - WC TERA_1Y, WC TERA_3Y, WC TERA_5Y, WC TERA_10Y: Wealth creation with risk adjustment
    
    These are L2 metrics calculated after TER/TER-KE metrics (Phase 10c).
    Computed simultaneously for efficiency across all intervals.
    
    Formulas (for each interval n):
    Load RA MM = (Load Rm - (Load Rf + ERP)) × (Load Ke - Load Rf) / ERP
                 where Load Rm is portfolio-weighted annual return
    
    WC TERA = Load Open MC × (1 + Load TER) - Load Open MC × (1 + Load Ke + Load RA MM)
    
    TER Alpha = TER-KE - (((1 + TER) - WC TERA / Open MC)^(1/n) - (TER - TER-KE) - 1)
    
    Key optimizations:
    - Load RA MM calculated once per year, broadcast to all companies
    - WC TERA and TER Alpha calculated per interval from shared intermediate values
    - Vectorized Pandas operations (no row-by-row iteration)
    - Single batch database insert for all metrics
    - 12 metrics (4 intervals × 3 metric types) × ~9,189 records = ~110,268 total inserts
    
    Prerequisites:
    - Phase 10a Core L2 Metrics (Calc MC, Calc KE in metrics_outputs)
    - Phase 10b FV_ECF Metrics (all 4 intervals in metrics_outputs)
    - Phase 10c TER/TER-KE Metrics (all 4 intervals in metrics_outputs)
    - cissa.fundamentals: Calc Rf, Calc EE
    - cissa.parameters: equity_risk_premium
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def calculate_ter_alpha_metrics(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
    ) -> dict:
        """
        Calculate Phase 10d TER Alpha metrics simultaneously for all intervals.
        
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
        logger.info(f"[TER Alpha] Starting TER Alpha calculation for dataset={dataset_id}, param_set={param_set_id}")
        
        try:
            # Step 1: Fetch Calc MC
            logger.info("[TER Alpha] Step 1: Fetching Calc MC from metrics_outputs...")
            calc_mc = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc MC',
                param_set_id=param_set_id
            )
            logger.info(f"[TER Alpha]   - Fetched {len(calc_mc)} Calc MC records")
            
            # Step 2: Fetch Calc KE
            logger.info("[TER Alpha] Step 2: Fetching Calc KE from metrics_outputs...")
            calc_ke = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc KE',
                param_set_id=param_set_id
            )
            logger.info(f"[TER Alpha]   - Fetched {len(calc_ke)} Calc KE records")
            
            # Step 3: Fetch Calc Rf from metrics_outputs and Calc EE from fundamentals
            logger.info("[TER Alpha] Step 3: Fetching Calc Rf from metrics_outputs and Calc EE from fundamentals...")
            calc_rf = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc Rf',
                param_set_id=param_set_id
            )
            calc_ee = await self._fetch_fundamentals_metric(dataset_id, 'TOTAL_EQUITY')
            logger.info(f"[TER Alpha]   - Fetched {len(calc_rf)} Calc Rf records, {len(calc_ee)} Calc EE records")
            
            # Step 4: Fetch all FV_ECF intervals
            logger.info("[TER Alpha] Step 4: Fetching FV_ECF metrics (all intervals)...")
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
            logger.info(f"[TER Alpha]   - Fetched FV_ECF: 1Y={len(fv_ecf_1y)}, 3Y={len(fv_ecf_3y)}, 5Y={len(fv_ecf_5y)}, 10Y={len(fv_ecf_10y)}")
            
            # Step 5: Fetch TER and TER-KE metrics (Phase 10c)
            logger.info("[TER Alpha] Step 5: Fetching TER and TER-KE metrics (all intervals)...")
            ter_1y = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc 1Y TER',
                param_set_id=param_set_id
            )
            ter_ke_1y = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc 1Y TER-KE',
                param_set_id=param_set_id
            )
            ter_3y = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc 3Y TER',
                param_set_id=param_set_id
            )
            ter_ke_3y = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc 3Y TER-KE',
                param_set_id=param_set_id
            )
            ter_5y = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc 5Y TER',
                param_set_id=param_set_id
            )
            ter_ke_5y = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc 5Y TER-KE',
                param_set_id=param_set_id
            )
            ter_10y = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc 10Y TER',
                param_set_id=param_set_id
            )
            ter_ke_10y = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc 10Y TER-KE',
                param_set_id=param_set_id
            )
            logger.info(f"[TER Alpha]   - Fetched TER/TER-KE for all intervals")
            
            # Step 6: Fetch equity risk premium parameter
            logger.info("[TER Alpha] Step 6: Fetching equity_risk_premium parameter...")
            erp = await self._get_parameter_value(param_set_id, 'equity_risk_premium', 0.05)
            logger.info(f"[TER Alpha]   - Equity Risk Premium = {erp}")
            
            # Step 7: Fetch fundamentals for ticker-year coverage
            logger.info("[TER Alpha] Step 7: Fetching fundamentals for ticker-year coverage...")
            fundamentals_df = await self._fetch_all_fundamentals(dataset_id)
            logger.info(f"[TER Alpha]   - Fetched {len(fundamentals_df)} fundamentals records")
            
            # Step 8: Calculate Load RA MM (portfolio-level, once per year)
            logger.info("[TER Alpha] Step 8: Calculating portfolio Load RA MM...")
            load_ra_mm_by_year = self._calculate_portfolio_ra_mm(
                calc_mc=calc_mc,
                calc_ke=calc_ke,
                calc_rf=calc_rf,
                fv_ecf_1y=fv_ecf_1y,
                erp=erp
            )
            logger.info(f"[TER Alpha]   - Calculated Load RA MM for {len(load_ra_mm_by_year)} years")
            
            # Step 9: Calculate TER Alpha metrics for each interval
            logger.info("[TER Alpha] Step 9: Calculating TER Alpha for all intervals...")
            
            ter_alpha_1y = self._calculate_ter_alpha_for_interval(
                calc_mc=calc_mc,
                calc_ke=calc_ke,
                calc_ee=calc_ee,
                ter=ter_1y,
                ter_ke=ter_ke_1y,
                fv_ecf=fv_ecf_1y,
                load_ra_mm_by_year=load_ra_mm_by_year,
                interval=1
            )
            logger.info(f"[TER Alpha]   - Calculated 1Y TER Alpha: {len(ter_alpha_1y)} records")
            
            ter_alpha_3y = self._calculate_ter_alpha_for_interval(
                calc_mc=calc_mc,
                calc_ke=calc_ke,
                calc_ee=calc_ee,
                ter=ter_3y,
                ter_ke=ter_ke_3y,
                fv_ecf=fv_ecf_3y,
                load_ra_mm_by_year=load_ra_mm_by_year,
                interval=3
            )
            logger.info(f"[TER Alpha]   - Calculated 3Y TER Alpha: {len(ter_alpha_3y)} records")
            
            ter_alpha_5y = self._calculate_ter_alpha_for_interval(
                calc_mc=calc_mc,
                calc_ke=calc_ke,
                calc_ee=calc_ee,
                ter=ter_5y,
                ter_ke=ter_ke_5y,
                fv_ecf=fv_ecf_5y,
                load_ra_mm_by_year=load_ra_mm_by_year,
                interval=5
            )
            logger.info(f"[TER Alpha]   - Calculated 5Y TER Alpha: {len(ter_alpha_5y)} records")
            
            ter_alpha_10y = self._calculate_ter_alpha_for_interval(
                calc_mc=calc_mc,
                calc_ke=calc_ke,
                calc_ee=calc_ee,
                ter=ter_10y,
                ter_ke=ter_ke_10y,
                fv_ecf=fv_ecf_10y,
                load_ra_mm_by_year=load_ra_mm_by_year,
                interval=10
            )
            logger.info(f"[TER Alpha]   - Calculated 10Y TER Alpha: {len(ter_alpha_10y)} records")
            
            # Combine all intervals
            ter_alpha_combined = pd.concat([ter_alpha_1y, ter_alpha_3y, ter_alpha_5y, ter_alpha_10y], ignore_index=True)
            logger.info(f"[TER Alpha]   - Total records calculated: {len(ter_alpha_combined)}")
            
            # Step 9a: Add NULL rows for insufficient history
            logger.info("[TER Alpha] Step 9a: Adding NULL rows for insufficient history...")
            ter_alpha_combined, null_breakdown = self._add_null_rows_for_ter_alpha(ter_alpha_combined, fundamentals_df)
            logger.info(f"[TER Alpha]   - Total records after NULL rows: {len(ter_alpha_combined)}")
            
            # Step 10: Insert results in batches
            logger.info("[TER Alpha] Step 10: Inserting into metrics_outputs...")
            await self._insert_ter_alpha_batch(
                ter_alpha_df=ter_alpha_combined,
                null_breakdown=null_breakdown,
                dataset_id=dataset_id,
                param_set_id=param_set_id
            )
            logger.info(f"[TER Alpha]   - Insertion complete")
            
            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"[TER Alpha] ✓ TER Alpha calculation completed in {elapsed_ms:.0f}ms")
            
            return {
                'dataset_id': str(dataset_id),
                'param_set_id': str(param_set_id),
                'intervals': ['1Y', '3Y', '5Y', '10Y'],
                'total_records_calculated': len(ter_alpha_combined) - sum(null_breakdown.values()),
                'total_records_with_nulls': len(ter_alpha_combined),
                'null_row_breakdown': null_breakdown,
                'metrics_inserted': [
                    'Calc 1Y Load RA MM', 'Calc 1Y WC TERA', 'Calc 1Y TER Alpha',
                    'Calc 3Y Load RA MM', 'Calc 3Y WC TERA', 'Calc 3Y TER Alpha',
                    'Calc 5Y Load RA MM', 'Calc 5Y WC TERA', 'Calc 5Y TER Alpha',
                    'Calc 10Y Load RA MM', 'Calc 10Y WC TERA', 'Calc 10Y TER Alpha',
                ],
                'calculation_time_ms': elapsed_ms
            }
        
        except Exception as e:
            logger.error(f"[TER Alpha] ✗ Error in TER Alpha calculation: {str(e)}", exc_info=True)
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
    
    async def _fetch_fundamentals_metric(
        self,
        dataset_id: UUID,
        metric_name: str
    ) -> pd.DataFrame:
        """Fetch metric from fundamentals table using metric_name filter."""
        query = text("""
            SELECT ticker, fiscal_year, numeric_value
            FROM cissa.fundamentals
            WHERE dataset_id = :dataset_id
              AND metric_name = :metric_name
            ORDER BY ticker, fiscal_year
        """)
        
        result = await self.session.execute(query, {
            'dataset_id': dataset_id,
            'metric_name': metric_name
        })
        rows = result.fetchall()
        df = pd.DataFrame(rows, columns=['ticker', 'fiscal_year', 'value'])
        df['fiscal_year'] = df['fiscal_year'].astype(int)
        df['value'] = df['value'].apply(to_float)
        return df
    
    async def _fetch_all_fundamentals(self, dataset_id: UUID) -> pd.DataFrame:
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
    
    async def _get_parameter_value(
        self,
        param_set_id: UUID,
        param_name: str,
        default: float
    ) -> float:
        """Get a single parameter value from parameter_sets or parameters table."""
        query = text("""
            SELECT param_overrides
            FROM cissa.parameter_sets
            WHERE param_set_id = :param_set_id
        """)
        
        result = await self.session.execute(query, {"param_set_id": str(param_set_id)})
        row = result.fetchone()
        
        if row and row[0] and param_name in row[0]:
            return float(row[0][param_name])
        
        # Fall back to parameters table default
        query = text("""
            SELECT default_value
            FROM cissa.parameters
            WHERE parameter_name = :param_name
        """)
        
        result = await self.session.execute(query, {"param_name": param_name})
        row = result.fetchone()
        
        if row and row[0] is not None:
            return float(row[0])
        
        return default
    
    def _calculate_portfolio_ra_mm(
        self,
        calc_mc: pd.DataFrame,
        calc_ke: pd.DataFrame,
        calc_rf: pd.DataFrame,
        fv_ecf_1y: pd.DataFrame,
        erp: float
    ) -> Dict[int, float]:
        """
        Calculate portfolio-level Load RA MM (same for all companies per year).
        
        Returns:
            Dict mapping fiscal_year → load_ra_mm_value
        """
        # Rename for clarity
        calc_mc = calc_mc.rename(columns={'value': 'calc_mc'}).copy()
        calc_ke = calc_ke.rename(columns={'value': 'calc_ke'}).copy()
        calc_rf = calc_rf.rename(columns={'value': 'calc_rf'}).copy()
        fv_ecf_1y = fv_ecf_1y.rename(columns={'value': 'fv_ecf'}).copy()
        
        # Merge all data
        df = calc_mc.merge(calc_ke, on=['ticker', 'fiscal_year'], how='inner')
        df = df.merge(calc_rf, on=['ticker', 'fiscal_year'], how='inner')
        df = df.merge(fv_ecf_1y, on=['ticker', 'fiscal_year'], how='inner')
        
        # Sort for lag calculation
        df = df.sort_values(['ticker', 'fiscal_year']).reset_index(drop=True)
        
        # Calculate LAG(Calc MC)
        df['calc_mc_lag'] = df.groupby('ticker')['calc_mc'].shift(1)
        df['open_mc'] = df['calc_mc_lag']
        
        # Calculate Load TRTE = FV ECF + (Calc MC - Open MC)
        df['load_trte'] = df['fv_ecf'] + (df['calc_mc'] - df['open_mc'])
        
        # Group by fiscal_year to get portfolio aggregates
        portfolio_df = df.groupby('fiscal_year').agg({
            'load_trte': 'sum',
            'open_mc': 'sum'
        }).reset_index()
        
        # Calculate portfolio Load Rm = (1 + Σ Load TRTE / Σ Open MC) - 1
        portfolio_df['load_rm'] = (1 + (portfolio_df['load_trte'] / portfolio_df['open_mc'])) - 1
        
        # Get average Load Rf and Load Ke per year (should be same across companies)
        year_rf_ke = df.groupby('fiscal_year').agg({
            'calc_rf': 'first',  # Should be same for all companies in year
            'calc_ke': 'mean'    # Average in case of small variations
        }).reset_index()
        
        # Merge to get Rf and Ke
        portfolio_df = portfolio_df.merge(year_rf_ke, on='fiscal_year')
        
        # Calculate Load RA MM = (Load Rm - (Load Rf + ERP)) × (Load Ke - Load Rf) / ERP
        portfolio_df['load_ra_mm'] = np.where(
            (portfolio_df['open_mc'] != 0),
            (portfolio_df['load_rm'] - (portfolio_df['calc_rf'] + erp)) * 
            (portfolio_df['calc_ke'] - portfolio_df['calc_rf']) / erp,
            np.nan
        )
        
        # Return as dict {fiscal_year: load_ra_mm}
        return dict(zip(portfolio_df['fiscal_year'], portfolio_df['load_ra_mm']))
    
    def _calculate_ter_alpha_for_interval(
        self,
        calc_mc: pd.DataFrame,
        calc_ke: pd.DataFrame,
        calc_ee: pd.DataFrame,
        ter: pd.DataFrame,
        ter_ke: pd.DataFrame,
        fv_ecf: pd.DataFrame,
        load_ra_mm_by_year: Dict[int, float],
        interval: int
    ) -> pd.DataFrame:
        """
        Calculate Load RA MM (broadcast), WC TERA, and TER Alpha for a specific interval.
        
        Returns:
            DataFrame with ticker, fiscal_year, and 3 metrics (Load RA MM, WC TERA, TER Alpha)
        """
        # Rename columns for clarity
        calc_mc = calc_mc.rename(columns={'value': 'calc_mc'}).copy()
        calc_ke = calc_ke.rename(columns={'value': 'calc_ke'}).copy()
        calc_ee = calc_ee.rename(columns={'value': 'calc_ee'}).copy()
        ter = ter.rename(columns={'value': 'ter'}).copy()
        ter_ke = ter_ke.rename(columns={'value': 'ter_ke'}).copy()
        fv_ecf = fv_ecf.rename(columns={'value': 'fv_ecf'}).copy()
        
        # Merge all data
        df = calc_mc.merge(calc_ke, on=['ticker', 'fiscal_year'], how='inner')
        df = df.merge(calc_ee, on=['ticker', 'fiscal_year'], how='inner')
        df = df.merge(ter, on=['ticker', 'fiscal_year'], how='inner')
        df = df.merge(ter_ke, on=['ticker', 'fiscal_year'], how='inner')
        df = df.merge(fv_ecf, on=['ticker', 'fiscal_year'], how='inner')
        
        # Sort for lag calculations
        df = df.sort_values(['ticker', 'fiscal_year']).reset_index(drop=True)
        
        # Calculate LAG(Calc MC) and LAG(Calc EE)
        df['calc_mc_lag'] = df.groupby('ticker')['calc_mc'].shift(1)
        df['calc_ee_lag'] = df.groupby('ticker')['calc_ee'].shift(1)
        
        # Open MC
        df['open_mc'] = df['calc_mc_lag']
        
        # Step 1: Calculate Calc Incl flag
        # Calc Incl = 1 if can calculate Calc MB, else 0
        df['calc_mb'] = np.where(
            df['calc_ee'].notna() & (df['calc_ee'] != 0),
            df['calc_mc'] / df['calc_ee'],
            np.nan
        )
        df['calc_incl'] = np.where(
            (df['calc_ee_lag'].notna()) & (df['calc_mb'].notna()),
            1.0,
            0.0
        )
        
        # Step 2: Calculate Load TRTE and Load TER
        df['load_trte'] = df['fv_ecf'] + (df['calc_mc'] - df['open_mc'])
        df['load_ter'] = np.where(
            df['open_mc'].notna() & (df['open_mc'] != 0),
            (df['load_trte'] / df['open_mc']) - 1,
            np.nan
        )
        
        # Step 3: Broadcast Load RA MM by fiscal year
        df['load_ra_mm'] = df['fiscal_year'].map(load_ra_mm_by_year)
        
        # Step 4: Calculate WC TERA
        # WC TERA = Open MC × (1 + Load TER) - Open MC × (1 + Calc KE + Load RA MM)
        df['wc_tera'] = np.where(
            df['open_mc'].notna() & (df['open_mc'] != 0),
            df['open_mc'] * (1 + df['load_ter']) - df['open_mc'] * (1 + df['calc_ke'] + df['load_ra_mm']),
            np.nan
        )
        
        # Step 5: Calculate TER Alpha
        # TER Alpha = TER-KE - (((1 + TER) - WC TERA / Open MC)^(1/interval) - (TER - TER-KE) - 1)
        exponent = 1.0 / interval
        ratio_numerator = (1 + df['ter']) - (df['wc_tera'] / df['open_mc'])
        df['ter_alpha'] = np.where(
            (df['open_mc'].notna() & (df['open_mc'] != 0)) & (df['calc_incl'] == 1),
            df['ter_ke'] - (np.power(ratio_numerator, exponent) - (df['ter'] - df['ter_ke']) - 1),
            np.nan
        )
        
        # Build result dataframe with all 3 metrics (Load RA MM, WC TERA, TER Alpha)
        # We'll return separate rows for each metric type
        
        load_ra_mm_results = pd.DataFrame({
            'ticker': df['ticker'],
            'fiscal_year': df['fiscal_year'],
            'TER_ALPHA_VALUE': df['load_ra_mm'],
            'METRIC_TYPE': f'Calc {interval}Y Load RA MM'
        })
        
        wc_tera_results = pd.DataFrame({
            'ticker': df['ticker'],
            'fiscal_year': df['fiscal_year'],
            'TER_ALPHA_VALUE': df['wc_tera'],
            'METRIC_TYPE': f'Calc {interval}Y WC TERA'
        })
        
        ter_alpha_results = pd.DataFrame({
            'ticker': df['ticker'],
            'fiscal_year': df['fiscal_year'],
            'TER_ALPHA_VALUE': df['ter_alpha'],
            'METRIC_TYPE': f'Calc {interval}Y TER Alpha'
        })
        
        return pd.concat([load_ra_mm_results, wc_tera_results, ter_alpha_results], ignore_index=True)
    
    def _add_null_rows_for_ter_alpha(
        self,
        ter_alpha_df: pd.DataFrame,
        fundamentals_df: pd.DataFrame
    ) -> tuple:
        """
        Add NULL rows for fiscal years with insufficient lag history.
        
        Load RA MM: No NULL rows (calculated for all years)
        WC TERA and TER Alpha: NULL rows for insufficient history
        
        Args:
            ter_alpha_df: DataFrame with calculated TER Alpha metrics
            fundamentals_df: Original fundamentals data with all ticker-year combinations
        
        Returns:
            Tuple of (DataFrame with NULL rows added, null_row_breakdown dict)
        """
        ticker_year_info = fundamentals_df.groupby('ticker')['fiscal_year'].agg(['min', 'max']).reset_index()
        
        null_rows = []
        null_row_breakdown = {
            '1Y_WC_TERA': 0,
            '1Y_TER_Alpha': 0,
            '3Y_WC_TERA': 0,
            '3Y_TER_Alpha': 0,
            '5Y_WC_TERA': 0,
            '5Y_TER_Alpha': 0,
            '10Y_WC_TERA': 0,
            '10Y_TER_Alpha': 0
        }
        
        for _, row in ticker_year_info.iterrows():
            ticker = row['ticker']
            min_year = int(row['min'])
            max_year = int(row['max'])
            
            # For 1Y: first year should have NULL
            if min_year <= max_year:
                null_rows.append({
                    'ticker': ticker,
                    'fiscal_year': min_year,
                    'TER_ALPHA_VALUE': np.nan,
                    'METRIC_TYPE': 'Calc 1Y WC TERA'
                })
                null_row_breakdown['1Y_WC_TERA'] += 1
                null_rows.append({
                    'ticker': ticker,
                    'fiscal_year': min_year,
                    'TER_ALPHA_VALUE': np.nan,
                    'METRIC_TYPE': 'Calc 1Y TER Alpha'
                })
                null_row_breakdown['1Y_TER_Alpha'] += 1
            
            # For 3Y: first 2 years should have NULL
            for year_offset in range(1, 3):
                target_year = min_year + year_offset
                if target_year <= max_year:
                    null_rows.append({
                        'ticker': ticker,
                        'fiscal_year': target_year,
                        'TER_ALPHA_VALUE': np.nan,
                        'METRIC_TYPE': 'Calc 3Y WC TERA'
                    })
                    null_row_breakdown['3Y_WC_TERA'] += 1
                    null_rows.append({
                        'ticker': ticker,
                        'fiscal_year': target_year,
                        'TER_ALPHA_VALUE': np.nan,
                        'METRIC_TYPE': 'Calc 3Y TER Alpha'
                    })
                    null_row_breakdown['3Y_TER_Alpha'] += 1
            
            # For 5Y: first 4 years should have NULL
            for year_offset in range(1, 5):
                target_year = min_year + year_offset
                if target_year <= max_year:
                    null_rows.append({
                        'ticker': ticker,
                        'fiscal_year': target_year,
                        'TER_ALPHA_VALUE': np.nan,
                        'METRIC_TYPE': 'Calc 5Y WC TERA'
                    })
                    null_row_breakdown['5Y_WC_TERA'] += 1
                    null_rows.append({
                        'ticker': ticker,
                        'fiscal_year': target_year,
                        'TER_ALPHA_VALUE': np.nan,
                        'METRIC_TYPE': 'Calc 5Y TER Alpha'
                    })
                    null_row_breakdown['5Y_TER_Alpha'] += 1
            
            # For 10Y: first 9 years should have NULL
            for year_offset in range(1, 10):
                target_year = min_year + year_offset
                if target_year <= max_year:
                    null_rows.append({
                        'ticker': ticker,
                        'fiscal_year': target_year,
                        'TER_ALPHA_VALUE': np.nan,
                        'METRIC_TYPE': 'Calc 10Y WC TERA'
                    })
                    null_row_breakdown['10Y_WC_TERA'] += 1
                    null_rows.append({
                        'ticker': ticker,
                        'fiscal_year': target_year,
                        'TER_ALPHA_VALUE': np.nan,
                        'METRIC_TYPE': 'Calc 10Y TER Alpha'
                    })
                    null_row_breakdown['10Y_TER_Alpha'] += 1
        
        null_rows_df = pd.DataFrame(null_rows)
        
        # Remove any calculated rows that conflict with NULL rows
        combined = ter_alpha_df.copy()
        if len(null_rows_df) > 0:
            conflict_key = null_rows_df[['ticker', 'fiscal_year', 'METRIC_TYPE']].copy()
            conflict_key['_conflict'] = True
            
            combined = combined.merge(
                conflict_key,
                on=['ticker', 'fiscal_year', 'METRIC_TYPE'],
                how='left'
            )
            
            combined = combined[combined['_conflict'].isna()].copy()
            combined = combined.drop('_conflict', axis=1)
        
        # Combine with NULL rows
        combined = pd.concat([combined, null_rows_df], ignore_index=True)
        
        return combined, null_row_breakdown
    
    async def _insert_ter_alpha_batch(
        self,
        ter_alpha_df: pd.DataFrame,
        null_breakdown: dict,
        dataset_id: UUID,
        param_set_id: UUID
    ) -> None:
        """
        Insert TER Alpha metrics into metrics_outputs using single multi-row INSERT.
        
        Args:
            ter_alpha_df: DataFrame with all TER Alpha metrics (Load RA MM, WC TERA, TER Alpha)
            null_breakdown: Dictionary with NULL row counts per metric type
            dataset_id: Dataset version ID
            param_set_id: Parameter set ID
        """
        try:
            # Build multi-row VALUES clause
            rows_sql_parts = []
            for _, row in ter_alpha_df.iterrows():
                metric_value = row['TER_ALPHA_VALUE']
                metric_value_sql = float(metric_value) if pd.notna(metric_value) else 'NULL'
                
                # Extract interval from metric type (e.g., "Calc 1Y Load RA MM" → "1Y")
                metric_type_parts = row['METRIC_TYPE'].split()
                interval = metric_type_parts[1]  # e.g., "1Y"
                
                metadata = {
                    'metric_level': 'L2',
                    'interval': interval
                }
                metadata_json = json.dumps(metadata).replace("'", "''")
                
                row_sql = f"('{str(dataset_id)}', '{str(param_set_id)}', '{row['ticker']}', {int(row['fiscal_year'])}, '{row['METRIC_TYPE']}', {metric_value_sql}, '{metadata_json}')"
                rows_sql_parts.append(row_sql)
            
            rows_sql = ", ".join(rows_sql_parts)
            
            # Execute single multi-row INSERT
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
            logger.info(f"[TER Alpha]   - Executed single multi-row INSERT for {len(ter_alpha_df)} records")
            
            # Single commit at the end
            await self.session.commit()
            logger.info(f"[TER Alpha]   - Batch insert complete: {len(ter_alpha_df)} records committed")
        
        except Exception as e:
            logger.error(f"[TER Alpha]   - Failed to insert TER Alpha batch: {e}", exc_info=True)
            await self.session.rollback()
            raise
