"""
ingest/validator.py — NumericValidator

Pre-checks every raw value before it enters the database.
Non-numeric values are stored as NULL with a rejection log entry.
"""

from __future__ import annotations

import re

# Values that are definitively non-numeric
NON_NUMERIC_MARKERS: frozenset[str] = frozenset({
    '', 'n/a', 'na', 'n.a.', 'n.a', 'nil', 'none', 'null', '-',
    '#ref!', '#value!', '#div/0!', '#n/a', '#name?', '#null!', '#num!',
    '#error!', 'error', 'inf', '-inf', 'nan',
})

# Matches: optional sign, digits, optional decimal, optional exponent
_NUMERIC_RE = re.compile(
    r'^[+-]?'
    r'(\d{1,3}(,\d{3})*|\d+)'   # integer part (with optional thousands commas)
    r'(\.\d+)?'                  # optional decimal
    r'([eE][+-]?\d+)?$'          # optional scientific notation
)

# Characters to strip before numeric check
_STRIP_CHARS_RE = re.compile(r'[$%£€¥\s]')


def validate_numeric(raw_value: str) -> tuple[float | None, bool, str | None]:
    """
    Validate whether raw_value can be interpreted as a number.

    Returns:
        (numeric_value, is_valid, rejection_reason)
        - numeric_value:    float if valid, None otherwise
        - is_valid:         True if numeric
        - rejection_reason: description of failure, or None if valid

    Examples:
        validate_numeric('1234.56')  → (1234.56, True, None)
        validate_numeric('n/a')      → (None, False, "non-numeric marker: 'n/a'")
        validate_numeric('#REF!')    → (None, False, "non-numeric marker: '#REF!'")
        validate_numeric('')         → (None, False, "non-numeric marker: ''")
        validate_numeric('1,234')    → (1234.0, True, None)
        validate_numeric('12.5%')    → (12.5, True, None)   # % stripped
    """
    if raw_value is None:
        return None, False, 'null input'

    stripped = raw_value.strip().lower()

    if stripped in NON_NUMERIC_MARKERS:
        return None, False, f'non-numeric marker: {raw_value!r}'

    # Remove currency symbols, percent signs, whitespace
    cleaned = _STRIP_CHARS_RE.sub('', stripped)

    # Remove thousands separators for matching, but keep for float()
    matchable = cleaned.replace(',', '')

    if not _NUMERIC_RE.match(matchable):
        return None, False, f'cannot parse as number: {raw_value!r}'

    try:
        value = float(matchable)
        return value, True, None
    except ValueError:
        return None, False, f'float() failed: {raw_value!r}'
