"""
Coverage — one definition, used everywhere.

    coverage = rows where the field holds a real value / rows profiled × 100

A row counts against coverage when the field is missing from the row, null, or
empty ("" / [] / {}). Every report table, export, drift metric, alert and AI prompt
uses this function, so the same field always shows the same number.
"""

from __future__ import annotations

from typing import Any


def filled_count(field: dict[str, Any]) -> int:
    """Rows where the field is present and not null/empty."""
    return max(0, int(field.get("presence_count", 0) or 0) - int(field.get("null_empty_count", 0) or 0))


def coverage_pct(field: dict[str, Any], rows: int) -> float:
    """True coverage of a field in %, excluding missing, null and empty values."""
    if not rows:
        return 0.0
    return min(100.0, filled_count(field) / rows * 100)


def missing_pct(field: dict[str, Any], rows: int) -> float:
    """Rows where the key is absent altogether, in %."""
    if not rows:
        return 0.0
    return max(0.0, (rows - int(field.get("presence_count", 0) or 0)) / rows * 100)


def null_empty_pct(field: dict[str, Any], rows: int) -> float:
    """Rows where the key is present but null/empty, in %."""
    if not rows:
        return 0.0
    return int(field.get("null_empty_count", 0) or 0) / rows * 100
