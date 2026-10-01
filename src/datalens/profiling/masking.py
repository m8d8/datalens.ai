"""
PII masking of profiling output.

Analytics run on the raw profile (PII detection, patterns and joins need the
real values), but everything that *leaves* the process — the HTML report, the
schema JSON file, history snapshots and AI prompts — is built from a masked
copy produced here when ``config.mask_pii`` is on (the default).

What is masked: every field whose PII detection is high-confidence
(>= HIGH_RISK_CONFIDENCE, i.e. confirmed by values or a strong field name) or
forced via ``pii_force``. Low-confidence "possible" detections (e.g. a field
simply called ``name``) are listed in the report but not masked; add them to
``pii_force`` to mask them, or to ``pii_ignore`` to stop flagging them.

Where values are masked, per field: ``examples``, ``value_counts`` keys (counts
of values that mask to the same string are merged), ``distinct_values``, the
matching values inside ``sample_records``; ``date_range`` and ``numeric``
(min/max/percentiles) are dropped.
"""

from __future__ import annotations

import copy
from typing import Any

from datalens.profiling.pii import HIGH_RISK_CONFIDENCE, PIIDetection, PIIType, mask_value


def fields_to_mask(pii_data: dict[str, list[PIIDetection]] | None) -> dict[str, dict[str, PIIType]]:
    """object → {field path → PII type} for every detection that must be masked."""
    out: dict[str, dict[str, PIIType]] = {}
    for obj_name, detections in (pii_data or {}).items():
        for det in sorted(detections, key=lambda d: d.confidence):
            if det.confidence >= HIGH_RISK_CONFIDENCE or det.method == "config":
                out.setdefault(obj_name, {})[det.field_path] = det.pii_type
    return out


def _mask_record(record: Any, parts: list[str], pii_type: PIIType) -> Any:
    """Return a copy of `record` with the value at the path (dot / [] notation) masked."""
    if not parts:
        if record is None or isinstance(record, (dict, list)):
            return record
        return mask_value(record, pii_type)
    head, rest = parts[0], parts[1:]
    is_array = head.endswith("[]")
    key = head[:-2] if is_array else head
    if not isinstance(record, dict) or key not in record:
        return record
    out = dict(record)
    value = record[key]
    if is_array and isinstance(value, list):
        out[key] = [_mask_record(item, rest, pii_type) for item in value]
    else:
        out[key] = _mask_record(value, rest, pii_type)
    return out


def mask_schema(
    schema_json: dict[str, Any],
    pii_data: dict[str, list[PIIDetection]] | None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """
    Return (masked deep copy of schema_json, list of masked fields).

    The masked-field list ({object, field, type}) is shown in the report so
    readers can see exactly what was hidden and why.
    """
    targets = fields_to_mask(pii_data)
    masked = copy.deepcopy(schema_json)
    masked_fields: list[dict[str, str]] = []
    if not targets:
        return masked, masked_fields

    for obj in masked.get("objects", []):
        obj_targets = targets.get(obj.get("object", ""), {})
        if not obj_targets:
            continue
        for field in obj.get("fields", []):
            pii_type = obj_targets.get(field.get("path", ""))
            if pii_type is None:
                continue
            field["examples"] = [mask_value(v, pii_type) for v in field.get("examples", [])]
            if field.get("value_counts"):
                merged: dict[str, int] = {}
                for value, count in field["value_counts"].items():
                    key = mask_value(value, pii_type)
                    merged[key] = merged.get(key, 0) + count
                field["value_counts"] = dict(sorted(merged.items(), key=lambda kv: -kv[1]))
            if field.get("distinct_values"):
                field["distinct_values"] = sorted({mask_value(v, pii_type) for v in field["distinct_values"]})
            # Ranges and percentiles of a PII field (e.g. dates of birth) are identifying too.
            field.pop("date_range", None)
            field.pop("numeric", None)
            field["masked"] = pii_type.value
            masked_fields.append({"object": obj.get("object", ""), "field": field["path"], "type": pii_type.value})

        records = obj.get("sample_records") or []
        for path, pii_type in obj_targets.items():
            parts = path.split(".")
            records = [_mask_record(r, parts, pii_type) for r in records]
        obj["sample_records"] = records

    return masked, masked_fields


def raw_values_for_masked_fields(
    schema_json: dict[str, Any],
    pii_data: dict[str, list[PIIDetection]] | None,
) -> set[str]:
    """Raw (unmasked) string values of masked fields — used to scrub free text such as join evidence."""
    targets = fields_to_mask(pii_data)
    values: set[str] = set()
    for obj in schema_json.get("objects", []):
        obj_targets = targets.get(obj.get("object", ""), {})
        for field in obj.get("fields", []):
            if field.get("path") in obj_targets:
                values.update(str(v) for v in field.get("examples", []))
                values.update(str(v) for v in (field.get("value_counts") or {}))
    return {v for v in values if len(v) >= 3}


def scrub(obj: Any, raw_values: set[str], replacement: str = "***") -> Any:
    """Recursively replace any raw PII value found in strings of a JSON-like structure."""
    if not raw_values:
        return obj
    if isinstance(obj, str):
        if obj in raw_values:
            return replacement
        for raw in raw_values:
            if raw in obj:
                obj = obj.replace(raw, replacement)
        return obj
    if isinstance(obj, list):
        return [scrub(item, raw_values, replacement) for item in obj]
    if isinstance(obj, tuple):
        return tuple(scrub(item, raw_values, replacement) for item in obj)
    if isinstance(obj, dict):
        return {k: scrub(v, raw_values, replacement) for k, v in obj.items()}
    return obj
