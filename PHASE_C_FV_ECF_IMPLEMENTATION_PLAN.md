# Phase C: FV ECF Integration into Runtime-Metrics Orchestration

## Executive Summary

This phase integrates FV ECF (1Y, 3Y, 5Y, 10Y) calculation into the `runtime-metrics` endpoint as Phase 4. FV ECF is **parameter-dependent** (requires param_set_id for franking treatment, tax rates, franking credit values) and must be calculated at runtime, not pre-computed.

The refactored FV ECF service is complete and tested (46 tests passing). It now needs to be integrated into the existing runtime-metrics orchestration flow alongside Beta Rounding, Risk-Free Rate, and Cost of Equity calculations.

---

## Architecture

### Current Runtime-Metrics Orchestration (3 phases)
```
POST /api/v1/metrics/runtime-metrics
  → dataset_id, param_set_id, parameter_id (optional)
  
  Phase 1: Beta Rounding (param-dependent)
    - Fetch pre-computed Beta (param_set_id=NULL)
    - Apply parameter-specific rounding/approach
    - Store 11,000 records with param_set_id
    
  Phase 2: Risk-Free Rate (parameter-independent)
    - Calculate from monthly bond yields
    - Store 11,000 records with param_set_id
    
  Phase 3: Cost of Equity (param-dependent)
    - Fetch Beta Rounding results
    - Fetch Rf results
    - Calculate KE = Rf + Beta × RiskPremium
    - Store 11,000 records with param_set_id
```

### Proposed Addition: Phase 4
```
Phase 4: FV ECF (param-dependent)
  - Fetch Non Div ECF (pre-computed in ingestion)
  - Fetch fundamentals (dividends, franking from fundamentals table)
  - Fetch lagged KE (current-year KE from Phase 3 results, lagged on-the-fly)
  - Load parameters: include_franking_credits_tsr, tax_rate_franking_credits, value_of_franking_credits
  - Calculate all 4 intervals (1Y, 3Y, 5Y, 10Y) in single call
  - Store 4 × ~9,000 = ~36,000 records with param_set_id
```

---

## Data Dependencies

### Input Data Sources

| Data | Source | Availability | Notes |
|------|--------|--------------|-------|
| Non Div ECF | metrics_outputs (pre-computed in ingestion) | Phase 2 orchestration | Parameter-independent |
| Dividends | fundamentals table | Always available | From financial statements |
| Franking | fundamentals table | Always available | Australia-specific |
| Calc KE (current year) | metrics_outputs (Phase 3 results) | Phase 3 complete | Runtime calculation |
| Calc KE (prior year) | metrics_outputs (Phase 3 results) | Need to lag on-the-fly | For ke_open |
| Parameters | cissa.parameter_sets table | Loaded with param_set_id | Via ParameterRepository |

### Parameter Names in `cissa.parameter_sets.param_overrides`
- `include_franking_credits_tsr` (boolean: true/false or "Yes"/"No")
- `tax_rate_franking_credits` (float: 0.0-1.0)
- `value_of_franking_credits` (float: 0.0-1.0)

### Temporal Window Behavior
- **Input**: Data spanning e.g., 2000-2020 (21 years)
- **1Y results**: 2000-2020 (all 21 years, all have sufficient history)
- **3Y results**: 2002-2020 (19 years, first 2 have NULL)
- **5Y results**: 2004-2020 (17 years, first 4 have NULL)
- **10Y results**: 2009-2020 (12 years, first 9 have NULL)
- **Expected row count**: Varies per interval, all with NaN for insufficient history

---

## Implementation Tasks

### Task 1: Modify FVECFService for Runtime Context
**File**: `backend/app/services/fv_ecf_service.py`

**Scope**: Add ~200 lines for runtime capabilities

**Changes Required**:

1. **New method: `calculate_fv_ecf_for_runtime()`**
   - Signature: `async def calculate_fv_ecf_for_runtime(dataset_id: UUID, param_set_id: UUID, parameter_id: Optional[UUID] = None) -> dict`
   - Returns: `{status: "success"|"error", total_inserted: int, intervals_summary: dict, duration_seconds: float, message: str}`
   - Similar structure to existing `calculate_fv_ecf_metrics()` but:
     - Loads parameters from param_set_id
     - Fetches lagged KE from Phase 3 results
     - Handles parameter-dependent calculations
     - Stores all 4 metrics in single orchestration call

2. **New method: `_load_parameters_from_param_set()`**
   - Fetch param_overrides JSONB from cissa.parameter_sets
   - Map parameter names:
     - `include_franking_credits_tsr` (bool) → `incl_franking` ("Yes"/"No")
     - `tax_rate_franking_credits` (float) → `frank_tax_rate`
     - `value_of_franking_credits` (float) → `value_franking_cr`
   - Apply defaults if parameters missing:
     - `incl_franking`: "No" (conservative default)
     - `frank_tax_rate`: 0.30
     - `value_franking_cr`: 0.75
   - Returns: `dict` with mapped parameter names

3. **New method: `_fetch_lagged_ke()`**
   - Query: Fetch current-year Calc KE from metrics_outputs (param_set_id-specific)
   - Transform: Create lag on fiscal_year within each ticker
     - Group by ticker, sort by fiscal_year ascending
     - Shift KE values down by 1 to create prior-year reference
     - Result: DataFrame with (ticker, fiscal_year, ke_current, ke_open) where ke_open = prior-year KE
   - Handle first year: ke_open = NaN (expected)
   - Returns: DataFrame with ke_open column

4. **New method: `_insert_fv_ecf_batch()`**
   - Batch insert ~36,000 records (4 intervals × ~9,000 each)
   - Use existing batch pattern: 1,000 records per batch
   - Insert template:
     ```sql
     INSERT INTO metrics_outputs 
       (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata)
     VALUES (:dataset_id, :param_set_id, :ticker, :fiscal_year, :output_metric_name, :output_metric_value, :metadata)
     ```
   - Output metric names:
     - "Calc 1Y FV ECF"
     - "Calc 3Y FV ECF"
     - "Calc 5Y FV ECF"
     - "Calc 10Y FV ECF"
   - Metadata: Include parameters used, interval, calculation timestamp

5. **Update existing method: `_calculate_fv_ecf_for_interval()`**
   - Already takes DataFrame and interval as parameters
   - Already has helper methods that accept params dict
   - No changes needed - it's ready for runtime use

6. **Ensure Non Div ECF fetch works**
   - Verify `_fetch_fundamentals_data()` includes Non Div ECF from metrics_outputs
   - Confirm it works without param_set_id filter (parameter-independent data)

---

### Task 2: Update RuntimeMetricsOrchestrationService
**File**: `backend/app/services/runtime_metrics_orchestration_service.py`

**Scope**: Add ~50 lines for Phase 4 orchestration

**Changes Required**:

1. **New method: `_orchestrate_fv_ecf()`**
   - Signature: Similar to `_orchestrate_beta_rounding()`, `_orchestrate_risk_free_rate()`, etc.
   - Calls: `FVECFService.calculate_fv_ecf_for_runtime(dataset_id, param_set_id, resolved_param_id)`
   - Returns: `{status: "success"|"error", results_count: int, message: str}`
   - Handles errors: Log and continue (partial results), don't fail-fast

2. **Update main orchestration method: `orchestrate_runtime_metrics()`**
   - Add Phase 4 after Phase 3 completion
   - Dependency: Phase 4 runs SEQUENTIAL after Phase 3 (needs Calc KE data stored)
   - Execution order:
     ```python
     Phase 1: Beta Rounding (sequential)
       ↓ (on success)
     Phase 2: Risk-Free Rate (sequential)
       ↓ (on success)
     Phase 3: Cost of Equity (sequential, depends on Beta & Rf)
       ↓ (on success)
     Phase 4: FV ECF (sequential, depends on Calc KE)
       ↓ (on success OR error, continue)
     Return result
     ```

3. **Update response structure**
   - Add "fv_ecf" key to metrics_completed dict
   - Structure: `metrics_completed["fv_ecf"] = {status, results_count, duration_seconds, message}`
   - Maintain metrics_completed for all 4 phases even if some fail

4. **Update logging**
   - Log Phase 4 start: "Step 3: Running FV ECF (sequential, depends on Calc KE)..."
   - Log Phase 4 progress: Interval calculation completion (1Y, 3Y, 5Y, 10Y)
   - Log Phase 4 completion: "✓ Phase 4 complete: FV ECF X,XXX records"
   - Log Phase 4 errors: "⚠️ Phase 4 warning: {error_message}" (don't fail entire orchestration)

5. **Update response summary**
   - Add execution time for Phase 4
   - Update total execution time to include Phase 4

---

### Task 3: Update API Response Models
**File**: `backend/app/models/schemas.py` or relevant response models file

**Scope**: Extend response models for Phase 4

**Changes Required**:

1. **Update RuntimeMetricsResponse model**
   - Add field: `fv_ecf: dict = Field(description="FV ECF calculation results")`
   - Or extend metrics_completed structure to support Phase 4

2. **Update endpoint docstring**
   - `/api/v1/endpoints/metrics.py` line 1095
   - Add Phase 4 description to orchestration flow
   - Update example response to show fv_ecf in metrics_completed
   - Update execution time estimate from ~45s to ~60-90s

3. **Ensure backward compatibility**
   - Existing clients expecting 3 metrics should still work
   - FV ECF is additive (doesn't change existing Beta/Rf/KE results)
   - Consider adding deprecation notice if version tracking needed

---

### Task 4: Implement Parameter Handling & Validation
**File**: Within FVECFService `_load_parameters_from_param_set()` method

**Scope**: Parameter loading, mapping, validation

**Changes Required**:

1. **Use ParameterRepository**
   - Import: `from ..repositories.parameter_repository import ParameterRepository`
   - Call: `repo.get_parameter_set_by_id(param_set_id)` to fetch param_overrides JSONB
   - Extract: `param_overrides = result.get('param_overrides', {})`

2. **Implement safe mapping**
   ```python
   def _map_parameter_names(param_overrides):
       # Map from cissa.parameter_sets.param_overrides names to FV ECF service names
       incl_franking_raw = param_overrides.get('include_franking_credits_tsr', False)
       # Convert bool to "Yes"/"No"
       incl_franking = "Yes" if incl_franking_raw else "No"
       
       tax_rate = float(param_overrides.get('tax_rate_franking_credits', 0.30))
       franking_cr = float(param_overrides.get('value_of_franking_credits', 0.75))
       
       return {
           'incl_franking': incl_franking,
           'frank_tax_rate': tax_rate,
           'value_franking_cr': franking_cr
       }
   ```

3. **Implement validation**
   - Ensure `incl_franking` is "Yes" or "No"
   - Ensure `frank_tax_rate` is 0.0 ≤ x ≤ 1.0
   - Ensure `value_franking_cr` is 0.0 ≤ x ≤ 1.0
   - Log warnings for out-of-range values, use defaults if invalid
   - Return: `dict` with validated parameters

4. **Apply defaults**
   - If parameters missing: Use conservative defaults
     - `incl_franking`: "No"
     - `frank_tax_rate`: 0.30
     - `value_franking_cr`: 0.75
   - Log: "Using default parameter values"

5. **Pass to calculation methods**
   - Dict structure: `{"incl_franking": "Yes", "frank_tax_rate": 0.30, "value_franking_cr": 0.75}`
   - Pass through `_calculate_fv_ecf_for_interval(df, interval, params)`
   - Existing helper methods already accept this dict structure ✓

---

### Task 5: Implement Lagged KE Fetch
**File**: Within FVECFService `_fetch_lagged_ke()` method

**Scope**: Fetch Calc KE and create fiscal_year lag

**Changes Required**:

1. **Query current-year Calc KE**
   ```sql
   SELECT ticker, fiscal_year, output_metric_value as ke_current
   FROM metrics_outputs
   WHERE dataset_id = :dataset_id 
     AND output_metric_name = 'Calc KE'
     AND param_set_id = :param_set_id
   ORDER BY ticker, fiscal_year
   ```
   - Param_set_id-specific (uses results from Phase 3 of same orchestration run)

2. **Transform to lagged DataFrame**
   ```python
   # Group by ticker, sort by fiscal_year
   ke_df = ke_df.sort_values(['ticker', 'fiscal_year'])
   
   # Create lag: ke_open = prior-year KE
   ke_df['ke_open'] = ke_df.groupby('ticker')['ke_current'].shift(1)
   
   # First year of each ticker will have NaN ke_open (expected)
   # Result: DataFrame with (ticker, fiscal_year, ke_current, ke_open)
   ```

3. **Return prepared DataFrame**
   - Columns: ticker, fiscal_year, ke_open
   - First year per ticker: ke_open = NaN
   - Ready to merge with fundamentals on (ticker, fiscal_year)

4. **Error handling**
   - Empty result: Log warning "No Calc KE data found" but continue
   - If ke_open all NaN: Log warning but continue (will result in NaN FV_ECF)
   - Missing ticker: NaN ke_open for that ticker (expected behavior)

---

### Task 6: Write Parameter Loading Tests
**File**: Add to `backend/tests/test_fv_ecf_service.py`

**Scope**: New test class `TestParameterLoading`

**Test Cases**:
1. `test_load_parameters_with_all_fields_present()` - Happy path
2. `test_load_parameters_maps_bool_to_yes_no()` - Convert `include_franking_credits_tsr: true` to `incl_franking: "Yes"`
3. `test_load_parameters_applies_defaults_when_missing()` - Use defaults if param_overrides empty
4. `test_load_parameters_validates_tax_rate_range()` - Warn if outside 0.0-1.0
5. `test_load_parameters_validates_franking_cr_range()` - Warn if outside 0.0-1.0
6. `test_load_parameters_converts_types()` - Ensure float conversion works
7. `test_load_parameters_case_insensitive_incl_franking()` - Both "Yes" and "yes" work

---

### Task 7: Write Lagged KE Fetch Tests
**File**: Add to `backend/tests/test_fv_ecf_service.py`

**Scope**: New test class `TestLaggedKEFetch`

**Test Cases**:
1. `test_fetch_lagged_ke_creates_lag()` - First year ke_open=NaN, subsequent years get prior KE
2. `test_fetch_lagged_ke_respects_ticker_groups()` - Lagging doesn't cross ticker boundaries
3. `test_fetch_lagged_ke_sorted_by_fiscal_year()` - Result maintains fiscal_year order
4. `test_fetch_lagged_ke_empty_result()` - Returns empty DataFrame gracefully
5. `test_fetch_lagged_ke_single_ticker()` - Works with single ticker
6. `test_fetch_lagged_ke_multiple_tickers()` - Works with multiple tickers independently
7. `test_fetch_lagged_ke_nan_handling()` - NaN KE values propagate correctly

---

### Task 8: Write Runtime Integration Tests
**File**: Add to `backend/tests/integration/test_fv_ecf_integration.py`

**Scope**: New test class `TestFVECFRuntime`

**Test Cases**:
1. `test_calculate_fv_ecf_for_runtime_returns_correct_structure()` - Check response dict keys
2. `test_calculate_fv_ecf_for_runtime_all_intervals_calculated()` - All 4 intervals present
3. `test_calculate_fv_ecf_for_runtime_row_counts_correct()` - 1Y>3Y>5Y>10Y
4. `test_calculate_fv_ecf_for_runtime_stores_with_param_set_id()` - Verify param_set_id in results
5. `test_calculate_fv_ecf_for_runtime_temporal_windows_respected()` - NaN for insufficient history
6. `test_calculate_fv_ecf_for_runtime_with_franking_yes()` - Includes franking in calculations
7. `test_calculate_fv_ecf_for_runtime_with_franking_no()` - Excludes franking in calculations
8. `test_calculate_fv_ecf_for_runtime_parameter_loading_works()` - Parameters loaded correctly
9. `test_calculate_fv_ecf_for_runtime_lagged_ke_correct()` - ke_open values correct

---

### Task 9: Write Orchestration Integration Tests
**File**: Create `backend/tests/integration/test_fv_ecf_orchestration.py`

**Scope**: Test full runtime-metrics endpoint integration

**Test Cases**:
1. `test_orchestrate_runtime_metrics_includes_fv_ecf()` - FV ECF results in response
2. `test_orchestrate_runtime_metrics_fv_ecf_executes_after_koe()` - Verify Phase 4 after Phase 3
3. `test_orchestrate_runtime_metrics_fv_ecf_with_valid_param_set()` - End-to-end with params
4. `test_orchestrate_runtime_metrics_fv_ecf_failure_continues()` - Partial results on error
5. `test_orchestrate_runtime_metrics_all_records_have_param_set_id()` - Verify param_set_id stored
6. `test_orchestrate_runtime_metrics_execution_time_under_limit()` - Performance < 60s
7. `test_orchestrate_runtime_metrics_fv_ecf_metrics_named_correctly()` - Check metric names

---

### Task 10: Write Parameter Variation Tests
**File**: Add to `backend/tests/integration/test_fv_ecf_orchestration.py`

**Scope**: Verify parameter-dependent behavior

**Test Cases**:
1. `test_different_param_sets_different_results()` - Param_set_A vs Param_set_B give different FV_ECF
2. `test_incl_franking_yes_vs_no_different()` - Results differ with/without franking
3. `test_different_tax_rates_different_results()` - Changing tax_rate affects calculations
4. `test_different_franking_cr_different_results()` - Changing franking_cr affects calculations
5. `test_metadata_preserves_parameters_used()` - Store which params used in metadata
6. `test_parameter_defaults_applied()` - Defaults work when params not provided

---

### Task 11: Comprehensive Integration Validation
**File**: Manual testing or additional integration test

**Validate**:
1. **Data Integrity**
   - All Non Div ECF pre-computed and available ✓
   - All Calc KE from Phase 3 available ✓
   - All fundamentals (dividend, franking) available ✓
   - Parameter loading from param_set_id works ✓

2. **Calculation Correctness**
   - 1Y FV ECF formula verified ✓ (from unit tests)
   - 3Y FV ECF formula verified ✓ (from unit tests)
   - 5Y FV ECF formula verified ✓ (from unit tests)
   - 10Y FV ECF formula verified ✓ (from unit tests)

3. **Row Counts**
   - Expected decreasing: 1Y > 3Y > 5Y > 10Y ✓ (from integration tests)
   - All with NaN handling correct ✓

4. **Database Storage**
   - 4 metrics stored: "Calc 1Y FV ECF", "Calc 3Y FV ECF", "Calc 5Y FV ECF", "Calc 10Y FV ECF" ✓
   - All with param_set_id ✓
   - All with correct dataset_id ✓

5. **Performance**
   - Phase 4 execution < 60 seconds ✓
   - Total runtime-metrics < 60 seconds ✓

6. **Error Handling**
   - Missing Non Div ECF → Log warning, NaN FV_ECF ✓
   - Missing Calc KE → Log warning, NaN FV_ECF ✓
   - Invalid parameters → Log warning, use defaults ✓
   - Phase 4 error → Log error, continue, other phases still stored ✓

---

### Task 12: Final Checklist & Validation
**Pre-Deployment Checklist**:

- [ ] Task 1-5 implementation complete
- [ ] FV ECF service compiles and no regressions
- [ ] All 46 existing tests still pass
- [ ] Tasks 6-10 new tests written and passing
- [ ] Task 11 comprehensive validation complete
- [ ] Code reviewed for:
  - Error handling correctness
  - Parameter mapping correctness
  - Temporal window logic correctness
  - Database query correctness
  - Performance acceptable
- [ ] Documentation updated:
  - Endpoint docstring updated
  - Parameter mapping documented
  - Temporal window behavior documented
- [ ] Git commits prepared with clear messages
- [ ] Ready for TRTE/downstream metric integration

---

## Implementation Sequence

The tasks should be executed in this order:

1. **Task 1**: Modify FVECFService (foundational changes)
2. **Task 2**: Update RuntimeMetricsOrchestrationService (depends on Task 1)
3. **Task 3**: Update API response models (depends on Tasks 1-2)
4. **Task 4-5**: Implement parameter loading & lagged KE (can be done during or after Tasks 1-3)
5. **Task 6-7**: Write parameter and lagged KE tests (validate Tasks 4-5)
6. **Task 8-10**: Write integration and orchestration tests (validate all)
7. **Task 11**: Run comprehensive integration validation
8. **Task 12**: Final checklist and deployment preparation

---

## Success Criteria

- [x] All 46 existing FV ECF tests passing
- [ ] FVECFService modified for runtime context
- [ ] RuntimeMetricsOrchestrationService updated with Phase 4
- [ ] API response models extended
- [ ] Parameter loading & validation implemented
- [ ] Lagged KE fetch implemented
- [ ] Parameter loading tests passing
- [ ] Lagged KE fetch tests passing
- [ ] Runtime integration tests passing
- [ ] Orchestration integration tests passing
- [ ] Parameter variation tests passing
- [ ] Full integration validation passing
- [ ] All tests pass (existing + new)
- [ ] Performance < 60 seconds total
- [ ] Code reviewed and documented
- [ ] Ready for TRTE/downstream integration

---

## Files to Modify/Create

### Modified Files
1. `backend/app/services/fv_ecf_service.py` (731 lines → +200)
2. `backend/app/services/runtime_metrics_orchestration_service.py` (342 lines → +50)
3. `backend/app/api/v1/endpoints/metrics.py` (update docstrings)
4. `backend/app/models/schemas.py` (update response models if needed)
5. `backend/tests/test_fv_ecf_service.py` (keep 27, +6 tests)
6. `backend/tests/integration/test_fv_ecf_integration.py` (keep 19, +9 tests)

### New Files
1. `backend/tests/integration/test_fv_ecf_orchestration.py` (~300 lines, 13 tests)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Parameter not in cissa.parameter_sets | Wrong defaults used | Use safe defaults, log warnings, document defaults |
| Lagged KE unavailable (first year) | Row skipped or NaN | Expected behavior, return NaN for ke_open (already handled by unit tests) |
| Non Div ECF missing | FV_ECF=NaN | Log warning, continue, results will be NaN (acceptable) |
| Large data volume (36k+ records) | Slow inserts | Use batch inserts (1000 per batch), parallel Phase 2 if needed (future) |
| param_set_id mismatch | Wrong results stored | Validate param_set_id before calculations, store in metadata |
| Temporal window logic wrong | Incorrect NULLs | Unit tests validate temporal logic ✓ (already passing) |
| Phase 4 failure breaks orchestration | No other metrics stored | Implement partial results (don't fail-fast), log errors |
| Performance degradation | Exceeds 60s target | Profile Phase 4, consider parallelization (future), batch optimization |

---

## Notes for Implementation

1. **Existing Unit Tests Already Passing**: The 27 unit tests for FV ECF helper methods are complete and passing. They validate:
   - Temporal window filtering
   - ECF base calculation with/without franking
   - Single-year FV ECF calculation with correct formulas
   - All edge cases (NaN, zero ke, insufficient history, etc.)
   
2. **Existing Integration Tests Already Passing**: The 19 integration tests validate:
   - Complete FV ECF flow for all 4 intervals
   - Row count hierarchy (1Y > 3Y > 5Y > 10Y)
   - Franking parameter effects
   - Multi-ticker support
   - End-to-end workflow

3. **Refactored Service Is Production-Ready**: The FVECFService with the 3 new helper methods is well-designed:
   - `_validate_temporal_window()`: Simple index-based filtering
   - `_calculate_ecf_base_value()`: Safe parameter handling
   - `_calculate_fv_ecf_single_year()`: Correct formula implementation
   
4. **Parameter Mapping Strategy**:
   - Keep mapping logic centralized in `_load_parameters_from_param_set()`
   - Use consistent dict keys throughout service
   - Apply defaults early, validate once
   - Log parameter values for audit trail

5. **Lagged KE Strategy**:
   - Fetch in separate method for clarity
   - Use groupby/shift for efficiency (vectorized)
   - Merge into fundamentals DataFrame early
   - NaN for first year is expected and handled

6. **Error Handling Philosophy**:
   - Phase 4 errors don't fail entire orchestration (partial results)
   - Log all errors with context (dataset_id, param_set_id, phase)
   - Continue processing other phases even if Phase 4 fails
   - Store what we can calculate, mark failures in metadata

---

## Next Steps

1. Review this plan document
2. Confirm any clarifications or changes
3. Begin implementation with Task 1 (FVECFService modifications)
4. Proceed through Tasks 2-12 in sequence
5. Commit changes with clear messages after each major task
6. Validate all tests pass before moving to next task
7. Document any deviations from plan

This plan ensures FV ECF is properly integrated into the runtime-metrics orchestration while maintaining the quality, testability, and performance standards of the codebase.

