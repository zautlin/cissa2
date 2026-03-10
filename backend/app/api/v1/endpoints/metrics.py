# ============================================================================
# Metrics API Endpoints
# ============================================================================
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from ....core.database import get_db
from ....models import (
    CalculateMetricsRequest,
    CalculateMetricsResponse,
    CalculateL2Request,
    CalculateL2Response,
    CalculateBetaRequest,
    CalculateBetaResponse,
    CalculateRiskFreeRateRequest,
    CalculateRiskFreeRateResponse,
    MetricsHealthResponse,
    GetMetricsResponse,
)
from ....services.metrics_service import MetricsService
from ....services.l2_metrics_service import L2MetricsService
from ....services.beta_calculation_service import BetaCalculationService
from ....services.risk_free_rate_service import RiskFreeRateCalculationService
from ....repositories.metrics_query_repository import MetricsQueryRepository
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


# ============================================================================
# Phase 09: Cost of Equity Calculation Endpoint
# ============================================================================

@router.post("/cost-of-equity/calculate", response_model=CalculateEnhancedMetricsResponse, status_code=status.HTTP_200_OK)
async def calculate_cost_of_equity(
    request: CalculateEnhancedMetricsRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate Cost of Equity (Phase 09): KE = Rf + Beta × RiskPremium
    
    This endpoint efficiently calculates Cost of Equity using existing:
    - Phase 07 Beta results
    - Phase 08 Risk-Free Rate (Rf_1Y) results
    
    **Prerequisites:**
    - Phase 07 (Beta) must be calculated first
    - Phase 08 (Risk-Free Rate) must be calculated first
    
    **Approach Parameter:**
    - FIXED: Rf = benchmark - risk_premium (deterministic)
    - FLOATING: Rf = Rf_1Y (from Phase 08, recommended)
    
    **Example Request:**
    ```json
    {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "param_set_id": "660e8400-e29b-41d4-a716-446655440001"
    }
    ```
    
    **Response:**
    - status: 'success' or 'error'
    - results_count: number of KE records inserted
     - metrics_calculated: ['Calc KE']
     """
    
    logger.info(f"Phase 09: Calculating Cost of Equity (dataset={request.dataset_id}, param_set={request.param_set_id})")
    
    try:
        from ....services.cost_of_equity_service import CostOfEquityService
        
        service = CostOfEquityService(db)
        result = await service.calculate_cost_of_equity(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id
        )
        
        if result["status"] == "error":
            logger.warning(f"Phase 09 calculation failed: {result['message']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        logger.info(f"Phase 09 calculation successful: {result['records_inserted']} KE records")
        
        return CalculateEnhancedMetricsResponse(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id,
            results_count=result["records_inserted"],
            metrics_calculated=["Calc KE"],
            status="success",
            message=result["message"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Phase 09 error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cost of Equity calculation failed: {str(e)}"
        )


# ============================================================================
# Phase 10a: Core L2 Metrics Calculation Endpoint
# ============================================================================

@router.post("/l2-core/calculate", response_model=CalculateEnhancedMetricsResponse, status_code=status.HTTP_200_OK)
async def calculate_core_l2_metrics(
    request: CalculateEnhancedMetricsRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate Phase 10a Core L2 Metrics: EP, PAT_EX, XO_COST_EX, FC
    
    This endpoint efficiently calculates core Level 2 metrics using:
    - Phase 06 L1 Basic Metrics (pat, patxo, ee)
    - Phase 09 Cost of Equity (ke)
    - Lagged/opened versions (prior fiscal year values)
    
    **Metrics Calculated:**
    - EP: Economic Profit = pat - (ke_open × ee_open)
    - PAT_EX: Adjusted Profit = (ep / |ee_open + ke_open|) × ee_open
    - XO_COST_EX: Adjusted XO Cost = patxo - pat_ex
    - FC: Franking Credit = conditionally based on incl_franking parameter
    
    **Prerequisites:**
    - Phase 06 (L1 Basic Metrics) must be calculated first
    - Phase 09 (Cost of Equity) must be calculated first
    
    **Data Handling:**
    - Creates lagged versions via LEFT JOIN (preserves NaN for missing prior years)
    - NaN rows are retained in output (matches legacy approach)
    
    **Parameters from param_set:**
    - incl_franking: "Yes" or "No"
    - frank_tax_rate: Franking tax rate (e.g., 0.30)
    - value_franking_cr: Franking credit value (e.g., 0.75)
    
    **Example Request:**
    ```json
    {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "param_set_id": "660e8400-e29b-41d4-a716-446655440001"
    }
    ```
    
    **Response:**
    - status: 'success' or 'error'
    - results_count: number of records calculated (per metric)
     - metrics_calculated: ['EP', 'PAT_EX', 'XO_COST_EX', 'FC']
    """
    
    logger.info(f"Phase 10a: Calculating Core L2 metrics (dataset={request.dataset_id}, param_set={request.param_set_id})")
    
    try:
        from ....services.economic_profit_service import EconomicProfitService
        
        service = EconomicProfitService(db)
        result = await service.calculate_core_l2_metrics(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id
        )
        
        if result["status"] == "error":
            logger.warning(f"Phase 10a calculation failed: {result['message']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        logger.info(f"Phase 10a calculation successful: {result['records_inserted']} L2 metric records inserted")
        
        return CalculateEnhancedMetricsResponse(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id,
            results_count=result["records_calculated"],
            metrics_calculated=["EP", "PAT_EX", "XO_COST_EX", "FC"],
            status="success",
            message=result["message"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Phase 10a error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Core L2 metrics calculation failed: {str(e)}"
        )


# ============================================================================
# Phase 10b: Future Value Economic Cash Flow (FV_ECF) Metrics Endpoint
# ============================================================================

@router.post("/l2-fv-ecf/calculate", status_code=status.HTTP_200_OK)
async def calculate_fv_ecf_metrics(
    dataset_id: UUID,
    param_set_id: UUID,
    incl_franking: str = "Yes",
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate Phase 10b Future Value Economic Cash Flow (FV_ECF) Metrics
    
    This endpoint efficiently calculates FV_ECF metrics using:
    - Phase 06 L1 Basic Metrics (DIVIDENDS, FRANKING, NON_DIV_ECF from fundamentals)
    - Phase 10a Cost of Equity (CALC_KE lagged by 1 fiscal year)
    
    **Metrics Calculated:**
    - FV_ECF_1Y: 1-year future value economic cash flow
    - FV_ECF_3Y: 3-year future value economic cash flow
    - FV_ECF_5Y: 5-year future value economic cash flow
    - FV_ECF_10Y: 10-year future value economic cash flow
    
    These are L2 metrics used in DCF valuation models.
    
    **Prerequisites:**
    - Phase 06 (L1 Basic Metrics) must be calculated first
    - Phase 09 (Cost of Equity) must be calculated first
    
    **Algorithm:**
    - Creates scale_by flag (1 if KE > 0, else 0) to handle negative KE
    - For each interval, uses vectorized Pandas operations with shifting
    - Sums across interval periods with optional franking adjustments
    - Applies final shift to align fiscal year reporting
    
    **Parameters:**
    - incl_franking: "Yes" (include franking credit adjustments) or "No" (exclude)
    - frank_tax_rate: Franking tax rate (from parameter_sets)
    - value_franking_cr: Franking credit value (from parameter_sets)
    
    **Example Request:**
    ```
    POST /api/v1/metrics/l2-fv-ecf/calculate?dataset_id=...&param_set_id=...&incl_franking=Yes
    ```
    
    **Response:**
    ```json
    {
        "status": "success",
        "total_calculated": 9189,
        "total_inserted": 36756,
        "intervals_summary": {
            "1Y": 9189,
            "3Y": 9189,
            "5Y": 9189,
            "10Y": 9189
        },
        "duration_seconds": 12.34,
        "message": "Calculated and stored 36756 FV_ECF metric values"
    }
    ```
    """
    
    logger.info(f"Phase 10b: Calculating FV_ECF metrics (dataset={dataset_id}, param_set={param_set_id}, incl_franking={incl_franking})")
    
    try:
        from ....services.fv_ecf_service import FVECFService
        
        service = FVECFService(db)
        result = await service.calculate_fv_ecf_metrics(
            dataset_id=dataset_id,
            param_set_id=param_set_id,
            incl_franking=incl_franking
        )
        
        if result["status"] == "error":
            logger.warning(f"Phase 10b calculation failed: {result['message']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        logger.info(f"Phase 10b calculation successful: {result['total_inserted']} FV_ECF metric records inserted")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Phase 10b error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"FV_ECF metrics calculation failed: {str(e)}"
        )


# ============================================================================
# Metrics Query/Retrieval Endpoint
# ============================================================================

@router.get("/get_metrics/", response_model=GetMetricsResponse)
async def get_metrics(
    dataset_id: UUID = Query(..., description="UUID of the dataset to retrieve metrics for"),
    parameter_set_id: UUID = Query(..., description="UUID of the parameter set"),
    ticker: Optional[str] = Query(None, description="Optional: filter by ticker (case-insensitive)"),
    metric_name: Optional[str] = Query(None, description="Optional: filter by metric name (case-insensitive)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Query metrics from the database with flexible filtering.
    
    Returns a flat array of metric records with unit information, suitable for charting and filtering in the UI.
    
    **Parameters:**
    - `dataset_id` (required): UUID of the dataset
    - `parameter_set_id` (required): UUID of the parameter set
    - `ticker` (optional): Filter by ticker symbol (case-insensitive, e.g., "AAPL")
    - `metric_name` (optional): Filter by metric name (case-insensitive, e.g., "ECF", "Beta")
    
    **Example Requests:**
    
    Get all metrics for a dataset and parameter set:
    ```
    GET /api/v1/metrics/get_metrics/?dataset_id=550e8400-e29b-41d4-a716-446655440000&parameter_set_id=660e8400-e29b-41d4-a716-446655440001
    ```
    
    Get all metrics for a specific ticker:
    ```
    GET /api/v1/metrics/get_metrics/?dataset_id=550e8400-e29b-41d4-a716-446655440000&parameter_set_id=660e8400-e29b-41d4-a716-446655440001&ticker=AAPL
    ```
    
    Get a specific metric for all tickers:
    ```
    GET /api/v1/metrics/get_metrics/?dataset_id=550e8400-e29b-41d4-a716-446655440000&parameter_set_id=660e8400-e29b-41d4-a716-446655440001&metric_name=ECF
    ```
    
    Get a specific metric for a specific ticker:
    ```
    GET /api/v1/metrics/get_metrics/?dataset_id=550e8400-e29b-41d4-a716-446655440000&parameter_set_id=660e8400-e29b-41d4-a716-446655440001&ticker=AAPL&metric_name=ECF
    ```
    
    **Response:**
    Returns a flat array of metric records, ordered by ticker, fiscal_year, and metric_name:
    ```json
    {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "parameter_set_id": "660e8400-e29b-41d4-a716-446655440001",
        "results_count": 125,
        "results": [
            {
                "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
                "parameter_set_id": "660e8400-e29b-41d4-a716-446655440001",
                "ticker": "AAPL",
                "fiscal_year": 2020,
                "metric_name": "Beta",
                "value": 1.25,
                "unit": "dimensionless"
            },
            {
                "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
                "parameter_set_id": "660e8400-e29b-41d4-a716-446655440001",
                "ticker": "AAPL",
                "fiscal_year": 2020,
                "metric_name": "ECF",
                "value": 1250000000.0,
                "unit": "USD"
            }
        ],
        "filters_applied": {
            "ticker": "AAPL"
        },
        "status": "success",
        "message": null
    }
    ```
    
    **Note:** If no metrics are found for the given criteria, an empty array is returned with a warning message.
    Metric units come from the `metric_units` table and may be null for metrics without defined units.
    """
    try:
        # Initialize repository
        repo = MetricsQueryRepository(db)
        
        # Query metrics
        records = await repo.get_metrics(
            dataset_id=dataset_id,
            parameter_set_id=parameter_set_id,
            ticker=ticker,
            metric_name=metric_name,
        )
        
        # Log results
        logger.info(
            f"Retrieved {len(records)} metrics for dataset {dataset_id}, "
            f"param_set {parameter_set_id}, ticker={ticker}, metric_name={metric_name}"
        )
        
        # Build filters_applied summary
        filters_applied = {}
        if ticker:
            filters_applied["ticker"] = ticker
        if metric_name:
            filters_applied["metric_name"] = metric_name
        
        # Warn if no results found
        message = None
        if len(records) == 0:
            message = f"No metrics found for dataset {dataset_id} and parameter_set {parameter_set_id}"
            if ticker or metric_name:
                message += f" with filters: ticker={ticker}, metric_name={metric_name}"
            logger.warning(message)
        
        # Build response
        return GetMetricsResponse(
            dataset_id=dataset_id,
            parameter_set_id=parameter_set_id,
            results_count=len(records),
            results=records,
            filters_applied=filters_applied,
            status="success",
            message=message,
        )
    
    except Exception as e:
        logger.error(f"Error retrieving metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metrics: {str(e)}"
        )

