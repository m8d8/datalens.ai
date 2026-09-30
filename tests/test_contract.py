"""BYOS: expected-schema loading, validation, inference and threshold rules."""

from __future__ import annotations

import json
from pathlib import Path

from datalens import analyze
from datalens.config.config import Config
from datalens.contract import infer_schema, load_expected_schemas, validate_contract


def _write(path: Path, data) -> Path:
    path.write_text(json.dumps(data) if not isinstance(data, str) else data)
    return path


def _data(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "orders.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


ROWS = [
    {"id": f"o{i}", "title": "Order" if i % 10 else None, "status": "paid" if i % 3 else "open",
     "qty": i % 5, "country": "IN", "meta": {"channel": "web"}}
    for i in range(200)
]
ROWS[5]["status"] = "lost"
ROWS[6]["qty"] = -1

EXPECTED = {
    "title": "orders",
    "type": "object",
    "required": ["id", "title", "status", "sku"],
    "additionalProperties": False,
    "x-datalens": {"defaults": {"coverage": {"change_pct": 20}}},
    "properties": {
        "id": {"type": "string", "x-datalens": {"coverage": {"drop_pct": 5}}},
        "title": {"type": "string", "x-datalens": {"coverage": {"drop_pct": 10}}},
        "status": {"type": "string", "enum": ["paid", "open"]},
        "qty": {"type": "integer", "minimum": 0},
        "sku": {"type": "string"},
        "meta": {"type": "object", "properties": {"channel": {"type": "string"}}},
    },
}


def _checks(report, status=None):
    return {(c["field"], c["check"]) for o in report["objects"] for c in o["checks"]
            if status is None or c["status"] == status}


def test_validation_reports_each_violation(tmp_path):
    result = analyze({"source": "file", "path": str(_data(tmp_path, ROWS))}, Config(sample_size=0))
    report = validate_contract(result.schema_json, load_expected_schemas([str(_write(tmp_path / "s.json", EXPECTED))]))
    fails = _checks(report, "fail")
    assert ("sku", "required") in fails            # missing required field
    assert ("title", "required") in fails          # 90% < 99% required coverage
    assert ("status", "enum") in fails             # 'lost' not allowed
    assert ("qty", "range") in fails               # -1 < minimum 0
    assert ("id", "type") not in fails
    assert ("country", "unexpected_fields") in _checks(report, "warn")  # additionalProperties false
    assert report["status"] == "fail" and 0 < report["conformance_pct"] < 100


def test_object_mapping_forms(tmp_path):
    schema_file = _write(tmp_path / "s.json", {**EXPECTED, "title": None})
    (one,) = load_expected_schemas([f"orders={schema_file}"])
    assert one.object == "orders"
    multi = _write(tmp_path / "m.json", {"x-datalens": {"objects": True}, "objects": {"a": EXPECTED, "b": EXPECTED}})
    assert [o.object for o in load_expected_schemas([str(multi)])] == ["a", "b"]


def test_x_datalens_thresholds_become_drift_rules(tmp_path):
    (exp,) = load_expected_schemas([str(_write(tmp_path / "s.json", EXPECTED))])
    rules = exp.drift_rules()
    assert rules["coverage"] == {"change_pct": 20}
    assert rules["fields"]["id"] == {"coverage": {"drop_pct": 5}}


def test_contract_thresholds_drive_drift_and_health(tmp_path):
    schema_file = str(_write(tmp_path / "s.json", EXPECTED))
    before = analyze({"source": "file", "path": str(_data(tmp_path, ROWS))}, Config(sample_size=0))
    worse = [dict(r, title=None) if i % 4 == 0 else r for i, r in enumerate(ROWS)]
    (tmp_path / "v2").mkdir()
    after = analyze({"source": "file", "path": str(_data(tmp_path / "v2", worse))},
                    Config(sample_size=0, expected_schemas=[schema_file]),
                    previous_schema=before.schema_json, reference_tag="v1")
    title = next(f for f in after.drift_report["findings"] if f.get("field") == "title" and f["kind"] == "coverage")
    assert title["rule"]["scope"] == "field" and title["severity"] == "fail"  # 90% → ~67%: > 10% drop
    assert any("Expected schema" in d for d in after.decision["health_verdict"]["drivers"])


def test_infer_then_validate_round_trip(tmp_path):
    result = analyze({"source": "file", "path": str(_data(tmp_path, ROWS))}, Config(sample_size=0))
    inferred = infer_schema(result.schema_json)
    orders = inferred["objects"]["orders"]
    assert "id" in orders["required"] and "title" not in orders["required"]
    assert set(orders["properties"]["status"]["enum"]) == {"paid", "open", "lost"}
    assert orders["properties"]["qty"].get("minimum") is None  # -1 seen → no sign constraint
    assert orders["properties"]["meta"]["properties"]["channel"]["type"] == "string"
    path = _write(tmp_path / "inferred.json", inferred)
    report = validate_contract(result.schema_json, load_expected_schemas([str(path)]))
    assert report["status"] in ("pass", "info")
