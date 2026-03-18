# ============================================================================
# Runtime Tests for FV ECF Service (Phase C - Tasks 4-8)
# ============================================================================
"""
Comprehensive tests for FVECFService runtime methods:
- Task 4: Parameter loading from param_set_id
- Task 5: Lagged KE fetching for runtime
- Task 6: Runtime FV_ECF calculation end-to-end
- Task 8: Parameter variation scenarios
"""

import pytest
import pandas as pd
import numpy as np
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
import sys
import json

sys.path.insert(0, '/home/ubuntu/cissa')
from backend.app.services.fv_ecf_service import FVECFService


class TestParameterLoading:
    """Task 4: Test parameter loading from param_set_id"""
    
    @pytest.mark.asyncio
    async def test_load_parameters_from_param_set_with_all_overrides(self):
        """Test loading parameters when all overrides are present"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = FVECFService(mock_session)
        param_set_id = uuid4()
        
        # Mock the database response with param_overrides
        param_overrides = {
            'include_franking_credits_tsr': True,
            'tax_rate_franking_credits': 30.0,
            'value_of_franking_credits': 75.0
        }
        
        mock_result = MagicMock()
        mock_result.fetchone.return_value = [param_overrides]
        mock_session.execute.return_value = mock_result
        
        # Execute
        params = await service._load_parameters_from_param_set(param_set_id)
        
        # Verify
        assert params['incl_franking'] == 'Yes'
        assert np.isclose(params['frank_tax_rate'], 0.30, atol=0.001)
        assert np.isclose(params['value_franking_cr'], 0.75, atol=0.001)
    
    @pytest.mark.asyncio
    async def test_load_parameters_with_false_franking_flag(self):
        """Test that False franking flag maps to 'No'"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = FVECFService(mock_session)
        param_set_id = uuid4()
        
        param_overrides = {
            'include_franking_credits_tsr': False,
            'tax_rate_franking_credits': 30.0,
            'value_of_franking_credits': 0.75
        }
        
        mock_result = MagicMock()
        mock_result.fetchone.return_value = [param_overrides]
        mock_session.execute.return_value = mock_result
        
        params = await service._load_parameters_from_param_set(param_set_id)
        
        assert params['incl_franking'] == 'No'
    
    @pytest.mark.asyncio
    async def test_load_parameters_with_partial_overrides(self):
        """Test loading parameters when only some overrides are present"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = FVECFService(mock_session)
        param_set_id = uuid4()
        
        # Only franking flag provided, others use defaults
        param_overrides = {
            'include_franking_credits_tsr': True,
        }
        
        mock_result = MagicMock()
        mock_result.fetchone.return_value = [param_overrides]
        mock_session.execute.return_value = mock_result
        
        params = await service._load_parameters_from_param_set(param_set_id)
        
        assert params['incl_franking'] == 'Yes'
        assert params['frank_tax_rate'] == 0.30  # Default
        assert params['value_franking_cr'] == 0.75  # Default
    
    @pytest.mark.asyncio
    async def test_load_parameters_with_no_overrides(self):
        """Test loading parameters when param_set has no overrides"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = FVECFService(mock_session)
        param_set_id = uuid4()
        
        # No param_set found or empty overrides
        mock_result = MagicMock()
        mock_result.fetchone.return_value = [None]
        mock_session.execute.return_value = mock_result
        
        params = await service._load_parameters_from_param_set(param_set_id)
        
        # Should return all defaults
        assert params['incl_franking'] == 'No'
        assert params['frank_tax_rate'] == 0.30
        assert params['value_franking_cr'] == 0.75
    
    @pytest.mark.asyncio
    async def test_load_parameters_with_percentage_values(self):
        """Test that percentage values (>1) are converted to decimals"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = FVECFService(mock_session)
        param_set_id = uuid4()
        
        # Provide percentages that should be converted
        param_overrides = {
            'tax_rate_franking_credits': 45.0,  # Will be divided by 100
            'value_of_franking_credits': 100.0  # Will be divided by 100
        }
        
        mock_result = MagicMock()
        mock_result.fetchone.return_value = [param_overrides]
        mock_session.execute.return_value = mock_result
        
        params = await service._load_parameters_from_param_set(param_set_id)
        
        assert np.isclose(params['frank_tax_rate'], 0.45, atol=0.001)
        assert np.isclose(params['value_franking_cr'], 1.0, atol=0.001)
    
    @pytest.mark.asyncio
    async def test_load_parameters_with_decimal_values(self):
        """Test that decimal values (<1) are used as-is"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = FVECFService(mock_session)
        param_set_id = uuid4()
        
        # Provide decimal values
        param_overrides = {
            'tax_rate_franking_credits': 0.35,
            'value_of_franking_credits': 0.80
        }
        
        mock_result = MagicMock()
        mock_result.fetchone.return_value = [param_overrides]
        mock_session.execute.return_value = mock_result
        
        params = await service._load_parameters_from_param_set(param_set_id)
        
        assert np.isclose(params['frank_tax_rate'], 0.35, atol=0.001)
        assert np.isclose(params['value_franking_cr'], 0.80, atol=0.001)
    
    @pytest.mark.asyncio
    async def test_load_parameters_database_error_returns_defaults(self):
        """Test that database errors gracefully fall back to defaults"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = FVECFService(mock_session)
        param_set_id = uuid4()
        
        # Simulate database error
        mock_session.execute.side_effect = Exception("Database connection error")
        
        params = await service._load_parameters_from_param_set(param_set_id)
        
        # Should return all defaults
        assert params['incl_franking'] == 'No'
        assert params['frank_tax_rate'] == 0.30
        assert params['value_franking_cr'] == 0.75


class TestLaggedKEFetch:
    """Task 5: Test lagged KE fetching for runtime"""
    
    @pytest.mark.asyncio
    async def test_fetch_lagged_ke_creates_proper_lags(self):
        """Test that lagged KE is properly created within ticker groups"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = FVECFService(mock_session)
        dataset_id = uuid4()
        param_set_id = uuid4()
        
        # Mock KE data for single ticker across multiple years
        ke_data = [
            ('AAPL', 2020, 0.08),
            ('AAPL', 2021, 0.09),
            ('AAPL', 2022, 0.10),
            ('AAPL', 2023, 0.11),
        ]
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = ke_data
        mock_session.execute.return_value = mock_result
        
        # Execute
        df = await service._fetch_lagged_ke_for_runtime(dataset_id, param_set_id)
        
        # Verify
        assert len(df) == 4
        assert list(df.columns) == ['ticker', 'fiscal_year', 'ke_open']
        
        # Check lagging: first row should have NaN (no prior year)
        assert pd.isna(df.iloc[0]['ke_open'])
        
        # Subsequent rows should have lagged values
        assert np.isclose(df.iloc[1]['ke_open'], 0.08, atol=0.001)
        assert np.isclose(df.iloc[2]['ke_open'], 0.09, atol=0.001)
        assert np.isclose(df.iloc[3]['ke_open'], 0.10, atol=0.001)
    
    @pytest.mark.asyncio
    async def test_fetch_lagged_ke_handles_multiple_tickers(self):
        """Test that lagging respects ticker boundaries"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = FVECFService(mock_session)
        dataset_id = uuid4()
        param_set_id = uuid4()
        
        # Mock KE data for two tickers
        ke_data = [
            ('AAPL', 2020, 0.08),
            ('AAPL', 2021, 0.09),
            ('MSFT', 2020, 0.10),
            ('MSFT', 2021, 0.11),
        ]
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = ke_data
        mock_session.execute.return_value = mock_result
        
        # Execute
        df = await service._fetch_lagged_ke_for_runtime(dataset_id, param_set_id)
        
        # Verify
        assert len(df) == 4
        
        # AAPL 2020 should have NaN (first year)
        aapl_2020 = df[(df['ticker'] == 'AAPL') & (df['fiscal_year'] == 2020)]
        assert pd.isna(aapl_2020['ke_open'].iloc[0])
        
        # AAPL 2021 should have lagged value from AAPL 2020
        aapl_2021 = df[(df['ticker'] == 'AAPL') & (df['fiscal_year'] == 2021)]
        assert np.isclose(aapl_2021['ke_open'].iloc[0], 0.08, atol=0.001)
        
        # MSFT 2020 should have NaN (first year for this ticker)
        msft_2020 = df[(df['ticker'] == 'MSFT') & (df['fiscal_year'] == 2020)]
        assert pd.isna(msft_2020['ke_open'].iloc[0])
        
        # MSFT 2021 should have lagged value from MSFT 2020
        msft_2021 = df[(df['ticker'] == 'MSFT') & (df['fiscal_year'] == 2021)]
        assert np.isclose(msft_2021['ke_open'].iloc[0], 0.10, atol=0.001)
    
    @pytest.mark.asyncio
    async def test_fetch_lagged_ke_with_no_data(self):
        """Test handling of empty KE data"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = FVECFService(mock_session)
        dataset_id = uuid4()
        param_set_id = uuid4()
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result
        
        df = await service._fetch_lagged_ke_for_runtime(dataset_id, param_set_id)
        
        # Should return empty DataFrame
        assert df.empty
    
    @pytest.mark.asyncio
    async def test_fetch_lagged_ke_converts_decimal_values(self):
        """Test that Decimal KE values are converted to float"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = FVECFService(mock_session)
        dataset_id = uuid4()
        param_set_id = uuid4()
        
        from decimal import Decimal
        
        # Mock KE data with Decimal values
        ke_data = [
            ('AAPL', 2020, Decimal('0.08')),
            ('AAPL', 2021, Decimal('0.09')),
        ]
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = ke_data
        mock_session.execute.return_value = mock_result
        
        df = await service._fetch_lagged_ke_for_runtime(dataset_id, param_set_id)
        
        # Should convert to float
        assert df['ke_open'].dtype in [np.float64, np.float32]
        assert np.isclose(df.iloc[1]['ke_open'], 0.08, atol=0.001)


class TestRuntimeIntegration:
    """Task 6: Test runtime FV_ECF calculation end-to-end"""
    
    @pytest.mark.asyncio
    async def test_calculate_fv_ecf_for_runtime_success_flow(self):
        """Test complete runtime FV_ECF calculation"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = FVECFService(mock_session)
        dataset_id = uuid4()
        param_set_id = uuid4()
        
        # Mock parameter loading
        with patch.object(
            service, '_load_parameters_from_param_set',
            return_value={'incl_franking': 'No', 'frank_tax_rate': 0.30, 'value_franking_cr': 0.75}
        ):
            # Mock fundamentals data
            with patch.object(
                service, '_fetch_fundamentals_data',
                return_value=pd.DataFrame({
                    'ticker': ['AAPL'] * 5,
                    'fiscal_year': [2019, 2020, 2021, 2022, 2023],
                    'dividend': [50, 55, 60, 65, 70],
                    'franking': [0.5] * 5,
                    'non_div_ecf': [100, 110, 120, 130, 140]
                })
            ):
                # Mock lagged KE
                with patch.object(
                    service, '_fetch_lagged_ke_for_runtime',
                    return_value=pd.DataFrame({
                        'ticker': ['AAPL'] * 5,
                        'fiscal_year': [2019, 2020, 2021, 2022, 2023],
                        'ke_open': [0.08, 0.09, 0.10, 0.11, 0.12]
                    })
                ):
                    # Mock insert
                    with patch.object(
                        service, '_insert_fv_ecf_batch',
                        return_value=20  # Total records inserted across 4 intervals
                    ):
                        # Execute
                        result = await service.calculate_fv_ecf_for_runtime(dataset_id, param_set_id)
                        
                        # Verify
                        assert result['status'] == 'success'
                        assert result['total_inserted'] == 20
                        assert 'intervals_summary' in result
                        assert set(result['intervals_summary'].keys()) == {'1Y', '3Y', '5Y', '10Y'}
                        assert result['duration_seconds'] > 0
    
    @pytest.mark.asyncio
    async def test_calculate_fv_ecf_for_runtime_with_no_fundamentals(self):
        """Test handling when no fundamentals data found"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = FVECFService(mock_session)
        dataset_id = uuid4()
        param_set_id = uuid4()
        
        with patch.object(
            service, '_load_parameters_from_param_set',
            return_value={'incl_franking': 'No', 'frank_tax_rate': 0.30, 'value_franking_cr': 0.75}
        ):
            with patch.object(
                service, '_fetch_fundamentals_data',
                return_value=pd.DataFrame()  # Empty
            ):
                result = await service.calculate_fv_ecf_for_runtime(dataset_id, param_set_id)
                
                assert result['status'] == 'success'
                assert result['total_inserted'] == 0
                assert 'No fundamentals data found' in result['message']
    
    @pytest.mark.asyncio
    async def test_calculate_fv_ecf_for_runtime_with_no_ke_data(self):
        """Test handling when no KE data found"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = FVECFService(mock_session)
        dataset_id = uuid4()
        param_set_id = uuid4()
        
        with patch.object(
            service, '_load_parameters_from_param_set',
            return_value={'incl_franking': 'No', 'frank_tax_rate': 0.30, 'value_franking_cr': 0.75}
        ):
            with patch.object(
                service, '_fetch_fundamentals_data',
                return_value=pd.DataFrame({
                    'ticker': ['AAPL'],
                    'fiscal_year': [2023],
                    'dividend': [70],
                    'franking': [0.5],
                    'non_div_ecf': [140]
                })
            ):
                with patch.object(
                    service, '_fetch_lagged_ke_for_runtime',
                    return_value=pd.DataFrame()  # Empty
                ):
                    result = await service.calculate_fv_ecf_for_runtime(dataset_id, param_set_id)
                    
                    assert result['status'] == 'success'
                    assert result['total_inserted'] == 0
                    assert 'No KE data found' in result['message']
    
    @pytest.mark.asyncio
    async def test_calculate_fv_ecf_for_runtime_error_handling(self):
        """Test error handling in runtime FV_ECF calculation"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = FVECFService(mock_session)
        dataset_id = uuid4()
        param_set_id = uuid4()
        
        # Simulate parameter loading error
        with patch.object(
            service, '_load_parameters_from_param_set',
            side_effect=Exception("Parameter loading failed")
        ):
            result = await service.calculate_fv_ecf_for_runtime(dataset_id, param_set_id)
            
            assert result['status'] == 'error'
            assert 'Parameter loading failed' in result['message']


class TestParameterVariation:
    """Task 8: Test FV_ECF calculations with different parameter combinations"""
    
    def test_fv_ecf_with_franking_yes_vs_no(self):
        """Test that franking inclusion affects ECF calculation"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        # Test data with franking
        test_df = pd.DataFrame({
            'ticker': ['TEST'] * 5,
            'fiscal_year': [2019, 2020, 2021, 2022, 2023],
            'dividend': [50, 55, 60, 65, 70],
            'franking': [1.0, 1.0, 1.0, 1.0, 1.0],  # All fully franked
            'non_div_ecf': [100, 110, 120, 130, 140],
            'ke_open': [0.08, 0.09, 0.10, 0.11, 0.12]
        })
        
        params_with_franking = {
            'incl_franking': 'Yes',
            'frank_tax_rate': 0.30,
            'value_franking_cr': 0.75
        }
        
        params_without_franking = {
            'incl_franking': 'No',
            'frank_tax_rate': 0.30,
            'value_franking_cr': 0.75
        }
        
        # Calculate with and without franking
        result_with = service._calculate_fv_ecf_for_interval(test_df, 1, params_with_franking)
        result_without = service._calculate_fv_ecf_for_interval(test_df, 1, params_without_franking)
        
        # Values should differ due to franking adjustment
        # With franking, ECF_base = -dividend + non_div_ecf - franking adjustment
        # Without franking, ECF_base = -dividend + non_div_ecf
        
        assert not np.allclose(
            result_with['FV_ECF_Y'].values,
            result_without['FV_ECF_Y'].values,
            atol=0.1
        )
    
    def test_fv_ecf_with_different_tax_rates(self):
        """Test that different tax rates produce different results"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        test_df = pd.DataFrame({
            'ticker': ['TEST'] * 5,
            'fiscal_year': [2019, 2020, 2021, 2022, 2023],
            'dividend': [50, 55, 60, 65, 70],
            'franking': [1.0, 1.0, 1.0, 1.0, 1.0],
            'non_div_ecf': [100, 110, 120, 130, 140],
            'ke_open': [0.08, 0.09, 0.10, 0.11, 0.12]
        })
        
        params_low_tax = {
            'incl_franking': 'Yes',
            'frank_tax_rate': 0.20,
            'value_franking_cr': 0.75
        }
        
        params_high_tax = {
            'incl_franking': 'Yes',
            'frank_tax_rate': 0.45,
            'value_franking_cr': 0.75
        }
        
        result_low = service._calculate_fv_ecf_for_interval(test_df, 1, params_low_tax)
        result_high = service._calculate_fv_ecf_for_interval(test_df, 1, params_high_tax)
        
        # Results should differ based on tax rate impact on franking adjustment
        assert not np.allclose(
            result_low['FV_ECF_Y'].values,
            result_high['FV_ECF_Y'].values,
            atol=0.1
        )
    
    def test_fv_ecf_with_different_franking_values(self):
        """Test that different franking credit values produce different results"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        test_df = pd.DataFrame({
            'ticker': ['TEST'] * 5,
            'fiscal_year': [2019, 2020, 2021, 2022, 2023],
            'dividend': [50, 55, 60, 65, 70],
            'franking': [1.0, 1.0, 1.0, 1.0, 1.0],
            'non_div_ecf': [100, 110, 120, 130, 140],
            'ke_open': [0.08, 0.09, 0.10, 0.11, 0.12]
        })
        
        params_low_value = {
            'incl_franking': 'Yes',
            'frank_tax_rate': 0.30,
            'value_franking_cr': 0.50
        }
        
        params_high_value = {
            'incl_franking': 'Yes',
            'frank_tax_rate': 0.30,
            'value_franking_cr': 1.00
        }
        
        result_low = service._calculate_fv_ecf_for_interval(test_df, 1, params_low_value)
        result_high = service._calculate_fv_ecf_for_interval(test_df, 1, params_high_value)
        
        # Results should differ based on franking credit value
        assert not np.allclose(
            result_low['FV_ECF_Y'].values,
            result_high['FV_ECF_Y'].values,
            atol=0.1
        )
    
    def test_fv_ecf_partial_franking_vs_full_franking(self):
        """Test handling of partial franking (0.5, 0.75) vs full (1.0)"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        # Test with different franking levels
        test_df_partial = pd.DataFrame({
            'ticker': ['TEST'] * 3,
            'fiscal_year': [2021, 2022, 2023],
            'dividend': [60, 65, 70],
            'franking': [0.50, 0.50, 0.50],  # 50% franked
            'non_div_ecf': [120, 130, 140],
            'ke_open': [0.10, 0.11, 0.12]
        })
        
        test_df_full = pd.DataFrame({
            'ticker': ['TEST'] * 3,
            'fiscal_year': [2021, 2022, 2023],
            'dividend': [60, 65, 70],
            'franking': [1.0, 1.0, 1.0],  # 100% franked
            'non_div_ecf': [120, 130, 140],
            'ke_open': [0.10, 0.11, 0.12]
        })
        
        params = {
            'incl_franking': 'Yes',
            'frank_tax_rate': 0.30,
            'value_franking_cr': 0.75
        }
        
        result_partial = service._calculate_fv_ecf_for_interval(test_df_partial, 1, params)
        result_full = service._calculate_fv_ecf_for_interval(test_df_full, 1, params)
        
        # Full franking adjustment should differ from partial
        assert not np.allclose(
            result_partial['FV_ECF_Y'].values,
            result_full['FV_ECF_Y'].values,
            atol=0.1
        )
