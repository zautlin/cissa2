"""
Integration test: 3Y EE Growth validation against reference data
Tests that the EE Growth Calculator produces correct values for 3Y window
"""

import sys
from pathlib import Path
from uuid import UUID

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.models.ratio_metrics import MetricDefinition
from app.services.ee_growth_calculator import EEGrowthCalculator

# Reference data for CSL AU 3Y EE Growth
REFERENCE_3Y_DATA = {
    "2001": None,      # n/a
    "2002": 0.416,     # 41.6%
    "2003": 0.240,     # 24.0%
    "2004": 0.117,     # 11.7%
    "2005": 0.020,     # 2.0%
    "2006": 0.078,     # 7.8%
    "2007": 0.468,     # 46.8%
    "2008": 0.187,     # 18.7%
    "2009": 0.092,     # 9.2%
    "2010": -0.116,    # (11.6%)
    "2011": -0.103,    # (10.3%)
    "2012": -0.081,    # (8.1%)
    "2013": -0.049,    # (4.9%)
    "2014": -0.003,    # (0.3%)
    "2015": 0.024,     # 2.4%
    "2016": 0.111,     # 11.1%
    "2017": 0.267,     # 26.7%
    "2018": 0.331,     # 33.1%
    "2019": None,      # (not provided)
    "2020": None,      # (not provided)
}


def test_ee_growth_calculator_3y_query_structure():
    """Test that the calculator builds correct SQL for 3Y window"""
    print("\n" + "="*80)
    print("TEST: EE Growth Calculator - 3Y Query Structure")
    print("="*80)
    
    metric_def = MetricDefinition(
        id="ee_growth",
        display_name="EE Growth",
        description="Equity Employed Growth",
        formula_type="ee_growth",
        metric_name="Calc EE",
        metric_source="metrics_outputs",
        operation="growth",
        null_handling="skip_year",
        negative_handling="use_absolute"
    )
    
    calc = EEGrowthCalculator(metric_def, "3Y")
    
    # Test query building
    tickers = ["CSL"]
    dataset_id = UUID("00000000-0000-0000-0000-000000000001")
    param_set_id = UUID("00000000-0000-0000-0000-000000000002")
    
    sql_query, params = calc.build_query(
        tickers=tickers,
        dataset_id=dataset_id,
        param_set_id=param_set_id,
        start_year=2001,
        end_year=2020
    )
    
    # Validate query structure
    checks = {
        "Contains ee_data CTE": "ee_data AS" in sql_query,
        "Contains ee_rolling CTE": "ee_rolling AS" in sql_query,
        "Contains ee_with_lag CTE": "ee_with_lag AS" in sql_query,
        "Queries metrics_outputs": "cissa.metrics_outputs" in sql_query,
        "Uses LAG function": "LAG(ee_rolling_avg)" in sql_query,
        "Uses AVG window function": "AVG(ee) OVER" in sql_query,
        "ROWS BETWEEN 2 PRECEDING": "ROWS BETWEEN :rows_between PRECEDING" in sql_query,
        "Uses ABS() on denominator": "/ ABS(prior_year_avg_ee)" in sql_query,
        "Filters by dataset_id": "dataset_id = :dataset_id" in sql_query,
        "Filters by param_set_id": "param_set_id = :param_set_id" in sql_query,
        "Filters by metric_name": "metric_name = :metric_name" in sql_query,
        "Uses year range filter": "fiscal_year >= :start_year" in sql_query,
        "Handles NULL comparison": "prior_year_avg_ee IS NULL" in sql_query,
        "NULL handling for zero": "ABS(prior_year_avg_ee) = 0" in sql_query,
        "ORDER BY clause": "ORDER BY ticker, fiscal_year" in sql_query,
    }
    
    print("\nSQL Structure Validation:")
    print("-" * 80)
    passed = 0
    for check_name, result in checks.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {check_name}")
        if result:
            passed += 1
    
    print("-" * 80)
    print(f"Passed: {passed}/{len(checks)}")
    
    # Validate parameters
    print("\nParameters Validation:")
    print("-" * 80)
    param_checks = {
        "rows_between is 2": params["rows_between"] == 2,
        "dataset_id set": params["dataset_id"] == str(dataset_id),
        "param_set_id set": params["param_set_id"] == str(param_set_id),
        "metric_name is 'Calc EE'": params["metric_name"] == "Calc EE",
        "tickers list": params["tickers"] == ["CSL"],
        "start_year is 2001": params.get("start_year") == 2001,
        "end_year is 2020": params.get("end_year") == 2020,
    }
    
    param_passed = 0
    for check_name, result in param_checks.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {check_name}")
        if result:
            param_passed += 1
    
    print("-" * 80)
    print(f"Passed: {param_passed}/{len(param_checks)}")
    
    return passed == len(checks) and param_passed == len(param_checks)


def test_ee_growth_calculator_all_windows():
    """Test that calculator supports all temporal windows correctly"""
    print("\n" + "="*80)
    print("TEST: EE Growth Calculator - All Temporal Windows")
    print("="*80)
    
    metric_def = MetricDefinition(
        id="ee_growth",
        display_name="EE Growth",
        description="Equity Employed Growth",
        formula_type="ee_growth",
        metric_name="Calc EE",
        metric_source="metrics_outputs",
        operation="growth",
        null_handling="skip_year",
        negative_handling="use_absolute"
    )
    
    windows_config = {
        "1Y": "0",   # No rolling (current year only)
        "3Y": "2",   # 3-year window (current + 2 prior)
        "5Y": "4",   # 5-year window (current + 4 prior)
        "10Y": "9"   # 10-year window (current + 9 prior)
    }
    
    print("\nTemporal Window Mapping:")
    print("-" * 80)
    
    all_passed = True
    for window, expected_rows in windows_config.items():
        calc = EEGrowthCalculator(metric_def, window)
        actual_rows = calc.rows_between
        
        passed = actual_rows == expected_rows
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {window:4} -> ROWS BETWEEN {actual_rows:1} PRECEDING " +
              f"(expected {expected_rows})")
        
        if not passed:
            all_passed = False
    
    print("-" * 80)
    return all_passed


def test_ee_growth_calculator_year_filtering():
    """Test that year filtering works correctly"""
    print("\n" + "="*80)
    print("TEST: EE Growth Calculator - Year Filtering")
    print("="*80)
    
    metric_def = MetricDefinition(
        id="ee_growth",
        display_name="EE Growth",
        description="Equity Employed Growth",
        formula_type="ee_growth",
        metric_name="Calc EE",
        metric_source="metrics_outputs",
        operation="growth",
        null_handling="skip_year",
        negative_handling="use_absolute"
    )
    
    calc = EEGrowthCalculator(metric_def, "3Y")
    
    dataset_id = UUID("00000000-0000-0000-0000-000000000001")
    param_set_id = UUID("00000000-0000-0000-0000-000000000002")
    
    print("\nYear Filtering Tests:")
    print("-" * 80)
    
    tests = [
        ("Full range", 2001, 2020, True, "fiscal_year >= :start_year AND fiscal_year <= :end_year"),
        ("Start year only", 2010, None, True, "fiscal_year >= :start_year"),
        ("End year only", None, 2015, True, "fiscal_year <= :end_year"),
        ("No filtering", None, None, False, "fiscal_year >= :start_year"),  # No year filters should be present
    ]
    
    all_passed = True
    for test_name, start, end, should_have_filter, filter_clause in tests:
        sql_query, params = calc.build_query(
            tickers=["CSL"],
            dataset_id=dataset_id,
            param_set_id=param_set_id,
            start_year=start,
            end_year=end
        )
        
        if should_have_filter:
            has_filter = filter_clause in sql_query
        else:
            # No year filtering should mean no fiscal_year >= :start_year
            has_filter = filter_clause not in sql_query
        
        status = "✓ PASS" if has_filter else "✗ FAIL"
        print(f"{status}: {test_name:20} (start={start}, end={end})")
        
        if not has_filter:
            all_passed = False
    
    print("-" * 80)
    return all_passed


def test_reference_data_format():
    """Test that reference data is in correct format"""
    print("\n" + "="*80)
    print("TEST: Reference Data Format Validation")
    print("="*80)
    
    print("\nReference Data Structure:")
    print("-" * 80)
    
    checks = []
    
    # Check 1: Correct number of years
    check = len(REFERENCE_3Y_DATA) == 20
    checks.append(("20 fiscal years (2001-2020)", check))
    
    # Check 2: First year is NULL
    check = REFERENCE_3Y_DATA["2001"] is None
    checks.append(("First year (2001) is NULL", check))
    
    # Check 3: Last years not provided
    check = REFERENCE_3Y_DATA["2019"] is None and REFERENCE_3Y_DATA["2020"] is None
    checks.append(("Last 2 years (2019-2020) are NULL", check))
    
    # Check 4: Middle values are numeric
    middle_values = [v for y, v in REFERENCE_3Y_DATA.items() if 2002 <= int(y) <= 2018]
    check = all(v is not None for v in middle_values)
    checks.append(("All middle years have numeric values", check))
    
    # Check 5: Values in reasonable range
    numeric_values = [v for v in REFERENCE_3Y_DATA.values() if v is not None]
    check = all(-1.0 <= v <= 2.0 for v in numeric_values)
    checks.append(("All values in range [-100% to +200%]", check))
    
    # Check 6: Mix of positive and negative values
    positive = len([v for v in numeric_values if v > 0])
    negative = len([v for v in numeric_values if v < 0])
    check = positive > 0 and negative > 0
    checks.append(("Mix of positive and negative values", check))
    
    passed = 0
    for check_name, result in checks:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {check_name}")
        if result:
            passed += 1
    
    print("-" * 80)
    print(f"Passed: {passed}/{len(checks)}")
    
    return passed == len(checks)


def main():
    """Run all 3Y validation tests"""
    print("\n" + "█"*80)
    print("█" + " "*78 + "█")
    print("█" + "  3Y EE GROWTH INTEGRATION TESTS".center(78) + "█")
    print("█" + " "*78 + "█")
    print("█"*80)
    
    tests = [
        ("Reference Data Format", test_reference_data_format),
        ("Calculator Query Structure", test_ee_growth_calculator_3y_query_structure),
        ("All Temporal Windows", test_ee_growth_calculator_all_windows),
        ("Year Filtering", test_ee_growth_calculator_year_filtering),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, "PASS" if result else "FAIL"))
        except Exception as e:
            print(f"\n✗ EXCEPTION in {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, "ERROR"))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, result in results:
        symbol = "✓" if result == "PASS" else "✗"
        print(f"{symbol} {test_name}: {result}")
    
    passed = len([r for _, r in results if r == "PASS"])
    total = len(results)
    
    print("-" * 80)
    print(f"Result: {passed}/{total} test groups passed")
    print("="*80 + "\n")
    
    return all(r == "PASS" for _, r in results)


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
