"""Load expected JSON Schemas and flatten them to Datalens field paths."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# JSON Schema type → Datalens observed value shapes that satisfy it.
TYPE_MAP: dict[str, set[str]] = {
    "string": {"string", "email", "url", "uri", "uuid", "date", "phone", "numeric_id"},
    "integer": {"int"},
    "number": {"int", "float"},
    "boolean": {"bool"},
    "object": {"object"},
    "array": {"array"},
    "null": {"null"},
}

# format → the Datalens shape the values should have
FORMAT_MAP: dict[str, str] = {
    "date": "date", "date-time": "date", "email": "email", "uri": "url", "url": "url", "uuid": "uuid",
}


@dataclass
class ExpectedField:
    path: str
    types: list[str]                      # JSON Schema types (["string","null"] …)
    required: bool = False
    enum: list[Any] | None = None
    minimum: float | None = None
    maximum: float | None = None
    exclusive_minimum: float | None = None
    exclusive_maximum: float | None = None
    pattern: str | None = None
    format: str | None = None
    min_coverage: float = 99.0
    rules: dict[str, Any] = field(default_factory=dict)   # x-datalens drift rules for this field

    @property
    def nullable(self) -> bool:
        return "null" in self.types

    def allowed_shapes(self) -> set[str]:
        shapes: set[str] = set()
        for t in self.types or []:
            shapes |= TYPE_MAP.get(t, set())
        return shapes


@dataclass
class ExpectedObject:
    object: str | None                    # None = applies to every object
    source: str
    fields: dict[str, ExpectedField]
    closed: bool = False                  # additionalProperties: false at the top level
    defaults: dict[str, Any] = field(default_factory=dict)  # x-datalens.defaults

    def drift_rules(self) -> dict[str, Any]:
        """x-datalens thresholds as a drift-rules object entry: {metric…, fields: {path: {metric…}}}."""
        entry: dict[str, Any] = dict(self.defaults)
        field_rules = {p: f.rules for p, f in self.fields.items() if f.rules}
        if field_rules:
            entry["fields"] = field_rules
        return entry


def load_expected_schemas(specs: list[str] | tuple[str, ...]) -> list[ExpectedObject]:
    """
    Load ``--schema`` specs: "path.json" or "OBJECT=path.json" (YAML works too).
    """
    out: list[ExpectedObject] = []
    for spec in specs:
        obj_name, sep, path = spec.partition("=")
        if not sep or not path or Path(spec).exists():
            obj_name, path = "", spec
        data = _read(Path(path))
        multi = data.get("objects") or (data.get("$defs") if data.get("x-datalens", {}).get("objects") else None)
        if isinstance(multi, dict) and not obj_name:
            for name, schema in multi.items():
                out.append(_expected(schema, name, f"{path}#{name}"))
            continue
        target = obj_name or data.get("x-datalens", {}).get("object") or data.get("title") or None
        out.append(_expected(data, target, path))
    return out


def _read(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml

        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Expected schema {path} must be a JSON object")
    return data


def _expected(schema: dict[str, Any], obj_name: str | None, source: str) -> ExpectedObject:
    fields: dict[str, ExpectedField] = {}
    _walk(schema, "", True, fields)
    xd = schema.get("x-datalens") or {}
    return ExpectedObject(
        object=obj_name,
        source=source,
        fields=fields,
        closed=schema.get("additionalProperties") is False,
        defaults=dict(xd.get("defaults") or {}),
    )


def _types(node: dict[str, Any]) -> list[str]:
    t = node.get("type")
    if isinstance(t, list):
        return [str(x) for x in t]
    if isinstance(t, str):
        return [t]
    if "properties" in node:
        return ["object"]
    if "items" in node:
        return ["array"]
    if "enum" in node or "const" in node:
        values = node.get("enum") or [node.get("const")]
        kinds = {"string" if isinstance(v, str) else "boolean" if isinstance(v, bool)
                 else "integer" if isinstance(v, int) else "number" if isinstance(v, float)
                 else "null" if v is None else "object" for v in values}
        return sorted(kinds)
    return []


def _walk(node: dict[str, Any], prefix: str, parent_required: bool, out: dict[str, ExpectedField]) -> None:
    required = set(node.get("required") or [])
    for name, child in (node.get("properties") or {}).items():
        if not isinstance(child, dict):
            continue
        path = f"{prefix}.{name}" if prefix else name
        _add(path, child, parent_required and name in required, out)
        _descend(path, child, parent_required and name in required, out)


def _descend(path: str, node: dict[str, Any], required: bool, out: dict[str, ExpectedField]) -> None:
    if "properties" in node:
        _walk(node, path, required, out)
    items = node.get("items")
    if isinstance(items, dict):
        arr = f"{path}[]"
        if items.get("properties"):
            _walk(items, arr, False, out)
        elif items:
            _add(arr, items, False, out)


def _add(path: str, node: dict[str, Any], required: bool, out: dict[str, ExpectedField]) -> None:
    xd = node.get("x-datalens") or {}
    rules = {k: v for k, v in xd.items() if k not in ("min_coverage",)}
    enum = node.get("enum")
    if enum is None and "const" in node:
        enum = [node["const"]]
    out[path] = ExpectedField(
        path=path,
        types=_types(node),
        required=required,
        enum=list(enum) if enum is not None else None,
        minimum=node.get("minimum"),
        maximum=node.get("maximum"),
        exclusive_minimum=node.get("exclusiveMinimum"),
        exclusive_maximum=node.get("exclusiveMaximum"),
        pattern=node.get("pattern"),
        format=node.get("format"),
        min_coverage=float(xd.get("min_coverage", 99.0)),
        rules=rules,
    )
