"""
Schema Diff — compare schemas and detect drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Fallback breach threshold (percentage points) when coverage_thresholds is
# enabled but no dataset/object/field override applies.
DEFAULT_COVERAGE_BREACH_THRESHOLD = 10.0


def resolve_coverage_threshold(
    thresholds: dict[str, Any],
    object_name: str,
    field_path: str,
) -> tuple[float, str]:
    """
    Resolve the coverage-change breach threshold (percentage points) for a field.

    Precedence, most to least specific:
      1. thresholds["fields"][object_name][field_path]
      2. thresholds["objects"][object_name]
      3. thresholds["dataset"] (global default)
      4. DEFAULT_COVERAGE_BREACH_THRESHOLD

    Returns:
        (threshold, scope) where scope is "field" | "object" | "dataset" | "default".
    """
    field_overrides = (thresholds.get("fields") or {}).get(object_name) or {}
    if field_path in field_overrides:
        return float(field_overrides[field_path]), "field"

    object_overrides = thresholds.get("objects") or {}
    if object_name in object_overrides:
        return float(object_overrides[object_name]), "object"

    if thresholds.get("dataset") is not None:
        return float(thresholds["dataset"]), "dataset"

    return DEFAULT_COVERAGE_BREACH_THRESHOLD, "default"


@dataclass
class SchemaDiff:
    """Result of comparing two schema versions."""

    # Added/removed objects
    added_objects: list[str] = field(default_factory=list)
    removed_objects: list[str] = field(default_factory=list)

    # Added/removed fields (per object)
    added_fields: dict[str, list[str]] = field(default_factory=dict)
    removed_fields: dict[str, list[str]] = field(default_factory=dict)

    # Type changes
    type_changes: list[dict[str, Any]] = field(default_factory=list)

    # Coverage changes (significant shifts). Each entry also carries
    # direction/threshold/threshold_scope/breach when coverage_thresholds
    # was configured (see resolve_coverage_threshold).
    coverage_changes: list[dict[str, Any]] = field(default_factory=list)

    # Cardinality changes
    cardinality_changes: list[dict[str, Any]] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        """Check if any drift was detected."""
        return bool(
            self.added_objects
            or self.removed_objects
            or self.added_fields
            or self.removed_fields
            or self.type_changes
            or self.coverage_changes
            or self.cardinality_changes
        )

    @property
    def coverage_breaches(self) -> list[dict[str, Any]]:
        """Coverage changes that exceeded their resolved threshold (breach=True)."""
        return [c for c in self.coverage_changes if c.get("breach")]

    def to_schema_drift_json(self) -> dict[str, Any]:
        """Machine-readable schema-drift artifact (objects/fields/types) for CI/CD."""
        return {
            "has_drift": self.has_drift,
            "added_objects": self.added_objects,
            "removed_objects": self.removed_objects,
            "added_fields": self.added_fields,
            "removed_fields": self.removed_fields,
            "type_changes": self.type_changes,
        }

    def to_coverage_drift_json(self) -> dict[str, Any]:
        """Machine-readable coverage-drift artifact (per-field %-change + threshold breaches) for CI/CD."""
        breaches = self.coverage_breaches
        reduction_breaches = [c for c in breaches if c.get("direction") == "decrease"]
        increase_breaches = [c for c in breaches if c.get("direction") == "increase"]
        return {
            "coverage_changes": self.coverage_changes,
            "breaches": breaches,
            "summary": {
                "total_changes": len(self.coverage_changes),
                "total_breaches": len(breaches),
                "reduction_breaches": len(reduction_breaches),
                "increase_breaches": len(increase_breaches),
                "any_breach": bool(breaches),
            },
        }

    def summary(self) -> str:
        """Generate a human-readable summary of changes."""
        lines = ["# Schema Drift Report", ""]

        if not self.has_drift:
            lines.append("No drift detected. Schemas are identical.")
            return "\n".join(lines)

        if self.added_objects:
            lines.append(f"## Added Objects ({len(self.added_objects)})")
            for obj in self.added_objects:
                lines.append(f"- {obj}")
            lines.append("")

        if self.removed_objects:
            lines.append(f"## Removed Objects ({len(self.removed_objects)})")
            for obj in self.removed_objects:
                lines.append(f"- {obj}")
            lines.append("")

        if self.added_fields:
            total = sum(len(fields) for fields in self.added_fields.values())
            lines.append(f"## Added Fields ({total})")
            for obj, fields in self.added_fields.items():
                for field_path in fields:
                    lines.append(f"- {obj}.{field_path}")
            lines.append("")

        if self.removed_fields:
            total = sum(len(fields) for fields in self.removed_fields.values())
            lines.append(f"## Removed Fields ({total})")
            for obj, fields in self.removed_fields.items():
                for field_path in fields:
                    lines.append(f"- {obj}.{field_path}")
            lines.append("")

        if self.type_changes:
            lines.append(f"## Type Changes ({len(self.type_changes)})")
            for change in self.type_changes:
                lines.append(
                    f"- {change['object']}.{change['field']}: "
                    f"{change['old_types']} → {change['new_types']}"
                )
            lines.append("")

        if self.coverage_changes:
            lines.append(f"## Coverage Changes ({len(self.coverage_changes)})")
            for change in self.coverage_changes:
                lines.append(
                    f"- {change['object']}.{change['field']}: "
                    f"{change['old_coverage']:.1f}% → {change['new_coverage']:.1f}%"
                )
            lines.append("")

        return "\n".join(lines)


def _material_types(field: dict[str, Any], threshold: float) -> set[str]:
    """
    Return the set of *material* (non-null) value-shapes for a field.

    A type is material if it accounts for at least ``threshold`` of the field's
    non-null values. This suppresses sampling noise: when a field is sampled
    differently across runs (e.g. MongoDB ``$sample``), a single stray value of
    a rare shape (one UUID among thousands of numeric IDs) would otherwise flip
    the observed type set and report a phantom "type change". Minority shapes
    below the threshold are ignored for drift purposes.
    """
    types = field.get("types", {})
    total = sum(c for t, c in types.items() if t != "null")
    if total <= 0:
        return set()
    cutoff = max(1.0, total * threshold)
    return {t for t, c in types.items() if t != "null" and c >= cutoff}


def compare_schemas(
    old_schema: dict[str, Any],
    new_schema: dict[str, Any],
    coverage_threshold: float = 10.0,
    type_minor_threshold: float = 0.02,
    coverage_thresholds: dict[str, Any] | None = None,
    report_reduction_exceeds: bool = True,
    report_increase_exceeds: bool = True,
) -> SchemaDiff:
    """
    Compare two schema versions and identify differences.

    Args:
        old_schema: Previous schema JSON.
        new_schema: Current schema JSON.
        coverage_threshold: Minimum coverage change % to report (default: 10%).
        type_minor_threshold: Minimum share (0–1) of non-null values a type must
            represent to count toward a type change. Shapes below this are
            treated as sampling noise and ignored (default: 0.02 = 2%).
        coverage_thresholds: Optional dataset/object/field breach thresholds
            (see ``resolve_coverage_threshold``). Empty/None disables breach
            detection entirely — coverage_changes reporting is unaffected.
        report_reduction_exceeds: When breach detection is enabled, flag fields
            whose coverage *dropped* beyond their resolved threshold.
        report_increase_exceeds: When breach detection is enabled, flag fields
            whose coverage *rose* beyond their resolved threshold.

    Returns:
        SchemaDiff with all detected changes.
    """
    diff = SchemaDiff()
    thresholds_enabled = bool(coverage_thresholds)

    old_objects = {obj["object"]: obj for obj in old_schema.get("objects", [])}
    new_objects = {obj["object"]: obj for obj in new_schema.get("objects", [])}

    # Check added/removed objects
    diff.added_objects = [name for name in new_objects if name not in old_objects]
    diff.removed_objects = [name for name in old_objects if name not in new_objects]

    # Compare fields for common objects
    for obj_name in set(old_objects) & set(new_objects):
        old_obj = old_objects[obj_name]
        new_obj = new_objects[obj_name]

        old_fields = {f["path"]: f for f in old_obj.get("fields", [])}
        new_fields = {f["path"]: f for f in new_obj.get("fields", [])}

        # Added/removed fields
        added = [path for path in new_fields if path not in old_fields]
        removed = [path for path in old_fields if path not in new_fields]

        if added:
            diff.added_fields[obj_name] = added
        if removed:
            diff.removed_fields[obj_name] = removed

        # Compare common fields
        for path in set(old_fields) & set(new_fields):
            old_field = old_fields[path]
            new_field = new_fields[path]

            # Type changes — compare only *material* shapes so a stray value
            # from a different sample doesn't report a phantom type change.
            old_types = _material_types(old_field, type_minor_threshold)
            new_types = _material_types(new_field, type_minor_threshold)
            if old_types != new_types:
                diff.type_changes.append({
                    "object": obj_name,
                    "field": path,
                    "old_types": sorted(old_types),
                    "new_types": sorted(new_types),
                })

            # Coverage changes — "coverage" means *meaningfully present* (key
            # exists and isn't null/empty), matching the rest of the report
            # (e.g. the Field Explorer's effective-coverage calculation).
            old_sampled = old_obj.get("sampled", 1) or 1
            new_sampled = new_obj.get("sampled", 1) or 1
            old_effective = max(0, old_field.get("presence_count", 0) - old_field.get("null_empty_count", 0))
            new_effective = max(0, new_field.get("presence_count", 0) - new_field.get("null_empty_count", 0))
            old_coverage = old_effective / old_sampled * 100
            new_coverage = new_effective / new_sampled * 100
            delta = new_coverage - old_coverage

            direction = "increase" if delta > 0 else "decrease" if delta < 0 else "unchanged"
            breach = False
            threshold: float | None = None
            threshold_scope: str | None = None
            if thresholds_enabled:
                threshold, threshold_scope = resolve_coverage_threshold(
                    coverage_thresholds, obj_name, path
                )
                breach = abs(delta) >= threshold and (
                    (direction == "decrease" and report_reduction_exceeds)
                    or (direction == "increase" and report_increase_exceeds)
                )

            if abs(delta) >= coverage_threshold or breach:
                diff.coverage_changes.append({
                    "object": obj_name,
                    "field": path,
                    "old_coverage": old_coverage,
                    "new_coverage": new_coverage,
                    "delta": delta,
                    "direction": direction,
                    "threshold": threshold,
                    "threshold_scope": threshold_scope,
                    "breach": breach,
                })

    return diff


def detect_drift(
    current_schema: dict[str, Any],
    previous_schema: dict[str, Any] | None,
    coverage_threshold: float = 10.0,
    type_minor_threshold: float = 0.02,
    coverage_thresholds: dict[str, Any] | None = None,
    report_reduction_exceeds: bool = True,
    report_increase_exceeds: bool = True,
) -> SchemaDiff | None:
    """
    Detect schema drift from previous version.

    Args:
        current_schema: Current schema JSON.
        previous_schema: Previous schema JSON (None if no history).
        coverage_threshold: Minimum coverage change % to report.
        type_minor_threshold: Minimum share (0–1) of non-null values a type must
            represent to count toward a type change (suppresses sampling noise).
        coverage_thresholds: Optional dataset/object/field breach thresholds.
        report_reduction_exceeds: Flag coverage drops beyond their threshold.
        report_increase_exceeds: Flag coverage rises beyond their threshold.

    Returns:
        SchemaDiff if drift detected, None if no previous schema.
    """
    if previous_schema is None:
        return None

    return compare_schemas(
        previous_schema,
        current_schema,
        coverage_threshold=coverage_threshold,
        type_minor_threshold=type_minor_threshold,
        coverage_thresholds=coverage_thresholds,
        report_reduction_exceeds=report_reduction_exceeds,
        report_increase_exceeds=report_increase_exceeds,
    )
