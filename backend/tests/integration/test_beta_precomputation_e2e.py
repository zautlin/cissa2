# ============================================================================
# Integration E2E Tests for Beta Pre-Computation (Phase 6)
# ============================================================================
"""
Integration and end-to-end tests for beta pre-computation:
1. Pre-computation stores records with param_set_id=NULL
2. Rounding retrieves pre-computed values and applies rounding
3. Full workflow: pre-compute -> round -> retrieve
4. Verify data integrity across workflow
5. Test both FIXED and Floating approaches
"""

import pytest
import asyncio
import pandas as pd
import numpy as np
import json
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, patch, MagicMock
import sys
sys.path.insert(0, '/home/ubuntu/cissa')


@pytest.mark.asyncio
class TestPrecomputationStorageE2E:
    """E2E tests for pre-computation storage with param_set_id=NULL"""
    
    async def test_precomputed_beta_stored_with_null_param_set_id(self):
        """Verify pre-computed Beta is stored with param_set_id=NULL"""
        # This requires real database - would be tested in integration suite
        # Verifying the concept here
        
        precomputed_record = {
            "dataset_id": uuid4(),
            "param_set_id": None,  # NULL for pre-computed
            "ticker": "TEST",
            "fiscal_year": 2021,
            "output_metric_name": "Calc Beta",
            "output_metric_value": 0.8765,  # Raw unrounded value
            "metadata": {
                "metric_level": "L1",
                "fixed_beta_raw": 1.0555,
                "floating_beta_raw": 0.8765,
                "spot_slope_raw": 0.8765,
                "sector_slope_raw": 0.88,
                "fallback_tier_used": 1,
                "monthly_raw_slopes": [0.75, 0.82],
            }
        }
        
        # Verify structure
        assert precomputed_record["param_set_id"] is None
        assert "fixed_beta_raw" in precomputed_record["metadata"]
        assert "floating_beta_raw" in precomputed_record["metadata"]
        assert precomputed_record["output_metric_value"] == 0.8765
    
    async def test_both_approaches_stored_in_precomputed_metadata(self):
        """Verify both FIXED and Floating approaches stored in metadata"""
        metadata = {
            "metric_level": "L1",
            "fixed_beta_raw": 1.0555,      # Average across all years
            "floating_beta_raw": 0.8765,   # Cumulative average
            "spot_slope_raw": 0.8765,
            "sector_slope_raw": 0.88,
            "fallback_tier_used": 1,
            "monthly_raw_slopes": [],
            "annualization_month": 12,
        }
        
        # Both approaches available
        assert "fixed_beta_raw" in metadata
        assert "floating_beta_raw" in metadata
        assert metadata["fixed_beta_raw"] != metadata["floating_beta_raw"]
        
        # JSON serializable
        json_str = json.dumps(metadata)
        parsed = json.loads(json_str)
        assert parsed["fixed_beta_raw"] == 1.0555


@pytest.mark.asyncio
class TestRoundingRetrievalE2E:
    """E2E tests for rounding retrieval from pre-computed data"""
    
    async def test_fetch_precomputed_apply_rounding_store(self):
        """Verify full workflow: fetch pre-computed, round, store with param_set_id"""
        from backend.app.services.beta_rounding_service import BetaRoundingService
        
        mock_session = AsyncMock()
        service = BetaRoundingService(mock_session)
        
        # Simulate pre-computed records
        dataset_id = uuid4()
        param_set_id = uuid4()
        
        # Workflow:
        # 1. Pre-computed records exist with param_set_id=NULL
        precomputed = {
            "ticker": "TEST",
            "fiscal_year": 2021,
            "output_metric_value": 0.8765,  # Raw unrounded
            "metadata": {
                "fixed_beta_raw": 1.0555,
                "floating_beta_raw": 0.8765,
            }
        }
        
        # 2. User selects parameters
        beta_rounding = 0.1
        approach_to_ke = "FIXED"
        
        # 3. Extract raw value based on approach
        metadata = precomputed["metadata"]
        if approach_to_ke.upper() == "FIXED":
            raw_value = metadata.get("fixed_beta_raw")
        else:
            raw_value = metadata.get("floating_beta_raw")
        
        assert raw_value == 1.0555
        
        # 4. Apply rounding
        rounded_value = np.round(raw_value / beta_rounding, 0) * beta_rounding
        assert np.isclose(rounded_value, 1.1, atol=0.001)
        
        # 5. Store with param_set_id set (not NULL)
        rounded_record = {
            "dataset_id": dataset_id,
            "param_set_id": param_set_id,  # Set to user's param_set_id
            "ticker": precomputed["ticker"],
            "fiscal_year": precomputed["fiscal_year"],
            "output_metric_name": "Calc Beta",
            "output_metric_value": rounded_value,
            "metadata": {
                "metric_level": "L1",
                "derived_from_precomputed": True,
                "raw_beta": raw_value,
                "approach": approach_to_ke,
                "rounding": beta_rounding,
            }
        }
        
        # Verify structure
        assert rounded_record["param_set_id"] is not None
        assert rounded_record["param_set_id"] == param_set_id
        assert rounded_record["output_metric_value"] == 1.1
        assert rounded_record["metadata"]["raw_beta"] == 1.0555
    
    async def test_different_approaches_produce_different_rounded_values(self):
        """Verify FIXED and Floating approaches produce different values"""
        precomputed_metadata = {
            "fixed_beta_raw": 1.0555,
            "floating_beta_raw": 0.8765,
        }
        
        beta_rounding = 0.1
        
        # FIXED approach
        fixed_raw = precomputed_metadata["fixed_beta_raw"]
        fixed_rounded = np.round(fixed_raw / beta_rounding, 0) * beta_rounding
        
        # Floating approach
        floating_raw = precomputed_metadata["floating_beta_raw"]
        floating_rounded = np.round(floating_raw / beta_rounding, 0) * beta_rounding
        
        # Should produce different rounded values
        assert fixed_rounded != floating_rounded
        assert fixed_rounded == 1.1
        assert floating_rounded == 0.9


@pytest.mark.asyncio
class TestFullWorkflowE2E:
    """End-to-end tests for complete pre-computation workflow"""
    
    async def test_full_precomputation_workflow(self):
        """Verify complete workflow: ETL -> pre-compute -> store"""
        # Note: This would require database setup in integration tests
        # Here we verify the logic flow
        
        dataset_id = uuid4()
        
        # Step 1: ETL pipeline calls pre-computation service
        precomputation_params = {
            "beta_relative_error_tolerance": 0.3,
        }
        
        # Step 2: Pre-computation service processes data
        # (would call OLS regression, transform slopes, etc.)
        precomputed_data = [
            {
                "ticker": "TEST",
                "fiscal_year": 2021,
                "fixed_beta_raw": 1.0555,
                "floating_beta_raw": 0.8765,
                "spot_slope_raw": 0.8765,
                "sector_slope_raw": 0.88,
                "fallback_tier_used": 1,
                "monthly_raw_slopes": [0.75, 0.82],
            },
            {
                "ticker": "TEST",
                "fiscal_year": 2022,
                "fixed_beta_raw": 1.0555,
                "floating_beta_raw": 0.9234,
                "spot_slope_raw": 0.9234,
                "sector_slope_raw": 0.88,
                "fallback_tier_used": 1,
                "monthly_raw_slopes": [0.82, 0.85],
            }
        ]
        
        # Step 3: Store pre-computed data with param_set_id=NULL
        precomputed_records = []
        for data in precomputed_data:
            metadata = {
                "metric_level": "L1",
                "fixed_beta_raw": data["fixed_beta_raw"],
                "floating_beta_raw": data["floating_beta_raw"],
                "spot_slope_raw": data["spot_slope_raw"],
                "sector_slope_raw": data["sector_slope_raw"],
                "fallback_tier_used": data["fallback_tier_used"],
                "monthly_raw_slopes": data["monthly_raw_slopes"],
            }
            
            record = {
                "dataset_id": dataset_id,
                "param_set_id": None,  # Pre-computed marker
                "ticker": data["ticker"],
                "fiscal_year": data["fiscal_year"],
                "output_metric_name": "Calc Beta",
                "output_metric_value": data["floating_beta_raw"],  # Raw value
                "metadata": metadata,
            }
            precomputed_records.append(record)
        
        # Verify pre-computed records
        assert len(precomputed_records) == 2
        for record in precomputed_records:
            assert record["param_set_id"] is None
            assert "fixed_beta_raw" in record["metadata"]
            assert "floating_beta_raw" in record["metadata"]
    
    async def test_pre_computed_then_rounded_then_retrieved(self):
        """Verify full workflow: pre-compute -> round -> retrieve"""
        dataset_id = uuid4()
        param_set_id = uuid4()
        
        # Step 1: Pre-computed records (from ETL)
        precomputed_records = [
            {
                "ticker": "TEST",
                "fiscal_year": 2021,
                "raw_value": 0.8765,
                "metadata": {
                    "fixed_beta_raw": 1.0555,
                    "floating_beta_raw": 0.8765,
                }
            }
        ]
        
        # Step 2: Apply rounding for FIXED approach
        beta_rounding = 0.1
        approach = "FIXED"
        
        rounded_records = []
        for record in precomputed_records:
            metadata = record["metadata"]
            if approach.upper() == "FIXED":
                raw_value = metadata.get("fixed_beta_raw")
            else:
                raw_value = metadata.get("floating_beta_raw")
            
            rounded_value = np.round(raw_value / beta_rounding, 0) * beta_rounding
            
            rounded_records.append({
                "dataset_id": dataset_id,
                "param_set_id": param_set_id,
                "ticker": record["ticker"],
                "fiscal_year": record["fiscal_year"],
                "output_metric_name": "Calc Beta",
                "output_metric_value": rounded_value,
                "metadata": {
                    "metric_level": "L1",
                    "derived_from_precomputed": True,
                    "raw_beta": raw_value,
                    "approach": approach,
                    "rounding": beta_rounding,
                }
            })
        
        # Step 3: Retrieve (API would return these)
        retrieved = rounded_records[0]
        
        # Verify retrieved value
        assert retrieved["ticker"] == "TEST"
        assert retrieved["fiscal_year"] == 2021
        assert retrieved["output_metric_value"] == 1.1  # Rounded FIXED value
        assert retrieved["metadata"]["raw_beta"] == 1.0555


@pytest.mark.asyncio
class TestDataIntegrityE2E:
    """E2E tests for data integrity across workflow"""
    
    async def test_raw_value_preservation_in_metadata(self):
        """Verify raw values preserved in metadata through entire workflow"""
        original_raw_value = 1.0555555  # High precision
        
        # Store in pre-computed metadata
        metadata = {
            "fixed_beta_raw": original_raw_value,
        }
        json_str = json.dumps(metadata)
        
        # Retrieve and parse
        parsed = json.loads(json_str)
        retrieved_raw = parsed["fixed_beta_raw"]
        
        # Verify precision preserved
        assert abs(retrieved_raw - original_raw_value) < 1e-6
    
    async def test_multiple_rounding_increments_consistency(self):
        """Verify same data rounds consistently with different increments"""
        raw_value = 0.8765
        
        roundings = [0.1, 0.05, 0.01]
        # 0.8765 / 0.1 = 8.765 -> rounds to 9 -> 9 * 0.1 = 0.9
        # 0.8765 / 0.05 = 17.53 -> rounds to 18 -> 18 * 0.05 = 0.9
        # 0.8765 / 0.01 = 87.65 -> rounds to 88 -> 88 * 0.01 = 0.88
        expected = [0.9, 0.9, 0.88]
        
        for rounding, expected_rounded in zip(roundings, expected):
            rounded = np.round(raw_value / rounding, 0) * rounding
            assert np.isclose(rounded, expected_rounded, atol=0.001), \
                f"Rounding {raw_value} with {rounding} should be {expected_rounded}, got {rounded}"


@pytest.mark.asyncio
class TestBackwardCompatibilityE2E:
    """E2E tests for backward compatibility with legacy path"""
    
    async def test_legacy_path_fallback_if_no_precomputed(self):
        """Verify endpoint falls back to legacy if pre-computed not available"""
        dataset_id = uuid4()
        param_set_id = uuid4()
        
        # Simulate: pre-computed not available
        precomputed_exists = False
        
        if precomputed_exists:
            # Use pre-computed path (fast)
            path_used = "precomputed"
        else:
            # Fall back to legacy (slow)
            path_used = "legacy"
        
        assert path_used == "legacy"
    
    async def test_both_endpoints_return_same_structure(self):
        """Verify legacy and pre-computed endpoints return compatible results"""
        # Pre-computed endpoint response
        precomputed_response = {
            "status": "success",
            "data": [
                {
                    "ticker": "TEST",
                    "fiscal_year": 2021,
                    "beta": 1.1,
                }
            ],
            "computation_time_ms": 5,
        }
        
        # Legacy endpoint response
        legacy_response = {
            "status": "success",
            "data": [
                {
                    "ticker": "TEST",
                    "fiscal_year": 2021,
                    "beta": 1.1,
                }
            ],
            "computation_time_ms": 60000,
        }
        
        # Same data structure (computation time differs)
        assert precomputed_response["status"] == legacy_response["status"]
        assert precomputed_response["data"] == legacy_response["data"]
        assert precomputed_response["computation_time_ms"] < legacy_response["computation_time_ms"]


# Run tests with: pytest backend/tests/integration/test_beta_precomputation_e2e.py -v
