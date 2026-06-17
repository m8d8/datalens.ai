"""
Type inference utilities.

Detects value types with semantic enrichment (URLs, URIs, emails, etc.).
"""

from __future__ import annotations

import re
from typing import Any

# Common patterns for semantic type detection
_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?")
# Phone: require a `+` country prefix OR at least one separator (space, hyphen, paren).
# Otherwise pure-digit strings like long numeric IDs get mis-classified as phones.
_PHONE_PATTERN = re.compile(
    r"^(?:\+\d[\d\s\-\(\)]{6,19}|\(\d{2,4}\)[\d\s\-]{4,16}|\d{1,4}[\s\-]\d{2,5}[\s\-\d]{2,15})$"
)
# Long pure-digit identifier (10+ digits, no separators) — e.g. legacy numeric IDs.
_NUMERIC_ID_PATTERN = re.compile(r"^\d{10,}$")


def infer_type(value: Any) -> str:
    """
    Infer the type of a value with semantic enrichment.

    Returns one of:
    - Primitive: "null", "bool", "int", "float", "string"
    - Semantic string subtypes: "url", "uri", "email", "uuid", "date", "phone"
    - Complex: "object", "array"

    Args:
        value: Any value to type-check.

    Returns:
        Type string.
    """
    if value is None:
        return "null"

    if isinstance(value, bool):
        return "bool"

    if isinstance(value, int) and not isinstance(value, bool):
        return "int"

    if isinstance(value, float):
        return "float"

    if isinstance(value, dict):
        return "object"

    if isinstance(value, list):
        return "array"

    if isinstance(value, str):
        return _infer_string_type(value)

    # Fallback to Python type name
    return type(value).__name__


def _infer_string_type(value: str) -> str:
    """Infer semantic subtype for string values."""
    if not value:
        return "string"

    v_lower = value.lower().strip()

    # URL detection
    if v_lower.startswith(("http://", "https://")):
        return "url"

    # URI detection (custom schemes)
    if "://" in value[:20] or v_lower.startswith("uri:"):
        return "uri"

    # Email detection
    if "@" in value and _EMAIL_PATTERN.match(value):
        return "email"

    # UUID detection
    if len(value) == 36 and _UUID_PATTERN.match(value):
        return "uuid"

    # ISO date detection
    if len(value) >= 10 and _ISO_DATE_PATTERN.match(value):
        return "date"

    # Phone number detection (requires + or separator — see _PHONE_PATTERN)
    if _PHONE_PATTERN.match(value):
        return "phone"

    # Long pure-digit numeric identifier (e.g. legacy snowflake/long IDs)
    if _NUMERIC_ID_PATTERN.match(value):
        return "numeric_id"

    return "string"


def is_empty_value(value: Any) -> bool:
    """
    Check if a value is considered "empty" for coverage purposes.

    Empty values: None, "", [], {}

    Args:
        value: Value to check.

    Returns:
        True if the value is empty.
    """
    if value is None:
        return True
    if value == "":
        return True
    if value == []:
        return True
    if value == {}:
        return True
    return False


def get_primitive_value(value: Any) -> Any:
    """
    Convert value to a primitive for storage/comparison.

    Complex objects become their string representation.
    """
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, (list, dict)):
        return None  # Don't store complex values in value_counts
    return str(value)


def is_numeric_type(type_str: str) -> bool:
    """Check if a type string represents a numeric type."""
    return type_str in {"int", "float"}


def is_temporal_type(type_str: str) -> bool:
    """Check if a type string represents a temporal type."""
    return type_str in {"date"}


def is_identifier_type(type_str: str) -> bool:
    """Check if a type string likely represents an identifier."""
    return type_str in {"uuid", "uri"}
