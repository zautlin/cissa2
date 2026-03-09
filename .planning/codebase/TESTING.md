# Testing Patterns

**Analysis Date:** 2026-03-09

## Test Framework

**Status:** No testing framework detected
- No pytest.ini, tox.ini, vitest.config.*, or jest.config.* files present
- No test files found in the codebase (no *_test.py, test_*.py, or tests/ directories)
- No testing dependencies in `requirements.txt`

**Implication:** The project currently has zero automated tests. This is a significant quality gap documented in CONCERNS.md.

## Test File Organization

**Location Pattern:** Not applicable - no tests present

**Expected Structure (if tests were added):**
- Co-located pattern recommended: `backend/app/services/test_metrics_service.py` alongside source
- Or separate tree: `backend/tests/unit/services/test_metrics_service.py`
- CLI tests: `backend/tests/unit/cli/test_run_l2_metrics.py`
- Integration tests: `backend/tests/integration/test_endpoints_metrics.py`

**Naming Convention (if tests were added):**
- Test files: `test_*.py` or `*_test.py` prefix
- Test functions: `test_*` prefix (e.g., `test_calculate_metric_success()`, `test_invalid_metric_name()`)
- Test classes: `Test*` prefix (e.g., `TestMetricsService`, `TestMetricsEndpoint`)

## Test Structure

**Recommended Pattern (not currently used):**

```python
import pytest
from uuid import UUID
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.metrics_service import MetricsService
from backend.app.models import CalculateMetricsResponse

class TestMetricsService:
    """Test suite for MetricsService"""
    
    @pytest.fixture
    async def mock_session(self):
        """Fixture: mock async database session"""
        session = AsyncMock(spec=AsyncSession)
        return session
    
    @pytest.fixture
    async def service(self, mock_session):
        """Fixture: MetricsService instance with mock session"""
        return MetricsService(mock_session)
    
    @pytest.mark.asyncio
    async def test_calculate_metric_success(self, service, mock_session):
        """Test: successful metric calculation"""
        dataset_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        metric_name = "Calc MC"
        
        # Mock SQL function return
        mock_session.execute.return_value.fetchall.return_value = [
            ("AAPL", 2023, 2500.0),
            ("MSFT", 2023, 1800.0),
        ]
        
        result = await service.calculate_metric(dataset_id, metric_name)
        
        assert result.status == "success"
        assert result.results_count == 2
        assert len(result.results) == 2
        assert result.results[0].ticker == "AAPL"
    
    @pytest.mark.asyncio
    async def test_calculate_metric_invalid_name(self, service):
        """Test: error on unknown metric name"""
        dataset_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        metric_name = "Unknown Metric"
        
        result = await service.calculate_metric(dataset_id, metric_name)
        
        assert result.status == "error"
        assert "Unknown metric" in result.message
```

**Setup/Teardown Pattern (if tests were added):**
- Use pytest fixtures for resource management
- Example: `@pytest.fixture(autouse=True)` for automatic database rollback
- Async fixtures with `@pytest.fixture` decorator and async def

**Assertion Pattern (if tests were added):**
- Use pytest assertions: `assert result.status == "success"`
- For async: use `pytest.mark.asyncio` decorator
- Group assertions logically: validate response structure, then content

## Mocking

**Recommended Framework (not currently used):**
- `unittest.mock` for AsyncMock (built-in)
- `pytest-mock` for cleaner patch syntax
- `pytest-asyncio` for async test support

**Pattern (recommended but not implemented):**
```python
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

# Mock database session
mock_session = AsyncMock(spec=AsyncSession)
mock_session.execute.return_value.fetchall.return_value = test_data

# Mock SQL function result
with patch('backend.app.services.metrics_service.text') as mock_text:
    mock_text.return_value = "SELECT ..."
    # Test code
```

**What to Mock (if tests were added):**
- Database: AsyncSession for unit tests (use real database for integration tests)
- External SQL functions: Mock `session.execute()` returns
- Settings/Configuration: Use fixture to override `.env` settings
- Repository layer: Mock in endpoint tests to isolate API logic

**What NOT to Mock (if tests were added):**
- Pydantic model validation (test with real models)
- Local utility functions (test with real implementations)
- Database transaction management (use test database)

## Fixtures and Factories

**Test Data Pattern (not currently used):**

```python
import pytest
from uuid import UUID

@pytest.fixture
def sample_dataset_id():
    """Fixture: standard test dataset UUID"""
    return UUID("550e8400-e29b-41d4-a716-446655440000")

@pytest.fixture
def sample_param_set_id():
    """Fixture: standard test parameter set UUID"""
    return UUID("550e8400-e29b-41d4-a716-446655440001")

@pytest.fixture
def metric_result_factory():
    """Factory: create test MetricResultItem objects"""
    def _factory(ticker="AAPL", fiscal_year=2023, value=100.0):
        from backend.app.models import MetricResultItem
        return MetricResultItem(
            ticker=ticker,
            fiscal_year=fiscal_year,
            value=value
        )
    return _factory

@pytest.fixture
def calculate_metrics_response_factory(metric_result_factory):
    """Factory: create test CalculateMetricsResponse objects"""
    def _factory(dataset_id=None, metric_name="Calc MC", results_count=2, status="success"):
        from backend.app.models import CalculateMetricsResponse
        return CalculateMetricsResponse(
            dataset_id=dataset_id or UUID("550e8400-e29b-41d4-a716-446655440000"),
            metric_name=metric_name,
            results_count=results_count,
            results=[metric_result_factory() for _ in range(results_count)],
            status=status,
            message=None if status == "success" else "Error occurred"
        )
    return _factory
```

**Expected Location (if tests were added):**
- `backend/tests/fixtures/` - Shared pytest fixtures
- `backend/tests/factories/` - Factory classes for test data
- Or in conftest.py at appropriate level

## Coverage

**Requirements:** Not enforced (no testing infrastructure exists)

**Recommended Setup (not implemented):**
```bash
# Install coverage
pip install pytest-cov

# Run tests with coverage
pytest --cov=backend.app --cov-report=html

# View coverage
open htmlcov/index.html
```

**Target Coverage (recommendation):** 80%+ for critical paths (services, repositories, endpoints)

## Test Types

**Unit Tests (if implemented):**
- Scope: Individual functions/methods in isolation
- Pattern: Mock all external dependencies (database, HTTP, file I/O)
- Where: `backend/tests/unit/` or co-located with source
- Example targets: Service methods, utility functions, Pydantic validators

**Integration Tests (if implemented):**
- Scope: Multiple components working together
- Pattern: Use real database (test database instance) or in-memory SQLite
- Where: `backend/tests/integration/`
- Example targets: Service + Repository + Database, Full API endpoint flows

**E2E Tests (if implemented):**
- Framework: Not detected (could use pytest with TestClient)
- Pattern: Start actual FastAPI app, make HTTP requests, validate responses
- Example with TestClient:

```python
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_health_endpoint():
    """E2E test: health check endpoint"""
    response = client.get("/api/v1/metrics/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_calculate_metrics_endpoint():
    """E2E test: metrics calculation endpoint"""
    payload = {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "metric_name": "Calc MC"
    }
    response = client.post("/api/v1/metrics/calculate", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
```

## Async Testing

**Pattern (for async functions like in services):**

```python
import pytest

@pytest.mark.asyncio
async def test_async_service_method():
    """Test: async method in service"""
    service = MetricsService(mock_session)
    result = await service.calculate_metric(dataset_id, metric_name)
    assert result.status == "success"
```

**Configuration Needed (not present):**
- `pytest.ini` with: `asyncio_mode = auto`
- Or `pyproject.toml` with pytest config

## Error Testing

**Pattern (for error cases):**

```python
@pytest.mark.asyncio
async def test_calculate_metric_database_error(service, mock_session):
    """Test: handles database error gracefully"""
    mock_session.execute.side_effect = Exception("Connection failed")
    
    # Service should catch and return error response
    result = await service.calculate_metric(dataset_id, "Calc MC")
    assert result.status == "error"
    assert "Connection failed" in result.message

def test_invalid_uuid_format():
    """Test: rejects malformed UUID"""
    with pytest.raises(ValueError):
        UUID("invalid-uuid-string")

@pytest.mark.asyncio
async def test_endpoint_returns_http_error(client):
    """Test: endpoint converts service errors to HTTP exceptions"""
    payload = {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "metric_name": "Unknown Metric"
    }
    response = client.post("/api/v1/metrics/calculate", json=payload)
    assert response.status_code == 400
    assert "error" in response.json()
```

## Critical Testing Gaps

**Current State:**
- Zero automated tests
- No test fixtures or factories
- No mocking infrastructure
- No CI/CD test pipeline

**Impact:**
- Regressions undetected
- Refactoring risky
- Large service methods (400+ lines) untested
- API endpoints (249 lines) untested
- Database layer (175 lines in repository) untested

**Priority for Implementation:**
1. Service layer unit tests (highest ROI: `metrics_service.py`, `l2_metrics_service.py`, `enhanced_metrics_service.py`)
2. Endpoint integration tests (`api/v1/endpoints/metrics.py`)
3. Repository tests with test database (`repositories/metrics_repository.py`)
4. CLI tests (`cli/run_l2_metrics.py`)

---

*Testing analysis: 2026-03-09*
