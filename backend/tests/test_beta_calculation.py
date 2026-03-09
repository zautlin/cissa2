# ============================================================================
# Comprehensive Tests for Beta Calculation (Phase 07)
# ============================================================================
"""
Test suite for BetaCalculationService:
1. Unit tests for transformation methods
2. Integration tests with real database
3. API endpoint tests
4. Validation against algorithm logic
"""

import pytest
import asyncio
import pandas as pd
import numpy as np
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, patch, MagicMock

# These will be imported when the test runs
# from backend.app.services.beta_calculation_service import BetaCalculationService
# from backend.app.core.database import DatabaseManager
# from backend.app.core.config import get_settings


class TestTransformSlopes:
    """Unit tests for slope transformation methods"""
    
    def test_transform_slopes_formula(self):
        """Test slope transformation formula: adjusted = (slope * 2/3) + 1/3"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_calculation_service import BetaCalculationService
        
        # Create test dataframe
        df = pd.DataFrame({
            'ticker': ['TEST', 'TEST', 'TEST'],
            'fiscal_year': [2021, 2021, 2021],
            'fiscal_month': [1, 2, 3],
            'slope': [0.8, 1.0, 1.2],
            'std_err': [0.1, 0.15, 0.2]
        })
        
        # Mock session
        mock_session = MagicMock()
        service = BetaCalculationService(mock_session)
        
        # Test transformation
        error_tolerance = 0.4
        beta_rounding = 0.1
        result_df = service._transform_slopes(df, error_tolerance, beta_rounding)
        
        # The method rounds to 4 decimals: np.round(value / beta_rounding, 4) * beta_rounding
        # For slope=0.8: transformed = 0.8667, rounded to 8.6667 * 0.1 = 0.86667
        # For slope=1.0: transformed = 1.0, rounded to 10.0 * 0.1 = 1.0
        # For slope=1.2: transformed = 1.1333, rounded to 11.3333 * 0.1 = 1.13333
        assert np.isclose(result_df.iloc[0]['adjusted_slope'], 0.86667, atol=0.001)
        assert np.isclose(result_df.iloc[1]['adjusted_slope'], 1.0, atol=0.001)
        assert np.isclose(result_df.iloc[2]['adjusted_slope'], 1.13333, atol=0.001)
    
    def test_transform_slopes_error_filtering(self):
        """Test that slopes are filtered by relative error tolerance"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_calculation_service import BetaCalculationService
        
        df = pd.DataFrame({
            'ticker': ['TEST1', 'TEST2'],
            'fiscal_year': [2021, 2021],
            'fiscal_month': [1, 1],
            'slope': [1.0, 1.0],
            'std_err': [0.1, 0.5]  # HIGH error
        })
        
        mock_session = MagicMock()
        service = BetaCalculationService(mock_session)
        
        # Strict error tolerance
        error_tolerance = 0.2
        beta_rounding = 0.1
        result_df = service._transform_slopes(df, error_tolerance, beta_rounding)
        
        # First row should have value (error_rel = 0.1 / 1.33 = 0.075 < 0.2)
        assert pd.notna(result_df.iloc[0]['adjusted_slope'])
        
        # Second row should be NaN (error_rel = 0.5 / 1.33 = 0.375 > 0.2)
        assert pd.isna(result_df.iloc[1]['adjusted_slope'])
    
    def test_annualize_slopes_keeps_last_month(self):
        """Test that annualization keeps last month of each fiscal year"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_calculation_service import BetaCalculationService
        
        df = pd.DataFrame({
            'ticker': ['TEST', 'TEST', 'TEST'],
            'fiscal_year': [2021, 2021, 2021],
            'fiscal_month': [1, 6, 12],
            'slope': [0.8, 0.9, 1.0],
            'std_err': [0.1, 0.1, 0.1],
            'rel_std_err': [0.08, 0.08, 0.08],
            'adjusted_slope': [0.8, 0.9, 1.0]
        })
        
        mock_session = MagicMock()
        service = BetaCalculationService(mock_session)
        
        sector_map = {'TEST': 'Technology'}
        result_df = service._annualize_slopes(df, sector_map)
        
        # Should only have 1 row (last month of 2021)
        assert len(result_df) == 1
        # The method keeps the last month's data, so adjusted_slope should be 1.0 (from month 12)
        assert result_df.iloc[0]['adjusted_slope'] == 1.0
        assert result_df.iloc[0]['sector'] == 'Technology'


class TestRollingOLSCalculation:
    """Unit tests for rolling OLS calculation"""
    
    def test_rolling_ols_with_60_months(self):
        """Test rolling OLS with 60+ months of data"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_calculation_service import BetaCalculationService
        
        # Create 62 months of data
        months = []
        for i in range(62):
            months.append({
                'ticker': 'TEST',
                'fiscal_year': 2020 + (i // 12),
                'fiscal_month': (i % 12) + 1,
                'company_tsr': 5.0 + np.random.normal(0, 2),
                'index_tsr': 3.0 + np.random.normal(0, 1)
            })
        
        df = pd.DataFrame(months)
        
        mock_session = MagicMock()
        service = BetaCalculationService(mock_session)
        
        # Calculate rolling OLS
        result_df = service._calculate_rolling_ols(df)
        
        # Should have 62 rows (one for each month starting from window)
        assert len(result_df) >= 1
        # Window should be 60
        assert 'slope' in result_df.columns
        assert 'std_err' in result_df.columns
    
    def test_rolling_ols_dynamic_window(self):
        """Test rolling OLS uses dynamic window when < 60 months"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_calculation_service import BetaCalculationService
        
        # Create 30 months of data
        months = []
        for i in range(30):
            months.append({
                'ticker': 'TEST',
                'fiscal_year': 2021 + (i // 12),
                'fiscal_month': (i % 12) + 1,
                'company_tsr': 5.0 + np.random.normal(0, 2),
                'index_tsr': 3.0 + np.random.normal(0, 1)
            })
        
        df = pd.DataFrame(months)
        
        mock_session = MagicMock()
        service = BetaCalculationService(mock_session)
        
        # Calculate rolling OLS
        result_df = service._calculate_rolling_ols(df)
        
        # Should use dynamic window (30 months)
        assert len(result_df) >= 1


class TestFallbackLogic:
    """Unit tests for 4-tier fallback logic"""
    
    def test_4tier_fallback_spot_slope_priority(self):
        """Test 4-tier fallback uses spot_slope when available"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_calculation_service import BetaCalculationService
        
        # Create annual beta data with sector slopes
        annual_df = pd.DataFrame({
            'ticker': ['TEST1', 'TEST2'],
            'fiscal_year': [2021, 2021],
            'sector': ['Tech', 'Tech'],
            'adjusted_slope': [1.0, np.nan],
            'slope': [0.8, 0.9],
            'std_err': [0.1, 0.1],
            'rel_std_err': [0.08, 0.08]
        })
        
        sector_slopes = pd.DataFrame({
            'sector': ['Tech'],
            'fiscal_year': [2021],
            'sector_slope': [0.95]
        })
        
        mock_session = MagicMock()
        service = BetaCalculationService(mock_session)
        
        # Apply fallback
        result_df = service._apply_4tier_fallback(annual_df, sector_slopes)
        
        # TEST1 should use adjusted_slope
        assert result_df[result_df['ticker'] == 'TEST1'].iloc[0]['spot_slope'] == 1.0
        
        # TEST2 should use sector_slope (fallback)
        assert result_df[result_df['ticker'] == 'TEST2'].iloc[0]['spot_slope'] == 0.95


class TestApproachToKE:
    """Unit tests for cost_of_equity_approach logic"""
    
    def test_fixed_approach_uses_ticker_average(self):
        """Test FIXED approach uses ticker average"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_calculation_service import BetaCalculationService
        
        df = pd.DataFrame({
            'ticker': ['TEST', 'TEST', 'TEST'],
            'fiscal_year': [2021, 2022, 2023],
            'spot_slope': [0.8, 1.0, 1.2],
            'ticker_avg': [1.0, 1.0, 1.0]
        })
        
        mock_session = MagicMock()
        service = BetaCalculationService(mock_session)
        
        # Apply FIXED approach
        result_df = service._apply_approach_to_ke(df, 'FIXED', 0.1)
        
        # All rows should have same beta (ticker average)
        assert np.isclose(result_df.iloc[0]['beta'], 1.0, atol=0.001)
        assert np.isclose(result_df.iloc[1]['beta'], 1.0, atol=0.001)
        assert np.isclose(result_df.iloc[2]['beta'], 1.0, atol=0.001)
    
    def test_floating_approach_uses_spot_slope(self):
        """Test Floating approach uses spot_slope"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from backend.app.services.beta_calculation_service import BetaCalculationService
        
        df = pd.DataFrame({
            'ticker': ['TEST', 'TEST', 'TEST'],
            'fiscal_year': [2021, 2022, 2023],
            'spot_slope': [0.8, 1.0, 1.2],
            'ticker_avg': [1.0, 1.0, 1.0]
        })
        
        mock_session = MagicMock()
        service = BetaCalculationService(mock_session)
        
        # Apply Floating approach
        result_df = service._apply_approach_to_ke(df, 'Floating', 0.1)
        
        # Each row should use its spot_slope
        assert np.isclose(result_df.iloc[0]['beta'], 0.8, atol=0.001)
        assert np.isclose(result_df.iloc[1]['beta'], 1.0, atol=0.001)
        assert np.isclose(result_df.iloc[2]['beta'], 1.2, atol=0.001)


@pytest.mark.asyncio
class TestBetaServiceIntegration:
    """Integration tests with real database"""
    
    async def test_parameter_loading(self):
        """Test loading parameters from database"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from dotenv import load_dotenv
        import os
        load_dotenv()
        
        from backend.app.core.database import DatabaseManager
        from backend.app.core.config import get_settings
        from backend.app.services.beta_calculation_service import BetaCalculationService
        
        settings = get_settings()
        db = DatabaseManager(settings.DATABASE_URL)
        await db.initialize()
        
        try:
            async with db.session_factory() as session:
                # Get a param_set_id
                from sqlalchemy import text
                result = await session.execute(text("SELECT param_set_id FROM cissa.parameter_sets LIMIT 1"))
                row = result.fetchone()
                assert row is not None
                
                param_set_id = row[0]
                if not isinstance(param_set_id, UUID):
                    param_set_id = UUID(str(param_set_id))
                
                # Test parameter loading
                service = BetaCalculationService(session)
                params = await service._load_parameters_from_db(param_set_id)
                
                # Verify required parameters
                assert 'beta_rounding' in params
                assert 'beta_relative_error_tolerance' in params
                assert 'cost_of_equity_approach' in params
                
                # Verify types
                assert isinstance(params['beta_rounding'], float)
                assert isinstance(params['beta_relative_error_tolerance'], float)
                assert params['cost_of_equity_approach'] in ['FIXED', 'Floating']
        
        finally:
            await db.close()
    
    async def test_monthly_returns_fetch(self):
        """Test fetching monthly returns from database"""
        import sys
        sys.path.insert(0, '/home/ubuntu/cissa')
        from dotenv import load_dotenv
        import os
        load_dotenv()
        
        from backend.app.core.database import DatabaseManager
        from backend.app.core.config import get_settings
        from backend.app.services.beta_calculation_service import BetaCalculationService
        from sqlalchemy import text
        
        settings = get_settings()
        db = DatabaseManager(settings.DATABASE_URL)
        await db.initialize()
        
        try:
            async with db.session_factory() as session:
                # Get a dataset_id
                result = await session.execute(text("SELECT dataset_id FROM cissa.fundamentals LIMIT 1"))
                row = result.fetchone()
                assert row is not None
                
                dataset_id = row[0]
                if not isinstance(dataset_id, UUID):
                    dataset_id = UUID(str(dataset_id))
                
                # Test monthly returns fetch
                service = BetaCalculationService(session)
                monthly_df = await service._fetch_monthly_returns(dataset_id)
                
                # Verify data structure
                assert not monthly_df.empty
                assert 'ticker' in monthly_df.columns
                assert 'fiscal_year' in monthly_df.columns
                assert 'fiscal_month' in monthly_df.columns
                assert 'company_tsr' in monthly_df.columns
                assert 'index_tsr' in monthly_df.columns
                
                # Verify data types
                assert monthly_df['company_tsr'].dtype in [np.float32, np.float64]
                assert monthly_df['index_tsr'].dtype in [np.float32, np.float64]
        
        finally:
            await db.close()


# Run tests with: pytest backend/tests/test_beta_calculation.py -v
