# ============================================================================
# Parameter Management Service Layer
# ============================================================================
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, Any
from datetime import datetime

from ..models.schemas import ParameterSetResponse
from ..repositories.parameter_repository import ParameterRepository
from .parameter_validator import ParameterValidator
from ..core.config import get_logger

logger = get_logger(__name__)


class ParameterService:
    """Service layer for parameter management operations."""
    
    def __init__(self, session: AsyncSession):
        """Initialize with async database session."""
        self.session = session
        self.repository = ParameterRepository(session)
    
    async def get_merged_parameters(self, param_set_id: UUID) -> dict[str, Any]:
        """
        Get all parameters for a parameter set with merged values.
        
        Merges baseline parameters from cissa.parameters table
        with JSONB overrides from parameter_set.param_overrides.
        
        Overrides take precedence over baseline values.
        
        Returns:
            Dictionary of parameter_name -> value (merged)
        """
        # Fetch baseline parameters
        baseline = await self.repository.get_baseline_parameters()
        
        # Fetch the parameter set with overrides
        param_set = await self.repository.get_parameter_set_by_id(param_set_id)
        
        if not param_set:
            raise ValueError(f"Parameter set {param_set_id} not found")
        
        # Merge: baseline + overrides (overrides take precedence)
        merged = baseline.copy()
        merged.update(param_set.get("param_overrides", {}))
        
        return merged
    
    async def get_parameter_set(self, param_set_id: UUID) -> ParameterSetResponse:
        """
        Fetch a parameter set with merged values.
        
        Args:
            param_set_id: UUID of the parameter set
        
        Returns:
            ParameterSetResponse with merged parameters
        
        Raises:
            ValueError: If parameter set not found
        """
        param_set = await self.repository.get_parameter_set_by_id(param_set_id)
        
        if not param_set:
            raise ValueError(f"Parameter set {param_set_id} not found")
        
        # Get merged parameters
        merged_params = await self.get_merged_parameters(param_set_id)
        
        return ParameterSetResponse(
            param_set_id=param_set["param_set_id"],
            param_set_name=param_set["param_set_name"],
            is_active=param_set["is_active"],
            is_default=param_set["is_default"],
            created_at=param_set["created_at"],
            updated_at=param_set["updated_at"],
            parameters=merged_params,
            status="success",
        )
    
    async def get_active_parameter_set(self) -> ParameterSetResponse:
        """
        Fetch the currently active parameter set with merged values.
        
        Returns:
            ParameterSetResponse of the active parameter set
        
        Raises:
            ValueError: If no active parameter set found
        """
        param_set = await self.repository.get_active_parameter_set()
        
        if not param_set:
            raise ValueError("No active parameter set found")
        
        # Get merged parameters
        merged_params = await self.get_merged_parameters(param_set["param_set_id"])
        
        return ParameterSetResponse(
            param_set_id=param_set["param_set_id"],
            param_set_name=param_set["param_set_name"],
            is_active=param_set["is_active"],
            is_default=param_set["is_default"],
            created_at=param_set["created_at"],
            updated_at=param_set["updated_at"],
            parameters=merged_params,
            status="success",
        )
    
    async def update_parameters(
        self,
        param_set_id: UUID,
        updates: dict[str, Any],
        set_as_active: bool = False,
        set_as_default: bool = False,
    ) -> ParameterSetResponse:
        """
        Update parameters by creating a new parameter set.
        
        This method:
        1. Validates all parameter values
        2. Fetches the current active parameter set
        3. Merges existing overrides with new updates
        4. Creates a NEW parameter_set record with updated overrides
        5. Optionally sets it as active or default
        
        Args:
            param_set_id: The parameter set to base updates on (usually current active)
            updates: Dictionary of parameter_name -> new_value
            set_as_active: If True, set the new set as active
            set_as_default: If True, set the new set as default
        
        Returns:
            ParameterSetResponse of the newly created parameter set
        
        Raises:
            ValueError: If parameter set not found or parameters are invalid
        """
        # Validate parameters first
        is_valid, errors = ParameterValidator.validate_parameters(updates)
        if not is_valid:
            error_msg = "Parameter validation failed: " + "; ".join(errors)
            raise ValueError(error_msg)
        
        # Fetch the current parameter set
        current_param_set = await self.repository.get_parameter_set_by_id(param_set_id)
        
        if not current_param_set:
            raise ValueError(f"Parameter set {param_set_id} not found")
        
        # Get current overrides
        current_overrides = current_param_set.get("param_overrides", {})
        
        # Merge with new updates
        new_overrides = current_overrides.copy()
        new_overrides.update(updates)
        
        # Generate a new parameter set name (timestamp-based for uniqueness)
        from datetime import datetime as dt
        timestamp = dt.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        new_param_set_name = f"param_set_{timestamp}"
        
        # Create the new parameter set
        new_param_set_id = await self.repository.create_parameter_set(
            param_set_name=new_param_set_name,
            param_overrides=new_overrides,
            is_active=set_as_active,
            is_default=set_as_default,
            description=f"Updated from {current_param_set.get('param_set_name', str(param_set_id))}",
        )
        
        logger.info(
            f"Created new parameter set {new_param_set_id} "
            f"(active={set_as_active}, default={set_as_default})"
        )
        
        # Update active/default flags if requested
        if set_as_active:
            await self.repository.set_active_parameter_set(new_param_set_id)
            logger.info(f"Set parameter set {new_param_set_id} as active")
        
        if set_as_default:
            await self.repository.set_default_parameter_set(new_param_set_id)
            logger.info(f"Set parameter set {new_param_set_id} as default")
        
        # Return the newly created parameter set
        return await self.get_parameter_set(new_param_set_id)
    
    async def set_active_parameter_set(self, param_set_id: UUID) -> ParameterSetResponse:
        """
        Set a parameter set as the active one.
        
        Only one parameter set can be active at a time.
        
        Args:
            param_set_id: UUID of the parameter set to activate
        
        Returns:
            ParameterSetResponse of the newly active parameter set
        
        Raises:
            ValueError: If parameter set not found
        """
        param_set = await self.repository.get_parameter_set_by_id(param_set_id)
        
        if not param_set:
            raise ValueError(f"Parameter set {param_set_id} not found")
        
        await self.repository.set_active_parameter_set(param_set_id)
        logger.info(f"Set parameter set {param_set_id} as active")
        
        return await self.get_parameter_set(param_set_id)
    
    async def set_default_parameter_set(self, param_set_id: UUID) -> ParameterSetResponse:
        """
        Set a parameter set as the default one.
        
        Only one parameter set can be default at a time.
        
        Args:
            param_set_id: UUID of the parameter set to set as default
        
        Returns:
            ParameterSetResponse of the newly default parameter set
        
        Raises:
            ValueError: If parameter set not found
        """
        param_set = await self.repository.get_parameter_set_by_id(param_set_id)
        
        if not param_set:
            raise ValueError(f"Parameter set {param_set_id} not found")
        
        await self.repository.set_default_parameter_set(param_set_id)
        logger.info(f"Set parameter set {param_set_id} as default")
        
        return await self.get_parameter_set(param_set_id)
