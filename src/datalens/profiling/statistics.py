"""
Statistics — numeric and temporal field profiling.

For numeric fields:
- Min, max, mean, median, stddev
- Percentiles (p25, p50, p75, p95, p99)
- Zero count, negative count
- Distribution shape (skewness indicator)

For temporal fields:
- Min, max dates
- Date range span (days)
- Gaps analysis
- Temporal distribution
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

# Date parsing patterns
_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y/%m/%d",
]


@dataclass
class NumericStats:
    """Statistics for a numeric field."""

    field_path: str
    count: int
    min_value: float | None
    max_value: float | None
    mean: float | None
    median: float | None
    stddev: float | None
    p25: float | None
    p50: float | None
    p75: float | None
    p95: float | None
    p99: float | None
    zero_count: int
    negative_count: int
    positive_count: int
    distribution: str  # "uniform", "skewed_left", "skewed_right", "bimodal", "unknown"

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "path": self.field_path,
            "count": self.count,
            "min": self.min_value,
            "max": self.max_value,
            "mean": round(self.mean, 4) if self.mean is not None else None,
            "median": round(self.median, 4) if self.median is not None else None,
            "stddev": round(self.stddev, 4) if self.stddev is not None else None,
            "percentiles": {
                "p25": round(self.p25, 4) if self.p25 is not None else None,
                "p50": round(self.p50, 4) if self.p50 is not None else None,
                "p75": round(self.p75, 4) if self.p75 is not None else None,
                "p95": round(self.p95, 4) if self.p95 is not None else None,
                "p99": round(self.p99, 4) if self.p99 is not None else None,
            },
            "zero_count": self.zero_count,
            "negative_count": self.negative_count,
            "positive_count": self.positive_count,
            "distribution": self.distribution,
        }


@dataclass
class TemporalStats:
    """Statistics for a temporal (date/datetime) field."""

    field_path: str
    count: int
    min_date: str | None
    max_date: str | None
    span_days: int | None
    null_count: int
    future_count: int  # Dates after today
    date_distribution: dict[str, int] = field(default_factory=dict)  # Year/month bins

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "path": self.field_path,
            "count": self.count,
            "min_date": self.min_date,
            "max_date": self.max_date,
            "span_days": self.span_days,
            "null_count": self.null_count,
            "future_count": self.future_count,
            "date_distribution": self.date_distribution,
        }


@dataclass
class FieldStatistics:
    """Container for all statistical analyses of a field."""

    path: str
    numeric: NumericStats | None = None
    temporal: TemporalStats | None = None


def parse_date(value: Any) -> datetime | None:
    """Attempt to parse a date from various formats."""
    if isinstance(value, datetime):
        return value

    if not isinstance(value, str):
        return None

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    return None


def compute_percentile(sorted_values: list[float], percentile: float) -> float | None:
    """Compute a percentile from sorted values."""
    if not sorted_values:
        return None

    k = (len(sorted_values) - 1) * (percentile / 100)
    f = math.floor(k)
    c = math.ceil(k)

    if f == c:
        return sorted_values[int(k)]

    return sorted_values[int(f)] * (c - k) + sorted_values[int(c)] * (k - f)


def compute_stddev(values: list[float], mean: float) -> float:
    """Compute standard deviation."""
    if len(values) < 2:
        return 0.0

    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def detect_distribution(values: list[float], mean: float, median: float) -> str:
    """
    Detect distribution shape based on mean/median relationship.

    Returns: "uniform", "skewed_left", "skewed_right", or "unknown"
    """
    if not values or mean is None or median is None:
        return "unknown"

    if len(values) < 10:
        return "unknown"

    # Calculate skewness indicator
    if abs(mean - median) < 0.01 * abs(mean):
        return "uniform"

    if mean > median:
        return "skewed_right"

    return "skewed_left"


def compute_numeric_stats(field_path: str, values: list[Any]) -> NumericStats | None:
    """
    Compute numeric statistics for a field.

    Args:
        field_path: Path to the field.
        values: List of values (may include non-numeric).

    Returns:
        NumericStats or None if no numeric values found.
    """
    # Extract numeric values
    numeric_values: list[float] = []
    zero_count = 0
    negative_count = 0
    positive_count = 0

    for v in values:
        if v is None:
            continue
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            numeric_values.append(float(v))
            if v == 0:
                zero_count += 1
            elif v < 0:
                negative_count += 1
            else:
                positive_count += 1
        elif isinstance(v, str):
            try:
                num = float(v)
                numeric_values.append(num)
                if num == 0:
                    zero_count += 1
                elif num < 0:
                    negative_count += 1
                else:
                    positive_count += 1
            except ValueError:
                continue

    if not numeric_values:
        return None

    # Sort for percentile calculations
    sorted_values = sorted(numeric_values)
    count = len(sorted_values)

    min_value = sorted_values[0]
    max_value = sorted_values[-1]
    mean = sum(sorted_values) / count
    median = compute_percentile(sorted_values, 50)
    stddev = compute_stddev(sorted_values, mean)

    p25 = compute_percentile(sorted_values, 25)
    p50 = median
    p75 = compute_percentile(sorted_values, 75)
    p95 = compute_percentile(sorted_values, 95)
    p99 = compute_percentile(sorted_values, 99)

    distribution = detect_distribution(sorted_values, mean, median or mean)

    return NumericStats(
        field_path=field_path,
        count=count,
        min_value=min_value,
        max_value=max_value,
        mean=mean,
        median=median,
        stddev=stddev,
        p25=p25,
        p50=p50,
        p75=p75,
        p95=p95,
        p99=p99,
        zero_count=zero_count,
        negative_count=negative_count,
        positive_count=positive_count,
        distribution=distribution,
    )


def compute_temporal_stats(field_path: str, values: list[Any]) -> TemporalStats | None:
    """
    Compute temporal statistics for a date field.

    Args:
        field_path: Path to the field.
        values: List of values (dates as strings or datetime objects).

    Returns:
        TemporalStats or None if no dates found.
    """
    dates: list[datetime] = []
    null_count = 0
    future_count = 0
    now = datetime.now()
    date_bins: dict[str, int] = {}

    for v in values:
        if v is None:
            null_count += 1
            continue

        parsed = parse_date(v)
        if parsed:
            dates.append(parsed)
            if parsed > now:
                future_count += 1

            # Bin by year-month
            bin_key = parsed.strftime("%Y-%m")
            date_bins[bin_key] = date_bins.get(bin_key, 0) + 1

    if not dates:
        return None

    sorted_dates = sorted(dates)
    min_date = sorted_dates[0]
    max_date = sorted_dates[-1]
    span = (max_date - min_date).days

    return TemporalStats(
        field_path=field_path,
        count=len(dates),
        min_date=min_date.isoformat(),
        max_date=max_date.isoformat(),
        span_days=span,
        null_count=null_count,
        future_count=future_count,
        date_distribution=dict(sorted(date_bins.items())),
    )


def analyze_field_statistics(
    field_data: dict[str, Any],
    sample_values: list[Any] | None = None,
) -> FieldStatistics:
    """
    Analyze a field and compute appropriate statistics.

    Args:
        field_data: Field dict from profiling output.
        sample_values: Optional list of actual values for deeper analysis.

    Returns:
        FieldStatistics with numeric and/or temporal stats.
    """
    path = field_data.get("path", "")
    types = field_data.get("types", {})
    examples = sample_values or field_data.get("examples", [])

    result = FieldStatistics(path=path)

    # Check if this is a numeric field
    numeric_types = {"int", "float"}
    has_numeric = any(t in types for t in numeric_types)

    if has_numeric:
        result.numeric = compute_numeric_stats(path, examples)

    # Check if this is a date field
    has_date = "date" in types or any(
        kw in path.lower()
        for kw in ("date", "time", "created", "updated", "timestamp")
    )

    if has_date:
        result.temporal = compute_temporal_stats(path, examples)

    return result


def compute_statistics_summary(schema_json: dict[str, Any]) -> dict[str, Any]:
    """
    Compute statistics summary for all fields in the schema.

    Args:
        schema_json: Schema analysis JSON from profiling.

    Returns:
        Summary dict with statistics by object.
    """
    result: dict[str, Any] = {"objects": []}

    for obj in schema_json.get("objects", []):
        obj_name = obj.get("object", "unknown")
        numeric_fields: list[dict[str, Any]] = []
        temporal_fields: list[dict[str, Any]] = []

        for field_data in obj.get("fields", []):
            stats = analyze_field_statistics(field_data)

            if stats.numeric:
                numeric_fields.append(stats.numeric.to_dict())

            if stats.temporal:
                temporal_fields.append(stats.temporal.to_dict())

        result["objects"].append({
            "object": obj_name,
            "numeric_fields": numeric_fields,
            "temporal_fields": temporal_fields,
            "numeric_field_count": len(numeric_fields),
            "temporal_field_count": len(temporal_fields),
        })

    # Summary stats
    result["total_numeric_fields"] = sum(
        o["numeric_field_count"] for o in result["objects"]
    )
    result["total_temporal_fields"] = sum(
        o["temporal_field_count"] for o in result["objects"]
    )

    return result
