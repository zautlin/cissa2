# ============================================================================
# Beta Rounding Service
# ============================================================================
# Applies user-selected rounding and approach to pre-computed Beta values.
# Retrieves unrounded Beta from metrics_outputs (param_set_id=NULL),
# applies rounding based on user parameter, and stores/returns result.
# ============================================================================

import numpy as np
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import pandas as pd
import json
import time

from ..core.config import get_logger

logger = get_logger(__name__)


class BetaRoundingService:
    """
    Service for applying rounding to pre-computed Beta values at runtime.
    
    Workflow:
    1. User selects beta_rounding parameter (0.1, 0.05, 0.01, etc.)
    2. User selects approach_to_ke (FIXED or Floating)
    3. Query pre-computed Beta (param_set_id=NULL)
    4. Extract appropriate raw value from metadata
    5. Apply rounding: round(raw / rounding, 0) * rounding
    6. Store rounded result with param_set_id set
    7. Return formatted results
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = get_logger(__name__)

    async def check_precomputed_exists(self, dataset_id: UUID) -> bool:
        """Check if pre-computed Beta exists for dataset."""
        try:
            query = text(
                """
                SELECT COUNT(*) 
                FROM cissa.metrics_outputs
                WHERE dataset_id = :dataset_id
                AND output_metric_name = 'Calc Beta'
                AND param_set_id IS NULL
            """
            )
            result = await self.session.execute(
                query, {"dataset_id": str(dataset_id)}
            )
            count = result.scalar()
            return count > 0
        except Exception as e:
            self.logger.error(f"Failed to check pre-computed Beta: {e}")
            return False

    async def apply_rounding_to_precomputed_beta(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        beta_rounding: float,
        approach_to_ke: str,
    ) -> dict:
        """
        Apply rounding to pre-computed Beta values and store with param_set_id.

        Args:
            dataset_id: Dataset ID
            param_set_id: Parameter set ID (for storage)
            beta_rounding: Rounding increment (0.1, 0.05, etc.)
            approach_to_ke: "FIXED" or "Floating"

        Returns:
            {
                "status": "success|error",
                "results_count": N,
                "message": "...",
                "results": [{ticker, fiscal_year, beta}, ...]
            }
        """
        try:
            self.logger.info(
                f"Applying rounding to pre-computed Beta: dataset={dataset_id}, param_set={param_set_id}, rounding={beta_rounding}, approach={approach_to_ke}"
            )

            # Fetch pre-computed Beta records
            precomputed_records = await self._fetch_precomputed_beta(dataset_id)

            if not precomputed_records:
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": "No pre-computed Beta found",
                    "results": [],
                }

            # Apply rounding and approach selection
            rounded_results = []
            for record in precomputed_records:
                metadata = record.get("metadata", {})

                # Select appropriate raw value based on approach
                if approach_to_ke.upper() == "FIXED":
                    raw_value = metadata.get("fixed_beta_raw")
                else:  # Floating
                    raw_value = metadata.get("floating_beta_raw")

                if raw_value is None:
                    continue

                # Apply rounding
                rounded_value = np.round(raw_value / beta_rounding, 0) * beta_rounding

                rounded_results.append(
                    {
                        "ticker": record["ticker"],
                        "fiscal_year": record["fiscal_year"],
                        "beta": float(rounded_value),
                        "raw_beta": raw_value,
                        "approach": approach_to_ke,
                        "rounding": beta_rounding,
                    }
                )

            # Store rounded results in metrics_outputs
            stored_count = await self._store_rounded_results(
                dataset_id, param_set_id, rounded_results
            )

            self.logger.info(
                f"Applied rounding: {stored_count} records stored with rounding={beta_rounding}, approach={approach_to_ke}"
            )

            return {
                "status": "success",
                "results_count": stored_count,
                "message": f"Applied rounding ({beta_rounding}) and approach ({approach_to_ke}): {stored_count} records",
                "results": rounded_results,
            }

        except Exception as e:
            self.logger.error(f"Failed to apply rounding to pre-computed Beta: {e}", exc_info=True)
            return {
                "status": "error",
                "results_count": 0,
                "message": f"Rounding application failed: {str(e)}",
                "results": [],
            }

    async def _fetch_precomputed_beta(self, dataset_id: UUID) -> list[dict]:
        """Fetch pre-computed Beta records (param_set_id=NULL)."""
        try:
            query = text(
                """
                SELECT 
                    ticker,
                    fiscal_year,
                    output_metric_value,
                    metadata
                FROM cissa.metrics_outputs
                WHERE dataset_id = :dataset_id
                AND output_metric_name = 'Calc Beta'
                AND param_set_id IS NULL
                ORDER BY ticker, fiscal_year
            """
            )
            result = await self.session.execute(
                query, {"dataset_id": str(dataset_id)}
            )
            rows = result.fetchall()

            records = []
            for row in rows:
                try:
                    metadata = json.loads(row[3]) if isinstance(row[3], str) else row[3]
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

                records.append(
                    {
                        "ticker": row[0],
                        "fiscal_year": row[1],
                        "output_metric_value": row[2],
                        "metadata": metadata,
                    }
                )

            self.logger.info(f"Fetched {len(records)} pre-computed Beta records")
            return records

        except Exception as e:
            self.logger.error(f"Failed to fetch pre-computed Beta: {e}")
            raise

    async def _store_rounded_results(
        self, dataset_id: UUID, param_set_id: UUID, results: list[dict]
    ) -> int:
        """Store rounded results in metrics_outputs."""
        try:
            if not results:
                return 0

            query = text(
                """
                INSERT INTO cissa.metrics_outputs 
                (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata)
                VALUES (:dataset_id, :param_set_id, :ticker, :fiscal_year, :output_metric_name, :output_metric_value, :metadata)
                ON CONFLICT DO NOTHING
            """
            )

            for result in results:
                metadata = {
                    "metric_level": "L1",
                    "derived_from_precomputed": True,
                    "raw_beta": result.get("raw_beta"),
                    "approach": result.get("approach"),
                    "rounding": result.get("rounding"),
                }

                await self.session.execute(
                    query,
                    {
                        "dataset_id": str(dataset_id),
                        "param_set_id": str(param_set_id),
                        "ticker": result["ticker"],
                        "fiscal_year": result["fiscal_year"],
                        "output_metric_name": "Calc Beta",
                        "output_metric_value": float(result["beta"]),
                        "metadata": json.dumps(metadata),
                    },
                )

            await self.session.commit()
            self.logger.info(f"Stored {len(results)} rounded Beta results")
            return len(results)

        except Exception as e:
            self.logger.error(f"Failed to store rounded results: {e}", exc_info=True)
            await self.session.rollback()
            raise

    async def get_precomputed_beta_for_retrieval(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        beta_rounding: float,
        approach_to_ke: str,
    ) -> list[dict]:
        """
        Get pre-computed Beta with rounding applied (used by API endpoint).
        
        This method applies rounding and approach selection but does NOT store.
        """
        try:
            precomputed_records = await self._fetch_precomputed_beta(dataset_id)

            results = []
            for record in precomputed_records:
                metadata = record.get("metadata", {})

                # Select appropriate raw value based on approach
                if approach_to_ke.upper() == "FIXED":
                    raw_value = metadata.get("fixed_beta_raw")
                else:  # Floating
                    raw_value = metadata.get("floating_beta_raw")

                if raw_value is None:
                    continue

                # Apply rounding
                rounded_value = np.round(raw_value / beta_rounding, 0) * beta_rounding

                results.append(
                    {
                        "ticker": record["ticker"],
                        "fiscal_year": record["fiscal_year"],
                        "beta": float(rounded_value),
                    }
                )

            return results

        except Exception as e:
            self.logger.error(
                f"Failed to get pre-computed Beta for retrieval: {e}", exc_info=True
            )
            raise

    async def apply_rounding_to_precomputed_beta_batch(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        parameter_id: UUID,
    ) -> dict:
        """
        Batch version: Apply rounding to pre-computed Beta and store with param_set_id.
        
        Extracts beta_rounding and approach_to_ke from parameter_overrides (JSONB).
        Batch inserts results (1000-2000 records per insert) for better performance.
        
        Args:
            dataset_id: Dataset ID
            param_set_id: Parameter set ID (for storage)
            parameter_id: Parameter ID (used to fetch parameters from parameter_sets)
        
        Returns:
            {
                "status": "success|error",
                "results_count": N,
                "message": "...",
            }
        """
        try:
            start_time = time.time()
            self.logger.info(
                f"[BETA-BATCH] Starting batch Beta rounding: dataset={dataset_id}, param_set={param_set_id}, parameter={parameter_id}"
            )
            
            # Step 1: Load parameters from parameter_sets
            params = await self._load_parameters_from_parameter_set(parameter_id)
            beta_rounding = params.get("beta_rounding", 0.1)
            approach_to_ke = params.get("cost_of_equity_approach", "Floating").upper()
            
            self.logger.info(
                f"[BETA-BATCH] Parameters loaded: rounding={beta_rounding}, approach={approach_to_ke}"
            )
            
            # Step 2: Fetch pre-computed Beta records
            precomputed_records = await self._fetch_precomputed_beta(dataset_id)
            
            if not precomputed_records:
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": "No pre-computed Beta found",
                }
            
            self.logger.info(f"[BETA-BATCH] Fetched {len(precomputed_records)} pre-computed Beta records")
            
            # Step 3: Apply rounding and approach selection (vectorized)
            rounded_results = []
            for record in precomputed_records:
                metadata = record.get("metadata", {})
                
                # Select appropriate raw value based on approach
                if approach_to_ke == "FIXED":
                    raw_value = metadata.get("fixed_beta_raw")
                else:  # Floating
                    raw_value = metadata.get("floating_beta_raw")
                
                if raw_value is None:
                    continue
                
                # Apply rounding
                rounded_value = np.round(raw_value / beta_rounding, 0) * beta_rounding
                
                rounded_results.append({
                    "ticker": record["ticker"],
                    "fiscal_year": record["fiscal_year"],
                    "beta": float(rounded_value),
                    "raw_beta": raw_value,
                    "approach": approach_to_ke,
                    "rounding": beta_rounding,
                })
            
            self.logger.info(f"[BETA-BATCH] Rounded {len(rounded_results)} records")
            
            # Step 4: Batch insert results (1000 records per batch)
            stored_count = await self._store_rounded_results_batch(
                dataset_id, param_set_id, rounded_results, batch_size=1000
            )
            
            elapsed_time = time.time() - start_time
            self.logger.info(
                f"[BETA-BATCH] ✓ Batch Beta rounding complete: {stored_count} records stored in {elapsed_time:.2f}s"
            )
            
            return {
                "status": "success",
                "results_count": stored_count,
                "message": f"Applied rounding ({beta_rounding}) and approach ({approach_to_ke}): {stored_count} records stored",
            }
        
        except Exception as e:
            self.logger.error(f"[BETA-BATCH] Failed to apply batch rounding: {e}", exc_info=True)
            return {
                "status": "error",
                "results_count": 0,
                "message": f"Batch rounding failed: {str(e)}",
            }

    async def _load_parameters_from_parameter_set(self, parameter_id: UUID) -> dict:
        """
        Load parameters from parameter_sets table (JSONB param_overrides).
        
        Args:
            parameter_id: parameter_id (which is param_set_id in parameter_sets table)
        
        Returns:
            {
                "beta_rounding": 0.1,
                "cost_of_equity_approach": "Floating",
                ...
            }
        """
        try:
            query = text(
                """
                SELECT param_overrides
                FROM cissa.parameter_sets
                WHERE param_set_id = :parameter_id
                LIMIT 1
            """
            )
            result = await self.session.execute(query, {"parameter_id": str(parameter_id)})
            row = result.fetchone()
            
            if not row:
                self.logger.warning(f"[BETA-BATCH] Parameter set not found: {parameter_id}")
                return {}
            
            param_overrides = row[0]
            if isinstance(param_overrides, str):
                param_overrides = json.loads(param_overrides)
            elif param_overrides is None:
                param_overrides = {}
            
            return param_overrides
        
        except Exception as e:
            self.logger.error(f"[BETA-BATCH] Failed to load parameters: {e}")
            raise

    async def _store_rounded_results_batch(
        self, dataset_id: UUID, param_set_id: UUID, results: list[dict], batch_size: int = 1000
    ) -> int:
        """
        Batch insert rounded results using multi-row INSERT for better performance.
        
        Args:
            dataset_id: Dataset ID
            param_set_id: Parameter set ID
            results: List of rounded result dicts
            batch_size: Number of records per batch insert (default 1000)
        
        Returns:
            Total number of records inserted
        """
        if not results:
            return 0
        
        total_inserted = 0
        
        # Process results in batches using multi-row INSERT
        for i in range(0, len(results), batch_size):
            batch = results[i : i + batch_size]
            
            # Build multi-row VALUES clause for all records in batch
            rows_sql_parts = []
            for result in batch:
                metadata = {
                    "metric_level": "L1",
                    "derived_from_precomputed": True,
                    "raw_beta": result.get("raw_beta"),
                    "approach": result.get("approach"),
                    "rounding": result.get("rounding"),
                }
                metadata_json = json.dumps(metadata)
                row_sql = f"('{str(dataset_id)}', '{str(param_set_id)}', '{result['ticker']}', {result['fiscal_year']}, 'Calc Beta', {float(result['beta'])}, '{metadata_json}')"
                rows_sql_parts.append(row_sql)
            
            rows_sql = ", ".join(rows_sql_parts)
            
            # Execute single multi-row INSERT per batch
            query = text(f"""
                INSERT INTO cissa.metrics_outputs 
                (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata)
                VALUES {rows_sql}
                ON CONFLICT DO NOTHING
            """)
            
            await self.session.execute(query)
            total_inserted += len(batch)
            self.logger.info(f"[BETA-BATCH] Executed batch of {len(batch)} records ({total_inserted}/{len(results)} total)")
        
        # Single commit at the end
        await self.session.commit()
        self.logger.info(f"[BETA-BATCH] Batch insert complete: {total_inserted} records committed")
        return total_inserted
