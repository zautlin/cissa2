#!/usr/bin/env python
# ============================================================================
# Manual Test Script for Revenue Growth Implementation
# ============================================================================
"""
This script tests the Revenue Growth implementation without requiring a running server.
It verifies:
1. Config loading (revenue_growth metric)
2. Pydantic model validation for revenue_growth
3. SQL query generation for 1Y/3Y/5Y/10Y windows
4. Parameter handling and year filtering
"""

import sys
from pathlib import Path
from uuid import UUID
import json

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.ratio_metrics import MetricDefinition
from app.services.revenue_growth_calculator import RevenueGrowthCalculator


def test_revenue_growth_in_config():
    """Test that revenue_growth metric exists in config"""
    print("=" * 70)
    print("TEST 1: Checking revenue_growth in ratio_metrics.json")
    print("=" * 70)
    
    config_path = Path("backend/app/config/ratio_metrics.json")
    
    if not config_path.exists():
        print(f"❌ Config file not found at {config_path}")
        return False
    
    with open(config_path) as f:
        config = json.load(f)
    
    # Find revenue_growth metric
    revenue_growth = None
    for metric in config['metrics']:
        if metric['id'] == 'revenue_growth':
            revenue_growth = metric
            break
    
    if not revenue_growth:
        print("❌ revenue_growth metric not found in config")
        return False
    
    print("✓ revenue_growth metric found in config")
    print(f"  - Display Name: {revenue_growth['display_name']}")
    print(f"  - Formula Type: {revenue_growth['formula_type']}")
    print(f"  - Metric Name: {revenue_growth.get('metric_name', 'N/A')}")
    print(f"  - Data Source: {revenue_growth.get('data_source', 'N/A')}")
    
    return True


def test_metric_definition_revenue_growth():
    """Test Pydantic model validation for revenue_growth"""
    print("\n" + "=" * 70)
    print("TEST 2: Validating MetricDefinition for revenue_growth")
    print("=" * 70)
    
    metric_data = {
        "id": "revenue_growth",
        "display_name": "Revenue Growth",
        "description": "Year-over-year revenue growth",
        "formula_type": "revenue_growth",
        "metric_name": "REVENUE",
        "metric_source": "fundamentals",
        "data_source": "fundamentals",
        "data_source_field": "numeric_value",
        "parameter_dependent": False,
        "requires_prior_year": True,
        "operation": "growth",
        "null_handling": "skip_year",
        "negative_handling": "use_absolute"
    }
    
    try:
        metric_def = MetricDefinition(**metric_data)
        print("✓ MetricDefinition created successfully")
        print(f"  - ID: {metric_def.id}")
        print(f"  - Display Name: {metric_def.display_name}")
        print(f"  - Formula Type: {metric_def.formula_type}")
        print(f"  - Metric Name: {metric_def.metric_name}")
        print(f"  - Requires Prior Year: {metric_def.requires_prior_year}")
        return True, metric_def
    except Exception as e:
        print(f"❌ Error validating MetricDefinition: {e}")
        return False, None


def test_sql_generation_1y(metric_def):
    """Test SQL generation for 1Y window"""
    print("\n" + "=" * 70)
    print("TEST 3: SQL Query Generation - 1Y Window (Simple YoY)")
    print("=" * 70)
    
    try:
        calc = RevenueGrowthCalculator(metric_def, "1Y")
        
        dataset_id = UUID("12345678-1234-5678-1234-567812345678")
        sql, params = calc.build_query(
            tickers=["CSL"],
            dataset_id=dataset_id
        )
        
        print("✓ SQL query generated successfully")
        print(f"\nGenerated SQL (first 500 chars):")
        print("-" * 70)
        print(sql[:500] + "...")
        print("-" * 70)
        
        print(f"\nParameters:")
        for key, value in params.items():
            print(f"  - {key}: {value}")
        
        # Verify key components
        checks = [
            ("revenue_data CTE", "WITH revenue_data AS" in sql),
            ("revenue_rolling CTE", "revenue_rolling AS" in sql),
            ("revenue_with_lag CTE", "revenue_with_lag AS" in sql),
            ("LAG function", "LAG(revenue_rolling_avg)" in sql),
            ("NULL check", "prior_year_avg_revenue IS NULL" in sql),
            ("Division logic", "/ ABS(prior_year_avg_revenue)" in sql),
            ("fundamentals table", "cissa.fundamentals" in sql),
        ]
        
        print(f"\nSQL Structure Verification:")
        all_passed = True
        for check_name, result in checks:
            status = "✓" if result else "❌"
            print(f"  {status} {check_name}")
            if not result:
                all_passed = False
        
        return all_passed
    
    except Exception as e:
        print(f"❌ Error generating SQL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_sql_generation_windows(metric_def):
    """Test SQL generation for all temporal windows"""
    print("\n" + "=" * 70)
    print("TEST 4: SQL Query Generation - All Windows (1Y/3Y/5Y/10Y)")
    print("=" * 70)
    
    dataset_id = UUID("12345678-1234-5678-1234-567812345678")
    windows = ["1Y", "3Y", "5Y", "10Y"]
    rows_between_expected = {
        "1Y": 0,
        "3Y": 2,
        "5Y": 4,
        "10Y": 9
    }
    
    all_passed = True
    for window in windows:
        try:
            calc = RevenueGrowthCalculator(metric_def, window)
            sql, params = calc.build_query(
                tickers=["CSL"],
                dataset_id=dataset_id
            )
            
            expected_rows = rows_between_expected[window]
            actual_rows = params.get("rows_between")
            
            if actual_rows == expected_rows:
                print(f"✓ {window}: rows_between = {actual_rows} (correct)")
            else:
                print(f"❌ {window}: rows_between = {actual_rows}, expected {expected_rows}")
                all_passed = False
        
        except Exception as e:
            print(f"❌ {window}: Error - {e}")
            all_passed = False
    
    return all_passed


def test_year_filtering(metric_def):
    """Test year filtering in SQL"""
    print("\n" + "=" * 70)
    print("TEST 5: Year Filtering in SQL")
    print("=" * 70)
    
    dataset_id = UUID("12345678-1234-5678-1234-567812345678")
    
    try:
        calc = RevenueGrowthCalculator(metric_def, "1Y")
        sql, params = calc.build_query(
            tickers=["CSL"],
            dataset_id=dataset_id,
            start_year=2010,
            end_year=2020
        )
        
        print("✓ SQL generated with year filtering")
        
        checks = [
            ("start_year parameter", "start_year" in params and params["start_year"] == 2010),
            ("end_year parameter", "end_year" in params and params["end_year"] == 2020),
            ("WHERE clause", "WHERE fiscal_year" in sql),
        ]
        
        all_passed = True
        for check_name, result in checks:
            status = "✓" if result else "❌"
            print(f"  {status} {check_name}")
            if not result:
                all_passed = False
        
        return all_passed
    
    except Exception as e:
        print(f"❌ Error with year filtering: {e}")
        return False


def test_multi_ticker(metric_def):
    """Test multi-ticker support"""
    print("\n" + "=" * 70)
    print("TEST 6: Multi-Ticker Support")
    print("=" * 70)
    
    dataset_id = UUID("12345678-1234-5678-1234-567812345678")
    tickers = ["CSL", "XYZ", "ABC"]
    
    try:
        calc = RevenueGrowthCalculator(metric_def, "1Y")
        sql, params = calc.build_query(
            tickers=tickers,
            dataset_id=dataset_id
        )
        
        print(f"✓ SQL generated for {len(tickers)} tickers")
        
        if params["tickers"] == tickers:
            print(f"  ✓ Tickers parameter correct: {params['tickers']}")
        else:
            print(f"  ❌ Tickers parameter mismatch")
            return False
        
        # Verify PARTITION BY ticker exists (for multi-ticker isolation)
        if "PARTITION BY ticker" in sql:
            print(f"  ✓ PARTITION BY ticker found (correct isolation)")
        else:
            print(f"  ❌ PARTITION BY ticker missing")
            return False
        
        return True
    
    except Exception as e:
        print(f"❌ Error with multi-ticker: {e}")
        return False


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " REVENUE GROWTH IMPLEMENTATION - MANUAL TEST ".center(68) + "║")
    print("╚" + "=" * 68 + "╝")
    
    results = []
    
    # Test 1: Config loading
    results.append(("Config Loading", test_revenue_growth_in_config()))
    
    # Test 2: Metric definition
    test2_result, metric_def = test_metric_definition_revenue_growth()
    results.append(("Metric Definition Validation", test2_result))
    
    if not metric_def:
        print("\n❌ Cannot continue without metric definition")
        return
    
    # Test 3: SQL generation 1Y
    results.append(("SQL Generation - 1Y", test_sql_generation_1y(metric_def)))
    
    # Test 4: SQL generation all windows
    results.append(("SQL Generation - All Windows", test_sql_generation_windows(metric_def)))
    
    # Test 5: Year filtering
    results.append(("Year Filtering", test_year_filtering(metric_def)))
    
    # Test 6: Multi-ticker
    results.append(("Multi-Ticker Support", test_multi_ticker(metric_def)))
    
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
        print(f"\n❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
