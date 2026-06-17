"""
Pattern detection — infer value shapes / identifier patterns from sample values.

Domain-agnostic: detect UUID, integer ID, slug, prefixed code, hash, URL,
email, ISO date/datetime, IPv4/IPv6, locale code, currency, phone-like, etc.
Patterns are reported with conformance ratio (how many sampled values match).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

# Ordered: more specific first
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("uuid", re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")),
    ("iso_datetime", re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$")),
    ("iso_date", re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    ("email", re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")),
    ("url", re.compile(r"^(https?|ftp|s3)://[^\s]+$")),
    ("ipv4", re.compile(r"^(25[0-5]|2[0-4]\d|[01]?\d?\d)(\.(25[0-5]|2[0-4]\d|[01]?\d?\d)){3}$")),
    # IPv6 requires multiple colons (≥2) and at least one hex digit; excludes simple ratios like "16:9".
    ("ipv6", re.compile(r"^(?=.*:.*:)[0-9a-fA-F:]{3,}$")),
    ("ratio", re.compile(r"^\d{1,4}:\d{1,4}$")),
    ("md5", re.compile(r"^[a-f0-9]{32}$")),
    ("sha1", re.compile(r"^[a-f0-9]{40}$")),
    ("sha256", re.compile(r"^[a-f0-9]{64}$")),
    ("locale_code", re.compile(r"^[a-z]{2}(_[A-Z]{2})?$")),
    ("country_code_iso2", re.compile(r"^[A-Z]{2}$")),
    ("currency_code", re.compile(r"^[A-Z]{3}$")),
    ("integer_id", re.compile(r"^-?\d+$")),
    ("decimal", re.compile(r"^-?\d+\.\d+$")),
    ("slug", re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)+$")),
    ("prefixed_code", re.compile(r"^[A-Z][A-Z0-9]{1,8}[-_]?[A-Z0-9]+$")),
    ("base64ish", re.compile(r"^[A-Za-z0-9+/=]{16,}$")),
]


@dataclass
class PatternMatch:
    """One pattern detected for a field, with conformance metrics."""

    pattern: str
    conformance: float  # 0-1 ratio of sampled values matching this pattern
    sample_values: list[str]


@dataclass
class FieldPatterns:
    """All patterns detected for one field."""

    object_name: str
    path: str
    dominant_pattern: str | None
    dominant_conformance: float
    matches: list[PatternMatch]
    is_identifier: bool  # heuristic: looks like a unique ID

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": self.object_name,
            "path": self.path,
            "dominant_pattern": self.dominant_pattern,
            "dominant_conformance": round(self.dominant_conformance, 3),
            "is_identifier": self.is_identifier,
            "matches": [
                {
                    "pattern": m.pattern,
                    "conformance": round(m.conformance, 3),
                    "sample_values": m.sample_values[:3],
                }
                for m in self.matches
            ],
        }


def _candidate_values(field_data: dict[str, Any]) -> list[str]:
    """Collect string-coerced sample values from a field for pattern matching."""
    values: list[str] = []
    vc = field_data.get("value_counts") or {}
    if isinstance(vc, dict):
        values.extend(str(k) for k in vc.keys() if k is not None)
    elif isinstance(vc, list):
        for entry in vc:
            if isinstance(entry, (list, tuple)) and entry and entry[0] is not None:
                values.append(str(entry[0]))
    if not values:
        values.extend(str(v) for v in (field_data.get("examples") or []) if v is not None)
    if not values:
        for dv in field_data.get("distinct_values", []) or []:
            if dv is not None:
                values.append(str(dv))
    return values[:200]


def detect_field_patterns(
    object_name: str, field_data: dict[str, Any], sampled: int
) -> FieldPatterns | None:
    """Return the patterns detected for a single field, or None if no usable values."""
    values = _candidate_values(field_data)
    if not values:
        return None

    matches: list[PatternMatch] = []
    for name, regex in _PATTERNS:
        hit_values = [v for v in values if regex.match(v)]
        if not hit_values:
            continue
        conformance = len(hit_values) / len(values)
        if conformance >= 0.6:
            matches.append(
                PatternMatch(
                    pattern=name,
                    conformance=conformance,
                    sample_values=hit_values[:5],
                )
            )

    matches.sort(key=lambda m: (-m.conformance, m.pattern))
    dominant = matches[0] if matches else None

    distinct = field_data.get("distinct_count_in_sample", 0)
    presence = field_data.get("presence_count", 0)
    is_identifier = bool(
        dominant
        and dominant.pattern in {"uuid", "integer_id", "md5", "sha1", "sha256", "prefixed_code", "base64ish"}
        and presence > 0
        and distinct >= max(1, int(presence * 0.9))
    )

    if not matches:
        return None

    return FieldPatterns(
        object_name=object_name,
        path=field_data.get("path", ""),
        dominant_pattern=dominant.pattern if dominant else None,
        dominant_conformance=dominant.conformance if dominant else 0.0,
        matches=matches,
        is_identifier=is_identifier,
    )


def analyze_patterns(schema_json: dict[str, Any]) -> dict[str, Any]:
    """Detect patterns for every field across all objects."""
    by_object: dict[str, list[dict[str, Any]]] = {}
    pattern_counts: dict[str, int] = {}
    identifier_fields: list[dict[str, Any]] = []

    for obj in schema_json.get("objects", []):
        obj_name = obj.get("object", "Unknown")
        sampled = obj.get("sampled", 0)
        rows: list[dict[str, Any]] = []
        for field_data in obj.get("fields", []):
            result = detect_field_patterns(obj_name, field_data, sampled)
            if not result:
                continue
            rows.append(result.to_dict())
            if result.dominant_pattern:
                pattern_counts[result.dominant_pattern] = (
                    pattern_counts.get(result.dominant_pattern, 0) + 1
                )
            if result.is_identifier:
                identifier_fields.append(
                    {
                        "object": obj_name,
                        "path": result.path,
                        "pattern": result.dominant_pattern,
                        "distinct": field_data.get("distinct_count_in_sample", 0),
                        "presence": field_data.get("presence_count", 0),
                    }
                )
        if rows:
            by_object[obj_name] = rows

    return {
        "by_object": by_object,
        "pattern_counts": pattern_counts,
        "identifier_fields": identifier_fields,
        "total_fields_with_pattern": sum(len(v) for v in by_object.values()),
    }


def average_pattern_conformance(patterns_data: dict[str, Any]) -> float:
    """Average dominant-pattern conformance across all detected fields (0-100)."""
    conformances: list[float] = []
    for rows in patterns_data.get("by_object", {}).values():
        for row in rows:
            c = row.get("dominant_conformance")
            if isinstance(c, (int, float)):
                conformances.append(float(c))
    if not conformances:
        return 100.0
    return (sum(conformances) / len(conformances)) * 100
