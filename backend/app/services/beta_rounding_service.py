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
