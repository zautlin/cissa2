# ============================================================================
# Unit Tests for FV ECF Service Refactoring (Phase B)
# ============================================================================
"""
Test suite for FVECFService helper methods:
1. _validate_temporal_window() - Filtering logic
2. _calculate_ecf_base_value() - ECF base calculation with/without franking
3. _calculate_fv_ecf_single_year() - Year-by-year lookback algorithm
4. Integration tests for complete FV ECF flow
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock
import sys

sys.path.insert(0, '/home/ubuntu/cissa')
from backend.app.services.fv_ecf_service import FVECFService


class TestValidateTemporalWindow:
    """Unit tests for temporal window validation"""
    
    def test_empty_dataframe(self):
        """Test that empty DataFrame returns empty DataFrame"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        df = pd.DataFrame()
        result = service._validate_temporal_window(df, 3)
        
        assert result.empty
    
    def test_1y_interval_keeps_all_rows(self):
        """Test that 1Y interval keeps all rows (starting from position 0)"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        df = pd.DataFrame({
            'ticker': ['TEST'] * 5,
            'fiscal_year': [2017, 2018, 2019, 2020, 2021],
        })
        
        result = service._validate_temporal_window(df, 1)
        
        # 1Y needs 0 prior years, so all rows valid (from position 0)
        assert len(result) == 5
        assert list(result['fiscal_year']) == [2017, 2018, 2019, 2020, 2021]
    
    def test_3y_interval_skips_first_two_rows(self):
        """Test that 3Y interval skips first 2 rows (starting from position 2)"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        df = pd.DataFrame({
            'ticker': ['TEST'] * 5,
            'fiscal_year': [2017, 2018, 2019, 2020, 2021],
        })
        
        result = service._validate_temporal_window(df, 3)
        
        # 3Y needs 2 prior years, so start from row 3 (index 2)
        assert len(result) == 3
        assert list(result['fiscal_year']) == [2019, 2020, 2021]
    
    def test_5y_interval_skips_first_four_rows(self):
        """Test that 5Y interval skips first 4 rows"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        df = pd.DataFrame({
            'ticker': ['TEST'] * 10,
            'fiscal_year': list(range(2012, 2022)),
        })
        
        result = service._validate_temporal_window(df, 5)
        
        # 5Y needs 4 prior years, so start from row 5 (index 4)
        assert len(result) == 6
        assert list(result['fiscal_year']) == [2016, 2017, 2018, 2019, 2020, 2021]
    
    def test_10y_interval_skips_first_nine_rows(self):
        """Test that 10Y interval skips first 9 rows"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        df = pd.DataFrame({
            'ticker': ['TEST'] * 15,
            'fiscal_year': list(range(2007, 2022)),
        })
        
        result = service._validate_temporal_window(df, 10)
        
        # 10Y needs 9 prior years, so start from row 10 (index 9)
        assert len(result) == 6
        assert list(result['fiscal_year']) == [2016, 2017, 2018, 2019, 2020, 2021]
    
    def test_insufficient_data_returns_empty(self):
        """Test that interval larger than data returns empty DataFrame"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        df = pd.DataFrame({
            'ticker': ['TEST'] * 2,
            'fiscal_year': [2020, 2021],
        })
        
        result = service._validate_temporal_window(df, 5)
        
        # 5Y needs 4 prior years, but only have 2 rows total
        assert result.empty
    
    def test_reset_index_drops_old_index(self):
        """Test that result has reset index (0, 1, 2, ...)"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        df = pd.DataFrame({
            'ticker': ['TEST'] * 5,
            'fiscal_year': [2017, 2018, 2019, 2020, 2021],
        })
        # Manually set a non-default index to verify it gets reset
        df.index = [10, 11, 12, 13, 14]
        
        result = service._validate_temporal_window(df, 3)
        
        # Index should be reset to 0, 1, 2
        assert list(result.index) == [0, 1, 2]


class TestCalculateECFBaseValue:
    """Unit tests for ECF base value calculation"""
    
    def test_basic_calculation_without_franking(self):
        """Test basic ECF_base = -dividend + non_div_ecf (no franking)"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        params = {'incl_franking': 'No'}
        ecf_base = service._calculate_ecf_base_value(
            dividend=100.0,
            franking=0.5,
            non_div_ecf=50.0,
            params=params
        )
        
        # -100 + 50 = -50
        assert ecf_base == -50.0
    
    def test_nan_dividend_returns_nan(self):
        """Test that NaN dividend returns NaN"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        params = {'incl_franking': 'No'}
        ecf_base = service._calculate_ecf_base_value(
            dividend=np.nan,
            franking=0.5,
            non_div_ecf=50.0,
            params=params
        )
        
        assert pd.isna(ecf_base)
    
    def test_nan_non_div_ecf_returns_nan(self):
        """Test that NaN non_div_ecf returns NaN"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        params = {'incl_franking': 'No'}
        ecf_base = service._calculate_ecf_base_value(
            dividend=100.0,
            franking=0.5,
            non_div_ecf=np.nan,
            params=params
        )
        
        assert pd.isna(ecf_base)
    
    def test_zero_dividend_with_non_div_ecf(self):
        """Test calculation with zero dividend"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        params = {'incl_franking': 'No'}
        ecf_base = service._calculate_ecf_base_value(
            dividend=0.0,
            franking=0.5,
            non_div_ecf=100.0,
            params=params
        )
        
        # -0 + 100 = 100
        assert ecf_base == 100.0
    
    def test_franking_adjustment_applied_correctly(self):
        """Test franking adjustment calculation"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        # Using standard parameters
        params = {
            'incl_franking': 'Yes',
            'frank_tax_rate': 0.30,
            'value_franking_cr': 0.75
        }
        
        dividend = 100.0
        franking = 1.0  # Fully franked
        non_div_ecf = 50.0
        
        ecf_base = service._calculate_ecf_base_value(
            dividend=dividend,
            franking=franking,
            non_div_ecf=non_div_ecf,
            params=params
        )
        
        # Manual calculation:
        # base = -100 + 50 = -50
        # franking_adj = (100 / (1 - 0.30)) * 0.30 * 0.75 * 1.0
        #              = (100 / 0.70) * 0.30 * 0.75
        #              = 142.857 * 0.225 = 32.143
        # ecf_base = -50 - 32.143 = -82.143
        expected = -50.0 - ((100.0 / 0.70) * 0.30 * 0.75)
        assert np.isclose(ecf_base, expected, atol=0.01)
    
    def test_franking_adjustment_with_50_percent_franking(self):
        """Test franking adjustment with 50% franking"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        params = {
            'incl_franking': 'Yes',
            'frank_tax_rate': 0.30,
            'value_franking_cr': 0.75
        }
        
        dividend = 100.0
        franking = 0.5  # 50% franked
        non_div_ecf = 50.0
        
        ecf_base = service._calculate_ecf_base_value(
            dividend=dividend,
            franking=franking,
            non_div_ecf=non_div_ecf,
            params=params
        )
        
        # Franking adjustment should be half of fully franked case
        expected = -50.0 - ((100.0 / 0.70) * 0.30 * 0.75 * 0.5)
        assert np.isclose(ecf_base, expected, atol=0.01)
    
    def test_franking_ignored_when_incl_franking_is_no(self):
        """Test that franking is ignored when incl_franking='No'"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        params = {
            'incl_franking': 'No',
            'frank_tax_rate': 0.30,
            'value_franking_cr': 0.75
        }
        
        dividend = 100.0
        franking = 1.0
        non_div_ecf = 50.0
        
        ecf_base = service._calculate_ecf_base_value(
            dividend=dividend,
            franking=franking,
            non_div_ecf=non_div_ecf,
            params=params
        )
        
        # Franking should be ignored
        assert ecf_base == -50.0
    
    def test_nan_franking_with_incl_franking_yes(self):
        """Test that NaN franking is handled gracefully"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        params = {
            'incl_franking': 'Yes',
            'frank_tax_rate': 0.30,
            'value_franking_cr': 0.75
        }
        
        dividend = 100.0
        franking = np.nan  # NaN franking
        non_div_ecf = 50.0
        
        ecf_base = service._calculate_ecf_base_value(
            dividend=dividend,
            franking=franking,
            non_div_ecf=non_div_ecf,
            params=params
        )
        
        # Should not apply franking adjustment if franking is NaN
        assert ecf_base == -50.0
    
    def test_case_insensitive_incl_franking(self):
        """Test that incl_franking is case-insensitive"""
        mock_session = MagicMock()
        service = FVECFService(mock_session)
        
        # Test with 'yes' (lowercase)
        params = {
            'incl_franking': 'yes',
            'frank_tax_rate': 0.30,
            'value_franking_cr': 0.75
        }
        
        dividend = 100.0
        franking = 1.0
        non_div_ecf = 50.0
        
        ecf_base = service._calculate_ecf_base_value(
            dividend=dividend,
            franking=franking,
            non_div_ecf=non_div_ecf,
            params=params
        )
        
        # Should apply franking adjustment
        expected = -50.0 - ((100.0 / 0.70) * 0.30 * 0.75)
        assert np.isclose(ecf_base, expected, atol=0.01)


class TestCalculateFVECFSingleYear:
    """Unit tests for single-year FV ECF calculation"""
    
    def setup_method(self):
        """Set up common test data"""
        self.mock_session = MagicMock()
        self.service = FVECFService(self.mock_session)
        self.params = {'incl_franking': 'No'}
    
    def test_1y_calculation_power_zero(self):
        """Test 1Y calculation: ECF_base[t] * (1 + ke)^0 = ECF_base[t]"""
        df = pd.DataFrame({
            'ticker': ['TEST'] * 3,
            'fiscal_year': [2019, 2020, 2021],
            'dividend': [100.0, 100.0, 100.0],
            'franking': [1.0, 1.0, 1.0],
            'non_div_ecf': [50.0, 50.0, 50.0],
            'ke_open': [0.10, 0.10, 0.10],
        })
        
        # Current index 2 (2021)
        # 1Y: ECF_base[2] * (1 + 0.10)^0 = -50 * 1 = -50
        fv_ecf = self.service._calculate_fv_ecf_single_year(df, 2, 1, self.params)
        
        assert np.isclose(fv_ecf, -50.0, atol=0.01)
    
    def test_3y_calculation_multiple_terms(self):
        """Test 3Y calculation with three terms"""
        df = pd.DataFrame({
            'ticker': ['TEST'] * 4,
            'fiscal_year': [2018, 2019, 2020, 2021],
            'dividend': [100.0, 100.0, 100.0, 100.0],
            'franking': [1.0, 1.0, 1.0, 1.0],
            'non_div_ecf': [50.0, 50.0, 50.0, 50.0],
            'ke_open': [0.10, 0.10, 0.10, 0.10],
        })
        
        # Current index 3 (2021), interval 3
        # ke_open[3] = 0.10
        # term1 = -50 * (1 + 0.10)^2 = -50 * 1.21 = -60.5
        # term2 = -50 * (1 + 0.10)^1 = -50 * 1.10 = -55.0
        # term3 = -50 * (1 + 0.10)^0 = -50 * 1.00 = -50.0
        # Total = -165.5
        
        fv_ecf = self.service._calculate_fv_ecf_single_year(df, 3, 3, self.params)
        
        expected = -50.0 * (1.10 ** 2) + (-50.0 * 1.10) + (-50.0)
        assert np.isclose(fv_ecf, expected, atol=0.01)
    
    def test_nan_ke_open_returns_nan(self):
        """Test that NaN ke_open returns NaN"""
        df = pd.DataFrame({
            'ticker': ['TEST'] * 3,
            'fiscal_year': [2019, 2020, 2021],
            'dividend': [100.0, 100.0, 100.0],
            'franking': [1.0, 1.0, 1.0],
            'non_div_ecf': [50.0, 50.0, 50.0],
            'ke_open': [0.10, 0.10, np.nan],
        })
        
        fv_ecf = self.service._calculate_fv_ecf_single_year(df, 2, 1, self.params)
        
        assert pd.isna(fv_ecf)
    
    def test_zero_ke_open_returns_zero(self):
        """Test that ke_open <= 0 returns 0"""
        df = pd.DataFrame({
            'ticker': ['TEST'] * 3,
            'fiscal_year': [2019, 2020, 2021],
            'dividend': [100.0, 100.0, 100.0],
            'franking': [1.0, 1.0, 1.0],
            'non_div_ecf': [50.0, 50.0, 50.0],
            'ke_open': [0.10, 0.10, 0.0],
        })
        
        fv_ecf = self.service._calculate_fv_ecf_single_year(df, 2, 1, self.params)
        
        assert fv_ecf == 0.0
    
    def test_negative_ke_open_returns_zero(self):
        """Test that negative ke_open returns 0"""
        df = pd.DataFrame({
            'ticker': ['TEST'] * 3,
            'fiscal_year': [2019, 2020, 2021],
            'dividend': [100.0, 100.0, 100.0],
            'franking': [1.0, 1.0, 1.0],
            'non_div_ecf': [50.0, 50.0, 50.0],
            'ke_open': [0.10, 0.10, -0.05],
        })
        
        fv_ecf = self.service._calculate_fv_ecf_single_year(df, 2, 1, self.params)
        
        assert fv_ecf == 0.0
    
    def test_insufficient_history_returns_nan(self):
        """Test that insufficient history returns NaN"""
        df = pd.DataFrame({
            'ticker': ['TEST'] * 2,
            'fiscal_year': [2020, 2021],
            'dividend': [100.0, 100.0],
            'franking': [1.0, 1.0],
            'non_div_ecf': [50.0, 50.0],
            'ke_open': [0.10, 0.10],
        })
        
        # Try to calculate 5Y at index 1, but only have 2 rows
        fv_ecf = self.service._calculate_fv_ecf_single_year(df, 1, 5, self.params)
        
        assert pd.isna(fv_ecf)
    
    def test_nan_in_middle_year_returns_nan(self):
        """Test that NaN in any year of lookback window returns NaN"""
        df = pd.DataFrame({
            'ticker': ['TEST'] * 4,
            'fiscal_year': [2018, 2019, 2020, 2021],
            'dividend': [100.0, np.nan, 100.0, 100.0],  # NaN in year 2
            'franking': [1.0, 1.0, 1.0, 1.0],
            'non_div_ecf': [50.0, 50.0, 50.0, 50.0],
            'ke_open': [0.10, 0.10, 0.10, 0.10],
        })
        
        # 3Y calculation at index 3 includes index 1 (which has NaN dividend)
        fv_ecf = self.service._calculate_fv_ecf_single_year(df, 3, 3, self.params)
        
        assert pd.isna(fv_ecf)
    
    def test_5y_calculation_five_terms(self):
        """Test 5Y calculation with all five terms"""
        df = pd.DataFrame({
            'ticker': ['TEST'] * 6,
            'fiscal_year': [2016, 2017, 2018, 2019, 2020, 2021],
            'dividend': [100.0] * 6,
            'franking': [1.0] * 6,
            'non_div_ecf': [50.0] * 6,
            'ke_open': [0.10] * 6,
        })
        
        # 5Y at index 5
        # term1 = -50 * (1.10)^4
        # term2 = -50 * (1.10)^3
        # term3 = -50 * (1.10)^2
        # term4 = -50 * (1.10)^1
        # term5 = -50 * (1.10)^0
        
        fv_ecf = self.service._calculate_fv_ecf_single_year(df, 5, 5, self.params)
        
        expected = sum(-50.0 * (1.10 ** power) for power in range(4, -1, -1))
        assert np.isclose(fv_ecf, expected, atol=0.01)
    
    def test_10y_calculation_ten_terms(self):
        """Test 10Y calculation with all ten terms"""
        df = pd.DataFrame({
            'ticker': ['TEST'] * 11,
            'fiscal_year': list(range(2011, 2022)),
            'dividend': [100.0] * 11,
            'franking': [1.0] * 11,
            'non_div_ecf': [50.0] * 11,
            'ke_open': [0.10] * 11,
        })
        
        # 10Y at index 10
        # Sum of 10 terms with powers 9, 8, ..., 1, 0
        
        fv_ecf = self.service._calculate_fv_ecf_single_year(df, 10, 10, self.params)
        
        expected = sum(-50.0 * (1.10 ** power) for power in range(9, -1, -1))
        assert np.isclose(fv_ecf, expected, atol=0.01)
    
    def test_different_ke_open_values(self):
        """Test that calculation uses current row's ke_open"""
        df = pd.DataFrame({
            'ticker': ['TEST'] * 3,
            'fiscal_year': [2019, 2020, 2021],
            'dividend': [100.0, 100.0, 100.0],
            'franking': [1.0, 1.0, 1.0],
            'non_div_ecf': [50.0, 50.0, 50.0],
            'ke_open': [0.05, 0.08, 0.12],  # Different KE each year
        })
        
        # At index 2, use ke_open[2] = 0.12
        fv_ecf = self.service._calculate_fv_ecf_single_year(df, 2, 1, self.params)
        
        # 1Y: -50 * (1 + 0.12)^0 = -50
        assert np.isclose(fv_ecf, -50.0, atol=0.01)
    
    def test_3y_calculation_uses_current_year_ke(self):
        """Test that 3Y calculation uses current year's ke_open for all terms"""
        df = pd.DataFrame({
            'ticker': ['TEST'] * 4,
            'fiscal_year': [2018, 2019, 2020, 2021],
            'dividend': [100.0, 100.0, 100.0, 100.0],
            'franking': [1.0, 1.0, 1.0, 1.0],
            'non_div_ecf': [50.0, 50.0, 50.0, 50.0],
            'ke_open': [0.05, 0.08, 0.10, 0.15],  # Different each year
        })
        
        # At index 3, use ke_open[3] = 0.15 for ALL terms
        fv_ecf = self.service._calculate_fv_ecf_single_year(df, 3, 3, self.params)
        
        # All three terms use ke = 0.15
        expected = (
            -50.0 * (1.15 ** 2) +      # Current year, power=2
            -50.0 * (1.15 ** 1) +      # Year -1, power=1
            -50.0 * (1.15 ** 0)        # Year -2, power=0
        )
        assert np.isclose(fv_ecf, expected, atol=0.01)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
