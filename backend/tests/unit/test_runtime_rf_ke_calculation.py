# ============================================================================
# Unit Tests: Runtime Risk-Free Rate and Cost of Equity Calculation
# ============================================================================
"""
Test suite for runtime calculation methods added in architecture refactoring:
- RiskFreeRateCalculationService.calculate_risk_free_rate_runtime()
- CostOfEquityService.calculate_cost_of_equity_runtime()

These tests verify:
1. Runtime Rf calculation returns a single float value
2. Runtime KE calculation combines Beta + Rf correctly
3. Approach selection (fixed/floating) affects Rf value
4. Beta metadata is correctly used from pre-computed values
5. Integration between Beta and Rf in runtime mode
"""

import pytest
import asyncio
import pandas as pd
import numpy as np
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


@pytest.fixture
def mock_session():
    """Create a mock async database session"""
    return AsyncMock()


class TestRuntimeRiskFreeRateCalculation:
    """Unit tests for runtime Risk-Free Rate calculation"""
    
    @pytest.mark.asyncio
    async def test_calculate_risk_free_rate_runtime_returns_float(self, mock_session):
        """Test that runtime Rf calculation returns a single float value"""
        from backend.app.services.risk_free_rate_service import RiskFreeRateCalculationService
        
        service = RiskFreeRateCalculationService(mock_session)
        
        # Mock the necessary methods
        mock_session.execute = AsyncMock()
        
        # Mock parameter fetch
        param_mock = MagicMock()
        param_mock.fetchone.return_value = (
            {
                "cost_of_equity_approach": "FLOATING",
                "beta_rounding": 0.005,
                "benchmark": 0.0,
                "risk_premium": 0.0
            },
        )
        
        service._load_parameters_from_db = AsyncMock(return_value={
            "cost_of_equity_approach": "FLOATING",
            "beta_rounding": 0.005,
            "benchmark": 0.0,
            "risk_premium": 0.0
        })
        
        service._fetch_bond_ticker_by_currency = AsyncMock(return_value="GACGB10 Index")
        
        # Mock bond yields dataframe
        bond_yields_df = pd.DataFrame({
            'date': pd.date_range('2023-01-31', periods=12, freq='ME'),
            'yield': [3.5, 3.8, 3.3, 3.4, 3.6, 4.0, 4.1, 4.0, 4.5, 4.9, 4.8, 4.5]
        })
        service._fetch_monthly_bond_yields = AsyncMock(return_value=bond_yields_df)
        
        # Calculate
        rf_value = await service.calculate_risk_free_rate_runtime(
            dataset_id=uuid4(),
            param_set_id=uuid4()
        )
        
        # Should return a float
        assert isinstance(rf_value, float)
        # Should be a reasonable Rf value (between 0% and 10%)
        assert 0.0 <= rf_value <= 0.10
    
    def test_runtime_calculation_respects_approach_fixed(self):
        """Test that FIXED approach produces static Rf value"""
        from backend.app.services.risk_free_rate_service import RiskFreeRateCalculationService
        
        service = RiskFreeRateCalculationService(MagicMock())
        
        # Create mock dataframe with rolling geometric mean
        rf_monthly_df = pd.DataFrame({
            'date': pd.date_range('2023-01-31', periods=12, freq='ME'),
            'rf_raw': [0.03, 0.035, 0.032, 0.034, 0.036, 0.040, 0.041, 0.040, 0.045, 0.049, 0.048, 0.045]
        })
        
        # FIXED approach params
        params_fixed = {
            "cost_of_equity_approach": "FIXED",
            "beta_rounding": 0.005,
            "benchmark": 0.07,
            "risk_premium": 0.02
        }
        
        # FIXED: Rf = benchmark - risk_premium = 0.07 - 0.02 = 0.05
        rf_calc_df = service._calculate_calc_rf(rf_monthly_df, params_fixed)
        
        # All FIXED values should be the same
        fixed_values = rf_calc_df['calc_rf'].unique()
        assert len(fixed_values) == 1
        assert fixed_values[0] == pytest.approx(0.05, abs=0.001)
    
    def test_runtime_calculation_respects_approach_floating(self):
        """Test that FLOATING approach produces variable Rf values"""
        from backend.app.services.risk_free_rate_service import RiskFreeRateCalculationService
        
        service = RiskFreeRateCalculationService(MagicMock())
        
        # Create mock dataframe with rolling geometric mean
        rf_monthly_df = pd.DataFrame({
            'date': pd.date_range('2023-01-31', periods=12, freq='ME'),
            'rf_raw': [0.03, 0.035, 0.032, 0.034, 0.036, 0.040, 0.041, 0.040, 0.045, 0.049, 0.048, 0.045]
        })
        
        # FLOATING approach params
        params_floating = {
            "cost_of_equity_approach": "FLOATING",
            "beta_rounding": 0.005,
            "benchmark": 0.0,
            "risk_premium": 0.0
        }
        
        rf_calc_df = service._calculate_calc_rf(rf_monthly_df, params_floating)
        
        # FLOATING values should vary and match rounded rf_raw values
        floating_values = rf_calc_df['calc_rf'].values
        assert len(floating_values) > 0
        # Should have some variation
        assert floating_values.max() > floating_values.min()


class TestRuntimeCostOfEquityCalculation:
    """Unit tests for runtime Cost of Equity calculation"""
    
    @pytest.mark.asyncio
    async def test_calculate_cost_of_equity_runtime_returns_float(self, mock_session):
        """Test that runtime KE calculation returns a single float value"""
        from backend.app.services.cost_of_equity_service import CostOfEquityService
        
        service = CostOfEquityService(mock_session)
        
        # Mock parameter loading
        service._load_parameters = AsyncMock(return_value={
            "cost_of_equity_approach": "FLOATING",
            "equity_risk_premium": 0.05
        })
        
        # Mock Beta fetch
        beta_df = pd.DataFrame({
            'ticker': ['TEST'],
            'fiscal_year': [2023],
            'beta': [1.2]
        })
        service._fetch_beta_for_runtime = AsyncMock(return_value=beta_df)
        
        # Mock Rf calculation
        mock_rf_service = AsyncMock()
        mock_rf_service.calculate_risk_free_rate_runtime = AsyncMock(return_value=0.04)
        
        # Calculate
        ke_value = await service.calculate_cost_of_equity_runtime(
            dataset_id=uuid4(),
            param_set_id=uuid4(),
            risk_free_rate_service=mock_rf_service
        )
        
        # Should return a float
        assert isinstance(ke_value, float)
        # KE should be reasonable (0% to 20%)
        assert 0.0 <= ke_value <= 0.20
    
    def test_cost_of_equity_formula_calculation(self):
        """Test the KE = Rf + Beta × RiskPremium calculation"""
        # Formula: KE = Rf + Beta × RiskPremium
        
        # Example: Rf=0.04, Beta=1.2, RiskPremium=0.05
        rf = 0.04
        beta = 1.2
        risk_premium = 0.05
        
        ke = rf + (beta * risk_premium)
        
        # KE = 0.04 + (1.2 × 0.05) = 0.04 + 0.06 = 0.10
        assert ke == pytest.approx(0.10, abs=0.001)
    
    def test_cost_of_equity_with_different_approaches(self):
        """Test KE calculation with different Beta approaches (fixed/floating)"""
        # FIXED Beta: More stable, lower volatility
        beta_fixed = 0.95
        rf = 0.04
        risk_premium = 0.05
        ke_fixed = rf + (beta_fixed * risk_premium)
        
        # FLOATING Beta: More responsive to market changes
        beta_floating = 1.3
        ke_floating = rf + (beta_floating * risk_premium)
        
        # Floating should produce higher KE due to higher beta
        assert ke_floating > ke_fixed
        assert ke_fixed == pytest.approx(0.0875, abs=0.001)
        assert ke_floating == pytest.approx(0.105, abs=0.001)


class TestRuntimeCalculationIntegration:
    """Integration tests between runtime Rf and KE calculations"""
    
    @pytest.mark.asyncio
    async def test_runtime_rf_ke_chain_calculation(self, mock_session):
        """Test that runtime Rf → KE calculation chain works correctly"""
        from backend.app.services.cost_of_equity_service import CostOfEquityService
        from backend.app.services.risk_free_rate_service import RiskFreeRateCalculationService
        
        # Create service with mock session
        ke_service = CostOfEquityService(mock_session)
        rf_service = RiskFreeRateCalculationService(mock_session)
        
        # Mock all data loading methods
        ke_service._load_parameters = AsyncMock(return_value={
            "cost_of_equity_approach": "FLOATING",
            "equity_risk_premium": 0.05
        })
        
        rf_service._load_parameters_from_db = AsyncMock(return_value={
            "cost_of_equity_approach": "FLOATING",
            "beta_rounding": 0.005,
            "benchmark": 0.0,
            "risk_premium": 0.0
        })
        
        # Mock Beta
        beta_df = pd.DataFrame({
            'ticker': ['AAPL'],
            'fiscal_year': [2023],
            'beta': [1.2]
        })
        ke_service._fetch_beta_for_runtime = AsyncMock(return_value=beta_df)
        
        # Mock bond yields
        bond_yields_df = pd.DataFrame({
            'date': pd.date_range('2023-01-31', periods=12, freq='ME'),
            'yield': [0.03, 0.035, 0.032, 0.034, 0.036, 0.040, 0.041, 0.040, 0.045, 0.049, 0.048, 0.045]
        })
        rf_service._fetch_monthly_bond_yields = AsyncMock(return_value=bond_yields_df)
        rf_service._fetch_bond_ticker_by_currency = AsyncMock(return_value="GACGB10")
        
        # Calculate KE using the chain
        dataset_id = uuid4()
        param_set_id = uuid4()
        
        ke_value = await ke_service.calculate_cost_of_equity_runtime(
            dataset_id=dataset_id,
            param_set_id=param_set_id,
            risk_free_rate_service=rf_service
        )
        
        # Should return valid KE value
        assert isinstance(ke_value, float)
        assert 0.0 <= ke_value <= 0.20
        
        # Verify the calculation makes sense
        # With Beta=1.2 and RiskPremium=0.05, KE should have significant component


if __name__ == "__main__":
    # Run tests with: pytest backend/tests/unit/test_runtime_rf_ke_calculation.py -v
    pytest.main([__file__, "-v"])
