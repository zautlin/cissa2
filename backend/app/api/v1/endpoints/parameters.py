# ============================================================================
# Parameters API Endpoints
# ============================================================================
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from ....core.database import get_db
from ....models import (
    ParameterUpdateRequest,
    ParameterSetResponse,
)
from ....services.parameter_service import ParameterService
from ....core.config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/parameters", tags=["parameters"])


@router.get("/active", response_model=ParameterSetResponse)
async def get_active_parameters(
    db: AsyncSession = Depends(get_db)
):
    """
    Get the currently active parameter set with all merged parameter values.
    
    This endpoint returns the parameter set that is currently active (is_active=true)
    with all baseline parameters merged with any overrides.
    
    **Example Response:**
    ```json
    {
        "param_set_id": "550e8400-e29b-41d4-a716-446655440000",
        "param_set_name": "param_set_20260312_101530_123456",
        "is_active": true,
        "is_default": false,
        "created_at": "2026-03-12T10:15:30Z",
        "updated_at": "2026-03-12T10:15:30Z",
        "parameters": {
            "country": "AU",
            "currency_notation": "AUD",
            "cost_of_equity_approach": "CAPM",
            "include_franking_credits_tsr": true,
            "tax_rate_franking_credits": 0.30,
            "beta_rounding": 2,
            "risk_free_rate_rounding": 4,
            ...all other parameters
        },
        "status": "success",
        "message": null
    }
    ```
    
    **Use Cases:**
    - UI page load: retrieve user's current working parameters
    - Before calculation: verify which parameters will be used
    """
    try:
        service = ParameterService(db)
        response = await service.get_active_parameter_set()
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error fetching active parameters: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@router.get("/{param_set_id}", response_model=ParameterSetResponse)
async def get_parameter_set(
    param_set_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific parameter set by ID with all merged parameter values.
    
    This endpoint retrieves a parameter set by its UUID and returns all parameters
    with baseline values merged with any overrides from that specific set.
    
    **Path Parameters:**
    - `param_set_id` (UUID): The ID of the parameter set to retrieve
    
    **Example Request:**
    ```
    GET /api/v1/parameters/550e8400-e29b-41d4-a716-446655440000
    ```
    
    **Example Response:**
    ```json
    {
        "param_set_id": "550e8400-e29b-41d4-a716-446655440000",
        "param_set_name": "param_set_20260312_101530_123456",
        "is_active": false,
        "is_default": false,
        "created_at": "2026-03-12T10:15:30Z",
        "updated_at": "2026-03-12T10:15:30Z",
        "parameters": {
            "country": "AU",
            "currency_notation": "AUD",
            "cost_of_equity_approach": "CAPM",
            "tax_rate_franking_credits": 0.35,
            "beta_rounding": 3,
            ...
        },
        "status": "success",
        "message": null
    }
    ```
    
    **Use Cases:**
    - Retrieve a previously saved parameter set
    - Compare different parameter sets
    - Audit parameter values used in a past calculation
    """
    try:
        service = ParameterService(db)
        response = await service.get_parameter_set(param_set_id)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error fetching parameter set {param_set_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@router.post("/{param_set_id}/update", response_model=ParameterSetResponse)
async def update_parameters(
    param_set_id: UUID,
    request: ParameterUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Update one or more parameters and create a new parameter set.
    
    This endpoint creates a NEW parameter set with the updated parameter values.
    The new parameter set inherits all current values from the specified parameter set
    and applies the provided updates.
    
    **Important:** This does NOT modify the baseline `parameters` table directly.
    All customizations are stored as JSONB overrides in the new parameter_set record.
    
    **Path Parameters:**
    - `param_set_id` (UUID): The parameter set to base updates on (usually the current active one)
    
    **Request Body:**
    ```json
    {
        "parameters": {
            "tax_rate_franking_credits": 0.35,
            "beta_rounding": 3
        },
        "set_as_active": true,
        "set_as_default": false
    }
    ```
    
    **Response (same as GET endpoint):**
    ```json
    {
        "param_set_id": "660e8400-e29b-41d4-a716-446655440001",
        "param_set_name": "param_set_20260312_102045_654321",
        "is_active": true,
        "is_default": false,
        "created_at": "2026-03-12T10:20:45Z",
        "updated_at": "2026-03-12T10:20:45Z",
        "parameters": {
            "country": "AU",
            "currency_notation": "AUD",
            "cost_of_equity_approach": "CAPM",
            "include_franking_credits_tsr": true,
            "tax_rate_franking_credits": 0.35,
            "beta_rounding": 3,
            ...
        },
        "status": "success",
        "message": null
    }
    ```
    
    **Query Parameters:**
    - None
    
    **Request Schema:**
    - `parameters` (dict[str, any], required): Key-value pairs of parameters to update
      - Examples: `{'tax_rate_franking_credits': 0.35}` or `{'beta_rounding': 3, 'risk_free_rate_rounding': 4}`
    - `set_as_active` (bool, optional, default=false): If true, the new parameter set becomes active
    - `set_as_default` (bool, optional, default=false): If true, the new parameter set becomes the default
    
    **Workflow:**
    1. User updates one or more parameters in the UI
    2. UI calls POST with the updated values and flags
    3. A NEW parameter_set is created with updated JSONB overrides
    4. If `set_as_active=true`: new set becomes the active parameter set
    5. If `set_as_default=true`: new set becomes the default parameter set
    6. UI receives response with new parameter set ID and all merged values
    
    **Common Use Cases:**
    
    **Use Case 1: Update parameter and make active**
    ```json
    {
        "parameters": {"tax_rate_franking_credits": 0.35},
        "set_as_active": true,
        "set_as_default": false
    }
    ```
    Result: New parameter set created, becomes active, calculations now use new value
    
    **Use Case 2: Update multiple parameters and make both active AND default**
    ```json
    {
        "parameters": {
            "tax_rate_franking_credits": 0.35,
            "beta_rounding": 3,
            "risk_free_rate_rounding": 4
        },
        "set_as_active": true,
        "set_as_default": true
    }
    ```
    Result: New parameter set with all updates, becomes active and default
    
    **Use Case 3: Update parameter but keep current set active (save for later)**
    ```json
    {
        "parameters": {"beta_rounding": 3},
        "set_as_active": false,
        "set_as_default": false
    }
    ```
    Result: New parameter set created but not activated; current active set unchanged
    """
    try:
        service = ParameterService(db)
        response = await service.update_parameters(
            param_set_id=param_set_id,
            updates=request.parameters,
            set_as_active=request.set_as_active,
            set_as_default=request.set_as_default,
        )
        return response
    except ValueError as e:
        error_msg = str(e)
        # Check if it's a validation error
        if "Parameter validation failed" in error_msg:
            raise HTTPException(
                status_code=422,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=error_msg
            )
    except Exception as e:
        logger.error(f"Error updating parameters: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@router.post("/{param_set_id}/set-active", response_model=ParameterSetResponse)
async def set_parameter_set_active(
    param_set_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Set a parameter set as the currently active one.
    
    This endpoint activates a specific parameter set without creating a new one.
    Only one parameter set can be active at a time; this deactivates all others.
    
    **Path Parameters:**
    - `param_set_id` (UUID): The ID of the parameter set to activate
    
    **Example Request:**
    ```
    POST /api/v1/parameters/550e8400-e29b-41d4-a716-446655440000/set-active
    ```
    
    **Example Response:**
    ```json
    {
        "param_set_id": "550e8400-e29b-41d4-a716-446655440000",
        "param_set_name": "param_set_20260312_101530_123456",
        "is_active": true,
        "is_default": false,
        "created_at": "2026-03-12T10:15:30Z",
        "updated_at": "2026-03-12T10:15:30Z",
        "parameters": {...},
        "status": "success",
        "message": null
    }
    ```
    
    **Use Case:**
    - Switch back to a previously saved parameter set without modifying parameters
    - User wants to reactivate a past set they experimented with
    """
    try:
        service = ParameterService(db)
        response = await service.set_active_parameter_set(param_set_id)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error setting parameter set {param_set_id} as active: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@router.post("/{param_set_id}/set-default", response_model=ParameterSetResponse)
async def set_parameter_set_default(
    param_set_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Set a parameter set as the default one.
    
    This endpoint marks a specific parameter set as the default without creating a new one.
    Only one parameter set can be default at a time; this unsets all others.
    
    **Important:** The default parameter set does NOT need to be the active one.
    The default is what users "reset to" if desired, while the active set is what's
    currently being used for calculations.
    
    **Path Parameters:**
    - `param_set_id` (UUID): The ID of the parameter set to set as default
    
    **Example Request:**
    ```
    POST /api/v1/parameters/550e8400-e29b-41d4-a716-446655440000/set-default
    ```
    
    **Example Response:**
    ```json
    {
        "param_set_id": "550e8400-e29b-41d4-a716-446655440000",
        "param_set_name": "param_set_20260312_101530_123456",
        "is_active": false,
        "is_default": true,
        "created_at": "2026-03-12T10:15:30Z",
        "updated_at": "2026-03-12T10:15:30Z",
        "parameters": {...},
        "status": "success",
        "message": null
    }
    ```
    
    **Use Case:**
    - User has a standard configuration they want as their "baseline"
    - They can temporarily switch to other parameter sets for analysis
    - They can always reset to the default set when needed
    """
    try:
        service = ParameterService(db)
        response = await service.set_default_parameter_set(param_set_id)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error setting parameter set {param_set_id} as default: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
