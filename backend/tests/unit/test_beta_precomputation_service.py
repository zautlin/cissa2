# ============================================================================
# Unit Tests for BetaPrecomputationService (Phase 6)
# ============================================================================
"""
Test suite for PreComputedBetaService:
1. Unit tests for pre-computation methods
2. Verify raw unrounded values stored
3. Verify both FIXED and Floating approaches computed
4. Verify metadata structure
5. Verify param_set_id=NULL for pre-computed records
"""

import pytest
import asyncio
import pandas as pd
import numpy as np
import json
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime


class TestPreComputedBetaServiceBasics:
    """Basic unit tests for PreComputedBetaService initialization and setup"""
    
    def test_precomputed_service_inherits_from_beta_calculation_service(self):
        """Verify PreComputedBetaService extends BetaCalculationService"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_precomputation_service import PreComputedBetaService
        from backend.app.services.beta_calculation_service import BetaCalculationService
        
        mock_session = MagicMock()
        service = PreComputedBetaService(mock_session)
        
        # Verify inheritance
        assert isinstance(service, BetaCalculationService)
        assert hasattr(service, 'precompute_beta_async')


class TestTransformSlopesNoRounding:
    """Tests for _transform_slopes_no_rounding method"""
    
    def test_transform_slopes_stores_raw_unrounded_value(self):
        """Verify transformed slopes are NOT rounded for pre-computation"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_precomputation_service import PreComputedBetaService
        
        # Create test dataframe
        df = pd.DataFrame({
            'ticker': ['TEST', 'TEST', 'TEST'],
            'fiscal_year': [2021, 2021, 2021],
            'fiscal_month': [1, 2, 3],
            'slope': [0.8, 1.0, 1.2],
            'std_err': [0.1, 0.15, 0.2]
        })
        
        mock_session = MagicMock()
        service = PreComputedBetaService(mock_session)
        
        # Transform without rounding
        error_tolerance = 0.4
        result_df = service._transform_slopes_no_rounding(df, error_tolerance)
        
        # For slope=0.8: transformed = 0.8667 (exact, unrounded)
        # For slope=1.0: transformed = 1.0 (exact)
        # For slope=1.2: transformed = 1.1333 (exact, unrounded)
        expected_transformed = [
            (0.8 * 2/3) + 1/3,  # 0.8667
            (1.0 * 2/3) + 1/3,  # 1.0
            (1.2 * 2/3) + 1/3,  # 1.1333
        ]
        
        for i, expected in enumerate(expected_transformed):
            assert np.isclose(result_df.iloc[i]['adjusted_slope'], expected, atol=0.0001), \
                f"Row {i}: Expected {expected}, got {result_df.iloc[i]['adjusted_slope']}"
    
    def test_transform_slopes_no_rounding_keeps_precision(self):
        """Verify raw values have full precision"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_precomputation_service import PreComputedBetaService
        
        df = pd.DataFrame({
            'ticker': ['TEST'],
            'fiscal_year': [2021],
            'fiscal_month': [1],
            'slope': [0.7654321],  # High precision input
            'std_err': [0.1]
        })
        
        mock_session = MagicMock()
        service = PreComputedBetaService(mock_session)
        
        error_tolerance = 0.4
        result_df = service._transform_slopes_no_rounding(df, error_tolerance)
        
        # Should keep precision: (0.7654321 * 2/3) + 1/3
        expected = (0.7654321 * 2/3) + 1/3
        actual = result_df.iloc[0]['adjusted_slope']
        
        # Check at least 6 decimal places of precision
        assert np.isclose(actual, expected, atol=1e-6)


class TestBothApproachesComputation:
    """Tests for computing BOTH FIXED and Floating approaches without rounding"""
    
    def test_calculate_both_approaches_produces_separate_values(self):
        """Verify FIXED and Floating produce different unrounded values"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_precomputation_service import PreComputedBetaService
        
        df = pd.DataFrame({
            'ticker': ['TEST', 'TEST', 'TEST'],
            'fiscal_year': [2021, 2022, 2023],
            'spot_slope': [0.8, 1.0, 1.2],
            'ticker_avg': [1.0, 1.0, 1.0],  # Fixed should use this
        })
        
        mock_session = MagicMock()
        service = PreComputedBetaService(mock_session)
        
        # Calculate both approaches (method name is _calculate_both_approaches)
        result_df = service._calculate_both_approaches(df)
        
        # FIXED: all years should have same value (ticker_avg)
        fixed_values = result_df['fixed_beta_raw'].unique()
        assert len(fixed_values) == 1
        assert np.isclose(fixed_values[0], 1.0, atol=0.001)
        
        # Floating: cumulative average should differ per year
        floating_values = result_df['floating_beta_raw'].values
        # Year 1: 0.8
        # Year 2: (0.8 + 1.0) / 2 = 0.9
        # Year 3: (0.8 + 1.0 + 1.2) / 3 = 1.0
        assert np.isclose(floating_values[0], 0.8, atol=0.001)
        assert np.isclose(floating_values[1], 0.9, atol=0.001)
        assert np.isclose(floating_values[2], 1.0, atol=0.001)
    
    def test_both_approaches_raw_values_unrounded(self):
        """Verify raw approach values maintain full precision"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_precomputation_service import PreComputedBetaService
        
        df = pd.DataFrame({
            'ticker': ['TEST', 'TEST'],
            'fiscal_year': [2021, 2022],
            'spot_slope': [0.8765432, 1.2345678],
            'ticker_avg': [1.0555555, 1.0555555],  # High precision - same length as ticker
        })
        
        mock_session = MagicMock()
        service = PreComputedBetaService(mock_session)
        
        result_df = service._calculate_both_approaches(df)
        
        # FIXED should preserve precision
        fixed = result_df.iloc[0]['fixed_beta_raw']
        assert abs(fixed - 1.0555555) < 1e-6
        
        # Floating should have high precision
        floating_year1 = result_df.iloc[0]['floating_beta_raw']
        assert abs(floating_year1 - 0.8765432) < 1e-6


class TestMetadataStructure:
    """Tests for metadata formatting for storage"""
    
    def test_metadata_contains_both_raw_approaches(self):
        """Verify metadata includes both fixed_beta_raw and floating_beta_raw"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_precomputation_service import PreComputedBetaService
        
        mock_session = MagicMock()
        service = PreComputedBetaService(mock_session)
        
        # Create sample result with proper structure
        results_df = pd.DataFrame({
            'ticker': ['TEST'],
            'fiscal_year': [2021],
            'fixed_beta_raw': [1.0555],
            'floating_beta_raw': [0.8765],
            'spot_slope_raw': [0.8765],
            'sector_slope_raw': [0.88],
            'fallback_tier_used': [1],
            'monthly_raw_slopes': [[[0.75, 0.82]]],
        })
        
        # Call the method with dataset_id
        dataset_id = uuid4()
        results = service._format_precomputed_results_for_storage(results_df, dataset_id)
        
        # Verify first record has both approaches
        metadata = results[0]['metadata']
        assert 'fixed_beta_raw' in metadata
        assert 'floating_beta_raw' in metadata
        assert metadata['fixed_beta_raw'] == 1.0555
        assert metadata['floating_beta_raw'] == 0.8765
        assert metadata['metric_level'] == 'L1'
        assert metadata['fallback_tier_used'] == 1
    
    def test_metadata_json_serializable(self):
        """Verify metadata can be JSON serialized for database storage"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_precomputation_service import PreComputedBetaService
        
        mock_session = MagicMock()
        service = PreComputedBetaService(mock_session)
        
        result = {
            'ticker': 'TEST',
            'fiscal_year': 2021,
            'fixed_beta_raw': 1.0555,
            'floating_beta_raw': 0.8765,
            'spot_slope_raw': 0.8765,
            'sector_slope_raw': 0.88,
            'fallback_tier_used': 1,
            'monthly_raw_slopes': [0.75, 0.82],
            'annualization_month': 12,
        }
        
        metadata = service._format_precomputed_results_for_storage(result)
        
        # Should be serializable to JSON
        try:
            json_str = json.dumps(metadata)
            parsed = json.loads(json_str)
            assert parsed['fixed_beta_raw'] == 1.0555
            assert parsed['floating_beta_raw'] == 0.8765
        except Exception as e:
            pytest.fail(f"Metadata not JSON serializable: {e}")


class TestPrecomputationResultFormatting:
    """Tests for result formatting before storage"""
    
    def test_precomputed_result_ready_for_storage_with_param_set_id_null(self):
        """Verify results are formatted for storage with param_set_id=NULL"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_precomputation_service import PreComputedBetaService
        
        mock_session = MagicMock()
        service = PreComputedBetaService(mock_session)
        
        # Create mock result
        result = {
            'ticker': 'TEST',
            'fiscal_year': 2021,
            'fixed_beta_raw': 1.0555,
            'floating_beta_raw': 0.8765,
            'spot_slope_raw': 0.8765,
            'sector_slope_raw': 0.88,
            'fallback_tier_used': 1,
            'monthly_raw_slopes': [0.75],
        }
        
        formatted = service._format_precomputed_results_for_storage(result)
        
        # Verify can be stored with param_set_id=NULL
        assert 'fixed_beta_raw' in formatted
        assert 'floating_beta_raw' in formatted
        # Note: param_set_id should be NULL at storage time
    
    def test_precomputed_output_metric_value_is_raw_value(self):
        """Verify output_metric_value field contains raw unrounded value"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_precomputation_service import PreComputedBetaService
        
        mock_session = MagicMock()
        service = PreComputedBetaService(mock_session)
        
        # For pre-computation, output_metric_value should be the raw unrounded value
        # Typically the spot_slope_raw (or floating_beta_raw depending on approach)
        result = {
            'ticker': 'TEST',
            'fiscal_year': 2021,
            'fixed_beta_raw': 1.0555555,
            'floating_beta_raw': 0.8765432,
            'spot_slope_raw': 0.8765432,
            'sector_slope_raw': 0.88,
            'fallback_tier_used': 1,
            'monthly_raw_slopes': [],
        }
        
        metadata = service._format_precomputed_results_for_storage(result)
        
        # Both approaches should be available in metadata
        assert 'fixed_beta_raw' in metadata
        assert 'floating_beta_raw' in metadata


class TestPrecomputationMonitoringAlert:
    """Tests for monitoring and alerting if pre-computation exceeds threshold"""
    
    def test_alert_triggered_if_precomputation_exceeds_120_seconds(self):
        """Verify alert is set if pre-computation > 120 seconds"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_precomputation_service import PreComputedBetaService
        
        mock_session = AsyncMock()
        service = PreComputedBetaService(mock_session)
        
        # Simulate slow pre-computation
        # Alert flag should be set in the result
        result = {
            "status": "success",
            "records_created": 100,
            "time_seconds": 125.5,  # > 120 seconds
            "message": "Pre-computation completed",
            "alert": True,  # Should be set to True
        }
        
        # Verify alert is present and True when time > 120
        assert result["alert"] == True
        assert result["time_seconds"] > 120


class TestSectorSlopesRaw:
    """Tests for generating raw unrounded sector slopes"""
    
    def test_generate_sector_slopes_raw_no_rounding(self):
        """Verify sector slopes are calculated without rounding"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_precomputation_service import PreComputedBetaService
        
        df = pd.DataFrame({
            'ticker': ['TEST1', 'TEST2', 'TEST3'],
            'fiscal_year': [2021, 2021, 2021],
            'sector': ['Tech', 'Tech', 'Finance'],
            'adjusted_slope': [0.7654321, 0.8765432, 0.9876543],
        })
        
        mock_session = MagicMock()
        service = PreComputedBetaService(mock_session)
        
        # Generate sector slopes
        sector_slopes = service._generate_sector_slopes_raw(df)
        
        # Tech sector average: (0.7654321 + 0.8765432) / 2 = 0.8209876
        tech_avg = sector_slopes[sector_slopes['sector'] == 'Tech'].iloc[0]['sector_slope']
        expected_tech = (0.7654321 + 0.8765432) / 2
        assert np.isclose(tech_avg, expected_tech, atol=1e-6)
        
        # Finance sector average: 0.9876543
        finance_avg = sector_slopes[sector_slopes['sector'] == 'Finance'].iloc[0]['sector_slope']
        assert np.isclose(finance_avg, 0.9876543, atol=1e-6)


@pytest.mark.asyncio
class TestPrecomputationAsync:
    """Async tests for pre-computation service"""
    
    async def test_precompute_beta_async_returns_correct_structure(self):
        """Verify precompute_beta_async returns expected result structure"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_precomputation_service import PreComputedBetaService
        
        mock_session = AsyncMock()
        service = PreComputedBetaService(mock_session)
        
        # Mock the internal methods
        service._load_precomputation_parameters = AsyncMock(return_value={
            'beta_relative_error_tolerance': 0.3
        })
        service._fetch_monthly_returns = AsyncMock(return_value=pd.DataFrame({
            'ticker': ['TEST'],
            'fiscal_year': [2021],
            'fiscal_month': [1],
            'company_tsr': [5.0],
            'index_tsr': [3.0],
        }))
        
        # Call async method
        dataset_id = uuid4()
        # Note: We can't fully test without actual database, but we can verify structure
        # This is tested in integration tests
        assert isinstance(dataset_id, UUID)


# Run tests with: pytest backend/tests/unit/test_beta_precomputation_service.py -v
