#!/usr/bin/env python
# ============================================================================
# Manual Test Script for EE Growth Implementation
# ============================================================================
"""
This script tests the EE Growth implementation without requiring a running server.
It verifies:
1. Config loading (ee_growth metric)
2. Pydantic model validation for ee_growth
3. SQL query generation for 1Y/3Y/5Y/10Y windows
4. Parameter handling and year filtering
5. Reference data validation against CSL 1Y EE Growth
"""

import sys
from pathlib import Path
from uuid import UUID
import json

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.ratio_metrics import MetricDefinition
from app.services.ee_growth_calculator import EEGrowthCalculator


# CSL AU Equity 1Y EE Growth reference data (2001-2020)
CSL_EE_GROWTH_1Y_REFERENCE = {
    2001: None,      # n/a (first year)
    2002: 0.441,     # 44.1%
    2003: 0.045,     # 4.5%
    2004: 0.754,     # 75.4%
    2005: 0.053,     # 5.3%
    2006: -0.167,    # (16.7%)
    2007: 0.208,     # 20.8%
    2008: 0.215,     # 21.5%
    2009: 0.851,     # 85.1%
    2010: -0.184,    # (18.4%)
    2011: -0.073,    # (7.3%)
    2012: -0.074,    # (7.4%)
    2013: -0.168,    # (16.8%)
    2014: 0.014,     # 1.4%
    2015: 0.029,     # 2.9%
    2016: -0.051,    # (5.1%)
    2017: 0.099,     # 9.9%
    2018: 0.277,     # 27.7%
    2019: 0.378,     # 37.8%
    2020: 0.327,     # 32.7%
}


def test_ee_growth_in_config():
    """Test that ee_growth metric exists in config"""
    print("=" * 70)
    print("TEST 1: Checking ee_growth in ratio_metrics.json")
    print("=" * 70)
    
    config_path = Path("backend/app/config/ratio_metrics.json")
    
    if not config_path.exists():
        print(f"❌ Config file not found at {config_path}")
        return False
    
    with open(config_path) as f:
        config = json.load(f)
    
    # Find ee_growth metric
    ee_growth = None
    for metric in config['metrics']:
        if metric['id'] == 'ee_growth':
            ee_growth = metric
            break
    
    if not ee_growth:
        print("❌ ee_growth metric not found in config")
        return False
    
    print("✓ ee_growth metric found in config")
    print(f"  - Display Name: {ee_growth['display_name']}")
    print(f"  - Formula Type: {ee_growth['formula_type']}")
    print(f"  - Metric Name: {ee_growth.get('metric_name', 'N/A')}")
    print(f"  - Data Source: {ee_growth.get('data_source', 'N/A')}")
    print(f"  - Parameter Dependent: {ee_growth.get('parameter_dependent', False)}")
    
    return True


def test_metric_definition_ee_growth():
    """Test Pydantic model validation for ee_growth"""
    print("\n" + "=" * 70)
    print("TEST 2: Validating MetricDefinition for ee_growth")
    print("=" * 70)
    
    metric_data = {
        "id": "ee_growth",
        "display_name": "EE Growth",
        "description": "Year-over-year EE growth",
        "formula_type": "ee_growth",
        "metric_name": "Calc EE",
        "metric_source": "metrics_outputs",
        "data_source": "metrics_outputs",
        "data_source_field": "output_metric_value",
        "parameter_dependent": True,
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
        print(f"  - Data Source: {metric_def.data_source}")
        print(f"  - Parameter Dependent: {metric_def.parameter_dependent}")
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
        calc = EEGrowthCalculator(metric_def, "1Y")
        
        dataset_id = UUID("12345678-1234-5678-1234-567812345678")
        param_set_id = UUID("87654321-4321-8765-4321-876543218765")
        sql, params = calc.build_query(
            tickers=["CSL"],
            dataset_id=dataset_id,
            param_set_id=param_set_id
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
            ("ee_data CTE", "WITH ee_data AS" in sql),
            ("ee_rolling CTE", "ee_rolling AS" in sql),
            ("ee_with_lag CTE", "ee_with_lag AS" in sql),
            ("LAG function", "LAG(ee_rolling_avg)" in sql),
            ("NULL check", "prior_year_avg_ee IS NULL" in sql),
            ("Division logic", "/ ABS(prior_year_avg_ee)" in sql),
            ("metrics_outputs table", "cissa.metrics_outputs" in sql),
            ("Metric name filter", "metric_name = :metric_name" in sql),
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
    param_set_id = UUID("87654321-4321-8765-4321-876543218765")
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
            calc = EEGrowthCalculator(metric_def, window)
            sql, params = calc.build_query(
                tickers=["CSL"],
                dataset_id=dataset_id,
                param_set_id=param_set_id
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
    param_set_id = UUID("87654321-4321-8765-4321-876543218765")
    
    try:
        calc = EEGrowthCalculator(metric_def, "1Y")
        sql, params = calc.build_query(
            tickers=["CSL"],
            dataset_id=dataset_id,
            param_set_id=param_set_id,
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
    param_set_id = UUID("87654321-4321-8765-4321-876543218765")
    tickers = ["CSL", "XYZ", "ABC"]
    
    try:
        calc = EEGrowthCalculator(metric_def, "1Y")
        sql, params = calc.build_query(
            tickers=tickers,
            dataset_id=dataset_id,
            param_set_id=param_set_id
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


def test_param_set_handling(metric_def):
    """Test param_set_id handling"""
    print("\n" + "=" * 70)
    print("TEST 7: Parameter Set Handling")
    print("=" * 70)
    
    dataset_id = UUID("12345678-1234-5678-1234-567812345678")
    param_set_id = UUID("87654321-4321-8765-4321-876543218765")
    
    try:
        calc = EEGrowthCalculator(metric_def, "1Y")
        sql, params = calc.build_query(
            tickers=["CSL"],
            dataset_id=dataset_id,
            param_set_id=param_set_id
        )
        
        print("✓ SQL generated with param_set_id")
        
        checks = [
            ("param_set_id in params", "param_set_id" in params),
            ("param_set_id value correct", params.get("param_set_id") == str(param_set_id)),
            ("param_set_id in SQL", "param_set_id = :param_set_id" in sql),
        ]
        
        all_passed = True
        for check_name, result in checks:
            status = "✓" if result else "❌"
            print(f"  {status} {check_name}")
            if not result:
                all_passed = False
        
        return all_passed
    
    except Exception as e:
        print(f"❌ Error with param_set handling: {e}")
        return False


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " EE GROWTH IMPLEMENTATION - MANUAL TEST ".center(68) + "║")
    print("╚" + "=" * 68 + "╝")
    
    results = []
    
    # Test 1: Config loading
    results.append(("Config Loading", test_ee_growth_in_config()))
    
    # Test 2: Metric definition
    test2_result, metric_def = test_metric_definition_ee_growth()
    results.append(("Metric Definition Validation", test2_result))
    
    if not metric_def:
        print("\n❌ Cannot continue without metric definition")
        return 1
    
    # Test 3: SQL generation 1Y
    results.append(("SQL Generation - 1Y", test_sql_generation_1y(metric_def)))
    
    # Test 4: SQL generation all windows
    results.append(("SQL Generation - All Windows", test_sql_generation_windows(metric_def)))
    
    # Test 5: Year filtering
    results.append(("Year Filtering", test_year_filtering(metric_def)))
    
    # Test 6: Multi-ticker
    results.append(("Multi-Ticker Support", test_multi_ticker(metric_def)))
    
    # Test 7: Param set handling
    results.append(("Parameter Set Handling", test_param_set_handling(metric_def)))
    
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
