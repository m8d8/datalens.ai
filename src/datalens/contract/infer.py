"""Bootstrap an expected JSON Schema from a profiled run ("learn it, then own it")."""

from __future__ import annotations

from typing import Any

from datalens.contract.loader import FORMAT_MAP
from datalens.drift.metrics import field_coverage
from datalens.profiling.naming import is_identifier_name

_SHAPE_TO_JSON = {
    "string": "string", "email": "string", "url": "string", "uri": "string", "uuid": "string",
    "date": "string", "phone": "string", "numeric_id": "string",
    "int": "integer", "float": "number", "bool": "boolean", "object": "object", "array": "array",
}
_FORMAT_FROM_SHAPE = {v: k for k, v in FORMAT_MAP.items() if k in ("date", "email", "uuid", "uri")}


def infer_schema(
    schema_json: dict[str, Any],
    *,
    required_coverage: float = 99.0,
    max_enum: int = 20,
    coverage_drop_pts: float = 10.0,
) -> dict[str, Any]:
    """
    Expected-schema JSON for every object in a run.

    - ``required``: fields present and non-empty in ≥ ``required_coverage``% of rows
    - ``type``: the material observed types (plus "null" when nulls were seen)
    - ``enum``: category-like fields with ≤ ``max_enum`` values (never PII / ids)
    - ``minimum: 0`` for numeric fields that were never negative (ranges are yours to add)
    - ``format``: date / email / uuid / uri when ≥ 99% of values have that shape
    - ``x-datalens``: a starting coverage-drop threshold per field — edit freely
    """
    objects: dict[str, Any] = {}
    for obj in schema_json.get("objects", []):
        objects[obj["object"]] = _object_schema(obj, required_coverage, max_enum, coverage_drop_pts)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Expected schema (inferred by Datalens — review and edit)",
        "x-datalens": {"objects": True},
        "objects": objects,
    }


def _object_schema(obj: dict[str, Any], required_coverage: float, max_enum: int, drop_pts: float) -> dict[str, Any]:
    sampled = obj.get("sampled", 0) or 0
    root: dict[str, Any] = {"type": "object", "properties": {}}
    for f in sorted(obj.get("fields", []), key=lambda x: x["path"]):
        path = f["path"]
        spec = _field_spec(f, sampled, max_enum, drop_pts)
        if path.endswith("[]"):
            # items of an array: "tags[]" (scalars) or the array node for "a[].b"
            holder = _container(root, path[:-2])
            if not isinstance(holder.get("items"), dict) or "properties" not in holder["items"]:
                item_spec = {k: v for k, v in spec.items() if k != "x-datalens"}
                if item_spec.get("type") not in ("object", ["object"]):
                    holder["items"] = item_spec
            continue
        parent_path, _, key = path.rpartition(".")
        parent = _container(root, parent_path) if parent_path else root
        props = parent.setdefault("properties", {})
        existing = props.get(key, {})
        props[key] = {**spec, **{k: v for k, v in existing.items() if k in ("properties", "items")}}
        if "[]" not in path and field_coverage(f, sampled) >= required_coverage:
            req = parent.setdefault("required", [])
            if key not in req:
                req.append(key)
    _prune(root)
    return root


def _container(root: dict[str, Any], path: str) -> dict[str, Any]:
    """Node that holds children of `path` ("a.b", "a[].b" …), created on demand."""
    node = root
    for part in path.split("."):
        is_array = part.endswith("[]")
        key = part[:-2] if is_array else part
        child = node.setdefault("properties", {}).setdefault(key, {"type": "array" if is_array else "object"})
        if is_array:
            items = child.get("items")
            if not isinstance(items, dict) or "properties" not in items:
                child["items"] = {"type": "object", "properties": {}}
            node = child["items"]
        else:
            node = child
    return node


def _field_spec(f: dict[str, Any], sampled: int, max_enum: int, drop_pts: float) -> dict[str, Any]:
    types = f.get("types") or {}
    non_null = {t: c for t, c in types.items() if t != "null"}
    total = sum(non_null.values()) or 1
    material = [t for t, c in non_null.items() if c / total >= 0.02]
    json_types = sorted({_SHAPE_TO_JSON.get(t, "string") for t in material})
    if "integer" in json_types and "number" in json_types:
        json_types.remove("integer")
    if types.get("null") or f.get("null_empty_count"):
        json_types.append("null")
    spec: dict[str, Any] = {"type": json_types[0] if len(json_types) == 1 else json_types}

    if len(material) == 1 and material[0] in _FORMAT_FROM_SHAPE and non_null[material[0]] / total >= 0.99:
        spec["format"] = _FORMAT_FROM_SHAPE[material[0]]
    values = f.get("value_counts") or {}
    # Enums only for text categories; numeric measures get minimum/maximum instead.
    if (f.get("low_cardinality") and 0 < len(values) <= max_enum and not f.get("masked")
            and not is_identifier_name(f["path"]) and set(material) <= {"string", "bool"}):
        spec["enum"] = sorted(_typed(v, json_types) for v in values)
    # Observed min/max are not a contract (counters grow, ranges widen): only the
    # sign is inferred. Add real business ranges by hand.
    numeric = f.get("numeric")
    if numeric and not f.get("masked") and numeric["min"] >= 0:
        spec["minimum"] = 0
    cov = field_coverage(f, sampled)
    if cov >= 50:
        spec["x-datalens"] = {"coverage": {"drop_pts": {"warn": round(drop_pts / 2, 1), "fail": drop_pts}}}
    spec["description"] = f"Observed coverage {cov:.1f}%"
    return spec


def _typed(value: str, json_types: list[str]) -> Any:
    if "integer" in json_types:
        try:
            return int(value)
        except ValueError:
            return value
    if "number" in json_types:
        try:
            return float(value)
        except ValueError:
            return value
    if "boolean" in json_types and value in ("True", "False", "true", "false"):
        return value.lower() == "true"
    return value


def _prune(node: dict[str, Any]) -> None:
    if not node.get("required"):
        node.pop("required", None)
    for child in (node.get("properties") or {}).values():
        _prune(child)
        items = child.get("items")
        if isinstance(items, dict):
            _prune(items)
