"""JSON utilities for parameter deduplication and canonical representation."""

import json
from typing import Any, Dict


def canonical_json(data: Dict[str, Any]) -> str:
    """
    Convert dict to canonical JSON string for parameter deduplication.
    
    Ensures identical parameters always serialize to the same JSON string,
    enabling reliable hashing and comparison.
    
    Rules:
    - Sort keys alphabetically
    - No spaces after separators
    - Consistent key ordering
    
    Args:
        data: Dictionary of parameters
        
    Returns:
        Canonical JSON string
        
    Example:
        >>> canonical_json({'b': 2, 'a': 1})
        '{"a":1,"b":2}'
        >>> canonical_json({'b': 2, 'a': 1}) == canonical_json({'a': 1, 'b': 2})
        True
    """
    return json.dumps(data, sort_keys=True, separators=(',', ':'))
