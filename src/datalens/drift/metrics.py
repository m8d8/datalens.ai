"""
Run metrics — a flat, schema-agnostic snapshot of the numbers drift is measured on.

Every run is reduced to ``{metric key: value}``. Keys are
``"<metric>|<object>|<field>"`` (field empty for object- and dataset-level
metrics), so any schema — nested documents, arrays, many entities — maps onto
the same structure and can be compared across runs or fed to the rolling
baseline.

Metrics:

    row_count|obj|          rows in the object (true count when known, else sampled)
    sampled|obj|            rows actually profiled (sets the statistical noise floor)
    coverage|obj|path       % of rows where the field is present and non-empty
    distinct|obj|path       distinct values (low-cardinality fields only — a
                            category count; high-cardinality counts grow with volume)
    orphan_pct|obj|path     % of a foreign key's occurrences with no matching parent
    dqi||                   overall Data Quality Index
    dqi|obj|                per-object DQI
    dqi||<dimension>        dataset score of one DQI dimension (completeness, …)
    health||                health score (DQI minus penalties)

Distributions are compared separately (see ``psi``), from the ``value_counts``
and ``numeric.quantiles`` stored with each field in the schema snapshot.
"""

from __future__ import annotations

import math
from typing import Any

EPSILON = 1e-4
"""Floor for empty bins in PSI, so a category that appears/disappears doesn't give log(0)."""


def metric_key(metric: str, obj: str = "", path: str = "") -> str:
    return f"{metric}|{obj}|{path}"


def split_key(key: str) -> tuple[str, str, str]:
    metric, obj, path = (key.split("|", 2) + ["", ""])[:3]
    return metric, obj, path


def object_rows(obj: dict[str, Any]) -> int:
    total = obj.get("total_rows")
    return int(total) if total is not None else int(obj.get("sampled", 0))


def field_coverage(field: dict[str, Any], sampled: int) -> float:
    """True coverage (see datalens.profiling.coverage)."""
    from datalens.profiling.coverage import coverage_pct

    return coverage_pct(field, sampled)


def extract_metrics(
    schema_json: dict[str, Any],
    *,
    joins: dict[str, Any] | None = None,
    quality: dict[str, Any] | None = None,
    health: float | None = None,
) -> dict[str, float]:
    """Reduce one run to its metric dict."""
    from datalens.profiling.naming import is_identifier_name

    fk_fields = {link["child"] for link in (joins or {}).get("referential_integrity", [])}
    metrics: dict[str, float] = {}
    for obj in schema_json.get("objects", []):
        name = obj.get("object", "")
        sampled = obj.get("sampled", 0) or 0
        metrics[metric_key("row_count", name)] = float(object_rows(obj))
        metrics[metric_key("sampled", name)] = float(sampled)
        for field in obj.get("fields", []):
            path = field.get("path", "")
            metrics[metric_key("coverage", name, path)] = round(field_coverage(field, sampled), 4)
            # Category counts only for category-like fields: the number of distinct
            # ids, references or dates just grows with volume.
            if (field.get("low_cardinality") and not is_identifier_name(path)
                    and f"{name}.{path}" not in fk_fields and "date" not in field.get("types", {})):
                metrics[metric_key("distinct", name, path)] = float(field.get("distinct_count_in_sample", 0))

    for link in (joins or {}).get("referential_integrity", []):
        obj, _, path = link["child"].partition(".")
        metrics[metric_key("orphan_pct", obj, path)] = float(link["orphan_pct"])

    if quality:
        overall = quality.get("overall_dqi")
        if isinstance(overall, dict):
            overall = overall.get("score", overall.get("dqi"))
        if isinstance(overall, (int, float)):
            metrics[metric_key("dqi")] = round(float(overall), 2)
        for dim, score in (quality.get("schema_dimensions") or {}).items():
            if isinstance(score, (int, float)):
                metrics[metric_key("dqi", "", dim)] = round(float(score), 2)
        for obj_q in quality.get("objects", []) or []:
            if isinstance(obj_q, dict) and isinstance(obj_q.get("dqi"), (int, float)):
                metrics[metric_key("dqi", obj_q.get("object", ""))] = round(float(obj_q["dqi"]), 2)
    if health is not None:
        metrics[metric_key("health")] = round(float(health), 2)
    return metrics


def extract_categories(schema_json: dict[str, Any], *, joins: dict[str, Any] | None = None,
                       max_values: int = 50) -> dict[str, list[str]]:
    """
    Values of category-like fields, saved with each run so rolling mode can tell
    a genuinely new value from one that merely skipped yesterday's load.
    Identifier, foreign-key, date and PII (masked) fields are excluded.
    """
    from datalens.profiling.naming import is_identifier_name

    fk_fields = {link["child"] for link in (joins or {}).get("referential_integrity", [])}
    out: dict[str, list[str]] = {}
    for obj in schema_json.get("objects", []):
        name = obj.get("object", "")
        for field in obj.get("fields", []):
            path = field.get("path", "")
            values = field.get("value_counts") or {}
            if (not field.get("low_cardinality") or field.get("masked") or not values
                    or len(values) > max_values or is_identifier_name(path)
                    or f"{name}.{path}" in fk_fields or "date" in field.get("types", {})):
                continue
            out[metric_key("categories", name, path)] = sorted(values)
    return out


# ─── distributions ────────────────────────────────────────────────────────────

def psi(expected: list[float], actual: list[float]) -> float:
    """
    Population Stability Index between two binned distributions (proportions).

        PSI = Σ (aᵢ − eᵢ) · ln(aᵢ / eᵢ)

    Rule of thumb: < 0.10 stable, 0.10–0.25 moderate shift, > 0.25 major shift.
    """
    total = 0.0
    for e, a in zip(expected, actual):
        e = max(e, EPSILON)
        a = max(a, EPSILON)
        total += (a - e) * math.log(a / e)
    return round(total, 4)


def categorical_psi(old_counts: dict[str, int], new_counts: dict[str, int]) -> tuple[float, list[str], list[str]]:
    """PSI over the union of categories, plus new and vanished categories."""
    old_total = sum(old_counts.values()) or 1
    new_total = sum(new_counts.values()) or 1
    cats = sorted(set(old_counts) | set(new_counts))
    expected = [old_counts.get(c, 0) / old_total for c in cats]
    actual = [new_counts.get(c, 0) / new_total for c in cats]
    new_cats = sorted(set(new_counts) - set(old_counts))
    vanished = sorted(set(old_counts) - set(new_counts))
    return psi(expected, actual), new_cats, vanished


def _points(quantiles: dict[str, float]) -> list[tuple[float, float]]:
    return sorted((float(v), int(k[1:]) / 100) for k, v in quantiles.items())


def _cdf(quantiles: dict[str, float], x: float) -> float:
    """Approximate share of values ≤ x from a percentile table (linear interpolation)."""
    points = _points(quantiles)
    if x < points[0][0]:
        return 0.0
    if x >= points[-1][0]:
        return 1.0
    for (x0, q0), (x1, q1) in zip(points, points[1:]):
        if x0 <= x < x1 and (x1 > x0):
            # Several percentiles can share a value (discrete data): the highest
            # level at x0 is where this segment starts.
            return q0 + (q1 - q0) * (x - x0) / (x1 - x0)
    return 1.0


def _cdf_lower(quantiles: dict[str, float], x: float) -> float:
    """Approximate share of values < x (the lowest percentile level reaching x)."""
    points = _points(quantiles)
    for i, (xi, qi) in enumerate(points):
        if xi >= x:
            if i == 0:
                return 0.0
            x0, q0 = points[i - 1]
            return q0 + (qi - q0) * (x - x0) / (xi - x0) if xi > x0 else qi
    return 1.0


def numeric_psi(old_quantiles: dict[str, float], new_quantiles: dict[str, float], bins: int = 10) -> float:
    """
    PSI of a numeric field, computed from stored percentile tables only.

    Bins are the reference run's deciles (so each holds ~10% of the old data);
    each run's share of a bin comes from its interpolated CDF. Two extra bins
    catch mass below the old minimum and above the old maximum (new territory).
    Works for discrete data too (repeated edges collapse into one bin).
    """
    edges = sorted({float(old_quantiles[f"p{q}"]) for q in range(0, 101, 100 // bins) if f"p{q}" in old_quantiles})
    if len(edges) < 2:
        return 0.0

    def shares(q: dict[str, float]) -> list[float]:
        out = [_cdf_lower(q, edges[0])]
        prev = _cdf_lower(q, edges[0])
        for hi in edges[1:]:
            cur = _cdf(q, hi)
            out.append(max(0.0, cur - prev))
            prev = cur
        out.append(max(0.0, 1.0 - prev))
        return out

    return psi(shares(old_quantiles), shares(new_quantiles))


def proportion_se_pts(pct: float, n: float) -> float:
    """Standard error of a percentage measured on n rows, in percentage points."""
    if n <= 0:
        return 0.0
    p = min(max(pct / 100.0, 0.0), 1.0)
    return 100.0 * math.sqrt(max(p * (1 - p), 1.0 / (4 * n * n)) / n)


def psi_noise(categories: int, n_old: float, n_new: float) -> float:
    """
    Expected PSI between two samples of the *same* distribution:
    ≈ (k − 1) · (1/n₁ + 1/n₂). Thresholds below ~3× this are just sampling noise.
    """
    if n_old <= 0 or n_new <= 0:
        return float("inf")
    return max(0, categories - 1) * (1.0 / n_old + 1.0 / n_new)
