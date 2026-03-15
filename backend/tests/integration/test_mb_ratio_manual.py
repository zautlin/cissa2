#!/usr/bin/env python
# ============================================================================
# Manual Test Script for MB Ratio Implementation
# ============================================================================
"""
This script tests the MB Ratio implementation without requiring a running server.
It verifies:
1. Config loading
2. Pydantic model validation
3. SQL query generation
4. Parameter handling
"""

import sys
from pathlib import Path
from uuid import UUID

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.ratio_metrics import MetricDefinition, RatioMetricsResponse
from app.services.ratio_metrics_calculator import RatioMetricsCalculator
import json


def test_config_loading():
    """Test that config loads correctly"""
    print("=" * 70)
    print("TEST 1: Loading ratio_metrics.json config")
    print("=" * 70)
    
    config_path = Path("backend/app/config/ratio_metrics.json")
    
    if not config_path.exists():
        print(f"❌ Config file not found at {config_path}")
        return False
    
    with open(config_path) as f:
        config = json.load(f)
    
    print(f"✓ Config loaded successfully")
    print(f"✓ Number of metrics: {len(config['metrics'])}")
    
    for metric in config['metrics']:
        print(f"  - {metric['id']}: {metric['display_name']}")
    
    return True


def test_metric_definition_validation():
    """Test Pydantic model validation"""
    print("\n" + "=" * 70)
    print("TEST 2: Validating MetricDefinition model")
    print("=" * 70)
    
    metric_data = {
        "id": "mb_ratio",
        "display_name": "MB Ratio",
        "description": "Market-to-Book Ratio",
        "formula_type": "ratio",
        "numerator": {
            "metric_name": "Calc MC",
            "parameter_dependent": False
        },
        "denominator": {
            "metric_name": "Calc EE",
            "parameter_dependent": False
        },
        "operation": "divide",
        "null_handling": "skip_year",
        "negative_handling": "return_null"
    }
    
    try:
        metric_def = MetricDefinition(**metric_data)
        print(f"✓ MetricDefinition created successfully")
        print(f"  - ID: {metric_def.id}")
        print(f"  - Display Name: {metric_def.display_name}")
        print(f"  - Formula Type: {metric_def.formula_type}")
        print(f"  - Numerator: {metric_def.numerator['metric_name']}")
        print(f"  - Denominator: {metric_def.denominator['metric_name']}")
        return True
    except Exception as e:
        print(f"❌ Error validating MetricDefinition: {e}")
        return False


def test_sql_query_generation():
    """Test SQL query generation"""
    print("\n" + "=" * 70)
    print("TEST 3: SQL Query Generation")
    print("=" * 70)
    
    metric_def = MetricDefinition(
        id="mb_ratio",
        display_name="MB Ratio",
        description="Market-to-Book Ratio",
        formula_type="ratio",
        numerator={"metric_name": "Calc MC", "parameter_dependent": False},
        denominator={"metric_name": "Calc EE", "parameter_dependent": False},
        operation="divide",
        null_handling="skip_year",
        negative_handling="return_null"
    )
    
    # Test with 1Y window
    print("\n--- Testing 1Y (Annual) Window ---")
    calc_1y = RatioMetricsCalculator(metric_def, "1Y")
    sql_1y, params_1y = calc_1y.build_query(
        tickers=["AAPL"],
        dataset_id=UUID("12345678-1234-1234-1234-123456789012"),
        param_set_id=UUID("87654321-4321-4321-4321-210987654321")
    )
    
    print("✓ Generated SQL for 1Y window:")
    print(f"  - Window clause: {calc_1y.rows_between}")
    print(f"  - Query length: {len(sql_1y)} chars")
    print(f"  - Parameters: {len(params_1y)}")
    
    # Test with 3Y window
    print("\n--- Testing 3Y (3-Year Rolling Average) Window ---")
    calc_3y = RatioMetricsCalculator(metric_def, "3Y")
    sql_3y, params_3y = calc_3y.build_query(
        tickers=["AAPL", "MSFT"],
        dataset_id=UUID("12345678-1234-1234-1234-123456789012"),
        param_set_id=UUID("87654321-4321-4321-4321-210987654321")
    )
    
    print("✓ Generated SQL for 3Y window:")
    print(f"  - Window clause: {calc_3y.rows_between}")
    print(f"  - Query length: {len(sql_3y)} chars")
    print(f"  - Parameters: {len(params_3y)}")
    print(f"  - Tickers: {params_3y.get('ticker_0')}, {params_3y.get('ticker_1')}")
    
    # Test with year filters
    print("\n--- Testing with Year Filters (2015-2023) ---")
    sql_filtered, params_filtered = calc_3y.build_query(
        tickers=["AAPL"],
        dataset_id=UUID("12345678-1234-1234-1234-123456789012"),
        param_set_id=UUID("87654321-4321-4321-4321-210987654321"),
        start_year=2015,
        end_year=2023
    )
    
    print("✓ Generated SQL with year filters:")
    print(f"  - Start year: {params_filtered.get('start_year')}")
    print(f"  - End year: {params_filtered.get('end_year')}")
    
    # Verify SQL structure
    print("\n--- Verifying SQL Structure ---")
    required_keywords = [
        "numerator_rolling",
        "denominator_rolling",
        "FULL OUTER JOIN",
        "CASE",
        "AVG",
        "OVER",
        "PARTITION BY",
        "ORDER BY"
    ]
    
    for keyword in required_keywords:
        if keyword in sql_3y:
            print(f"✓ Contains: {keyword}")
        else:
            print(f"❌ Missing: {keyword}")
            return False
    
    return True


def test_temporal_windows():
    """Test all temporal windows"""
    print("\n" + "=" * 70)
    print("TEST 4: All Temporal Windows")
    print("=" * 70)
    
    metric_def = MetricDefinition(
        id="mb_ratio",
        display_name="MB Ratio",
        description="Test",
        formula_type="ratio",
        numerator={"metric_name": "Calc MC", "parameter_dependent": False},
        denominator={"metric_name": "Calc EE", "parameter_dependent": False},
        operation="divide",
        null_handling="skip_year",
        negative_handling="return_null"
    )
    
    windows = {
        "1Y": "ROWS BETWEEN 0 PRECEDING AND CURRENT ROW",
        "3Y": "ROWS BETWEEN 2 PRECEDING AND CURRENT ROW",
        "5Y": "ROWS BETWEEN 4 PRECEDING AND CURRENT ROW",
        "10Y": "ROWS BETWEEN 9 PRECEDING AND CURRENT ROW"
    }
    
    for window, expected_clause in windows.items():
        calc = RatioMetricsCalculator(metric_def, window)
        if expected_clause in calc.rows_between:
            print(f"✓ {window}: {expected_clause}")
        else:
            print(f"❌ {window}: Got {calc.rows_between}")
            return False
    
    # Test invalid window
    print("\n--- Testing Invalid Window ---")
    try:
        calc = RatioMetricsCalculator(metric_def, "2Y")
        print(f"❌ Should have raised ValueError for invalid window")
        return False
    except ValueError as e:
        print(f"✓ Correctly rejected invalid window: {e}")
    
    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("MB RATIO IMPLEMENTATION - MANUAL TESTS")
    print("=" * 70)
    
    tests = [
        ("Config Loading", test_config_loading),
        ("Metric Definition Validation", test_metric_definition_validation),
        ("SQL Query Generation", test_sql_query_generation),
        ("Temporal Windows", test_temporal_windows),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
