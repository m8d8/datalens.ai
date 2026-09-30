"""Next steps: specific actions, grouped root causes, one action per problem."""

from __future__ import annotations

from types import SimpleNamespace

from datalens.profiling.next_steps import build_next_steps


def _finding(kind, field, severity="fail", **kw):
    return {"kind": kind, "object": "orders", "field": field, "severity": severity,
            "message": f"{kind} on {field}", "rule": {"threshold": "t", "scope": "builtin"}, **kw}


def _result(**kw):
    base = dict(schema_json={"objects": []}, quality=None, joins=None, drift_report=None, contract=None,
                ai_insights=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_rename_explains_missing_required_field():
    drift = {"reference": {"tag": "d1"}, "findings": [
        _finding("field_renamed", "amount_usd", severity="warn", old="amount", new="amount_usd")]}
    contract = {"objects": [{"object": "orders", "checks": [
        {"field": "amount", "check": "required", "status": "fail", "expected": "present", "observed": "missing",
         "message": "Required field `orders.amount` is missing."}]}]}
    steps = build_next_steps(_result(drift_report=drift, contract=contract), {})
    assert len(steps) == 1
    (step,) = steps
    assert "rename" in step["title"] and step["severity"] == "high"
    assert set(step["sources"]) == {"contract", "drift"}
    assert "Required field" in step["why"]


def test_mixed_types_grouped_by_root_cause():
    fields = [{"path": p, "types": {"int": 50, "string": 50}} for p in ("season", "first_season", "last_season")]
    schema = {"objects": [{"object": "matches", "fields": fields[:1]}, {"object": "players", "fields": fields[1:]}]}
    steps = [s for s in build_next_steps(_result(schema_json=schema), {}) if s["category"] == "Consistency"]
    assert len(steps) == 1 and len(steps[0]["fields"]) == 3


def test_sparse_children_of_optional_parents_are_not_flagged():
    fields = [
        {"path": "extras", "presence_count": 5, "null_empty_count": 0, "types": {"object": 5}},
        {"path": "extras.wides", "presence_count": 4, "null_empty_count": 0, "types": {"int": 4}},
        {"path": "coupon", "presence_count": 10, "null_empty_count": 0, "types": {"string": 10}},
    ]
    schema = {"objects": [{"object": "orders", "sampled": 100, "fields": fields}]}
    steps = [s for s in build_next_steps(_result(schema_json=schema), {}) if s["category"] == "Completeness"]
    flagged = {f for s in steps for f in s["fields"]}
    assert "orders.coupon" in flagged and "orders.extras.wides" not in flagged


def test_priorities_and_ids_are_ordered():
    drift = {"reference": {"tag": "d1"}, "findings": [
        _finding("row_count", "", delta_pct=-60.0), _finding("categories_new", "status", severity="warn", new=["x"])]}
    steps = build_next_steps(_result(drift_report=drift), {})
    assert [s["id"] for s in steps] == ["A01", "A02"]
    assert steps[0]["priority"] > steps[1]["priority"] and "volume" in steps[0]["title"]
