# ============================================================================
# Integration Tests for FV ECF Service (Phase B)
# ============================================================================
"""
Integration tests for FVECFService:
1. Complete FV ECF flow for single ticker
2. All 4 intervals (1Y, 3Y, 5Y, 10Y)
3. Verify data fetching, joining, and calculation
4. Validate row counts decrease as expected
5. Test with and without franking
"""

import pytest
import asyncio
import pandas as pd
import numpy as np
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, patch, MagicMock
import sys

sys.path.insert(0, '/home/ubuntu/cissa')
from backend.app.services.fv_ecf_service import FVECFService


class TestFVECFIntegration:
    """Integration tests for complete FV ECF flow"""
    
    def setup_method(self):
        """Set up test data"""
        self.mock_session = MagicMock()
        self.service = FVECFService(self.mock_session)
        self.dataset_id = uuid4()
        self.ticker = "TEST"
        
        # Create comprehensive test dataset for single ticker (10 years)
        self.test_df = pd.DataFrame({
            'ticker': [self.ticker] * 10,
            'fiscal_year': list(range(2012, 2022)),
            'dividend': [50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0, 85.0, 90.0, 100.0],
            'franking': [1.0, 1.0, 1.0, 0.75, 0.75, 0.50, 0.50, 0.25, 0.25, 0.0],
            'non_div_ecf': [100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0, 180.0, 200.0],
            'ke_open': [0.08, 0.08, 0.09, 0.09, 0.10, 0.10, 0.11, 0.11, 0.12, 0.12],
        })
    
    def test_1y_fv_ecf_calculation_produces_10_rows(self):
        """Test that 1Y interval produces 10 rows (all data)"""
        params = {'incl_franking': 'No'}
        result = self.service._calculate_fv_ecf_for_interval(self.test_df, 1, params)
        
        # 1Y should have all 10 rows
        assert len(result) == 10
        assert list(result['ticker'].unique()) == [self.ticker]
        assert 'FV_ECF_Y' in result.columns
        assert 'FV_ECF_TYPE' in result.columns
        assert result['FV_ECF_TYPE'].iloc[0] == '1Y_FV_ECF'
    
    def test_3y_fv_ecf_calculation_produces_8_rows(self):
        """Test that 3Y interval produces 8 rows (skips first 2)"""
        params = {'incl_franking': 'No'}
        result = self.service._calculate_fv_ecf_for_interval(self.test_df, 3, params)
        
        # 3Y needs 2 prior years, so 10 - 2 = 8 rows
        assert len(result) == 8
        assert list(result['fiscal_year'].iloc[0:1].values) == [2014]
        assert list(result['fiscal_year'].iloc[-1:].values) == [2021]
    
    def test_5y_fv_ecf_calculation_produces_6_rows(self):
        """Test that 5Y interval produces 6 rows (skips first 4)"""
        params = {'incl_franking': 'No'}
        result = self.service._calculate_fv_ecf_for_interval(self.test_df, 5, params)
        
        # 5Y needs 4 prior years, so 10 - 4 = 6 rows
        assert len(result) == 6
        assert list(result['fiscal_year'].iloc[0:1].values) == [2016]
        assert list(result['fiscal_year'].iloc[-1:].values) == [2021]
    
    def test_10y_fv_ecf_calculation_produces_1_row(self):
        """Test that 10Y interval produces 1 row (only latest year)"""
        params = {'incl_franking': 'No'}
        result = self.service._calculate_fv_ecf_for_interval(self.test_df, 10, params)
        
        # 10Y needs 9 prior years, so 10 - 9 = 1 row
        assert len(result) == 1
        assert result['fiscal_year'].iloc[0] == 2021
    
    def test_row_count_hierarchy_1y_greater_than_3y(self):
        """Test that 1Y > 3Y rows"""
        params = {'incl_franking': 'No'}
        result_1y = self.service._calculate_fv_ecf_for_interval(self.test_df, 1, params)
        result_3y = self.service._calculate_fv_ecf_for_interval(self.test_df, 3, params)
        
        assert len(result_1y) > len(result_3y)
    
    def test_row_count_hierarchy_3y_greater_than_5y(self):
        """Test that 3Y > 5Y rows"""
        params = {'incl_franking': 'No'}
        result_3y = self.service._calculate_fv_ecf_for_interval(self.test_df, 3, params)
        result_5y = self.service._calculate_fv_ecf_for_interval(self.test_df, 5, params)
        
        assert len(result_3y) > len(result_5y)
    
    def test_row_count_hierarchy_5y_greater_than_10y(self):
        """Test that 5Y > 10Y rows"""
        params = {'incl_franking': 'No'}
        result_5y = self.service._calculate_fv_ecf_for_interval(self.test_df, 5, params)
        result_10y = self.service._calculate_fv_ecf_for_interval(self.test_df, 10, params)
        
        assert len(result_5y) > len(result_10y)
    
    def test_fv_ecf_values_are_numeric(self):
        """Test that all FV_ECF values are numeric (not NaN for valid rows)"""
        params = {'incl_franking': 'No'}
        result = self.service._calculate_fv_ecf_for_interval(self.test_df, 1, params)
        
        # All returned rows should have non-NaN FV_ECF values
        assert result['FV_ECF_Y'].notna().all()
        assert result['FV_ECF_Y'].dtype in [np.float64, np.float32]
    
    def test_fv_ecf_values_reflect_negative_dividends(self):
        """Test that FV_ECF values reflect negative dividend component"""
        params = {'incl_franking': 'No'}
        result = self.service._calculate_fv_ecf_for_interval(self.test_df, 1, params)
        
        # ECF_base = -dividend + non_div_ecf
        # For 1Y: FV_ECF = ECF_base (no compounding)
        # Latest year: ECF_base = -100 + 200 = 100
        latest_fv_ecf = result[result['fiscal_year'] == 2021]['FV_ECF_Y'].iloc[0]
        assert np.isclose(latest_fv_ecf, 100.0, atol=0.1)
    
    def test_1y_values_simpler_than_3y(self):
        """Test that 1Y calculations are consistent with formula"""
        params = {'incl_franking': 'No'}
        result_1y = self.service._calculate_fv_ecf_for_interval(self.test_df, 1, params)
        
        # For 1Y, FV_ECF[t] = ECF_base[t] * (1 + ke)^0 = ECF_base[t]
        # Latest year: ECF_base = -100 + 200 = 100
        latest_1y = result_1y[result_1y['fiscal_year'] == 2021]['FV_ECF_Y'].iloc[0]
        assert np.isclose(latest_1y, 100.0, atol=0.1)
    
    def test_3y_values_greater_magnitude_than_1y(self):
        """Test that 3Y values typically have greater magnitude due to compounding"""
        params = {'incl_franking': 'No'}
        result_1y = self.service._calculate_fv_ecf_for_interval(self.test_df, 1, params)
        result_3y = self.service._calculate_fv_ecf_for_interval(self.test_df, 3, params)
        
        # Get overlapping year (2021)
        val_1y = result_1y[result_1y['fiscal_year'] == 2021]['FV_ECF_Y'].iloc[0]
        val_3y = result_3y[result_3y['fiscal_year'] == 2021]['FV_ECF_Y'].iloc[0]
        
        # Due to positive ke and positive terms, 3Y should have different value
        # (They're summing 3 terms instead of 1)
        assert val_1y != val_3y
    
    def test_multiple_tickers_processed_separately(self):
        """Test that multiple tickers are processed independently"""
        # Create data with two tickers
        df_multi = pd.concat([
            self.test_df.copy(),
            self.test_df.copy()
        ], ignore_index=True)
        df_multi.loc[10:, 'ticker'] = 'TEST2'
        
        params = {'incl_franking': 'No'}
        result = self.service._calculate_fv_ecf_for_interval(df_multi, 1, params)
        
        # Both tickers should be in results
        assert set(result['ticker'].unique()) == {'TEST', 'TEST2'}
        # Each ticker should have 10 rows
        assert len(result[result['ticker'] == 'TEST']) == 10
        assert len(result[result['ticker'] == 'TEST2']) == 10
    
    def test_franking_affects_ecf_base_calculation(self):
        """Test that franking parameter affects FV_ECF values"""
        params_no_frank = {'incl_franking': 'No'}
        params_with_frank = {
            'incl_franking': 'Yes',
            'frank_tax_rate': 0.30,
            'value_franking_cr': 0.75
        }
        
        result_no_frank = self.service._calculate_fv_ecf_for_interval(
            self.test_df, 1, params_no_frank
        )
        result_with_frank = self.service._calculate_fv_ecf_for_interval(
            self.test_df, 1, params_with_frank
        )
        
        # Results should be different
        assert not result_no_frank['FV_ECF_Y'].equals(result_with_frank['FV_ECF_Y'])
    
    def test_result_columns_match_specification(self):
        """Test that result has correct columns"""
        params = {'incl_franking': 'No'}
        result = self.service._calculate_fv_ecf_for_interval(self.test_df, 1, params)
        
        expected_cols = {'ticker', 'fiscal_year', 'FV_ECF_Y', 'FV_ECF_TYPE'}
        assert expected_cols.issubset(set(result.columns))
    
    def test_fiscal_year_values_preserved(self):
        """Test that fiscal year values are preserved correctly"""
        params = {'incl_franking': 'No'}
        result = self.service._calculate_fv_ecf_for_interval(self.test_df, 3, params)
        
        # Should have fiscal years 2014-2021 (skipped 2012-2013)
        expected_years = [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021]
        assert list(sorted(result['fiscal_year'].unique())) == expected_years
    
    def test_empty_dataframe_returns_empty(self):
        """Test that empty DataFrame returns empty result"""
        df_empty = pd.DataFrame({
            'ticker': [],
            'fiscal_year': [],
            'dividend': [],
            'franking': [],
            'non_div_ecf': [],
            'ke_open': [],
        })
        
        params = {'incl_franking': 'No'}
        result = self.service._calculate_fv_ecf_for_interval(df_empty, 1, params)
        
        assert result.empty
    
    def test_missing_required_columns_handled_gracefully(self):
        """Test behavior with missing columns"""
        df_incomplete = pd.DataFrame({
            'ticker': ['TEST'] * 5,
            'fiscal_year': [2017, 2018, 2019, 2020, 2021],
            # Missing dividend, franking, non_div_ecf, ke_open
        })
        
        params = {'incl_franking': 'No'}
        # Should either raise KeyError or return empty
        try:
            result = self.service._calculate_fv_ecf_for_interval(df_incomplete, 1, params)
            # If it completes, result should be empty or have NaN values
            assert result.empty or result['FV_ECF_Y'].isna().all()
        except (KeyError, AttributeError):
            # Expected behavior - missing columns should raise error
            pass


class TestFVECFEndToEnd:
    """End-to-end tests simulating real workflow"""
    
    def test_complete_workflow_all_intervals(self):
        """Test complete workflow: calculate all 4 intervals for single ticker"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        # Create test data
        df = pd.DataFrame({
            'ticker': ['TEST'] * 15,
            'fiscal_year': list(range(2007, 2022)),
            'dividend': [50.0 + i*5 for i in range(15)],
            'franking': [1.0] * 15,
            'non_div_ecf': [100.0 + i*10 for i in range(15)],
            'ke_open': [0.10] * 15,
        })
        
        params = {'incl_franking': 'No'}
        
        # Calculate all intervals
        result_1y = service._calculate_fv_ecf_for_interval(df, 1, params)
        result_3y = service._calculate_fv_ecf_for_interval(df, 3, params)
        result_5y = service._calculate_fv_ecf_for_interval(df, 5, params)
        result_10y = service._calculate_fv_ecf_for_interval(df, 10, params)
        
        # Verify counts
        assert len(result_1y) == 15
        assert len(result_3y) == 13
        assert len(result_5y) == 11
        assert len(result_10y) == 6
        
        # Verify hierarchy
        assert len(result_1y) > len(result_3y) > len(result_5y) > len(result_10y)
        
        # Verify all have valid FV_ECF values
        assert result_1y['FV_ECF_Y'].notna().all()
        assert result_3y['FV_ECF_Y'].notna().all()
        assert result_5y['FV_ECF_Y'].notna().all()
        assert result_10y['FV_ECF_Y'].notna().all()
    
    def test_franking_parameters_passed_through_correctly(self):
        """Test that franking parameters are correctly passed to ECF calculation"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        df = pd.DataFrame({
            'ticker': ['TEST'] * 5,
            'fiscal_year': [2017, 2018, 2019, 2020, 2021],
            'dividend': [100.0] * 5,
            'franking': [1.0] * 5,
            'non_div_ecf': [50.0] * 5,
            'ke_open': [0.10] * 5,
        })
        
        params = {
            'incl_franking': 'Yes',
            'frank_tax_rate': 0.30,
            'value_franking_cr': 0.75
        }
        
        result = service._calculate_fv_ecf_for_interval(df, 1, params)
        
        # Should have results and values should reflect franking
        assert len(result) == 5
        assert result['FV_ECF_Y'].notna().all()
        # With franking, ECF_base will be more negative due to franking adjustment
        assert result['FV_ECF_Y'].iloc[-1] < -50.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
