# Coding Conventions

**Analysis Date:** 2026-03-09

## Naming Patterns

**Files:**
- All lowercase with underscores for compound words
- Examples: `metrics_service.py`, `metrics_repository.py`, `metrics_output.py`
- Special naming: `models.py` for backward compatibility, `schemas.py` for Pydantic models

**Functions:**
- snake_case for all functions (both sync and async)
- Private/internal methods prefixed with single underscore: `_insert_metric_results()`, `_calculate_beta()`
- Async methods use `async def` convention with same snake_case naming
- Examples: `calculate_metric()`, `get_fundamentals()`, `_execute_sql_function()`

**Classes:**
- PascalCase for all class names
- Service classes: `MetricsService`, `L2MetricsService`, `EnhancedMetricsService`
- Model classes: `MetricsOutput`, `Base` (SQLAlchemy declarative base)
- Repository classes: `MetricsRepository`
- Pydantic schema classes: `CalculateMetricsRequest`, `CalculateMetricsResponse`, `MetricsHealthResponse`, `L2MetricResultItem`

**Variables:**
- snake_case for all module-level and local variables
- Type hints used throughout with modern Python syntax (e.g., `dict | None`, `list[X]`)
- UUID variables: `dataset_id`, `param_set_id` (consistency across codebase)
- Examples: `dataset_id: UUID`, `ticker: str`, `fiscal_year: int`, `merged_df`, `all_results`

**Types:**
- Full qualified imports from typing module: `from typing import List, Dict, Any, Optional`
- Modern Python 3.10+ union syntax: `dict | None` instead of `Optional[dict]`
- Pydantic v2 ConfigDict: `model_config = ConfigDict(from_attributes=True)`
- SQLAlchemy v2 Mapped syntax: `Mapped[str] = mapped_column(String, nullable=False)`

## Code Style

**Formatting:**
- No detected linter config (no .eslintrc, .prettierrc, pylintrc, flake8, or ruff.toml)
- Manual adherence to PEP 8 principles
- Line length appears consistent around 80-100 characters
- 4 spaces for indentation (Python standard)

**Linting:**
- No active linting configuration found
- Code follows implicit conventions: imports organized, type hints used, docstrings present in key methods

**Comments:**
- File-level separator comments using visual block: `# ============================================================================`
- Used to delineate sections within files
- Example from `core/config.py`: 79 lines with clear section markers
- Inline comments rare, logic is self-documenting through naming

## Import Organization

**Order:**
1. Standard library imports (e.g., `asyncio`, `sys`, `logging`, `pathlib`)
2. Third-party imports (e.g., `sqlalchemy`, `pydantic`, `pandas`, `numpy`)
3. Relative local imports (e.g., `from ..core.database import get_db`)
4. Empty line between each group

**Pattern:**
```python
# Standard library first
from uuid import UUID
from datetime import datetime
from typing import List, Dict, Any

# Third-party next
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from pydantic import BaseModel, Field

# Local imports last
from ..core.config import get_logger
from ..models import MetricsOutput
from ..services.metrics_service import MetricsService
```

**Path Aliases:**
- Relative imports used extensively with `from ...` for parent directory traversal
- No path aliases configured (no tsconfig paths, no pytest conftest aliases)
- Direct imports like `from backend.app.cli` used in CLI modules

## Error Handling

**Patterns:**
- Try-except blocks used in service and endpoint layers
- HTTPException raised in endpoints with status codes: `HTTPException(status_code=400, detail=response.message)`
- Response objects carry error status and messages: `status="error"`, `message: Optional[str]`
- Database session errors caught and rolled back: `await session.rollback()`
- Logger.error() with `exc_info=True` for exception tracebacks
- Example from `api/v1/endpoints/metrics.py`: Line 75-76 raises HTTPException on error response

**Strategy:**
- Layer-specific error handling: services return structured response dicts with `"status"`, `"message"`, `"results_count"`
- Endpoints convert service failures to HTTP exceptions
- CLI module catches exceptions and logs with logger.error()

## Logging

**Framework:** `logging` module via custom `get_logger()` helper

**Implementation:** `core/config.py` lines 53-61 defines centralized logger configuration
- StreamHandler with consistent formatter: `'%(asctime)s - %(name)s - %(levelname)s - %(message)s'`
- Logger obtained via: `logger = get_logger(__name__)` in each module
- Log level configurable via settings: `log_level: str = "info"`

**Patterns:**
```python
logger.info(f"Starting {operation_name}")
logger.info(f"  Dataset ID: {dataset_id}")
logger.warning(f"Operation failed: {reason}")
logger.error(f"Unexpected error: {str(e)}", exc_info=True)
```

**When to Log:**
- Start of major operations: "Starting enhanced metrics calculation"
- Milestone events: "Fetching fundamentals...", "Pivoting L1 metrics..."
- Warnings on non-critical failures: "Calculation failed: No merged data"
- Errors with full tracebacks: `exc_info=True` for unexpected exceptions

## Comments & Documentation

**Docstring Style:**
- Triple-quoted docstrings on functions and classes
- Docstrings explain purpose and parameters, not obvious from name
- Service methods include numbered steps: Example from `metrics_service.py` line 46-51
- Pydantic models have descriptive docstrings: `"""Request to calculate a metric"""`
- Field descriptions in Pydantic: `Field(..., description="UUID of the dataset...")`

**Example Pattern:**
```python
async def calculate_enhanced_metrics(
    self,
    dataset_id: UUID,
    param_set_id: UUID,
) -> dict:
    """
    Main orchestration method. Calculates all Phase 3 metrics.
    
    Returns:
        {
            "status": "success|error",
            "results_count": N,
            "metrics_calculated": [...],
            "message": "..."
        }
    """
```

**Comment Placement:**
- Section separators at top of files
- Inline comments only for complex logic (rare)
- No commented-out code blocks observed
- TODOs noted in code: Example `metrics.py` line with `# TODO: make configurable`

## Function Design

**Size:**
- Most functions 15-50 lines (typical)
- Larger functions up to 80+ lines in service layer (e.g., `calculate_metric()` spans 412 lines including helper methods)
- Private helpers keep public methods focused

**Parameters:**
- Explicit type hints on all parameters
- Async functions accepted in FastAPI dependencies via `Depends()`
- Examples: `async def calculate_metric(request: CalculateMetricsRequest, db: AsyncSession = Depends(get_db))`
- Return types always specified: `-> CalculateMetricsResponse`, `-> dict`, `-> AsyncGenerator[AsyncSession, None]`

**Return Values:**
- Structured response objects (Pydantic models) from endpoints
- Plain dicts from service layer: `{"status": "success|error", "results_count": N, "message": "..."}`
- DataFrames from repository methods: `-> pd.DataFrame`
- None or single model instances from repository create/get methods

## Module Design

**Exports:**
- `__all__` list in `models/__init__.py` and `models.py` for explicit exports
- Barrel files used for package organization: `services/__init__.py` exports public classes
- Example from `models/__init__.py`: Exports both ORM and Pydantic models

**Barrel Files:**
- Location: `backend/app/models/__init__.py`, `backend/app/services/__init__.py`, `backend/app/repositories/__init__.py`
- Pattern: Re-export public classes and constants
- Enables: `from app.models import MetricsOutput` instead of `from app.models.metrics_output import MetricsOutput`

**Layer Structure:**
- Controllers/Endpoints: `backend/app/api/v1/endpoints/` - FastAPI route handlers
- Services: `backend/app/services/` - Business logic and orchestration
- Repositories: `backend/app/repositories/` - Data access patterns
- Models: `backend/app/models/` - ORM and Pydantic schemas
- Core: `backend/app/core/` - Infrastructure (config, database, logging)

---

*Convention analysis: 2026-03-09*
