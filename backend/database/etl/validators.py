"""
Data validation utilities.

Handles numeric validation and pre-checks before data enters the database.
Based on reference-dq-scripts/validator.py, refactored for clarity.
"""

import re
from typing import Tuple, Optional


# Values that are definitively non-numeric
NON_NUMERIC_MARKERS = frozenset({
    '', 'n/a', 'na', 'n.a.', 'n.a', 'nil', 'none', 'null', '-',
    '#ref!', '#value!', '#div/0!', '#n/a', '#name?', '#null!', '#num!',
    '#error!', 'error', 'inf', '-inf', 'nan',
})

# Regex for numeric matching: optional sign, digits, optional decimal, optional exponent
_NUMERIC_RE = re.compile(
    r'^[+-]?'
    r'(\d{1,3}(,\d{3})*|\d+)'   # integer part (with optional thousands commas)
    r'(\.\d+)?'                  # optional decimal
    r'([eE][+-]?\d+)?$'          # optional scientific notation
)

# Characters to strip before numeric check
_STRIP_CHARS_RE = re.compile(r'[$%£€¥\s]')


def validate_numeric(raw_value: str) -> Tuple[Optional[float], bool, Optional[str]]:
    """
    Validate whether raw_value can be interpreted as a number.
    
    Handles:
    - Non-numeric markers: '#REF!', 'n/a', '', etc. → (None, False, reason)
    - Currency symbols: '$1234.56' → (1234.56, True, None)
    - Percent signs: '12.5%' → (12.5, True, None)
    - Thousands separators: '1,234.56' → (1234.56, True, None)
    - Scientific notation: '1.5e-3' → (0.0015, True, None)
    
    Args:
        raw_value: Raw string value from Excel
        
    Returns:
        Tuple of (numeric_value, is_valid, rejection_reason):
        - numeric_value: float if valid, None otherwise
        - is_valid: True if numeric, False otherwise
        - rejection_reason: description of failure, or None if valid
        
    Examples:
        >>> validate_numeric('1234.56')
        (1234.56, True, None)
        
        >>> validate_numeric('n/a')
        (None, False, "non-numeric marker: 'n/a'")
        
        >>> validate_numeric('#REF!')
        (None, False, "non-numeric marker: '#REF!'")
        
        >>> validate_numeric('1,234')
        (1234.0, True, None)
        
        >>> validate_numeric('12.5%')
        (12.5, True, None)
    """
    if raw_value is None:
        return None, False, 'null input'
    
    stripped = raw_value.strip().lower()
    
    # Check for non-numeric markers
    if stripped in NON_NUMERIC_MARKERS:
        return None, False, f"non-numeric marker: '{raw_value}'"
    
    # Remove currency symbols, percent signs, whitespace
    cleaned = _STRIP_CHARS_RE.sub('', stripped)
    
    # Remove thousands separators for matching
    matchable = cleaned.replace(',', '')
    
    # Check if it matches numeric pattern
    if not _NUMERIC_RE.match(matchable):
        return None, False, f"cannot parse as number: '{raw_value}'"
    
    # Try to convert to float
    try:
        value = float(matchable)
        return value, True, None
    except ValueError:
        return None, False, f"float() failed: '{raw_value}'"
