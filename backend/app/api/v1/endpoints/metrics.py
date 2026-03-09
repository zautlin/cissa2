# ============================================================================
# Metrics API Endpoints
# ============================================================================
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from ....core.database import get_db
from ....models import (
    CalculateMetricsRequest,
    CalculateMetricsResponse,
    CalculateL2Request,
    CalculateL2Response,
    CalculateEnhancedMetricsRequest,
    CalculateEnhancedMetricsResponse,
    CalculateBetaRequest,
    CalculateBetaResponse,
    CalculateRiskFreeRateRequest,
    CalculateRiskFreeRateResponse,
    MetricsHealthResponse
)
from ....services.metrics_service import MetricsService
from ....services.l2_metrics_service import L2MetricsService
from ....services.enhanced_metrics_service import EnhancedMetricsService
from ....services.beta_calculation_service import BetaCalculationService
from ....services.risk_free_rate_service import RiskFreeRateCalculationService
from ....core.config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.get("/health", response_model=MetricsHealthResponse)
async def health_check():
    """Health check endpoint"""
    return MetricsHealthResponse(
        status="ok",
        message="Metrics service is running",
        database="connected"
    )


@router.post("/calculate", response_model=CalculateMetricsResponse)
async def calculate_metric(
    request: CalculateMetricsRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate a metric for a dataset.
    
    **Example Request (Simple Metric):**
    ```json
    {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "metric_name": "Calc MC"
    }
    ```
    
    **Example Request (Parameter-Sensitive Metric):**
    ```json
    {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "metric_name": "FY_TSR",
        "param_set_id": "660e8400-e29b-41d4-a716-446655440001"
    }
    ```
    
    **Supported L1 Metrics:**
    - Simple (7): Calc MC, Calc Assets, Calc OA, Calc Op Cost, Calc Non Op Cost, Calc Tax Cost, Calc XO Cost
    - Temporal (5): ECF, NON_DIV_ECF, EE, FY_TSR (requires param_set_id), FY_TSR_PREL (requires param_set_id)
    
    **Note:** FY_TSR and FY_TSR_PREL are parameter-sensitive. If param_set_id is not provided, the default parameter set will be used.
    """
    
    service = MetricsService(db)
    response = await service.calculate_metric(
        request.dataset_id, 
        request.metric_name,
        request.param_set_id
    )
    
    if response.status == "error":
        raise HTTPException(status_code=400, detail=response.message)
    
    return response


@router.get("/dataset/{dataset_id}/metrics/{metric_name}", response_model=CalculateMetricsResponse)
async def get_metric(
    dataset_id: UUID,
    metric_name: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get or calculate a metric for a dataset (GET endpoint for convenience).
    
    This endpoint:
    1. Checks if metric exists in metrics_outputs
    2. If not, calculates it
    3. Returns the results
    """
    
    service = MetricsService(db)
    response = await service.calculate_metric(dataset_id, metric_name)
    
    if response.status == "error":
        raise HTTPException(status_code=400, detail=response.message)
    
    return response


# ============================================================================
# L2 Metrics Endpoints
# ============================================================================

@router.post("/calculate-l2", response_model=CalculateL2Response, status_code=status.HTTP_200_OK)
async def calculate_l2_metrics(
    request: CalculateL2Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate L2 metrics for a dataset and parameter set.
    
    L2 metrics are complex calculations that require L1 metrics to be computed first.
    They typically involve regressions and multi-period analysis.
    
    **Prerequisites:**
    - L1 metrics must already be calculated and in metrics_outputs table
    - dataset_id must exist in dataset_versions
    - param_set_id must exist in parameter_sets
    
    **Example Request:**
    ```json
    {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "param_set_id": "660e8400-e29b-41d4-a716-446655440001"
    }
    ```
    
    **Response:**
    - status: 'success' or 'error'
    - results_count: number of L2 metrics calculated
    - results: array of individual metric results
    """
    
    logger.info(f"Processing L2 metrics calculation request: dataset={request.dataset_id}, param_set={request.param_set_id}")
    
    try:
        service = L2MetricsService(db)
        result = await service.calculate_l2_metrics(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id,
            inputs={
                "country": "AU",  # TODO: make configurable
                "risk_premium": 0.06,  # TODO: fetch from param_set
            }
        )
        
        if result["status"] == "error":
            logger.warning(f"L2 calculation failed: {result['message']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        logger.info(f"L2 calculation successful: {result['results_count']} records")
        
        return CalculateL2Response(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id,
            results_count=result["results_count"],
            status="success",
            message=result["message"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during L2 calculation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during L2 metrics calculation"
        )


# ============================================================================
# L3 Enhanced Metrics Endpoints (Phase 3)
# ============================================================================

@router.post("/calculate-enhanced", response_model=CalculateEnhancedMetricsResponse, status_code=status.HTTP_200_OK)
async def calculate_enhanced_metrics(
    request: CalculateEnhancedMetricsRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate enhanced metrics (Phase 3): Beta, Rf, KE, EP, TSR, Financial Ratios.
    
    Enhanced metrics are derived calculations that build on L1 metrics:
    - Beta: Stock beta (currently 1.0 default, future: rolling OLS from returns)
    - Rf: Risk-free rate (from parameter set)
    - Calc KE: Cost of Equity = Rf + Beta × Risk Premium
    - ROA, ROE, Profit Margin: Financial ratios
    
    **Prerequisites:**
    - L1 metrics must be calculated first
    - dataset_id and param_set_id must exist
    
    **Example Request:**
    ```json
    {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "param_set_id": "660e8400-e29b-41d4-a716-446655440001"
    }
    ```
    
    **Response:**
    - status: 'success' or 'error'
    - results_count: number of metric records inserted
    - metrics_calculated: list of metric types calculated
    """
    
    logger.info(f"Processing enhanced metrics: dataset={request.dataset_id}, param_set={request.param_set_id}")
    
    try:
        service = EnhancedMetricsService(db)
        result = await service.calculate_enhanced_metrics(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id
        )
        
        if result["status"] == "error":
            logger.warning(f"Enhanced metrics calculation failed: {result['message']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        logger.info(f"Enhanced metrics calculation successful: {result['results_count']} records, metrics={result['metrics_calculated']}")
        
        return CalculateEnhancedMetricsResponse(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id,
            results_count=result["results_count"],
            metrics_calculated=result["metrics_calculated"],
            status="success",
            message=result["message"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during enhanced metrics calculation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during enhanced metrics calculation"
        )


# ============================================================================
# Phase 07: Beta Calculation Endpoints
# ============================================================================

@router.post("/beta/calculate", response_model=CalculateBetaResponse, status_code=status.HTTP_200_OK)
async def calculate_beta(
    request: CalculateBetaRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate beta using rolling OLS regression on monthly returns.
    
    **Beta Calculation Algorithm:**
    1. Fetch monthly COMPANY_TSR and INDEX_TSR from fundamentals
    2. Calculate 60-month rolling OLS slopes
    3. Transform slopes: adjusted = (slope * 2/3) + 1/3
    4. Filter by relative error tolerance
    5. Round by beta_rounding parameter
    6. Annualize and apply 4-tier fallback logic
    7. Apply cost_of_equity_approach (FIXED or Floating)
    8. Store in metrics_outputs
    
    **Prerequisites:**
    - Monthly TSR data must exist in fundamentals table (COMPANY_TSR + INDEX_TSR)
    - dataset_id must exist in dataset_versions
    - param_set_id must exist in parameter_sets
    
    **Parameters from param_set:**
    - beta_rounding: Rounding increment (e.g., 0.1)
    - beta_relative_error_tolerance: Error tolerance as % (e.g., 40.0)
    - cost_of_equity_approach: "FIXED" or "Floating"
    
    **Caching:**
    - If beta results already exist for this dataset + param_set, returns cached results
    
    **Example Request:**
    ```json
    {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "param_set_id": "660e8400-e29b-41d4-a716-446655440001"
    }
    ```
    
    **Response:**
    - status: 'success', 'error', or 'cached'
    - results_count: number of beta records calculated
    - results: array of ticker, fiscal_year, beta value tuples
    """
    
    logger.info(f"Processing beta calculation request: dataset={request.dataset_id}, param_set={request.param_set_id}")
    
    try:
        service = BetaCalculationService(db)
        result = await service.calculate_beta_async(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id
        )
        
        if result["status"] == "error":
            logger.warning(f"Beta calculation failed: {result['message']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        logger.info(f"Beta calculation {'cached' if result['status'] == 'cached' else 'successful'}: {result['results_count']} records")
        
        return CalculateBetaResponse(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id,
            results_count=result["results_count"],
            status=result["status"],
            message=result["message"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during beta calculation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during beta calculation"
        )


@router.post("/rates/calculate", response_model=CalculateRiskFreeRateResponse, status_code=status.HTTP_200_OK)
async def calculate_risk_free_rate(
    request: CalculateRiskFreeRateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate risk-free rate (Rf, Rf_1Y, Rf_1Y_Raw) using monthly bond yields.
    
    **Risk-Free Rate Calculation Algorithm:**
    1. Fetch monthly RISK_FREE_RATE data for bond index (GACGB10 Index for Australia)
    2. Group by fiscal year (12 months per year)
    3. Calculate geometric mean: Rf_1Y_Raw = (∏monthly_rates)^(1/12) - 1
    4. Apply rounding: Rf_1Y = round((Rf_1Y_Raw / beta_rounding), 0) * beta_rounding
    5. Apply approach:
       - FIXED: Rf = benchmark - risk_premium
       - Floating: Rf = Rf_1Y
    6. Expand to all companies and store 3 metrics per (ticker, fiscal_year)
    
    **Prerequisites:**
    - Monthly RISK_FREE_RATE data must exist in fundamentals table (GACGB10 Index)
    - dataset_id must exist in dataset_versions
    - param_set_id must exist in parameter_sets
    - L1 metrics must already be calculated for the dataset
    
    **Parameters from param_set:**
    - bond_index_by_country: JSON mapping country→bond ticker (e.g., {"Australia": "GACGB10 Index"})
    - beta_rounding: Rounding increment (e.g., 0.1)
    - cost_of_equity_approach: "FIXED" or "Floating"
    - fixed_benchmark_return_wealth_preservation: Benchmark return for FIXED approach (e.g., 7.5)
    - equity_risk_premium: Risk premium for FIXED approach (e.g., 5.0)
    
    **Caching:**
    - If risk-free rate results already exist for this dataset + param_set, returns cached results
    
    **Example Request:**
    ```json
    {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "param_set_id": "660e8400-e29b-41d4-a716-446655440001"
    }
    ```
    
    **Output Metrics:**
    - Rf_1Y_Raw: Raw annualized 1-year rate (geometric mean, no rounding)
    - Rf_1Y: Rounded annualized 1-year rate
    - Rf: Final risk-free rate (after approach logic)
    
    **Response:**
    - status: 'success', 'error', or 'cached'
    - results_count: number of records calculated (3× number of tickers × number of fiscal years)
    - results: array of ticker, fiscal_year, metric_name, value tuples
    """
    
    logger.info(f"Processing risk-free rate calculation request: dataset={request.dataset_id}, param_set={request.param_set_id}")
    
    try:
        service = RiskFreeRateCalculationService(db)
        result = await service.calculate_risk_free_rate_async(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id
        )
        
        if result["status"] == "error":
            logger.warning(f"Risk-free rate calculation failed: {result['message']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        logger.info(f"Risk-free rate calculation {'cached' if result['status'] == 'cached' else 'successful'}: {result['results_count']} records")
        
        return CalculateRiskFreeRateResponse(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id,
            results_count=result["results_count"],
            status=result["status"],
            message=result["message"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during risk-free rate calculation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during risk-free rate calculation"
        )
