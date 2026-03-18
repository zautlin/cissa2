# CISSA Codebase Quick Reference

## Key File Paths

### Service Layer (L2 Metrics Calculation)
```
/home/ubuntu/cissa/backend/app/services/ter_service.py           (581 lines) - Phase 10c TER calculation
/home/ubuntu/cissa/backend/app/services/fv_ecf_service.py        (1069 lines) - Phase 10b FV_ECF calculation
/home/ubuntu/cissa/backend/app/services/cost_of_equity_service.py (604 lines) - Phase 09 Cost of Equity
/home/ubuntu/cissa/backend/app/services/economic_profit_service.py (520 lines) - Phase 10a Core L2
/home/ubuntu/cissa/backend/app/services/risk_free_rate_service.py (1108 lines) - Phase 08 Risk-Free Rate
/home/ubuntu/cissa/backend/app/services/runtime_metrics_orchestration_service.py (474 lines) - Orchestrator
/home/ubuntu/cissa/backend/app/services/parameter_service.py     (240 lines) - Parameter management
```

### Database & Models
```
/home/ubuntu/cissa/backend/database/schema/schema.sql            (459 lines) - All 12 tables
/home/ubuntu/cissa/backend/database/schema/schema_manager.py     (446 lines) - Schema init + parameter setup
/home/ubuntu/cissa/backend/app/models/metrics_output.py          (68 lines) - ORM model
/home/ubuntu/cissa/backend/app/models/schemas.py                 - Request/response Pydantic models
```

### API Layer
```
/home/ubuntu/cissa/backend/app/api/v1/endpoints/metrics.py       (1233 lines) - All metric endpoints
```

## Core Concepts

### 1. TERService Structure
- **Location**: `/home/ubuntu/cissa/backend/app/services/ter_service.py`
- **Main Method**: `calculate_ter_metrics(dataset_id, param_set_id)`
- **Metrics Produced**: 8 (Calc 1Y/3Y/5Y/10Y TER + TER-KE)
- **Pattern**: Fetch → Merge → Calculate (Vectorized) → Insert (Batch)

### 2. Parameters Table
- **Location**: Schema defined in `/home/ubuntu/cissa/backend/database/schema/schema_manager.py` lines 277-295
- **Key Parameter**: `equity_risk_premium` (default: 5.0, used in KE = Rf + Beta × RP)
- **How to Fetch**:
  ```python
  # Method 1: Baseline
  query = text("SELECT default_value FROM cissa.parameters WHERE parameter_name = 'equity_risk_premium'")
  
  # Method 2: With overrides
  service = ParameterService(session)
  params = await service.get_merged_parameters(param_set_id)
  equity_risk_premium = params['equity_risk_premium']
  ```

### 3. Metrics Storage
- **Table**: `metrics_outputs` in `/home/ubuntu/cissa/backend/database/schema/schema.sql`
- **Structure**: (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value)
- **Key Feature**: Unique constraint allows ON CONFLICT upserts for idempotent calculations
- **Fetch Pattern**:
  ```python
  query = text("""
      SELECT ticker, fiscal_year, output_metric_value
      FROM cissa.metrics_outputs
      WHERE dataset_id = :dataset_id
        AND param_set_id = :param_set_id
        AND output_metric_name = :metric_name
  """)
  ```

### 4. Phase Structure (Phase 10)
```
Phase 10a: Core L2 metrics (EP, PAT_EX, XO_COST_EX, FC)
Phase 10b: FV_ECF metrics (1Y, 3Y, 5Y, 10Y)
Phase 10c: TER & TER-KE metrics (8 total: 1Y, 3Y, 5Y, 10Y × 2 types)
Phase 10d: TER Alpha (NOT YET IMPLEMENTED) - would fit here
```

### 5. Cross-Metric Dependencies
TER depends on:
- Calc MC (Phase 10a)
- Calc KE (Phase 10a)
- Calc 1Y/3Y/5Y/10Y FV_ECF (Phase 10b)

FV_ECF depends on:
- Calc KE lagged (Phase 10a, offset by fiscal_year)
- DIVIDENDS, FRANKING (Phase 06, fundamentals table)

## Common Query Patterns

### Pattern 1: Fetch Single Metric
```python
async def _fetch_metric(self, dataset_id, metric_name, param_set_id):
    query = text("""
        SELECT ticker, fiscal_year, output_metric_value
        FROM cissa.metrics_outputs
        WHERE dataset_id = :dataset_id
          AND param_set_id = :param_set_id
          AND output_metric_name = :metric_name
        ORDER BY ticker, fiscal_year
    """)
    result = await session.execute(query, {...})
    rows = result.fetchall()
    return pd.DataFrame(rows, columns=['ticker', 'fiscal_year', 'value'])
```

### Pattern 2: Lag Calculation (Prior Year Value)
```python
df['calc_mc_lag'] = df.groupby('ticker')['calc_mc'].shift(1)
# Now for FY2023, calc_mc_lag contains FY2022's calc_mc value
```

### Pattern 3: Vectorized Calculation
```python
# Instead of iterating rows:
df['ter'] = np.where(
    df['open_mc'].notna() & (df['open_mc'] != 0),
    ((df['wc'] + df['wp']) / df['open_mc']) ** (1/interval) - 1,
    np.nan
)
```

### Pattern 4: Batch Insert
```python
query = text(f"""
    INSERT INTO cissa.metrics_outputs 
    (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata)
    VALUES {rows_sql}
    ON CONFLICT (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
    DO UPDATE SET
        output_metric_value = EXCLUDED.output_metric_value,
        metadata = EXCLUDED.metadata
""")
await session.execute(query)
await session.commit()
```

### Pattern 5: Generate NULL Rows (Insufficient History)
```python
# For metrics needing prior year data:
# - 1Y metric: NULL for first fiscal year
# - 3Y metric: NULL for first 2 fiscal years
# - 5Y metric: NULL for first 4 fiscal years

null_rows = []
for ticker in unique_tickers:
    for year_offset in range(1, num_prior_years_needed):
        null_rows.append({
            'ticker': ticker,
            'fiscal_year': min_year + year_offset,
            'metric_value': np.nan,
            'metric_type': f'Calc {interval}Y TER'
        })
```

## Orchestration Flow

**Runtime Orchestration** (`runtime_metrics_orchestration_service.py`):
```
Step 1: Resolve parameter_id (use provided or fallback to is_active)
Step 2: Beta Rounding & Risk-Free Rate (SEQUENTIAL)
Step 3: Cost of Equity (SEQUENTIAL, depends on step 2)
Step 4: FV_ECF (SEQUENTIAL, depends on step 3) - FAIL-SOFT
Step 5: TER (SEQUENTIAL, depends on step 4) - FAIL-SOFT
Step 6: (PROPOSED) TER Alpha (depends on step 5) - FAIL-SOFT
```

Error Handling:
- Phases 1-3: FAIL-FAST (errors stop orchestration)
- Phases 4-6: FAIL-SOFT (errors logged, orchestration continues)

## Recommendations for Phase 10d (TER Alpha)

### Implementation Strategy
1. Create: `/home/ubuntu/cissa/backend/app/services/ter_alpha_service.py`
2. Add Endpoint: `/home/ubuntu/cissa/backend/app/api/v1/endpoints/metrics.py` after line 900
3. Add Orchestration: Add step 6 to `runtime_metrics_orchestration_service.py` line ~442

### Service Structure (Follow TERService Pattern)
```python
class TERAlphaService:
    async def calculate_ter_alpha_metrics(self, dataset_id: UUID, param_set_id: UUID) -> dict:
        # Step 1: Fetch TER metrics (all 4 intervals)
        ter_1y = await self._fetch_metric(..., 'Calc 1Y TER')
        # ... 3Y, 5Y, 10Y
        
        # Step 2: Fetch TER-KE metrics (all 4 intervals)
        ter_ke_1y = await self._fetch_metric(..., 'Calc 1Y TER-KE')
        # ... 3Y, 5Y, 10Y
        
        # Step 3: Fetch market benchmark TER (TBD - may need new source)
        benchmark_ter = await self._fetch_benchmark_ter(...)
        
        # Step 4: Calculate TER Alpha = TER - Benchmark TER (vectorized)
        ter_alpha = self._calculate_ter_alpha_vectorized(ter_df, benchmark_ter)
        
        # Step 5: Generate NULL rows for insufficient history
        ter_alpha = self._add_null_rows_for_ter_alpha(ter_alpha, fundamentals_df)
        
        # Step 6: Single batch insert
        await self._insert_ter_alpha_batch(ter_alpha, dataset_id, param_set_id)
```

### Metrics to Calculate (8 total)
- Calc 1Y TER Alpha, Calc 3Y TER Alpha, Calc 5Y TER Alpha, Calc 10Y TER Alpha
- Calc 1Y TER-KE Alpha, Calc 3Y TER-KE Alpha, Calc 5Y TER-KE Alpha, Calc 10Y TER-KE Alpha

## Testing Key Areas

### For TERService
1. Fetch operations (Calc MC, KE, FV_ECF)
2. Lagging calculations (LAG operations)
3. Vectorized TER formula accuracy
4. NULL row generation (different counts per interval)
5. Batch insert idempotency (re-run test)

### For Parameter Fetching
1. Baseline parameter fetch
2. Override merging (overrides take precedence)
3. Parameter type conversion (% to decimal)
4. Default fallbacks (equity_risk_premium = 5.0%)

### For Phase 10d (TER Alpha)
1. Fetch TER metrics (should exist after Phase 10c)
2. Fetch/calculate benchmark TER (TBD)
3. Alpha calculation logic
4. NULL row generation (same as TER)
5. Batch insert with metadata

## Performance Notes

- TERService processes ~73,512 metric values (8 metrics × 9,189 records)
- Uses single multi-row INSERT instead of 73k individual INSERTs
- Vectorized Pandas operations (no Python loops over rows)
- Expected runtime: <1 second for insert phase
- Total calculation time: ~2-5 seconds depending on merge complexity

## Related Issues

- Phase 10d (TER Alpha) is NOT YET IMPLEMENTED
- TER Alpha calculations will follow same pattern as TER (Phase 10c)
- Benchmark TER source needs to be determined
- NULL row counts for TER Alpha may differ from TER (TBD based on alpha calculation requirements)
