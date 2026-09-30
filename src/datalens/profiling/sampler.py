"""
Sampler — drives a Connector to collect field statistics.

This is the core profiling engine that:
1. Iterates over objects from a connector
2. Samples records from each object
3. Walks document structure to collect per-field statistics
4. Produces the §3 JSON contract
"""

from __future__ import annotations

import math
import random
from collections import Counter
from typing import TYPE_CHECKING, Any

from datalens.connectors.base import Connector, ObjectRef
from datalens.profiling.types import get_primitive_value, infer_type, is_empty_value

if TYPE_CHECKING:
    from datalens.config import Config


ROW_SAMPLE_SIZE = 2000
"""Rows kept in memory per object for row-level checks (duplicate fields, dependencies)."""

NUMERIC_SAMPLE_SIZE = 20000
"""Numeric values kept per field (uniform reservoir) to compute quantiles for distribution drift."""

QUANTILE_POINTS = tuple(range(0, 101, 5))
"""Percentiles stored per numeric field (p0, p5, …, p100)."""


class ProfileScratch:
    """
    In-memory side data gathered while profiling, never serialized.

    Holds raw-value evidence that is too large or too sensitive to put in the
    schema JSON (which is written to disk, history and the HTML report):

    - ``hashes[obj][path]``: Counter of value hash → occurrences. Exact distinct
      counts, cross-object containment (FK/orphan checks) and value overlap use it.
    - ``rows[obj]``: up to ROW_SAMPLE_SIZE raw records, for row-level checks.
    - ``overflow[obj]``: paths whose distinct values exceeded distinct_track_limit.
    """

    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, Counter]] = {}
        self.rows: dict[str, list[dict[str, Any]]] = {}
        self.overflow: dict[str, set[str]] = {}

    def field_hashes(self, obj: str, path: str) -> Counter | None:
        return self.hashes.get(obj, {}).get(path)


def profile_source(
    connector: Connector,
    config: "Config",
    scratch: ProfileScratch | None = None,
) -> dict[str, Any]:
    """
    Profile all objects from a connector.

    Args:
        connector: Connected data source connector.
        config: Configuration object.
        scratch: Optional ProfileScratch that receives in-memory value evidence.

    Returns:
        Schema JSON with the §3 contract structure.
    """
    objects_data: list[dict[str, Any]] = []

    for obj in connector.list_objects():
        obj_profile = profile_object(connector, obj, config, scratch=scratch)
        objects_data.append(obj_profile)

    return {
        "source_type": connector.source_type,
        "objects": objects_data,
        "config": {
            "sample_size": config.sample_size,
            "sample_strategy": config.sample_strategy if config.sample_size else "full_scan",
            "max_depth": config.max_depth,
            "max_distinct_values": config.max_distinct_values,
        },
    }


def profile_object(
    connector: Connector,
    obj: ObjectRef,
    config: "Config",
    scratch: ProfileScratch | None = None,
) -> dict[str, Any]:
    """
    Profile a single object (collection/table/file).

    Args:
        connector: Connected data source connector.
        obj: Object reference to profile.
        config: Configuration object.
        scratch: Optional ProfileScratch that receives in-memory value evidence.

    Returns:
        Object profile dict with the §3 contract structure.
    """
    stats: dict[str, dict[str, Any]] = {}
    sample_records: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    sampled_count = 0

    # Sample records and collect stats
    for record in connector.sample(
        obj,
        sample_size=config.sample_size,
        max_depth=config.max_depth,
    ):
        sampled_count += 1

        # Collect sample records (up to configured limit)
        if len(sample_records) < config.sample_records_count:
            sample_records.append(_sanitize_record(record))
        if len(rows) < ROW_SAMPLE_SIZE:
            rows.append(record)

        # Walk document and collect field statistics
        doc_array_fields: dict[str, dict[str, bool]] = {}
        _walk_doc_for_stats(
            doc=record,
            prefix="",
            stats=stats,
            config=config,
            depth=0,
            array_depth=0,
            doc_array_fields=doc_array_fields,
        )

        # Flush array field tracking for this document
        _flush_doc_array_fields(stats, doc_array_fields)

    # Finalize field entries
    fields = _finalize_fields(stats, sampled_count, config)

    if scratch is not None:
        scratch.hashes[obj.name] = {path: info["hashes"] for path, info in stats.items()}
        scratch.rows[obj.name] = rows
        scratch.overflow[obj.name] = {p for p, info in stats.items() if info["hash_overflow"]}

    profile: dict[str, Any] = {
        "object": obj.name,
        "label": obj.label,
        "query_filter": obj.query_filter,
        "sampled": sampled_count,
        "fields": fields,
        "sample_records": sample_records,
    }
    # Connectors that saw every row while sampling (e.g. reservoir sampling of a
    # file) report the true row count, so volume drift isn't limited to the sample.
    total_rows = obj.metadata.get("total_rows") if obj.metadata else None
    if total_rows is None and not config.sample_size:
        total_rows = sampled_count
    if total_rows is not None:
        profile["total_rows"] = total_rows
    return profile


def _new_entry() -> dict[str, Any]:
    return {
        "presence_count": 0,
        "null_empty_count": 0,
        "types": Counter(),
        "examples": [],
        "value_counts": Counter(),
        "hashes": Counter(),
        "hash_overflow": False,
        "numbers": [],
        "numbers_seen": 0,
        "str_min": None,
        "str_max": None,
    }


_NUMERIC_RNG = random.Random(7)


def _reservoir_add(entry: dict[str, Any], value: float) -> None:
    numbers = entry["numbers"]
    entry["numbers_seen"] += 1
    if len(numbers) < NUMERIC_SAMPLE_SIZE:
        numbers.append(value)
    else:
        j = _NUMERIC_RNG.randrange(entry["numbers_seen"])
        if j < NUMERIC_SAMPLE_SIZE:
            numbers[j] = value


def numeric_profile(values: list[float], seen: int) -> dict[str, Any] | None:
    """Mean/std and percentile table (p0…p100 in 5% steps) of a numeric field."""
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mean = sum(ordered) / n
    var = sum((v - mean) ** 2 for v in ordered) / n
    quantiles = {}
    for q in QUANTILE_POINTS:
        pos = (n - 1) * q / 100
        lo = int(math.floor(pos))
        hi = min(lo + 1, n - 1)
        quantiles[f"p{q}"] = round(ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo), 6)
    return {
        "count": seen,
        "mean": round(mean, 6),
        "std": round(math.sqrt(var), 6),
        "min": ordered[0],
        "max": ordered[-1],
        "quantiles": quantiles,
    }


def _track_value(entry: dict[str, Any], prim_value: Any, config: "Config") -> None:
    """Record one primitive value: examples, capped value_counts, and exact distinct hashes."""
    if len(entry["examples"]) < config.max_examples:
        if prim_value not in entry["examples"]:
            entry["examples"].append(prim_value)

    if len(entry["value_counts"]) < config.max_distinct_values or prim_value in entry["value_counts"]:
        entry["value_counts"][prim_value] += 1

    if isinstance(prim_value, str):
        # Lexicographic min/max: exact for ISO-8601 dates (used for freshness).
        if entry["str_min"] is None or prim_value < entry["str_min"]:
            entry["str_min"] = prim_value
        if entry["str_max"] is None or prim_value > entry["str_max"]:
            entry["str_max"] = prim_value
    elif isinstance(prim_value, (int, float)) and not isinstance(prim_value, bool):
        if math.isfinite(prim_value):
            _reservoir_add(entry, float(prim_value))

    hashes = entry["hashes"]
    key = hash(prim_value)
    if key in hashes or len(hashes) < config.distinct_track_limit:
        hashes[key] += 1
    else:
        entry["hash_overflow"] = True


def _walk_doc_for_stats(
    doc: Any,
    prefix: str,
    stats: dict[str, dict[str, Any]],
    config: "Config",
    depth: int,
    array_depth: int,
    doc_array_fields: dict[str, dict[str, bool]],
) -> None:
    """
    Recursively walk a document and collect field statistics.

    Array field tracking uses "at least one" semantics:
    - Inside arrays, we track per-document whether a field is present
    - This avoids inflating counts based on array length
    """
    if depth > config.max_depth:
        return

    if isinstance(doc, dict):
        for key, value in doc.items():
            if key == "_id":  # Skip MongoDB _id
                continue

            path = f"{prefix}.{key}" if prefix else key
            entry = stats.get(path)
            if entry is None:
                entry = stats[path] = _new_entry()

            # Track presence/empty based on array context
            if array_depth > 0:
                # Inside an array: use per-document tracking
                if path not in doc_array_fields:
                    doc_array_fields[path] = {"present": True, "has_value": False}
                if not is_empty_value(value):
                    doc_array_fields[path]["has_value"] = True
            else:
                # Not in array: count directly
                entry["presence_count"] += 1
                if is_empty_value(value):
                    entry["null_empty_count"] += 1

            # Always track types
            value_type = infer_type(value)
            entry["types"][value_type] += 1

            # Track examples and value counts for primitives
            prim_value = get_primitive_value(value)
            if prim_value is not None:
                _track_value(entry, prim_value, config)

            # Recurse into nested structures
            _walk_doc_for_stats(
                doc=value,
                prefix=path,
                stats=stats,
                config=config,
                depth=depth + 1,
                array_depth=array_depth,
                doc_array_fields=doc_array_fields,
            )

        return

    if isinstance(doc, list):
        # Track array presence (including empty arrays)
        arr_path = f"{prefix}[]" if prefix else "[]"
        entry = stats.get(arr_path)
        if entry is None:
            entry = stats[arr_path] = _new_entry()

        if array_depth > 0:
            # Nested array inside another array
            if arr_path not in doc_array_fields:
                doc_array_fields[arr_path] = {"present": True, "has_value": False}
            if doc:
                doc_array_fields[arr_path]["has_value"] = True
        else:
            entry["presence_count"] += 1
            if not doc:
                entry["null_empty_count"] += 1

        if not doc:
            # Empty array: increment counters and return
            return

        # Process array items (limit to max_array_items)
        items = doc[: config.max_array_items] if config.max_array_items > 0 else doc

        for item in items:
            item_type = infer_type(item)
            entry["types"][item_type] += 1

            prim_value = get_primitive_value(item)
            if prim_value is not None:
                _track_value(entry, prim_value, config)

            # Recurse into array elements
            if array_depth < config.max_array_depth:
                _walk_doc_for_stats(
                    doc=item,
                    prefix=arr_path,
                    stats=stats,
                    config=config,
                    depth=depth + 1,
                    array_depth=array_depth + 1,
                    doc_array_fields=doc_array_fields,
                )


def _flush_doc_array_fields(
    stats: dict[str, dict[str, Any]],
    doc_array_fields: dict[str, dict[str, bool]],
) -> None:
    """
    Flush per-document array field tracking into aggregate stats.

    For each path tracked during a single document's traversal:
    - Increment presence_count by 1 (field was present in at least one array element)
    - Increment null_empty_count by 1 if no element had a non-empty value
    """
    for path, info in doc_array_fields.items():
        entry = stats.get(path)
        if entry is None:
            entry = stats[path] = _new_entry()
        entry["presence_count"] += 1
        if not info["has_value"]:
            entry["null_empty_count"] += 1


def _finalize_fields(
    stats: dict[str, dict[str, Any]],
    total_sampled: int,
    config: "Config",
) -> list[dict[str, Any]]:
    """Convert raw stats to final field entries."""
    fields: list[dict[str, Any]] = []

    for path, info in sorted(stats.items()):
        value_counts = info["value_counts"]
        # Exact distinct count from value hashes (value_counts is capped at
        # max_distinct_values for display). Past distinct_track_limit it's a lower bound.
        distinct_count = len(info["hashes"]) or len(value_counts)
        low_cardinality = distinct_count <= config.low_cardinality_threshold

        field_entry: dict[str, Any] = {
            "path": path,
            "presence_count": info["presence_count"],
            "null_empty_count": info["null_empty_count"],
            "sampled_docs": total_sampled,
            "types": dict(info["types"]),
            "examples": info["examples"][:3],  # Limit examples in output
            "distinct_count_in_sample": distinct_count,
            "distinct_is_exact": not info["hash_overflow"],
            "low_cardinality": low_cardinality,
        }

        numeric = numeric_profile(info["numbers"], info["numbers_seen"])
        if numeric:
            field_entry["numeric"] = numeric
        if "date" in info["types"] and info["str_min"] is not None:
            field_entry["date_range"] = {"min": info["str_min"], "max": info["str_max"]}

        if low_cardinality:
            field_entry["distinct_values"] = sorted(str(v) for v in value_counts.keys())
            # Include all value counts for low cardinality fields
            field_entry["value_counts"] = {str(k): v for k, v in value_counts.most_common()}
        else:
            # For high cardinality fields, include top 20 values for visualization
            top_values = value_counts.most_common(20)
            if top_values:
                field_entry["value_counts"] = {str(k): v for k, v in top_values}

        fields.append(field_entry)

    return fields


def _sanitize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a record for inclusion in sample_records."""
    # Remove MongoDB _id if present
    sanitized = dict(record)
    sanitized.pop("_id", None)
    return sanitized
