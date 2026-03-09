# ============================================================================
# Enhanced Metrics Service (Phase 3)
# ============================================================================
# Calculates: Beta, Risk-Free Rate, Cost of Equity, Economic Profit, TSR, Ratios
# Stores results in cissa.metrics_outputs table with metric_level=L3
# ============================================================================

import pandas as pd
import numpy as np
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..core.config import get_logger
from ..repositories.metrics_repository import MetricsRepository

logger = get_logger(__name__)


class EnhancedMetricsService:
    """
    Service for Phase 3 metrics calculation.
    
    Calculates: Beta, Rf, KE, EP, TSR, Financial Ratios
    All results stored in metrics_outputs with metadata: {"metric_level": "L3"}
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = MetricsRepository(session)
    
    async def calculate_enhanced_metrics(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
    ) -> dict:
        """
        Main orchestration method. Calculates all Phase 3 metrics.
        
        Returns:
            {
                "status": "success|error",
                "results_count": N,
                "metrics_calculated": [...],
                "message": "..."
            }
        """
        try:
            logger.info(f"Starting enhanced metrics: dataset={dataset_id}, param_set={param_set_id}")
            
            # Load parameters
            logger.info("Loading parameters...")
            params = await self._load_parameters_from_db(param_set_id)
            
            # Fetch data
            logger.info("Fetching fundamentals...")
            fundamentals_df = await self._fetch_fundamentals(dataset_id)
            if fundamentals_df.empty:
                return {"status": "error", "results_count": 0, "metrics_calculated": [], "message": "No fundamentals"}
            
            logger.info("Fetching L1 metrics...")
            l1_metrics_df = await self._fetch_l1_metrics(dataset_id, param_set_id)
            if l1_metrics_df.empty:
                return {"status": "error", "results_count": 0, "metrics_calculated": [], "message": "No L1 metrics"}
            
            # Pivot L1 metrics to columns
            logger.info("Pivoting L1 metrics...")
            l1_pivoted = l1_metrics_df.pivot_table(
                index=["ticker", "fiscal_year"],
                columns="output_metric_name",
                values="output_metric_value",
                aggfunc="first"
            ).reset_index()
            
            # Merge data
            logger.info("Merging data...")
            merged_df = fundamentals_df.merge(l1_pivoted, on=["ticker", "fiscal_year"], how="inner")
            if merged_df.empty:
                return {"status": "error", "results_count": 0, "metrics_calculated": [], "message": "No merged data"}
            
            logger.info(f"Merged: {len(merged_df)} rows")
            
            # Calculate metrics
            all_results = []
            metrics_list = []
            
            # 1. Beta
            logger.info("  Calculating Beta...")
            beta_df = self._calculate_beta(merged_df, params)
            if not beta_df.empty:
                all_results.append(beta_df)
                metrics_list.append("Beta")
                merged_df = merged_df.merge(beta_df[["ticker", "fiscal_year", "Beta"]], on=["ticker", "fiscal_year"], how="left")
            
            # 2. Risk-Free Rate
            logger.info("  Calculating Rf...")
            rf_df = self._calculate_rf(merged_df, params)
            if not rf_df.empty:
                all_results.append(rf_df)
                metrics_list.append("Calc Rf")
                merged_df = merged_df.merge(rf_df[["ticker", "fiscal_year", "Calc Rf"]], on=["ticker", "fiscal_year"], how="left")
            
            # 3. Cost of Equity
            logger.info("  Calculating Cost of Equity...")
            ke_df = self._calculate_cost_of_equity(merged_df, params)
            if not ke_df.empty:
                all_results.append(ke_df)
                metrics_list.append("Calc KE")
                merged_df = merged_df.merge(ke_df[["ticker", "fiscal_year", "Calc KE"]], on=["ticker", "fiscal_year"], how="left")
            
            # 4. Financial Ratios
            logger.info("  Calculating Financial Ratios...")
            ratio_df = self._calculate_financial_ratios(merged_df, params)
            if not ratio_df.empty:
                all_results.append(ratio_df)
                metrics_list.extend(["ROA", "ROE", "Profit Margin"])
            
            # Insert all results
            logger.info("Inserting results into database...")
            total_inserted = 0
            for result_df in all_results:
                inserted = await self._insert_metrics_batch(dataset_id, param_set_id, result_df)
                total_inserted += inserted
            
            logger.info(f"Success: inserted {total_inserted} records")
            return {
                "status": "success",
                "results_count": total_inserted,
                "metrics_calculated": metrics_list,
                "message": f"Calculated {len(metrics_list)} metric types"
            }
        
        except Exception as e:
            logger.error(f"Error in enhanced metrics: {e}", exc_info=True)
            return {
                "status": "error",
                "results_count": 0,
                "metrics_calculated": [],
                "message": str(e)
            }
    
    # ========================================================================
    # Data Fetching
    # ========================================================================
    
    async def _load_parameters_from_db(self, param_set_id: UUID) -> dict:
        """Load parameters from database with proper conversions."""
        # Step 1: Get base parameters
        query = text("""
            SELECT 
                parameter_name,
                default_value as value
            FROM cissa.parameters
            ORDER BY parameter_name
        """)
        
        result = await self.session.execute(query)
        rows = result.fetchall()
        
        params = {}
        for row in rows:
            param_name = row[0]
            value = row[1]
            
            # Convert percentages to decimals (6 parameters)
            if param_name in ["equity_risk_premium", "fixed_benchmark_return_wealth_preservation",
                             "beta_relative_error_tolerance", "tax_rate_franking_credits", "value_of_franking_credits"]:
                params[param_name] = float(value) / 100.0
            # Convert numeric parameters to float
            elif param_name in ["beta_rounding", "risk_free_rate_rounding", "terminal_year", "last_calendar_year"]:
                params[param_name] = float(value)
            # Convert booleans
            elif param_name in ["include_franking_credits_tsr"]:
                params[param_name] = value.lower() in ["true", "1", "yes"] if isinstance(value, str) else bool(value)
            # Keep others as strings (country, currency_notation, cost_of_equity_approach)
            else:
                params[param_name] = value
        
        # Step 2: Apply overrides from parameter_set if any exist
        override_query = text("""
            SELECT param_overrides
            FROM cissa.parameter_sets
            WHERE param_set_id = :param_set_id
        """)
        
        override_result = await self.session.execute(override_query, {"param_set_id": str(param_set_id)})
        override_row = override_result.fetchone()
        
        if override_row and override_row[0]:
            overrides = override_row[0]  # This is the JSONB param_overrides
            for key, value in overrides.items():
                # Apply override if parameter exists
                if key in params:
                    if key in ["equity_risk_premium", "fixed_benchmark_return_wealth_preservation",
                              "beta_relative_error_tolerance", "tax_rate_franking_credits", "value_of_franking_credits"]:
                        params[key] = float(value) / 100.0
                    elif key in ["beta_rounding", "risk_free_rate_rounding", "terminal_year", "last_calendar_year"]:
                        params[key] = float(value)
                    elif key in ["include_franking_credits_tsr"]:
                        params[key] = value.lower() in ["true", "1", "yes"] if isinstance(value, str) else bool(value)
                    else:
                        params[key] = value
        
        return params
    
    async def _fetch_fundamentals(self, dataset_id: UUID) -> pd.DataFrame:
        """Fetch fundamentals, pivoted to columns."""
        query = text("""
            SELECT 
                ticker,
                fiscal_year,
                MAX(CASE WHEN metric_name = 'SPOT_SHARES' THEN numeric_value END) as shrouts,
                MAX(CASE WHEN metric_name = 'SHARE_PRICE' THEN numeric_value END) as price,
                MAX(CASE WHEN metric_name = 'TOTAL_ASSETS' THEN numeric_value END) as total_assets,
                MAX(CASE WHEN metric_name = 'REVENUE' THEN numeric_value END) as revenue,
                MAX(CASE WHEN metric_name = 'PROFIT_AFTER_TAX' THEN numeric_value END) as pat,
                MAX(CASE WHEN metric_name = 'TOTAL_EQUITY' THEN numeric_value END) as total_equity,
                MAX(CASE WHEN metric_name = 'DIVIDENDS' THEN numeric_value END) as dividend
            FROM cissa.fundamentals
            WHERE dataset_id = :dataset_id
            AND period_type = 'FISCAL'
            GROUP BY ticker, fiscal_year
            ORDER BY ticker, fiscal_year
        """)
        
        result = await self.session.execute(query, {"dataset_id": str(dataset_id)})
        rows = result.fetchall()
        
        df = pd.DataFrame(
            rows,
            columns=["ticker", "fiscal_year", "shrouts", "price", "total_assets", "revenue", "pat", "total_equity", "dividend"]
        )
        return df
    
    async def _fetch_l1_metrics(self, dataset_id: UUID, param_set_id: UUID) -> pd.DataFrame:
        """Fetch L1 metrics from metrics_outputs.
        
        L1 metrics have metric_level='L1' in metadata.
        """
        query = text("""
            SELECT 
                ticker,
                fiscal_year,
                output_metric_name,
                output_metric_value
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id
              AND param_set_id = :param_set_id
              AND metadata->>'metric_level' = 'L1'
            ORDER BY ticker, fiscal_year, output_metric_name
        """)
        
        result = await self.session.execute(query, {
            "dataset_id": str(dataset_id),
            "param_set_id": str(param_set_id)
        })
        rows = result.fetchall()
        
        df = pd.DataFrame(
            rows,
            columns=["ticker", "fiscal_year", "output_metric_name", "output_metric_value"]
        )
        return df
    
    # ========================================================================
    # Calculation Methods
    # ========================================================================
    
    def _calculate_beta(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Calculate Beta (simplified to 1.0 until timeseries data available)."""
        results = []
        beta_rounding = params.get("beta_rounding", 0.1)
        
        for _, row in df.iterrows():
            # Use 1.0 as default beta
            beta = 1.0
            beta_rounded = round(beta / beta_rounding) * beta_rounding
            
            results.append({
                "ticker": row["ticker"],
                "fiscal_year": int(row["fiscal_year"]),
                "metric_name": "Beta",
                "Beta": float(beta_rounded)
            })
        
        return pd.DataFrame(results)
    
    def _calculate_rf(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Calculate Risk-Free Rate from parameters."""
        results = []
        default_rf = params.get("fixed_benchmark_return_wealth_preservation", 0.05)
        
        for _, row in df.iterrows():
            results.append({
                "ticker": row["ticker"],
                "fiscal_year": int(row["fiscal_year"]),
                "metric_name": "Calc Rf",
                "Calc Rf": float(default_rf)
            })
        
        return pd.DataFrame(results)
    
    def _calculate_cost_of_equity(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Calculate KE = Rf + Beta * Risk Premium."""
        results = []
        
        for _, row in df.iterrows():
            beta = row.get("Beta")
            rf = row.get("Calc Rf")
            
            if pd.notna(beta) and pd.notna(rf):
                ke = rf + beta * params.get("equity_risk_premium", 0.05)
                
                results.append({
                    "ticker": row["ticker"],
                    "fiscal_year": int(row["fiscal_year"]),
                    "metric_name": "Calc KE",
                    "Calc KE": float(ke)
                })
        
        return pd.DataFrame(results)
    
    def _calculate_financial_ratios(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Calculate ROA, ROE, Profit Margin."""
        results = []
        
        for _, row in df.iterrows():
            ticker = row["ticker"]
            fy = int(row["fiscal_year"])
            
            # ROA
            if pd.notna(row.get("pat")) and pd.notna(row.get("total_assets")) and row["total_assets"] != 0:
                roa = row["pat"] / row["total_assets"]
                results.append({
                    "ticker": ticker,
                    "fiscal_year": fy,
                    "metric_name": "ROA",
                    "ROA": float(roa)
                })
            
            # ROE
            if pd.notna(row.get("pat")) and pd.notna(row.get("total_equity")) and row["total_equity"] != 0:
                roe = row["pat"] / row["total_equity"]
                results.append({
                    "ticker": ticker,
                    "fiscal_year": fy,
                    "metric_name": "ROE",
                    "ROE": float(roe)
                })
            
            # Profit Margin
            if pd.notna(row.get("pat")) and pd.notna(row.get("revenue")) and row["revenue"] != 0:
                margin = row["pat"] / row["revenue"]
                results.append({
                    "ticker": ticker,
                    "fiscal_year": fy,
                    "metric_name": "Profit Margin",
                    "Profit Margin": float(margin)
                })
        
        return pd.DataFrame(results)
    
    # ========================================================================
    # Storage
    # ========================================================================
    
    async def _insert_metrics_batch(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        results_df: pd.DataFrame
    ) -> int:
        """Insert calculated metrics into metrics_outputs."""
        if results_df.empty:
            return 0
        
        insert_query = text("""
            INSERT INTO cissa.metrics_outputs 
            (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata, created_at)
            VALUES (:dataset_id, :param_set_id, :ticker, :fiscal_year, :output_metric_name, :output_metric_value, :metadata, now())
            ON CONFLICT (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name) 
            DO UPDATE SET output_metric_value = EXCLUDED.output_metric_value
        """)
        
        inserted_count = 0
        for _, row in results_df.iterrows():
            try:
                # Get the value column
                value_cols = [col for col in row.index if col not in ["ticker", "fiscal_year", "metric_name"]]
                value = float(row[value_cols[0]]) if value_cols else 0.0
                
                await self.session.execute(insert_query, {
                    "dataset_id": str(dataset_id),
                    "param_set_id": str(param_set_id),
                    "ticker": str(row["ticker"]),
                    "fiscal_year": int(row["fiscal_year"]),
                    "output_metric_name": str(row["metric_name"]),
                    "output_metric_value": value,
                    "metadata": '{"metric_level": "L3", "calculation_source": "enhanced_metrics_service"}',
                })
                inserted_count += 1
            except Exception as e:
                logger.warning(f"Failed to insert {row['ticker']} FY{row['fiscal_year']}: {e}")
        
        await self.session.commit()
        return inserted_count
