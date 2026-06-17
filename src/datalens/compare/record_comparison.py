"""
Record-level comparison — detect data-level changes for matching records.

Complements schema comparison by detecting value changes in matched records.
Example: Same product ID has different country codes in two datasets.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
from datetime import datetime


@dataclass
class RecordChange:
    """A single value change for a field in a matched record."""

    record_id: str  # Primary key value(s) as string (e.g., "yupptv" or "yupptv|IN")
    field_path: str  # Nested path (e.g., "countryCodesTwo")
    value_s1: Any  # Value in schema1
    value_s2: Any  # Value in schema2
    change_type: str  # "modified", "null_to_value", "value_to_null"

    def __post_init__(self):
        """Normalize values for comparison (convert lists to tuples for hashing)."""
        if isinstance(self.value_s1, list):
            self.value_s1 = tuple(self.value_s1)
        if isinstance(self.value_s2, list):
            self.value_s2 = tuple(self.value_s2)


@dataclass
class RecordDiffSummary:
    """Summary statistics for a field's changes."""

    field: str
    total_changes: int
    change_types: dict[str, int]  # {"modified": 45, "null_to_value": 2, ...}
    sample_changes: list[RecordChange] = field(default_factory=list)  # First 5 changes


@dataclass
class RecordDiff:
    """Result of record-level comparison."""

    # Metadata
    schema1_name: str = "Schema 1"
    schema2_name: str = "Schema 2"
    compared_at: str = ""
    primary_key: str | list[str] = ""  # Single field or composite key

    # Record matching stats
    total_records_s1: int = 0
    total_records_s2: int = 0
    matched_records: int = 0  # Records found in both datasets
    only_in_s1: int = 0  # Records only in schema1
    only_in_s2: int = 0  # Records only in schema2
    records_with_changes: int = 0  # Matched records that have at least one field change

    # Sampled vs full scan
    is_sampled: bool = False
    sample_size: int = 0

    # Changes organized by field
    changes_by_field: dict[str, list[RecordChange]] = field(default_factory=dict)

    # Summary statistics
    field_summaries: dict[str, RecordDiffSummary] = field(default_factory=dict)

    # Orphan records
    orphans_s1: list[str] = field(default_factory=list)  # Sample of records only in S1
    orphans_s2: list[str] = field(default_factory=list)  # Sample of records only in S2

    @property
    def has_changes(self) -> bool:
        """Check if any changes detected."""
        return (
            self.records_with_changes > 0
            or self.only_in_s1 > 0
            or self.only_in_s2 > 0
        )

    @property
    def total_changes(self) -> int:
        """Total number of value changes across all fields."""
        return sum(len(changes) for changes in self.changes_by_field.values())


def _get_nested_value(record: dict[str, Any], path: str) -> Any:
    """Get value from nested dict using dot notation."""
    keys = path.split(".")
    value = record
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


def _flatten_dict(obj: Any, parent_key: str = "", sep: str = ".") -> dict[str, Any]:
    """
    Flatten a nested dict/object to leaf node paths only.

    Example:
        {"metadata": {"owner": "john", "created": "2024-01-01"}}
        →
        {"metadata.owner": "john", "metadata.created": "2024-01-01"}

    Args:
        obj: Object to flatten (dict, list, or scalar)
        parent_key: Parent key for nesting
        sep: Separator for nested keys

    Returns:
        Dict with flattened leaf paths
    """
    items = {}

    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                # Recursively flatten nested dicts
                items.update(_flatten_dict(v, new_key, sep=sep))
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                # For arrays of objects, add array marker
                items.update(_flatten_dict(v[0], f"{new_key}[]", sep=sep))
            else:
                # Leaf node
                items[new_key] = v
    elif isinstance(obj, list):
        # If it's a list of scalars or a list of objects
        if obj and isinstance(obj[0], dict):
            items.update(_flatten_dict(obj[0], f"{parent_key}[]", sep=sep))
        else:
            items[parent_key] = obj
    else:
        items[parent_key] = obj

    return items


def _normalize_value(value: Any) -> Any:
    """Normalize values for comparison."""
    if isinstance(value, list):
        return tuple(sorted(str(v) for v in value))  # Sort for consistent comparison
    if isinstance(value, dict):
        return str(sorted(value.items()))
    return value


def _detect_change_type(val_s1: Any, val_s2: Any) -> str:
    """Detect type of change."""
    is_null_s1 = val_s1 is None or (isinstance(val_s1, list) and len(val_s1) == 0)
    is_null_s2 = val_s2 is None or (isinstance(val_s2, list) and len(val_s2) == 0)

    if is_null_s1 and not is_null_s2:
        return "null_to_value"
    elif not is_null_s1 and is_null_s2:
        return "value_to_null"
    else:
        return "modified"


def _make_composite_key(record: dict[str, Any], key_fields: str | list[str]) -> str:
    """Create composite primary key from one or more fields."""
    if isinstance(key_fields, str):
        key_fields = [key_fields]

    key_parts = []
    for field in key_fields:
        value = _get_nested_value(record, field)
        key_parts.append(str(value))

    return "|".join(key_parts)


def is_schema_file(data: Any) -> bool:
    """
    Detect if the JSON is a schema file (from datalens analyze).

    Schema files have a specific structure with "objects" array containing field metadata.
    """
    if not isinstance(data, dict):
        return False

    # Schema files have "objects" array with field definitions
    objects = data.get("objects", [])
    if not isinstance(objects, list) or len(objects) == 0:
        return False

    # Check if first object has schema-like structure
    first_obj = objects[0]
    if not isinstance(first_obj, dict):
        return False

    # Schema objects have "fields" array with metadata
    fields = first_obj.get("fields", [])
    if not isinstance(fields, list) or len(fields) == 0:
        return False

    # Check if fields have schema metadata (path, types, presence_count, etc.)
    first_field = fields[0]
    schema_indicators = {"path", "types", "presence_count", "cardinality"}
    has_schema_metadata = any(key in first_field for key in schema_indicators)

    return has_schema_metadata


def load_records_from_source(
    source_path: str | Path,
    primary_key: str | list[str],
    sample_size: int | None = None,
) -> tuple[dict[str, dict[str, Any]], int, bool]:
    """
    Load records from a JSON file and index by primary key.

    Args:
        source_path: Path to JSON file.
        primary_key: Field name(s) to use as key (single or composite).
        sample_size: If set, sample this many records (None = all).

    Returns:
        (indexed_records, total_records, is_raw_data) where:
        - indexed_records is {key: record, ...}
        - is_raw_data is True if this is raw data, False if schema file
    """
    with open(source_path) as f:
        data = json.load(f)

    # Detect if this is a schema file or raw data
    is_raw = not is_schema_file(data)

    # Handle different JSON structures
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        # If it's a schema file, extract records from data.records or similar
        if not is_raw:
            # For schema files, look for actual data in common keys
            for key in ["data", "records", "items", "hits", "results"]:
                if key in data and isinstance(data[key], list):
                    records = data[key]
                    break
            else:
                raise ValueError("Schema file but no data array found")
        else:
            # Raw data - try to find array field or use whole dict
            for key in ["data", "records", "items", "hits", "results", "list"]:
                if key in data and isinstance(data[key], list):
                    records = data[key]
                    break
            else:
                # If no standard key found, use dict values or whole dict
                if isinstance(data, dict) and data:
                    first_val = next(iter(data.values()), None)
                    if isinstance(first_val, dict):
                        records = list(data.values())
                    else:
                        records = [data]
                else:
                    records = [data]
    else:
        raise ValueError(f"Unexpected JSON structure: {type(data)}")

    total = len(records)

    # Sample if requested
    if sample_size and total > sample_size:
        import random

        records = random.sample(records, sample_size)

    # Index by primary key
    indexed = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        key = _make_composite_key(record, primary_key)
        if key:
            indexed[key] = record

    return indexed, total, is_raw


def compare_records(
    records_s1: dict[str, dict[str, Any]],
    records_s2: dict[str, dict[str, Any]],
    primary_key: str | list[str],
    schema1_name: str = "Schema 1",
    schema2_name: str = "Schema 2",
    total_records_s1: int | None = None,
    total_records_s2: int | None = None,
    is_sampled: bool = False,
    sample_size: int = 0,
) -> RecordDiff:
    """
    Compare records by primary key.

    For each matched record:
    - Compare field values
    - Detect adds, deletes, changes
    - Aggregate by field

    Args:
        records_s1, records_s2: Indexed records {key: record, ...}
        primary_key: Primary key field(s).
        schema1_name, schema2_name: Display names.
        total_records_s1/s2: Original total before sampling (for reporting).
        is_sampled: Whether these are sampled records.
        sample_size: Sample size if sampled.

    Returns:
        RecordDiff with all detected changes.
    """
    diff = RecordDiff(
        schema1_name=schema1_name,
        schema2_name=schema2_name,
        compared_at=datetime.utcnow().isoformat() + "Z",
        primary_key=primary_key,
        total_records_s1=total_records_s1 or len(records_s1),
        total_records_s2=total_records_s2 or len(records_s2),
        is_sampled=is_sampled,
        sample_size=sample_size,
    )

    ids_s1 = set(records_s1.keys())
    ids_s2 = set(records_s2.keys())

    # Find common, added, removed
    common_ids = ids_s1 & ids_s2
    orphans_s1 = ids_s1 - ids_s2
    orphans_s2 = ids_s2 - ids_s1

    diff.matched_records = len(common_ids)
    diff.only_in_s1 = len(orphans_s1)
    diff.only_in_s2 = len(orphans_s2)

    # Sample orphans (show first 20)
    diff.orphans_s1 = sorted(orphans_s1)[:20]
    diff.orphans_s2 = sorted(orphans_s2)[:20]

    # Collect all LEAF fields from both datasets (flatten nested structures)
    all_leaf_fields = set()
    for record in records_s1.values():
        if isinstance(record, dict):
            flattened = _flatten_dict(record)
            all_leaf_fields.update(flattened.keys())
    for record in records_s2.values():
        if isinstance(record, dict):
            flattened = _flatten_dict(record)
            all_leaf_fields.update(flattened.keys())

    # Compare common records (using flattened leaf node paths)
    records_changed = set()

    for rec_id in common_ids:
        rec1 = records_s1[rec_id]
        rec2 = records_s2[rec_id]

        if not isinstance(rec1, dict) or not isinstance(rec2, dict):
            continue

        # Flatten both records to leaf nodes
        flat_rec1 = _flatten_dict(rec1)
        flat_rec2 = _flatten_dict(rec2)

        # Compare each leaf field
        for field in all_leaf_fields:
            val1 = flat_rec1.get(field)
            val2 = flat_rec2.get(field)

            # Normalize for comparison
            val1_norm = _normalize_value(val1)
            val2_norm = _normalize_value(val2)

            if val1_norm != val2_norm:
                change = RecordChange(
                    record_id=rec_id,
                    field_path=field,
                    value_s1=val1,
                    value_s2=val2,
                    change_type=_detect_change_type(val1, val2),
                )
                diff.changes_by_field.setdefault(field, []).append(change)
                records_changed.add(rec_id)

    diff.records_with_changes = len(records_changed)

    # Build field summaries
    for field, changes in diff.changes_by_field.items():
        change_types = {}
        for change in changes:
            change_types[change.change_type] = change_types.get(change.change_type, 0) + 1

        summary = RecordDiffSummary(
            field=field,
            total_changes=len(changes),
            change_types=change_types,
            sample_changes=changes[:5],  # First 5 samples
        )
        diff.field_summaries[field] = summary

    return diff
