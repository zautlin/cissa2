# ============================================================================
# Parameter Repository Layer
# ============================================================================
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import json
from typing import Optional, Any

from ..models.schemas import ParameterSetResponse


class ParameterRepository:
    """Repository for parameters and parameter_sets table access."""
    
    def __init__(self, session: AsyncSession) -> None:
        """Initialize with async database session."""
        self._session = session
    
    async def get_baseline_parameters(self) -> dict[str, Any]:
        """
        Fetch all baseline parameters from cissa.parameters table.
        
        Returns a dictionary mapping parameter_name -> default_value
        """
        query = text("""
            SELECT parameter_name, default_value, value_type
            FROM cissa.parameters
        """)
        
        result = await self._session.execute(query)
        rows = result.fetchall()
        
        baseline = {}
        for row in rows:
            baseline[row[0]] = row[1]
        
        return baseline
    
    async def get_parameter_set_by_id(self, param_set_id: UUID) -> Optional[dict[str, Any]]:
        """
        Fetch a parameter set by ID, including:
        - param_set_id, param_set_name, is_active, is_default
        - created_at, updated_at
        - param_overrides (JSONB)
        
        Returns raw data dict or None if not found.
        """
        query = """
        SELECT param_set_id, param_set_name, is_active, is_default, 
               param_overrides, created_at, updated_at
        FROM cissa.parameter_sets
        WHERE param_set_id = :param_set_id
        """
        
        result = await self._session.execute(
            query,
            {"param_set_id": str(param_set_id)}
        )
        row = result.fetchone()
        
        if not row:
            return None
        
        return {
            "param_set_id": row[0],
            "param_set_name": row[1],
            "is_active": row[2],
            "is_default": row[3],
            "param_overrides": row[4] or {},
            "created_at": row[5],
            "updated_at": row[6],
        }
    
    async def get_active_parameter_set(self) -> Optional[dict[str, Any]]:
        """
        Fetch the currently active parameter set.
        
        Returns raw data dict or None if not found.
        """
        query = """
        SELECT param_set_id, param_set_name, is_active, is_default, 
               param_overrides, created_at, updated_at
        FROM cissa.parameter_sets
        WHERE is_active = true
        LIMIT 1
        """
        
        result = await self._session.execute(query)
        row = result.fetchone()
        
        if not row:
            return None
        
        return {
            "param_set_id": row[0],
            "param_set_name": row[1],
            "is_active": row[2],
            "is_default": row[3],
            "param_overrides": row[4] or {},
            "created_at": row[5],
            "updated_at": row[6],
        }
    
    async def get_default_parameter_set(self) -> Optional[dict[str, Any]]:
        """
        Fetch the default parameter set.
        
        Returns raw data dict or None if not found.
        """
        query = """
        SELECT param_set_id, param_set_name, is_active, is_default, 
               param_overrides, created_at, updated_at
        FROM cissa.parameter_sets
        WHERE is_default = true
        LIMIT 1
        """
        
        result = await self._session.execute(query)
        row = result.fetchone()
        
        if not row:
            return None
        
        return {
            "param_set_id": row[0],
            "param_set_name": row[1],
            "is_active": row[2],
            "is_default": row[3],
            "param_overrides": row[4] or {},
            "created_at": row[5],
            "updated_at": row[6],
        }
    
    async def create_parameter_set(
        self,
        param_set_name: str,
        param_overrides: dict[str, Any],
        is_active: bool = False,
        is_default: bool = False,
        description: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> UUID:
        """
        Create a new parameter set with JSONB overrides.
        
        Returns the param_set_id of the newly created set.
        """
        query = """
        INSERT INTO cissa.parameter_sets 
        (param_set_name, description, param_overrides, is_active, is_default, created_by)
        VALUES (:param_set_name, :description, :param_overrides, :is_active, :is_default, :created_by)
        RETURNING param_set_id
        """
        
        result = await self._session.execute(
            query,
            {
                "param_set_name": param_set_name,
                "description": description,
                "param_overrides": json.dumps(param_overrides),
                "is_active": is_active,
                "is_default": is_default,
                "created_by": created_by,
            }
        )
        
        new_id = result.scalar()
        await self._session.commit()
        
        return UUID(new_id)
    
    async def set_active_parameter_set(self, param_set_id: UUID) -> None:
        """
        Set a parameter set as active (only one can be active).
        
        Deactivates all others and activates the specified one.
        """
        # First, deactivate all
        deactivate_query = """
        UPDATE cissa.parameter_sets
        SET is_active = false
        WHERE is_active = true
        """
        await self._session.execute(deactivate_query)
        
        # Then activate the specified one
        activate_query = """
        UPDATE cissa.parameter_sets
        SET is_active = true
        WHERE param_set_id = :param_set_id
        """
        await self._session.execute(
            activate_query,
            {"param_set_id": str(param_set_id)}
        )
        
        await self._session.commit()
    
    async def set_default_parameter_set(self, param_set_id: UUID) -> None:
        """
        Set a parameter set as default (only one can be default).
        
        Unsets the previous default and sets the specified one.
        """
        # First, unset all defaults
        unset_query = """
        UPDATE cissa.parameter_sets
        SET is_default = false
        WHERE is_default = true
        """
        await self._session.execute(unset_query)
        
        # Then set the specified one as default
        set_query = """
        UPDATE cissa.parameter_sets
        SET is_default = true
        WHERE param_set_id = :param_set_id
        """
        await self._session.execute(
            set_query,
            {"param_set_id": str(param_set_id)}
        )
        
        await self._session.commit()
    
    async def update_parameter_set_overrides(
        self,
        param_set_id: UUID,
        updated_overrides: dict[str, Any],
    ) -> None:
        """
        Update the JSONB overrides for an existing parameter set.
        """
        query = """
        UPDATE cissa.parameter_sets
        SET param_overrides = :param_overrides
        WHERE param_set_id = :param_set_id
        """
        
        await self._session.execute(
            query,
            {
                "param_set_id": str(param_set_id),
                "param_overrides": json.dumps(updated_overrides),
            }
        )
        
        await self._session.commit()
    
    async def get_all_parameter_sets(self) -> list[dict[str, Any]]:
        """
        Fetch all parameter sets.
        
        Returns list of dicts with parameter set data.
        """
        query = """
        SELECT param_set_id, param_set_name, is_active, is_default, 
               param_overrides, created_at, updated_at
        FROM cissa.parameter_sets
        ORDER BY created_at DESC
        """
        
        result = await self._session.execute(query)
        rows = result.fetchall()
        
        param_sets = []
        for row in rows:
            param_sets.append({
                "param_set_id": row[0],
                "param_set_name": row[1],
                "is_active": row[2],
                "is_default": row[3],
                "param_overrides": row[4] or {},
                "created_at": row[5],
                "updated_at": row[6],
            })
        
        return param_sets
