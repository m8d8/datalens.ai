"""
Deep schema comparison — compare two independent schemas comprehensively.

Supports both metadata mode (fast, structure/coverage/cardinality) and
deep mode (optional, with value sampling and overlap analysis).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any
from datetime import datetime


@dataclass
class PathComparison:
    """Side-by-side metrics for a single field path."""

    path: str

    # Structural
    in_schema1: bool
    in_schema2: bool
    type_s1: set[str] = field(default_factory=set)  # e.g., {"string"}
    type_s2: set[str] = field(default_factory=set)  # e.g., {"string", "null"}

    # Metadata metrics (always computed)
    coverage_s1: float = 0.0  # 0–100
    coverage_s2: float = 0.0
    null_pct_s1: float = 0.0
    null_pct_s2: float = 0.0
    distinct_s1: int = 0  # Cardinality only, no samples
    distinct_s2: int = 0

    # Deep comparison metrics (only if deep_compare=True)
    sample_distinct_s1: list[str] = field(default_factory=list)  # Top N values
    sample_distinct_s2: list[str] = field(default_factory=list)
    value_overlap_pct: float | None = None  # % of values in s1 that exist in s2
    is_high_cardinality_s1: bool = False  # Flag: showing samples only
    is_high_cardinality_s2: bool = False

    @property
    def types_match(self) -> bool:
        """Check if types are identical (ignoring null type)."""
        return self.type_s1 == self.type_s2

    @property
    def coverage_delta(self) -> float:
        """Coverage change from schema1 to schema2."""
        return self.coverage_s2 - self.coverage_s1

    @property
    def cardinality_ratio(self) -> float | None:
        """Ratio of cardinality (s2/s1). None if s1 is zero."""
        if self.distinct_s1 == 0:
            return None
        return self.distinct_s2 / self.distinct_s1

    @property
    def divergence_score(self) -> float:
        """
        Overall divergence score for this path (0–100).
        0 = identical, 100 = completely different.

        Weighted: types (50%), coverage (30%), cardinality (20%)
        """
        if not self.in_schema1 or not self.in_schema2:
            return 100.0  # Path exists in only one schema

        type_score = 0.0 if self.types_match else 100.0
        coverage_score = min(100.0, abs(self.coverage_delta))
        cardinality_score = 0.0
        if self.cardinality_ratio is not None:
            ratio = self.cardinality_ratio
            # Score: 0 if same, scales up to 100 for 10x difference
            cardinality_score = min(100.0, abs(ratio - 1) * 20)

        return (
            type_score * 0.5
            + coverage_score * 0.3
            + cardinality_score * 0.2
        )


@dataclass
class DeepSchemaDiff:
    """Result of comparing two independent schemas."""

    # Metadata
    schema1_name: str = "Schema 1"
    schema2_name: str = "Schema 2"
    compared_at: str = ""  # ISO timestamp
    deep_compare_enabled: bool = False

    # Structural
    added_objects: list[str] = field(default_factory=list)
    removed_objects: list[str] = field(default_factory=list)
    common_objects: list[str] = field(default_factory=list)

    added_fields: dict[str, list[str]] = field(default_factory=dict)
    removed_fields: dict[str, list[str]] = field(default_factory=dict)

    # Comparison details
    path_comparisons: list[PathComparison] = field(default_factory=list)

    # Divergences
    type_divergences: list[dict[str, Any]] = field(default_factory=list)
    coverage_gaps: list[dict[str, Any]] = field(default_factory=list)
    cardinality_explosions: list[dict[str, Any]] = field(default_factory=list)
    value_drifts: list[dict[str, Any]] = field(default_factory=list)

    # Summary scores
    schema_similarity_score: float = 0.0  # 0–100
    structural_alignment: float = 0.0  # % of paths with matching presence & type

    @property
    def has_divergence(self) -> bool:
        """Check if any significant divergence exists."""
        return bool(
            self.added_objects
            or self.removed_objects
            or self.type_divergences
            or self.coverage_gaps
            or self.cardinality_explosions
        )


def _material_types(field: dict[str, Any], threshold: float = 0.02) -> set[str]:
    """
    Return the set of *material* (non-null) value-shapes for a field.

    A type is material if it accounts for at least ``threshold`` of the field's
    non-null values. Suppresses sampling noise: when a field is sampled
    differently across runs, a single stray value of a rare shape would otherwise
    flip the observed type set and report a phantom "type change". Minority shapes
    below the threshold are ignored for comparison purposes.

    Args:
        field: Field metadata dict.
        threshold: Minimum share (0–1) a type must represent (default: 0.02 = 2%).

    Returns:
        Set of material type strings.
    """
    types = field.get("types", {})
    total = sum(c for t, c in types.items() if t != "null")
    if total <= 0:
        return set()
    cutoff = max(1.0, total * threshold)
    return {t for t, c in types.items() if t != "null" and c >= cutoff}


def _compute_coverage(field: dict[str, Any], sampled: int) -> float:
    """
    Compute coverage percentage for a field.

    Args:
        field: Field metadata.
        sampled: Number of records sampled for the object.

    Returns:
        Coverage as percentage (0–100).
    """
    if sampled == 0:
        return 0.0
    presence = field.get("presence_count", 0)
    return (presence / sampled) * 100.0


def _compute_null_percentage(field: dict[str, Any]) -> float:
    """
    Compute null percentage for a field.

    Args:
        field: Field metadata.

    Returns:
        Null percentage (0–100).
    """
    types = field.get("types", {})
    null_count = types.get("null", 0)
    total = sum(types.values())
    if total == 0:
        return 0.0
    return (null_count / total) * 100.0


def _get_value_samples(
    field: dict[str, Any],
    max_samples: int,
    cardinality_threshold: int,
) -> tuple[list[str], bool]:
    """
    Collect sample distinct values from a field.

    For high-cardinality fields (above threshold), use only top samples by frequency.
    For low-cardinality, return up to max_samples.

    Args:
        field: Field metadata (should include "sample_values" key).
        max_samples: Max samples to return.
        cardinality_threshold: High-cardinality cutoff.

    Returns:
        (sample_values, is_high_cardinality_flag)
    """
    cardinality = field.get("cardinality", 0)
    sample_values = field.get("sample_values", [])

    if cardinality > cardinality_threshold:
        # High cardinality: use pre-sampled top values
        return sample_values[:max_samples], True
    else:
        # Low cardinality: return all or most
        return sample_values[:max_samples], False


def _compute_value_overlap(
    samples_s1: list[str],
    samples_s2: list[str],
) -> float:
    """
    Compute value overlap as percentage of values in schema1 that exist in schema2.

    Args:
        samples_s1: Sample values from schema1.
        samples_s2: Sample values from schema2.

    Returns:
        Overlap percentage (0–100).
    """
    if not samples_s1:
        return 0.0
    set_s1 = set(samples_s1)
    set_s2 = set(samples_s2)
    overlap = len(set_s1 & set_s2)
    return (overlap / len(set_s1)) * 100.0


def compare_deep_schemas(
    schema1: dict[str, Any],
    schema2: dict[str, Any],
    name1: str = "Schema 1",
    name2: str = "Schema 2",
    deep_compare: bool = False,
    max_value_samples: int = 100,
    cardinality_threshold: int = 10000,
    coverage_threshold: float = 10.0,
    type_minor_threshold: float = 0.02,
    object_mapping: dict[str, str] | None = None,
) -> DeepSchemaDiff:
    """
    Compare two schemas comprehensively.

    Always computes: structure, types, coverage, nulls, cardinality (count only).
    Optionally computes: value samples, value overlap (if deep_compare=True).

    Args:
        schema1, schema2: Schema JSON dicts from analyzer.
        name1, name2: Display names for schemas.
        deep_compare: If True, collect value samples and overlap analysis.
        max_value_samples: Max distinct values to collect per field (deep mode only).
        cardinality_threshold: Fields with cardinality > this show samples only.
        coverage_threshold: Minimum coverage change % to flag as a gap (default: 10%).
        type_minor_threshold: Minimum share of non-null values a type must represent
            to count as a material type (default: 0.02 = 2%).
        object_mapping: Optional dict to map object names from schema1 to schema2.
            E.g., {"object1_name": "object2_name"}. If None, tries to auto-match
            by object index (first object to first object, etc.).

    Returns:
        DeepSchemaDiff with all detected differences.
    """
    diff = DeepSchemaDiff(
        schema1_name=name1,
        schema2_name=name2,
        compared_at=datetime.utcnow().isoformat() + "Z",
        deep_compare_enabled=deep_compare,
    )

    # Extract objects
    objects1 = {obj["object"]: obj for obj in schema1.get("objects", [])}
    objects2 = {obj["object"]: obj for obj in schema2.get("objects", [])}

    # Auto-match objects by index if mapping not provided and names don't match
    if object_mapping is None and objects1 and objects2:
        objs1_list = list(objects1.keys())
        objs2_list = list(objects2.keys())
        # If objects have different names but same count, auto-map by index
        if len(objs1_list) == len(objs2_list) and objs1_list[0] != objs2_list[0]:
            object_mapping = {o1: o2 for o1, o2 in zip(objs1_list, objs2_list)}

    # Apply object mapping if available: rename objects2 keys to match objects1
    if object_mapping:
        # object_mapping is {s1_name: s2_name}
        # We need to rename objects2 keys so they match objects1 keys
        reverse_mapping = {v: k for k, v in object_mapping.items()}
        objects2 = {reverse_mapping.get(k, k): v for k, v in objects2.items()}

    # Objects comparison
    diff.added_objects = sorted(set(objects2.keys()) - set(objects1.keys()))
    diff.removed_objects = sorted(set(objects1.keys()) - set(objects2.keys()))
    diff.common_objects = sorted(set(objects1.keys()) & set(objects2.keys()))

    # Compare common objects
    for obj_name in diff.common_objects:
        obj1 = objects1[obj_name]
        obj2 = objects2[obj_name]

        # Extract fields
        fields1 = {f["path"]: f for f in obj1.get("fields", [])}
        fields2 = {f["path"]: f for f in obj2.get("fields", [])}

        # Track added/removed fields
        added = sorted(set(fields2.keys()) - set(fields1.keys()))
        removed = sorted(set(fields1.keys()) - set(fields2.keys()))

        if added:
            diff.added_fields[obj_name] = added
        if removed:
            diff.removed_fields[obj_name] = removed

        # Get sampled counts for coverage computation
        sampled1 = obj1.get("sampled", 1) or 1
        sampled2 = obj2.get("sampled", 1) or 1

        # Compare common fields
        for path in sorted(set(fields1.keys()) & set(fields2.keys())):
            field1 = fields1[path]
            field2 = fields2[path]

            # Compute metrics
            type_s1 = _material_types(field1, type_minor_threshold)
            type_s2 = _material_types(field2, type_minor_threshold)
            coverage_s1 = _compute_coverage(field1, sampled1)
            coverage_s2 = _compute_coverage(field2, sampled2)
            null_pct_s1 = _compute_null_percentage(field1)
            null_pct_s2 = _compute_null_percentage(field2)
            distinct_s1 = field1.get("cardinality", 0)
            distinct_s2 = field2.get("cardinality", 0)

            # Build path comparison
            path_comp = PathComparison(
                path=path,
                in_schema1=True,
                in_schema2=True,
                type_s1=type_s1,
                type_s2=type_s2,
                coverage_s1=coverage_s1,
                coverage_s2=coverage_s2,
                null_pct_s1=null_pct_s1,
                null_pct_s2=null_pct_s2,
                distinct_s1=distinct_s1,
                distinct_s2=distinct_s2,
            )

            # Deep comparison: sample values if requested
            if deep_compare:
                samples_s1, high_card_s1 = _get_value_samples(
                    field1, max_value_samples, cardinality_threshold
                )
                samples_s2, high_card_s2 = _get_value_samples(
                    field2, max_value_samples, cardinality_threshold
                )
                path_comp.sample_distinct_s1 = samples_s1
                path_comp.sample_distinct_s2 = samples_s2
                path_comp.is_high_cardinality_s1 = high_card_s1
                path_comp.is_high_cardinality_s2 = high_card_s2

                if samples_s1 or samples_s2:
                    path_comp.value_overlap_pct = _compute_value_overlap(
                        samples_s1, samples_s2
                    )

            diff.path_comparisons.append(path_comp)

            # Flag divergences
            if not path_comp.types_match:
                diff.type_divergences.append({
                    "object": obj_name,
                    "path": path,
                    "type_s1": sorted(type_s1),
                    "type_s2": sorted(type_s2),
                })

            if abs(path_comp.coverage_delta) >= coverage_threshold:
                diff.coverage_gaps.append({
                    "object": obj_name,
                    "path": path,
                    "coverage_s1": coverage_s1,
                    "coverage_s2": coverage_s2,
                    "delta": path_comp.coverage_delta,
                })

            if path_comp.cardinality_ratio is not None and path_comp.cardinality_ratio > 2.0:
                diff.cardinality_explosions.append({
                    "object": obj_name,
                    "path": path,
                    "cardinality_s1": distinct_s1,
                    "cardinality_s2": distinct_s2,
                    "ratio": path_comp.cardinality_ratio,
                })

            # Value drift: high divergence in deep compare mode
            if deep_compare and path_comp.value_overlap_pct is not None:
                if path_comp.value_overlap_pct < 50.0:
                    diff.value_drifts.append({
                        "object": obj_name,
                        "path": path,
                        "overlap_pct": path_comp.value_overlap_pct,
                        "message": f"Only {path_comp.value_overlap_pct:.1f}% of values shared",
                    })

    # Compute similarity score: % of common paths with matching presence
    total_common_paths = len(diff.path_comparisons)
    if total_common_paths > 0:
        # Score based on paths that exist in both AND have same types
        aligned = sum(
            1 for pc in diff.path_comparisons
            if pc.in_schema1 and pc.in_schema2 and pc.types_match
        )
        diff.structural_alignment = (aligned / total_common_paths) * 100.0

    # Overall similarity: weighted average
    # (structural alignment) + (inverse of coverage gaps) + (cardinality stability)
    if total_common_paths > 0:
        coverage_score = 100.0 - (
            (len(diff.coverage_gaps) / total_common_paths) * 50.0
        )
        cardinality_score = 100.0 - (
            (len(diff.cardinality_explosions) / total_common_paths) * 25.0
        )
        diff.schema_similarity_score = (
            diff.structural_alignment * 0.5
            + coverage_score * 0.3
            + cardinality_score * 0.2
        )
        # Clamp to 0–100
        diff.schema_similarity_score = max(0.0, min(100.0, diff.schema_similarity_score))

    return diff
