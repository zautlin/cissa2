# ============================================================================
# Metrics API Endpoints
# ============================================================================
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, Union
from datetime import datetime

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
    MetricsHealthResponse,
    GetMetricsResponse,
)
from ....services.metrics_service import MetricsService
from ....services.l2_metrics_service import L2MetricsService
from ....services.beta_calculation_service import BetaCalculationService
from ....services.beta_rounding_service import BetaRoundingService
from ....services.risk_free_rate_service import RiskFreeRateCalculationService
from ....services.ratio_metrics_service import RatioMetricsService
from ....repositories.metrics_query_repository import MetricsQueryRepository
from ....models.ratio_metrics import (
    RatioMetricsResponse,
    RatioMetricsMultiWindowResponse
)
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
        "metric_name": "Calc FY TSR",
        "param_set_id": "660e8400-e29b-41d4-a716-446655440001"
    }
    ```
    
    **Supported L1 Metrics:**
    - Simple (7): Calc MC, Calc Assets, Calc OA, Calc Op Cost, Calc Non Op Cost, Calc Tax Cost, Calc XO Cost
    - Temporal (5): Calc ECF, Non Div ECF, Calc EE, Calc FY TSR (requires param_set_id), Calc FY TSR PREL (requires param_set_id)
    
    **Note:** Calc FY TSR and Calc FY TSR PREL are parameter-sensitive. If param_set_id is not provided, the default parameter set will be used.
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
    
    **DEPRECATED:** This endpoint is deprecated. Please use `/api/v1/metrics/get_metrics/` instead,
    which provides more flexible filtering and supports fundamentals table queries.
    
    This endpoint:
    1. Checks if metric exists in metrics_outputs
    2. If not, calculates it
    3. Returns the results
    """
    
    # Log deprecation warning
    logger.warning(
        f"DEPRECATED ENDPOINT CALLED: GET /api/v1/metrics/dataset/{dataset_id}/metrics/{metric_name} - "
        f"Please migrate to GET /api/v1/metrics/get_metrics/ which is more flexible"
    )
    
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

@router.post("/beta/calculate", response_model=CalculateBetaResponse, status_code=status.HTTP_200_OK, deprecated=True)
async def calculate_beta(
    request: CalculateBetaRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate beta using rolling OLS regression on monthly returns.
    
    **⚠️ DEPRECATED:** This endpoint uses the legacy runtime calculation path.
    For pre-computed Beta with instant results, use `/beta/calculate-from-precomputed` instead.
    
    **Legacy Beta Calculation Algorithm:**
    1. Fetch monthly COMPANY_TSR and INDEX_TSR from fundamentals
    2. Calculate 60-month rolling OLS slopes (60 seconds)
    3. Transform slopes: adjusted = (slope * 2/3) + 1/3
    4. Filter by relative error tolerance
    5. Round by beta_rounding parameter
    6. Annualize and apply 4-tier fallback logic
    7. Apply cost_of_equity_approach (FIXED or Floating)
    8. Store in metrics_outputs
    
    **NEW PATH (Recommended):**
    - Use `/beta/calculate-from-precomputed` (instant, <10ms)
    - Pre-computed Beta values are calculated during data ingestion
    
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
    
    logger.info(f"[LEGACY] Processing beta calculation request: dataset={request.dataset_id}, param_set={request.param_set_id}")
    
    try:
        service = BetaCalculationService(db)
        result = await service.calculate_beta_async(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id
        )
        
        if result["status"] == "error":
            logger.warning(f"[LEGACY] Beta calculation failed: {result['message']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        logger.info(f"[LEGACY] Beta calculation {'cached' if result['status'] == 'cached' else 'successful'}: {result['results_count']} records")
        
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
        logger.error(f"[LEGACY] Unexpected error during beta calculation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during beta calculation"
        )


@router.post("/beta/calculate-from-precomputed", response_model=CalculateBetaResponse, status_code=status.HTTP_200_OK)
async def calculate_beta_from_precomputed(
    request: CalculateBetaRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate beta using pre-computed values with user-selected rounding.
    
    **NEW FAST PATH (RECOMMENDED):** Returns results in <10ms
    
    **Algorithm:**
    1. Check if pre-computed Beta exists (param_set_id=NULL)
    2. If YES: Apply user-selected rounding + approach, store with param_set_id, return (instant)
    3. If NO: Fall back to legacy runtime calculation (60 seconds)
    
    **Pre-computed Beta:**
    - Pre-computed during data ingestion via ETL pipeline
    - Stored with param_set_id=NULL in metrics_outputs
    - Contains raw unrounded values for both FIXED and Floating approaches
    - Allows instant calculation with any rounding value
    
    **Performance:**
    - With pre-computed Beta: <10 milliseconds
    - Without pre-computed Beta: ~60 seconds (legacy path)
    - Expected speedup: 6,000x faster
    
    **Prerequisites:**
    - Pre-computed Beta must exist (created during data ingestion)
    - param_set_id must exist in parameter_sets
    
    **Parameters from param_set:**
    - beta_rounding: Rounding increment (e.g., 0.1, 0.05, 0.01)
    - cost_of_equity_approach: "FIXED" or "Floating"
    
    **Example Request:**
    ```json
    {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "param_set_id": "660e8400-e29b-41d4-a716-446655440001"
    }
    ```
    
    **Response:**
    - status: 'success', 'precomputed', or 'error'
    - results_count: number of beta records
    - message: operation summary
    """
    
    logger.info(f"[PRE-COMPUTED] Processing beta request: dataset={request.dataset_id}, param_set={request.param_set_id}")
    
    try:
        # Load parameters
        from ....repositories.parameter_repository import ParameterRepository
        param_repo = ParameterRepository(db)
        param_dict = await param_repo.get_parameter_set_dict(request.param_set_id)
        
        beta_rounding = float(param_dict.get("beta_rounding", 0.1))
        approach_to_ke = param_dict.get("cost_of_equity_approach", "Floating")
        
        logger.info(f"[PRE-COMPUTED] Parameters: rounding={beta_rounding}, approach={approach_to_ke}")
        
        # Check for pre-computed Beta
        rounding_service = BetaRoundingService(db)
        precomputed_exists = await rounding_service.check_precomputed_exists(
            request.dataset_id
        )
        
        if precomputed_exists:
            logger.info(f"[PRE-COMPUTED] Pre-computed Beta found, applying rounding...")
            
            # Apply rounding to pre-computed Beta
            result = await rounding_service.apply_rounding_to_precomputed_beta(
                dataset_id=request.dataset_id,
                param_set_id=request.param_set_id,
                beta_rounding=beta_rounding,
                approach_to_ke=approach_to_ke,
            )
            
            if result["status"] == "error":
                logger.warning(f"[PRE-COMPUTED] Rounding application failed: {result['message']}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result["message"]
                )
            
            logger.info(f"[PRE-COMPUTED] ✓ Rounding applied: {result['results_count']} records")
            
            return CalculateBetaResponse(
                dataset_id=request.dataset_id,
                param_set_id=request.param_set_id,
                results_count=result["results_count"],
                status="precomputed",
                message=f"✓ Pre-computed Beta with rounding={beta_rounding}, approach={approach_to_ke}: {result['results_count']} records"
            )
        else:
            logger.info(f"[PRE-COMPUTED] No pre-computed Beta found, falling back to legacy calculation...")
            
            # Fall back to legacy runtime calculation
            service = BetaCalculationService(db)
            result = await service.calculate_beta_async(
                dataset_id=request.dataset_id,
                param_set_id=request.param_set_id
            )
            
            if result["status"] == "error":
                logger.warning(f"[PRE-COMPUTED FALLBACK] Beta calculation failed: {result['message']}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result["message"]
                )
            
            logger.info(f"[PRE-COMPUTED FALLBACK] ✓ Fallback calculation successful: {result['results_count']} records")
            
            return CalculateBetaResponse(
                dataset_id=request.dataset_id,
                param_set_id=request.param_set_id,
                results_count=result["results_count"],
                status="fallback_legacy",
                message=f"⚠️  Using legacy path (no pre-computed Beta found): {result['results_count']} records"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PRE-COMPUTED] Unexpected error: {str(e)}", exc_info=True)
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
    Calculate risk-free rate at runtime using monthly bond yields.
    
    **NOTE:** This is now a runtime-only endpoint. Risk-Free Rate is calculated on-demand
    based on the selected parameter set's approach and rounding settings.
    
    **Risk-Free Rate Calculation Algorithm:**
    1. Fetch monthly RISK_FREE_RATE data for bond index (GACGB10 Index for Australia)
    2. Calculate rolling 12-month geometric mean: Rf_1Y_Raw = (∏monthly_rates)^(1/12) - 1
    3. Apply rounding: Rf_1Y = round((Rf_1Y_Raw / beta_rounding), 0) * beta_rounding
    4. Apply approach:
       - FIXED: Rf = benchmark - risk_premium (static)
       - FLOATING: Rf = Rf_1Y (dynamic, uses latest monthly data)
    
    **Prerequisites:**
    - Monthly RISK_FREE_RATE data must exist in fundamentals table (GACGB10 Index)
    - dataset_id must exist
    - param_set_id must exist with proper parameter overrides
    
    **Parameters from param_set:**
    - cost_of_equity_approach: "FIXED" or "FLOATING"
    - beta_rounding: Rounding increment (e.g., 0.005 for 0.5%)
    - benchmark: Benchmark return for FIXED approach
    - risk_premium: Risk premium amount
    
    **Example Request:**
    ```json
    {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "param_set_id": "660e8400-e29b-41d4-a716-446655440001"
    }
    ```
    
    **Response:**
    - value: Calculated risk-free rate as a float
    - status: 'success' or 'error'
    - timestamp: When calculation was performed
    """
    
    logger.info(f"Processing runtime risk-free rate calculation: dataset={request.dataset_id}, param_set={request.param_set_id}")
    
    try:
        service = RiskFreeRateCalculationService(db)
        rf_value = await service.calculate_risk_free_rate_runtime(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id
        )
        
        logger.info(f"Runtime risk-free rate calculation successful: {rf_value:.6f}")
        
        return CalculateRiskFreeRateResponse(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id,
            value=rf_value,
            status="success",
            timestamp=datetime.utcnow(),
            message=f"Risk-free rate calculated at runtime: {rf_value:.6f}"
        )
    
    except Exception as e:
        logger.error(f"Runtime risk-free rate calculation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk-free rate calculation failed: {str(e)}"
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
    Calculate Cost of Equity at runtime: KE = Rf + Beta × RiskPremium
    
    **NOTE:** This is now a runtime-only endpoint. Cost of Equity is calculated on-demand
    by combining pre-computed Beta with runtime Risk-Free Rate calculation.
    
    **Calculation Flow:**
    1. Fetch pre-computed Beta (stored with param_set_id=NULL) from Phase 2
    2. Apply param_set-specific rounding and approach (fixed/floating)
    3. Calculate Risk-Free Rate at runtime using selected approach
    4. Calculate KE = Rf + Beta × RiskPremium
    
    **Prerequisites:**
    - Phase 2 (Beta pre-computation) must be completed
    - Monthly bond yield data must exist in fundamentals
    - param_set_id must exist with proper parameter overrides
    
    **Parameters from param_set:**
    - cost_of_equity_approach: "FIXED" or "FLOATING"
    - equity_risk_premium: Risk premium multiplier (e.g., 0.05 for 5%)
    - beta_rounding: Rounding for Beta (e.g., 0.005 for 0.5%)
    - benchmark: Benchmark return for FIXED Rf approach
    
    **Example Request:**
    ```json
    {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "param_set_id": "660e8400-e29b-41d4-a716-446655440001"
    }
    ```
    
    **Response:**
    - value: Calculated Cost of Equity as a float
    - status: 'success' or 'error'
    - timestamp: When calculation was performed
    - message: Includes breakdown (Rf + Beta × RiskPremium)
    """
    
    logger.info(f"Processing runtime Cost of Equity calculation: dataset={request.dataset_id}, param_set={request.param_set_id}")
    
    try:
        from ....services.cost_of_equity_service import CostOfEquityService
        
        service = CostOfEquityService(db)
        ke_value = await service.calculate_cost_of_equity_runtime(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id
        )
        
        logger.info(f"Runtime Cost of Equity calculation successful: {ke_value:.6f}")
        
        return CalculateEnhancedMetricsResponse(
            dataset_id=request.dataset_id,
            param_set_id=request.param_set_id,
            value=ke_value,
            metrics_calculated=["Calc KE"],
            status="success",
            timestamp=datetime.utcnow(),
            message=f"Cost of Equity calculated at runtime: {ke_value:.6f}"
        )
    
    except Exception as e:
        logger.error(f"Runtime Cost of Equity calculation failed: {str(e)}", exc_info=True)
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
    - Phase 06 L1 Basic Metrics (DIVIDENDS, FRANKING, Non Div ECF from fundamentals)
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
     - `metric_name` (optional): Filter by metric name (case-insensitive, e.g., "Calc ECF", "Beta")
    
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
    GET /api/v1/metrics/get_metrics/?dataset_id=550e8400-e29b-41d4-a716-446655440000&parameter_set_id=660e8400-e29b-41d4-a716-446655440001&metric_name=Calc ECF
    ```
    
    Get a specific metric for a specific ticker:
    ```
    GET /api/v1/metrics/get_metrics/?dataset_id=550e8400-e29b-41d4-a716-446655440000&parameter_set_id=660e8400-e29b-41d4-a716-446655440001&ticker=AAPL&metric_name=Calc ECF
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
                "metric_name": "Calc ECF",
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
        
        # Build appropriate message based on results
        message = None
        filter_desc = []
        if ticker:
            filter_desc.append(f"ticker={ticker}")
        if metric_name:
            filter_desc.append(f"metric_name={metric_name}")
        
        if len(records) == 0:
            message = f"No metrics found for dataset {dataset_id} and parameter_set {parameter_set_id}"
            if filter_desc:
                message += f" with filters: {', '.join(filter_desc)}"
            logger.warning(message)
        else:
            # Provide success message with result count
            if filter_desc:
                message = f"Retrieved {len(records)} metrics with filters: {', '.join(filter_desc)}"
            else:
                message = f"Retrieved {len(records)} metrics"
        
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


@router.get("/ratio-metrics", response_model=Union[RatioMetricsResponse, RatioMetricsMultiWindowResponse])
async def get_ratio_metrics(
    metric: str = Query(..., description="Metric ID (e.g., 'mb_ratio')"),
    tickers: str = Query(..., description="Comma-separated ticker list (e.g., 'AAPL,MSFT')"),
    dataset_id: UUID = Query(..., description="Dataset ID"),
    temporal_window: str = Query("1Y", min_length=2, max_length=50, description="Temporal window(s): single value (1Y) or comma-separated (1Y,3Y,5Y)"),
    param_set_id: Optional[UUID] = Query(None, description="Parameter set ID (defaults to base_case)"),
    start_year: Optional[int] = Query(None, description="Optional start year filter"),
    end_year: Optional[int] = Query(None, description="Optional end year filter"),
    db: AsyncSession = Depends(get_db)
) -> Union[RatioMetricsResponse, RatioMetricsMultiWindowResponse]:
    """
    Calculate ratio metrics with rolling averages.
    
    **Supported metrics:**
    - mb_ratio: Market-to-Book Ratio (Market Cap / Economic Equity)
    
    **Temporal windows:**
    - 1Y: Annual values (current year only)
    - 3Y: 3-year rolling average (starts year 2003 if data from 2001)
    - 5Y: 5-year rolling average (starts year 2005)
    - 10Y: 10-year rolling average (starts year 2010)
    
    **Single window (backward compatible):**
        GET /api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=AAPL,MSFT&temporal_window=3Y&dataset_id=...
    
    **Multiple windows (new):**
        GET /api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=AAPL,MSFT&temporal_window=1Y,3Y,5Y&dataset_id=...
    """
    
    try:
        # Parse comma-separated tickers and validate (preserve original case)
        ticker_list = [t.strip() for t in tickers.split(",")]
        if not ticker_list or any(not t for t in ticker_list):
            raise ValueError("Invalid ticker list")
        
        # Parse temporal window(s)
        window_list = [w.strip() for w in temporal_window.split(",")]
        is_multi_window = len(window_list) > 1
        
        logger.info(
            f"Calculating {metric} for tickers {ticker_list}, "
            f"windows={window_list} ({'multi-window' if is_multi_window else 'single-window'})"
        )
        
        # Initialize service
        service = RatioMetricsService(db)
        
        # Calculate metric
        if is_multi_window:
            # Multi-window query
            result = await service.calculate_ratio_metric_multi_window(
                metric_id=metric,
                tickers=ticker_list,
                dataset_id=dataset_id,
                temporal_windows=window_list,
                param_set_id=param_set_id,
                start_year=start_year,
                end_year=end_year
            )
        else:
            # Single-window query (backward compatible)
            result = await service.calculate_ratio_metric(
                metric_id=metric,
                tickers=ticker_list,
                dataset_id=dataset_id,
                temporal_window=window_list[0],
                param_set_id=param_set_id,
                start_year=start_year,
                end_year=end_year
            )
        
        return result
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error calculating ratio metric: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate ratio metric: {str(e)}"
        )

