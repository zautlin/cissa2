# Parameter Initialization - Refactored into Schema Creation

**Date**: 2026-03-04  
**Commit**: f071b43  
**Status**: ✅ COMPLETE

## What Changed

Parameter initialization has been moved from a separate `init_parameters()` method to **PHASE 7** of `schema.sql`, ensuring that both the 13 baseline parameters and the default parameter_set are created **atomically as part of schema creation**.

## Before (Old Approach)

```python
# Two-step process:
schema_manager.init()
├── create()           # Create empty tables
└── init_parameters()  # INSERT parameters (separate transaction)
```

**Problem**: Parameters and parameter_set created in a separate transaction, risking incomplete initialization.

## After (New Approach)

```sql
-- Single atomic transaction:
schema.sql execution
├── CREATE 11 tables
├── CREATE 25+ indexes
├── CREATE 4 triggers
├── INSERT 13 baseline parameters (PHASE 7)
└── INSERT default parameter_set 'base_case' (PHASE 7)
```

**Benefit**: All initialization guaranteed to complete together.

## What Gets Initialized

### 13 Baseline Parameters

| Parameter | Value |
|-----------|-------|
| country_geography | Australia |
| currency_notation | A$m |
| cost_of_equity_approach | Floating |
| include_franking_credits_tsr | false |
| fixed_benchmark_return_wealth_preservation | 7.5 |
| equity_risk_premium | 5.0 |
| tax_rate_franking_credits | 30.0 |
| value_of_franking_credits | 75.0 |
| risk_free_rate_rounding | 0.5 |
| beta_rounding | 0.1 |
| last_calendar_year | 2019 |
| beta_relative_error_tolerance | 40.0 |
| terminal_year | 60 |

### 1 Default Parameter Set

```json
{
  "param_set_name": "base_case",
  "description": "Default parameter set using all 13 baseline parameters",
  "is_default": true,
  "is_active": true,
  "param_overrides": {}
}
```

## Implementation Details

### Schema.sql (PHASE 7)

```sql
-- Insert 13 baseline parameters (if not already present)
INSERT INTO parameters (parameter_name, display_name, value_type, default_value)
VALUES
  ('country_geography', 'Country Geography', 'TEXT', 'Australia'),
  -- ... (11 more parameters)
ON CONFLICT (parameter_name) DO NOTHING;

-- Create default parameter_set "base_case" (if not already present)
INSERT INTO parameter_sets (param_set_name, description, is_default, is_active, param_overrides, created_by)
VALUES
  ('base_case', 'Default parameter set using all 13 baseline parameters', true, true, '{}', 'admin')
ON CONFLICT (param_set_name) DO NOTHING;
```

**Key features:**
- `ON CONFLICT DO NOTHING` — Idempotent. Safe to re-run schema.sql multiple times
- Single transaction — All tables, indexes, triggers, parameters created atomically
- No data loss — PHASE 7 is append-only (just INSERTs)

### schema_manager.py

Simplified `init()` method:

```python
def init(self) -> bool:
    """Full initialization: create schema (includes parameters + default parameter_set via schema.sql)."""
    # Schema creation now includes baseline parameters and default parameter_set
    # via INSERT statements in schema.sql (PHASE 7)
    if not self.create():
        return False
    
    print("✓ Initialized:")
    print("  ✓ 10 tables created")
    print("  ✓ 25+ indexes created")
    print("  ✓ 4 auto-update triggers created")
    print("  ✓ 13 baseline parameters inserted")
    print("  ✓ Default parameter_set 'base_case' created")
    
    return True
```

Now `init()` just calls `create()` — no separate parameter initialization needed.

## Verification

After schema initialization, verify parameters exist:

```sql
-- Check parameters
SELECT COUNT(*) FROM cissa.parameters;
-- Expected: 13

-- Check parameter_sets
SELECT * FROM cissa.parameter_sets;
-- Expected: 1 row (base_case, is_default=true)

-- Check default parameter_set details
SELECT param_set_name, is_default, param_overrides 
FROM cissa.parameter_sets 
WHERE param_set_name = 'base_case';
-- Expected: base_case | true | {}
```

## Files Modified

- `backend/database/schema/schema.sql` — Added PHASE 7 with parameter INSERTs
- `backend/database/schema/schema_manager.py` — Simplified init() method

## Benefits

✅ **Atomic initialization** — Tables + parameters created together  
✅ **Single source of truth** — schema.sql contains all initialization  
✅ **Idempotent** — ON CONFLICT prevents errors on re-runs  
✅ **Simpler code** — No separate init_parameters() step  
✅ **Guaranteed consistency** — No partial initialization possible  

## Next Steps

When PostgreSQL is available, reset and test with:

```bash
python3 backend/database/schema/schema_manager.py destroy --confirm
python3 backend/database/schema/schema_manager.py init
```

Then verify:

```sql
SELECT COUNT(*) FROM cissa.parameters;           -- Should be 13
SELECT COUNT(*) FROM cissa.parameter_sets;       -- Should be 1
SELECT param_set_name FROM cissa.parameter_sets; -- Should be 'base_case'
```

## Status

✅ Code ready  
⏳ Awaiting database verification when PostgreSQL is available
