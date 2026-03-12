# ============================================================================
# Parameter Validation Service
# ============================================================================
from typing import Any, Optional, Tuple


class ParameterValidator:
    """Validates parameter values against their expected types."""
    
    # Mapping of parameter names to their expected types
    PARAMETER_TYPES = {
        # TEXT parameters
        "country": "TEXT",
        "currency_notation": "TEXT",
        "cost_of_equity_approach": "TEXT",
        
        # BOOLEAN parameters
        "include_franking_credits_tsr": "BOOLEAN",
        
        # NUMERIC parameters
        "fixed_benchmark_return_wealth_preservation": "NUMERIC",
        "equity_risk_premium": "NUMERIC",
        "tax_rate_franking_credits": "NUMERIC",
        "value_of_franking_credits": "NUMERIC",
        "risk_free_rate_rounding": "NUMERIC",
        "beta_rounding": "NUMERIC",
        "last_calendar_year": "NUMERIC",
        "beta_relative_error_tolerance": "NUMERIC",
        "terminal_year": "NUMERIC",
    }
    
    # Parameter constraints (value ranges)
    PARAMETER_CONSTRAINTS = {
        "tax_rate_franking_credits": {"min": 0, "max": 100, "description": "Must be between 0 and 100 (percentage)"},
        "value_of_franking_credits": {"min": 0, "max": 100, "description": "Must be between 0 and 100 (percentage)"},
        "beta_rounding": {"min": 0, "description": "Must be non-negative"},
        "risk_free_rate_rounding": {"min": 0, "description": "Must be non-negative"},
        "beta_relative_error_tolerance": {"min": 0, "max": 100, "description": "Must be between 0 and 100 (percentage)"},
        "equity_risk_premium": {"min": 0, "description": "Must be non-negative"},
        "fixed_benchmark_return_wealth_preservation": {"min": 0, "description": "Must be non-negative"},
        "last_calendar_year": {"min": 1900, "description": "Must be a reasonable year"},
        "terminal_year": {"min": 1, "description": "Must be a positive integer"},
    }
    
    @classmethod
    def validate_parameter(
        cls,
        param_name: str,
        param_value: Any,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a single parameter value.
        
        Args:
            param_name: Name of the parameter
            param_value: Value to validate
        
        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
            If valid: (True, None)
            If invalid: (False, error_description)
        """
        # Check if parameter is known
        if param_name not in cls.PARAMETER_TYPES:
            return False, f"Unknown parameter: {param_name}"
        
        expected_type = cls.PARAMETER_TYPES[param_name]
        
        # Validate based on expected type
        if expected_type == "TEXT":
            if not isinstance(param_value, str):
                return False, f"Parameter '{param_name}' must be TEXT (string), got {type(param_value).__name__}"
        
        elif expected_type == "BOOLEAN":
            if not isinstance(param_value, bool):
                return False, f"Parameter '{param_name}' must be BOOLEAN, got {type(param_value).__name__}"
        
        elif expected_type == "NUMERIC":
            if not isinstance(param_value, (int, float)):
                return False, f"Parameter '{param_name}' must be NUMERIC (number), got {type(param_value).__name__}"
            
            # Check constraints if defined
            if param_name in cls.PARAMETER_CONSTRAINTS:
                constraints = cls.PARAMETER_CONSTRAINTS[param_name]
                
                if "min" in constraints and param_value < constraints["min"]:
                    return False, f"Parameter '{param_name}': {constraints['description']}"
                
                if "max" in constraints and param_value > constraints["max"]:
                    return False, f"Parameter '{param_name}': {constraints['description']}"
        
        return True, None
    
    @classmethod
    def validate_parameters(
        cls,
        parameters: dict[str, Any],
    ) -> Tuple[bool, Optional[list[str]]]:
        """
        Validate multiple parameters.
        
        Args:
            parameters: Dictionary of parameter_name -> value
        
        Returns:
            Tuple of (all_valid: bool, error_messages: Optional[list[str]])
            If all valid: (True, None)
            If any invalid: (False, [list of error messages])
        """
        errors = []
        
        for param_name, param_value in parameters.items():
            is_valid, error_msg = cls.validate_parameter(param_name, param_value)
            if not is_valid:
                errors.append(error_msg)
        
        if errors:
            return False, errors
        
        return True, None
    
    @classmethod
    def get_parameter_info(cls, param_name: str) -> Optional[dict[str, Any]]:
        """
        Get information about a parameter.
        
        Args:
            param_name: Name of the parameter
        
        Returns:
            Dictionary with parameter metadata or None if not found
        """
        if param_name not in cls.PARAMETER_TYPES:
            return None
        
        info = {
            "parameter_name": param_name,
            "value_type": cls.PARAMETER_TYPES[param_name],
        }
        
        if param_name in cls.PARAMETER_CONSTRAINTS:
            info["constraints"] = cls.PARAMETER_CONSTRAINTS[param_name]
        
        return info
    
    @classmethod
    def list_all_parameters(cls) -> list[dict[str, Any]]:
        """
        Get list of all known parameters with their types.
        
        Returns:
            List of parameter info dictionaries
        """
        params = []
        for param_name in sorted(cls.PARAMETER_TYPES.keys()):
            params.append(cls.get_parameter_info(param_name))
        return params
