# ============================================================================
# Runtime Metrics Orchestration Service
# ============================================================================
# Orchestrates Phase 3+ metrics calculation and storage:
# 1. Beta Rounding: Apply param-specific rounding/approach to pre-computed Beta
# 2. Risk-Free Rate: Calculate Rf based on parameter set
# 3. Cost of Equity: Calculate KE = Rf + Beta × RiskPremium
# 4. FV ECF: Calculate FV_ECF for 4 intervals (1Y, 3Y, 5Y, 10Y)
#
# Execution Strategy:
# - Beta Rounding & Risk-Free Rate run in PARALLEL (no dependencies)
# - Cost of Equity runs SEQUENTIAL (depends on both Beta & Rf)
# - FV ECF runs SEQUENTIAL (depends on Cost of Equity results)
# - FAIL-SOFT: Phase 4 (FV_ECF) failure logs error but doesn't stop orchestration
# ============================================================================

import asyncio
import time
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, Dict, Any

from ..core.config import get_logger
from .beta_rounding_service import BetaRoundingService
from .risk_free_rate_service import RiskFreeRateCalculationService
from .cost_of_equity_service import CostOfEquityService
from .fv_ecf_service import FVECFService
from .ter_service import TERService

logger = get_logger(__name__)


class RuntimeMetricsOrchestrationService:
    """
    Orchestrates Phase 3+ runtime metrics calculation.
    
    Execution Flow:
    1. Resolve parameter_id (use provided or fallback to is_active=true)
    2. Run Beta Rounding & Rf Calculation in PARALLEL
    3. On success, run Cost of Equity SEQUENTIALLY
    4. FAIL-FAST on any error
    5. Return comprehensive status
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = get_logger(__name__)

    async def orchestrate_runtime_metrics(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        parameter_id: Optional[UUID] = None,
    ) -> dict:
        """
        Main orchestration method for runtime metrics.

        Phases:
        1. Beta Rounding & Risk-Free Rate (parallel)
        2. Cost of Equity (sequential, depends on phases 1)
        3. FV ECF (sequential, depends on phase 2)

        Args:
            dataset_id: Dataset ID
            param_set_id: Parameter set ID for storing results
            parameter_id: Specific parameter ID to use (optional, fallback to is_active)

        Returns:
            {
                "success": True/False,
                "execution_time_seconds": X.X,
                "dataset_id": "...",
                "param_set_id": "...",
                "parameter_id": "...",
                "timestamp": "...",
                "metrics_completed": {
                    "beta_rounding": {...},
                    "risk_free_rate": {...},
                    "cost_of_equity": {...},
                    "fv_ecf": {...}
                },
                "error": "..." (if failed)
            }
        """
        start_time = time.time()
        
        try:
            self.logger.info(
                f"[RUNTIME-METRICS] Starting orchestration: dataset={dataset_id}, param_set={param_set_id}, parameter_id={parameter_id}"
            )

            # Step 1: Resolve parameter_id
            resolved_param_id = await self._resolve_parameter_id(parameter_id)
            if not resolved_param_id:
                error_msg = "No parameter_id provided and no active parameter set found"
                self.logger.error(f"[RUNTIME-METRICS] {error_msg}")
                return {
                    "success": False,
                    "execution_time_seconds": time.time() - start_time,
                    "dataset_id": str(dataset_id),
                    "param_set_id": str(param_set_id),
                    "error": error_msg,
                    "metrics_completed": {},
                }

            self.logger.info(
                f"[RUNTIME-METRICS] Resolved parameter_id: {resolved_param_id}"
            )

            # Step 2: Run Beta Rounding & Rf SEQUENTIALLY (cannot run in parallel with shared session)
            # AsyncPG connections don't support concurrent operations on the same connection
            self.logger.info(
                "[RUNTIME-METRICS] Step 1: Running Beta Rounding & Risk-Free Rate sequentially..."
            )
            
            beta_result = await self._orchestrate_beta_rounding(
                dataset_id, param_set_id, resolved_param_id
            )
            
            # Check for failure in beta phase
            if beta_result["status"] == "error":
                error_msg = f"Beta rounding failed: {beta_result['message']}"
                self.logger.error(f"[RUNTIME-METRICS] {error_msg}")
                return {
                    "success": False,
                    "execution_time_seconds": time.time() - start_time,
                    "dataset_id": str(dataset_id),
                    "param_set_id": str(param_set_id),
                    "error": error_msg,
                    "metrics_completed": {},
                }
            
            rf_result = await self._orchestrate_risk_free_rate(
                dataset_id, param_set_id, resolved_param_id
            )
            
            # Check for failure in RF phase
            if rf_result["status"] == "error":
                error_msg = f"Risk-free rate calculation failed: {rf_result['message']}"
                self.logger.error(f"[RUNTIME-METRICS] {error_msg}")
                return {
                    "success": False,
                    "execution_time_seconds": time.time() - start_time,
                    "dataset_id": str(dataset_id),
                    "param_set_id": str(param_set_id),
                    "error": error_msg,
                    "metrics_completed": {},
                }

            self.logger.info(
                f"[RUNTIME-METRICS] ✓ Sequential phase 1 complete: Beta={beta_result.get('results_count', 0)} records, Rf={rf_result.get('results_count', 0)} records"
            )

            # Step 3: Run Cost of Equity SEQUENTIALLY (depends on Beta & Rf)
            self.logger.info(
                "[RUNTIME-METRICS] Step 2: Running Cost of Equity (sequential, depends on Beta & Rf)..."
            )

            ke_result = await self._orchestrate_cost_of_equity(
                dataset_id, param_set_id, resolved_param_id
            )

            if ke_result["status"] == "error":
                error_msg = f"Cost of equity calculation failed: {ke_result['message']}"
                self.logger.error(f"[RUNTIME-METRICS] {error_msg}")
                return {
                    "success": False,
                    "execution_time_seconds": time.time() - start_time,
                    "dataset_id": str(dataset_id),
                    "param_set_id": str(param_set_id),
                    "error": error_msg,
                    "metrics_completed": {},
                }

            self.logger.info(
                f"[RUNTIME-METRICS] ✓ Phase 2 (Cost of Equity) complete: {ke_result.get('records_inserted', 0)} records"
            )

            # Step 4: Run FV ECF SEQUENTIALLY (depends on Cost of Equity results)
            # NOTE: Phase 4 failure is logged but doesn't fail the orchestration (FAIL-SOFT)
            self.logger.info(
                "[RUNTIME-METRICS] Step 3: Running FV ECF (sequential, depends on Cost of Equity)..."
            )

            fv_ecf_result = await self._orchestrate_fv_ecf(
                dataset_id, param_set_id, resolved_param_id
            )

            if fv_ecf_result["status"] == "error":
                self.logger.warning(
                    f"[RUNTIME-METRICS] FV ECF calculation failed: {fv_ecf_result['message']}. Continuing with results from Phases 1-3."
                )
                # Log the error but don't fail orchestration
                fv_ecf_result_for_response = fv_ecf_result
            else:
                self.logger.info(
                    f"[RUNTIME-METRICS] ✓ Phase 3 (FV ECF) complete: {fv_ecf_result.get('total_inserted', 0)} records"
                )
                fv_ecf_result_for_response = fv_ecf_result

            # Step 5: Run TER SEQUENTIALLY (depends on FV ECF results)
            # NOTE: Phase 5 failure is logged but doesn't fail the orchestration (FAIL-SOFT)
            self.logger.info(
                "[RUNTIME-METRICS] Step 4: Running TER (sequential, depends on FV ECF)..."
            )

            ter_result = await self._orchestrate_ter(
                dataset_id, param_set_id
            )

            if ter_result["status"] == "error":
                self.logger.warning(
                    f"[RUNTIME-METRICS] TER calculation failed: {ter_result['message']}. Continuing with results from Phases 1-4."
                )
                # Log the error but don't fail orchestration
                ter_result_for_response = ter_result
            else:
                self.logger.info(
                    f"[RUNTIME-METRICS] ✓ Phase 4 (TER) complete: {ter_result.get('total_records_with_nulls', 0)} records"
                )
                ter_result_for_response = ter_result

            elapsed_time = time.time() - start_time

            self.logger.info(
                f"[RUNTIME-METRICS] ✓ Orchestration complete: all phases processed in {elapsed_time:.1f}s"
            )

            return {
                "success": True,
                "execution_time_seconds": elapsed_time,
                "dataset_id": str(dataset_id),
                "param_set_id": str(param_set_id),
                "parameter_id": str(resolved_param_id),
                "timestamp": self._get_timestamp(),
                "metrics_completed": {
                    "beta_rounding": {
                        "status": beta_result["status"],
                        "records_inserted": beta_result.get("results_count", 0),
                        "time_seconds": beta_result.get("time_seconds", 0),
                        "message": beta_result.get("message", ""),
                    },
                    "risk_free_rate": {
                        "status": rf_result["status"],
                        "records_inserted": rf_result.get("results_count", 0),
                        "time_seconds": rf_result.get("time_seconds", 0),
                        "message": rf_result.get("message", ""),
                    },
                    "cost_of_equity": {
                        "status": ke_result["status"],
                        "records_inserted": ke_result.get("records_inserted", 0),
                        "time_seconds": ke_result.get("time_seconds", 0),
                        "message": ke_result.get("message", ""),
                    },
                    "fv_ecf": {
                        "status": fv_ecf_result_for_response.get("status", "unknown"),
                        "records_inserted": fv_ecf_result_for_response.get("total_inserted", 0),
                        "intervals_summary": fv_ecf_result_for_response.get("intervals_summary", {}),
                        "time_seconds": fv_ecf_result_for_response.get("duration_seconds", 0),
                        "message": fv_ecf_result_for_response.get("message", ""),
                    },
                    "ter": {
                        "status": ter_result_for_response.get("status", "unknown"),
                        "records_inserted": ter_result_for_response.get("total_records_with_nulls", 0),
                        "intervals_summary": ter_result_for_response.get("intervals", []),
                        "time_seconds": ter_result_for_response.get("calculation_time_ms", 0) / 1000,
                        "message": ter_result_for_response.get("message", ""),
                    },
                },
            }

        except Exception as e:
            elapsed_time = time.time() - start_time
            self.logger.error(
                f"[RUNTIME-METRICS] Orchestration failed: {str(e)}", exc_info=True
            )
            return {
                "success": False,
                "execution_time_seconds": elapsed_time,
                "dataset_id": str(dataset_id),
                "param_set_id": str(param_set_id),
                "error": str(e),
                "metrics_completed": {},
            }

    async def _resolve_parameter_id(self, parameter_id: Optional[UUID]) -> Optional[UUID]:
        """
        Resolve parameter_id from input or fallback to is_active parameter set.

        Args:
            parameter_id: User-provided parameter ID (optional)

        Returns:
            Resolved UUID or None if not found
        """
        # If parameter_id provided, use it
        if parameter_id:
            self.logger.info(f"[RUNTIME-METRICS] Using provided parameter_id: {parameter_id}")
            return parameter_id

        # Fallback: fetch is_active parameter set
        self.logger.info(
            "[RUNTIME-METRICS] No parameter_id provided, fetching active parameter set..."
        )
        try:
            query = text(
                """
                SELECT param_set_id
                FROM cissa.parameter_sets
                WHERE is_active = true
                LIMIT 1
            """
            )
            result = await self.session.execute(query)
            row = result.fetchone()

            if row:
                param_set_id = row[0]
                self.logger.info(
                    f"[RUNTIME-METRICS] Found active parameter set: {param_set_id}"
                )
                return param_set_id
            else:
                self.logger.warning("[RUNTIME-METRICS] No active parameter set found")
                return None

        except Exception as e:
            self.logger.error(f"[RUNTIME-METRICS] Failed to fetch active parameter set: {e}")
            return None

    async def _orchestrate_beta_rounding(
        self, dataset_id: UUID, param_set_id: UUID, parameter_id: UUID
    ) -> dict:
        """Execute Beta rounding calculation."""
        try:
            start_time = time.time()
            service = BetaRoundingService(self.session)

            result = await service.apply_rounding_to_precomputed_beta_batch(
                dataset_id=dataset_id,
                param_set_id=param_set_id,
                parameter_id=parameter_id,
            )

            result["time_seconds"] = time.time() - start_time
            return result

        except Exception as e:
            self.logger.error(f"[RUNTIME-METRICS] Beta rounding error: {e}", exc_info=True)
            return {
                "status": "error",
                "results_count": 0,
                "message": str(e),
                "time_seconds": time.time() - start_time,
            }

    async def _orchestrate_risk_free_rate(
        self, dataset_id: UUID, param_set_id: UUID, parameter_id: UUID
    ) -> dict:
        """Execute Risk-Free Rate calculation."""
        try:
            start_time = time.time()
            service = RiskFreeRateCalculationService(self.session)

            result = await service.calculate_risk_free_rate_runtime_batch(
                dataset_id=dataset_id,
                param_set_id=param_set_id,
                parameter_id=parameter_id,
            )

            result["time_seconds"] = time.time() - start_time
            return result

        except Exception as e:
            self.logger.error(f"[RUNTIME-METRICS] Risk-free rate error: {e}", exc_info=True)
            return {
                "status": "error",
                "results_count": 0,
                "message": str(e),
                "time_seconds": time.time() - start_time,
            }

    async def _orchestrate_cost_of_equity(
        self, dataset_id: UUID, param_set_id: UUID, parameter_id: UUID
    ) -> dict:
        """Execute Cost of Equity calculation."""
        try:
            start_time = time.time()
            service = CostOfEquityService(self.session)

            result = await service.calculate_cost_of_equity_runtime_batch(
                dataset_id=dataset_id,
                param_set_id=param_set_id,
                parameter_id=parameter_id,
            )

            result["time_seconds"] = time.time() - start_time
            return result

        except Exception as e:
            self.logger.error(f"[RUNTIME-METRICS] Cost of equity error: {e}", exc_info=True)
            return {
                "status": "error",
                "records_inserted": 0,
                "message": str(e),
                "time_seconds": time.time() - start_time,
            }

    async def _orchestrate_fv_ecf(
        self, dataset_id: UUID, param_set_id: UUID, parameter_id: UUID
    ) -> dict:
        """
        Execute FV ECF calculation for Phase 4.
        
        Note: Failures in this phase are logged but don't fail the orchestration (FAIL-SOFT).
        """
        try:
            start_time = time.time()
            service = FVECFService(self.session)

            result = await service.calculate_fv_ecf_for_runtime(
                dataset_id=dataset_id,
                param_set_id=param_set_id,
                parameter_id=parameter_id,
            )

            # Ensure required fields are present in result
            result["duration_seconds"] = time.time() - start_time
            return result

        except Exception as e:
            self.logger.error(f"[RUNTIME-METRICS] FV ECF calculation error: {e}", exc_info=True)
            return {
                "status": "error",
                "total_inserted": 0,
                "intervals_summary": {"1Y": 0, "3Y": 0, "5Y": 0, "10Y": 0},
                "message": str(e),
                "duration_seconds": time.time() - start_time,
            }

    async def _orchestrate_ter(
        self, dataset_id: UUID, param_set_id: UUID
    ) -> dict:
        """
        Execute TER (Total Expense Ratio) calculation for Phase 5.
        
        Note: Failures in this phase are logged but don't fail the orchestration (FAIL-SOFT).
        """
        try:
            start_time = time.time()
            service = TERService(self.session)

            result = await service.calculate_ter_metrics(
                dataset_id=dataset_id,
                param_set_id=param_set_id,
            )

            # Ensure required fields are present in result
            result["calculation_time_ms"] = (time.time() - start_time) * 1000
            return result

        except Exception as e:
            self.logger.error(f"[RUNTIME-METRICS] TER calculation error: {e}", exc_info=True)
            return {
                "status": "error",
                "total_records_with_nulls": 0,
                "intervals": {"1Y": 0, "3Y": 0, "5Y": 0, "10Y": 0},
                "message": str(e),
                "calculation_time_ms": (time.time() - start_time) * 1000,
            }
        """Get ISO format timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat()
