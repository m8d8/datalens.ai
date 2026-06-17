"""
Data Quality Index (DQI) — composite quality scoring for data profiling.

Computes quality scores across multiple dimensions:
- Completeness: Percentage of non-null values
- Consistency: Type uniformity within fields
- Uniqueness: Cardinality relative to total records (for ID-like fields)
- Validity: Conformance to expected patterns/types
- Timeliness: For date fields, recency of data

Each dimension is scored 0-100, and the overall DQI is a weighted average.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityDimension:
    """A single quality dimension score."""

    name: str
    score: float  # 0-100
    weight: float  # Contribution to overall DQI
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class FieldQuality:
    """Quality assessment for a single field."""

    path: str
    completeness: float  # 0-100
    consistency: float  # 0-100 (type uniformity)
    validity: float  # 0-100 (pattern conformance)
    issues: list[str] = field(default_factory=list)

    @property
    def overall(self) -> float:
        """Compute overall field quality score."""
        return (self.completeness * 0.4 + self.consistency * 0.3 + self.validity * 0.3)


@dataclass
class ObjectQuality:
    """Quality assessment for a single object (table/collection)."""

    object_name: str
    completeness: QualityDimension
    consistency: QualityDimension
    uniqueness: QualityDimension
    validity: QualityDimension
    timeliness: QualityDimension | None = None
    fields: list[FieldQuality] = field(default_factory=list)
    # Extra dimensions (accuracy, granularity, integrity, …) keyed by name.
    extra_dimensions: dict[str, QualityDimension] = field(default_factory=dict)

    def all_dimensions(self) -> list[QualityDimension]:
        dims = [self.completeness, self.consistency, self.uniqueness, self.validity]
        if self.timeliness:
            dims.append(self.timeliness)
        dims.extend(self.extra_dimensions.values())
        return dims

    @property
    def dqi(self) -> float:
        """Weighted average of all dimensions (core + extras)."""
        dimensions = self.all_dimensions()
        total_weight = sum(d.weight for d in dimensions)
        weighted_sum = sum(d.score * d.weight for d in dimensions)
        return weighted_sum / total_weight if total_weight > 0 else 0


@dataclass
class SchemaQuality:
    """Quality assessment for the entire schema."""

    objects: list[ObjectQuality]

    @property
    def overall_dqi(self) -> float:
        """Average DQI across all objects."""
        if not self.objects:
            return 0
        return sum(obj.dqi for obj in self.objects) / len(self.objects)

    @property
    def schema_dimensions(self) -> dict[str, float]:
        """Average of each dimension's score across all objects (0-100). Used by the radar."""
        if not self.objects:
            return {}
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for obj in self.objects:
            for dim in obj.all_dimensions():
                totals[dim.name] = totals.get(dim.name, 0.0) + dim.score
                counts[dim.name] = counts.get(dim.name, 0) + 1
        return {k: round(totals[k] / counts[k], 1) for k in totals}

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "overall_dqi": round(self.overall_dqi, 1),
            "schema_dimensions": self.schema_dimensions,
            "objects": [
                {
                    "object": obj.object_name,
                    "dqi": round(obj.dqi, 1),
                    "dimensions": {
                        "completeness": {
                            "score": round(obj.completeness.score, 1),
                            "weight": obj.completeness.weight,
                            "details": obj.completeness.details,
                        },
                        "consistency": {
                            "score": round(obj.consistency.score, 1),
                            "weight": obj.consistency.weight,
                            "details": obj.consistency.details,
                        },
                        "uniqueness": {
                            "score": round(obj.uniqueness.score, 1),
                            "weight": obj.uniqueness.weight,
                            "details": obj.uniqueness.details,
                        },
                        "validity": {
                            "score": round(obj.validity.score, 1),
                            "weight": obj.validity.weight,
                            "details": obj.validity.details,
                        },
                        **(
                            {
                                "timeliness": {
                                    "score": round(obj.timeliness.score, 1),
                                    "weight": obj.timeliness.weight,
                                    "details": obj.timeliness.details,
                                }
                            }
                            if obj.timeliness
                            else {}
                        ),
                        **{
                            name: {
                                "score": round(dim.score, 1),
                                "weight": dim.weight,
                                "details": dim.details,
                            }
                            for name, dim in obj.extra_dimensions.items()
                        },
                    },
                    "problem_fields": [
                        {
                            "path": f.path,
                            "score": round(f.overall, 1),
                            "issues": f.issues,
                        }
                        for f in obj.fields
                        if f.overall < 70
                    ],
                }
                for obj in self.objects
            ],
        }


def compute_field_quality(field_data: dict[str, Any], sampled: int) -> FieldQuality:
    """
    Compute quality scores for a single field.

    Args:
        field_data: Field dict from profiling output.
        sampled: Total sampled records for this object.

    Returns:
        FieldQuality with computed scores.
    """
    path = field_data.get("path", "")
    presence_count = field_data.get("presence_count", 0)
    null_empty_count = field_data.get("null_empty_count", 0)
    types = field_data.get("types", {})
    distinct = field_data.get("distinct_count_in_sample", 0)
    issues: list[str] = []

    # Completeness: % of records with non-empty values
    if sampled > 0:
        non_empty = presence_count - null_empty_count
        completeness = (non_empty / sampled) * 100
    else:
        completeness = 0

    if completeness < 50:
        issues.append(f"Low completeness: {completeness:.0f}%")

    # Consistency: single-type dominance
    total_type_count = sum(types.values())
    if total_type_count > 0:
        dominant_count = max(types.values())
        consistency = (dominant_count / total_type_count) * 100
    else:
        consistency = 100  # No data = no inconsistency

    type_count = len([t for t, c in types.items() if c > 0 and t != "null"])
    if type_count > 1:
        issues.append(f"Mixed types: {list(types.keys())}")

    # Validity: semantic type conformance (penalize unexpected patterns)
    validity = 100.0
    primary_type = max(types, key=types.get) if types else "unknown"

    # Check for common validity issues
    if primary_type == "string" and distinct == 1 and presence_count > 10:
        validity -= 20
        issues.append("All values identical (possible default/placeholder)")

    if null_empty_count > 0 and presence_count > 0:
        empty_ratio = null_empty_count / presence_count
        if empty_ratio > 0.5:
            validity -= 30
            issues.append(f"High null/empty rate: {empty_ratio:.0%}")

    return FieldQuality(
        path=path,
        completeness=completeness,
        consistency=consistency,
        validity=max(0, validity),
        issues=issues,
    )


def compute_object_quality(obj_data: dict[str, Any]) -> ObjectQuality:
    """
    Compute quality scores for a single object.

    Args:
        obj_data: Object dict from profiling output.

    Returns:
        ObjectQuality with computed dimension scores.
    """
    object_name = obj_data.get("object", "unknown")
    fields = obj_data.get("fields", [])
    sampled = obj_data.get("sampled", 0)

    # Compute per-field quality
    field_qualities = [compute_field_quality(f, sampled) for f in fields]

    # Aggregate completeness (average across fields)
    if field_qualities:
        avg_completeness = sum(f.completeness for f in field_qualities) / len(field_qualities)
    else:
        avg_completeness = 0

    completeness = QualityDimension(
        name="completeness",
        score=avg_completeness,
        weight=0.30,
        details={
            "total_fields": len(fields),
            "high_coverage_fields": sum(1 for f in field_qualities if f.completeness >= 90),
            "low_coverage_fields": sum(1 for f in field_qualities if f.completeness < 50),
        },
    )

    # Aggregate consistency
    if field_qualities:
        avg_consistency = sum(f.consistency for f in field_qualities) / len(field_qualities)
    else:
        avg_consistency = 100

    multi_type_fields = [f for f in field_qualities if f.consistency < 100]
    consistency = QualityDimension(
        name="consistency",
        score=avg_consistency,
        weight=0.25,
        details={
            "uniform_type_fields": len(field_qualities) - len(multi_type_fields),
            "multi_type_fields": len(multi_type_fields),
        },
    )

    # Uniqueness: check ID-like fields
    id_fields = [
        f for f in fields
        if any(
            kw in f.get("path", "").lower()
            for kw in ("_id", "id", "uuid", "guid", "key")
        )
    ]
    if id_fields and sampled > 0:
        # Check if ID fields have high cardinality
        high_cardinality = sum(
            1 for f in id_fields
            if f.get("distinct_count_in_sample", 0) >= sampled * 0.9
        )
        uniqueness_score = (high_cardinality / len(id_fields)) * 100
    else:
        uniqueness_score = 100  # No ID fields to check

    uniqueness = QualityDimension(
        name="uniqueness",
        score=uniqueness_score,
        weight=0.20,
        details={
            "id_fields_checked": len(id_fields),
            "unique_id_fields": sum(
                1 for f in id_fields
                if f.get("distinct_count_in_sample", 0) >= sampled * 0.9
            ) if sampled > 0 else 0,
        },
    )

    # Validity: aggregate from field-level
    if field_qualities:
        avg_validity = sum(f.validity for f in field_qualities) / len(field_qualities)
    else:
        avg_validity = 100

    validity = QualityDimension(
        name="validity",
        score=avg_validity,
        weight=0.25,
        details={
            "fields_with_issues": sum(1 for f in field_qualities if f.issues),
        },
    )

    # Timeliness: scan date-like fields for recency / future-dated anomalies
    date_fields = [
        f for f in fields
        if "date" in f.get("types", {}) or any(
            kw in f.get("path", "").lower()
            for kw in ("created", "updated", "timestamp", "date")
        )
    ]
    timeliness = None
    if date_fields:
        timeliness = _compute_timeliness(date_fields)

    # Granularity: cardinality + depth health
    granularity = _compute_granularity(fields, sampled)

    obj_quality = ObjectQuality(
        object_name=object_name,
        completeness=completeness,
        consistency=consistency,
        uniqueness=uniqueness,
        validity=validity,
        timeliness=timeliness,
        fields=field_qualities,
    )
    obj_quality.extra_dimensions["granularity"] = granularity
    return obj_quality


def _compute_timeliness(date_fields: list[dict[str, Any]]) -> QualityDimension:
    """Score timeliness by inspecting sample date values for recency and future-date issues."""
    import datetime as _dt

    now = _dt.datetime.utcnow()
    parsed_ages_days: list[float] = []
    future_count = 0
    parsed_count = 0

    def _try_parse(v: Any) -> _dt.datetime | None:
        if isinstance(v, _dt.datetime):
            return v
        if not isinstance(v, str) or not v:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return _dt.datetime.strptime(v[: len(fmt) + 4], fmt)
            except (ValueError, TypeError):
                continue
        try:
            return _dt.datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, AttributeError):
            return None

    for f in date_fields:
        for v in (f.get("examples") or [])[:20]:
            parsed = _try_parse(v)
            if not parsed:
                continue
            parsed_count += 1
            delta = (now - parsed).days
            if delta < 0:
                future_count += 1
            else:
                parsed_ages_days.append(delta)

    if not parsed_ages_days:
        # No parseable dates — give neutral mid-score so we don't false-claim freshness
        return QualityDimension(
            name="timeliness",
            score=70.0,
            weight=0.10,
            details={"date_fields": len(date_fields), "parseable": parsed_count},
        )

    median_age = sorted(parsed_ages_days)[len(parsed_ages_days) // 2]
    # 0 days → 100, 30 days → ~90, 365 → ~60, 3650 → ~10
    import math
    recency_score = max(0.0, 100.0 - 25.0 * math.log10(max(1.0, median_age + 1)))
    future_penalty = min(40.0, future_count * 5.0)
    score = max(0.0, recency_score - future_penalty)

    return QualityDimension(
        name="timeliness",
        score=score,
        weight=0.10,
        details={
            "date_fields": len(date_fields),
            "parseable_samples": parsed_count,
            "median_age_days": int(median_age),
            "future_dated_samples": future_count,
        },
    )


def _compute_granularity(fields: list[dict[str, Any]], sampled: int) -> QualityDimension:
    """Score granularity: penalize fields whose distinct-cardinality is too low or too high to be useful."""
    if not fields or sampled <= 0:
        return QualityDimension(name="granularity", score=100.0, weight=0.10, details={})
    scalar_fields = [
        f for f in fields
        if not ({"object", "array"} & set(f.get("types", {}).keys()))
    ]
    if not scalar_fields:
        return QualityDimension(name="granularity", score=100.0, weight=0.10, details={"scalar_fields": 0})

    ok = 0
    constant = 0
    near_unique = 0
    for f in scalar_fields:
        distinct = f.get("distinct_count_in_sample", 0)
        if distinct <= 1:
            constant += 1
            continue
        ratio = distinct / sampled
        if ratio >= 0.99 and "id" not in f.get("path", "").lower():
            # Non-ID field with near-unique values — may be noise (free text)
            near_unique += 1
            continue
        ok += 1

    total = len(scalar_fields)
    score = (ok / total) * 100
    return QualityDimension(
        name="granularity",
        score=score,
        weight=0.10,
        details={
            "scalar_fields": total,
            "healthy_cardinality": ok,
            "constant_fields": constant,
            "near_unique_non_id_fields": near_unique,
        },
    )


def compute_schema_quality(
    schema_json: dict[str, Any],
    patterns_data: dict[str, Any] | None = None,
) -> SchemaQuality:
    """
    Compute quality scores for the entire schema.

    Args:
        schema_json: Schema analysis JSON from profiling.
        patterns_data: Optional output of ``analyze_patterns`` — enables
            an Accuracy dimension based on dominant-pattern conformance.

    Returns:
        SchemaQuality with per-object and overall scores.
    """
    objects = [
        compute_object_quality(obj)
        for obj in schema_json.get("objects", [])
    ]

    if patterns_data:
        by_obj = patterns_data.get("by_object", {})
        for q_obj in objects:
            rows = by_obj.get(q_obj.object_name, [])
            if not rows:
                continue
            conformances = [
                float(r.get("dominant_conformance", 0.0))
                for r in rows
                if isinstance(r.get("dominant_conformance"), (int, float))
            ]
            if not conformances:
                continue
            avg_conformance = sum(conformances) / len(conformances)
            q_obj.extra_dimensions["accuracy"] = QualityDimension(
                name="accuracy",
                score=avg_conformance * 100,
                weight=0.15,
                details={
                    "fields_with_pattern": len(rows),
                    "avg_pattern_conformance": round(avg_conformance, 3),
                },
            )

    return SchemaQuality(objects=objects)


def get_quality_grade(score: float) -> str:
    """
    Convert a numeric score to a letter grade.

    A: 90-100
    B: 80-89
    C: 70-79
    D: 60-69
    F: <60
    """
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def get_quality_color(score: float) -> str:
    """Get CSS color class for a quality score."""
    if score >= 90:
        return "quality-excellent"
    if score >= 80:
        return "quality-good"
    if score >= 70:
        return "quality-fair"
    if score >= 60:
        return "quality-poor"
    return "quality-critical"
