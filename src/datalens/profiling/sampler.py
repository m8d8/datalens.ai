"""
Sampler — drives a Connector to collect field statistics.

This is the core profiling engine that:
1. Iterates over objects from a connector
2. Samples records from each object
3. Walks document structure to collect per-field statistics
4. Produces the §3 JSON contract
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from datalens.connectors.base import Connector, ObjectRef
from datalens.profiling.types import get_primitive_value, infer_type, is_empty_value

if TYPE_CHECKING:
    from datalens.config import Config


def profile_source(connector: Connector, config: "Config") -> dict[str, Any]:
    """
    Profile all objects from a connector.

    Args:
        connector: Connected data source connector.
        config: Configuration object.

    Returns:
        Schema JSON with the §3 contract structure.
    """
    objects_data: list[dict[str, Any]] = []

    for obj in connector.list_objects():
        obj_profile = profile_object(connector, obj, config)
        objects_data.append(obj_profile)

    return {
        "source_type": connector.source_type,
        "objects": objects_data,
        "config": {
            "sample_size": config.sample_size,
            "max_depth": config.max_depth,
            "max_distinct_values": config.max_distinct_values,
        },
    }


def profile_object(
    connector: Connector,
    obj: ObjectRef,
    config: "Config",
) -> dict[str, Any]:
    """
    Profile a single object (collection/table/file).

    Args:
        connector: Connected data source connector.
        obj: Object reference to profile.
        config: Configuration object.

    Returns:
        Object profile dict with the §3 contract structure.
    """
    stats: dict[str, dict[str, Any]] = {}
    sample_records: list[dict[str, Any]] = []
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

    return {
        "object": obj.name,
        "label": obj.label,
        "query_filter": obj.query_filter,
        "sampled": sampled_count,
        "fields": fields,
        "sample_records": sample_records,
    }


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
            entry = stats.setdefault(
                path,
                {
                    "presence_count": 0,
                    "null_empty_count": 0,
                    "types": Counter(),
                    "examples": [],
                    "value_counts": Counter(),
                },
            )

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
                if len(entry["examples"]) < config.max_examples:
                    if prim_value not in entry["examples"]:
                        entry["examples"].append(prim_value)

                if len(entry["value_counts"]) < config.max_distinct_values or prim_value in entry["value_counts"]:
                    entry["value_counts"][prim_value] += 1

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
        entry = stats.setdefault(
            arr_path,
            {
                "presence_count": 0,
                "null_empty_count": 0,
                "types": Counter(),
                "examples": [],
                "value_counts": Counter(),
            },
        )

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
                if len(entry["examples"]) < config.max_examples:
                    if prim_value not in entry["examples"]:
                        entry["examples"].append(prim_value)
                if len(entry["value_counts"]) < config.max_distinct_values or prim_value in entry["value_counts"]:
                    entry["value_counts"][prim_value] += 1

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
        entry = stats.setdefault(
            path,
            {
                "presence_count": 0,
                "null_empty_count": 0,
                "types": Counter(),
                "examples": [],
                "value_counts": Counter(),
            },
        )
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
        distinct_count = len(value_counts)
        low_cardinality = distinct_count <= config.low_cardinality_threshold

        field_entry: dict[str, Any] = {
            "path": path,
            "presence_count": info["presence_count"],
            "null_empty_count": info["null_empty_count"],
            "sampled_docs": total_sampled,
            "types": dict(info["types"]),
            "examples": info["examples"][:3],  # Limit examples in output
            "distinct_count_in_sample": distinct_count,
            "low_cardinality": low_cardinality,
        }

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
