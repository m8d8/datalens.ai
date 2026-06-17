"""Tests for the v2 Decision Layer (profiling/decision.py)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from datalens.profiling import decision
from datalens.history.diff import SchemaDiff


# ─── Fixtures / helpers ──────────────────────────────────────────────────────

def _schema(n_fields: int = 4, multi_type: int = 0, sampled: int = 100) -> dict[str, Any]:
    fields = []
    for i in range(n_fields):
        types = {"string": sampled}
        if i < multi_type:
            types = {"string": sampled - 5, "int": 5}
        fields.append({
            "path": f"f{i}",
            "presence_count": sampled,
            "null_empty_count": 0,
            "types": types,
        })
    return {"objects": [{"object": "users", "sampled": sampled, "fields": fields}]}


def _quality(overall: float = 90.0, completeness: float = 95.0, consistency: float = 100.0,
             problem_fields: int = 0) -> dict[str, Any]:
    return {
        "overall_dqi": overall,
        "schema_dimensions": {},
        "objects": [{
            "object": "users",
            "dqi": overall,
            "dimensions": {
                "completeness": {"score": completeness, "weight": 0.3, "details": {}},
                "consistency": {"score": consistency, "weight": 0.25, "details": {}},
            },
            "problem_fields": [{"path": f"f{i}", "score": 40, "issues": []}
                               for i in range(problem_fields)],
        }],
    }


def _pii(by_type: dict[str, int] | None = None, high_risk: list[dict] | None = None) -> dict[str, Any]:
    by_type = by_type or {}
    high_risk = high_risk or []
    return {
        "total_pii_fields": sum(by_type.values()),
        "by_type": by_type,
        "high_risk_fields": high_risk,
    }


@dataclass
class _FakeResult:
    schema_json: dict[str, Any]
    quality: dict[str, Any] | None = None
    pii_summary: dict[str, Any] | None = None
    joins: dict[str, Any] | None = None
    insights: dict[str, Any] | None = None
    statistics: dict[str, Any] | None = field(default=None)


# ─── drift_severity ──────────────────────────────────────────────────────────

def test_drift_severity_none_when_no_diff():
    assert decision.drift_severity(None) == "none"
    assert decision.drift_severity(SchemaDiff()) == "none"


def test_drift_severity_high_on_removed_field():
    diff = SchemaDiff(removed_fields={"users": ["email"]})
    assert decision.drift_severity(diff) == "high"


def test_drift_severity_high_on_type_change():
    diff = SchemaDiff(type_changes=[{"object": "users", "field": "age",
                                     "old_types": ["int"], "new_types": ["string"]}])
    assert decision.drift_severity(diff) == "high"


def test_drift_severity_high_on_large_coverage_drop():
    diff = SchemaDiff(coverage_changes=[
        {"object": "users", "field": "email", "old_coverage": 98.0, "new_coverage": 60.0},
    ])
    assert decision.drift_severity(diff) == "high"


def test_drift_severity_medium_on_notable_shift():
    diff = SchemaDiff(coverage_changes=[
        {"object": "users", "field": "email", "old_coverage": 90.0, "new_coverage": 78.0},
    ])
    assert decision.drift_severity(diff) == "medium"


def test_drift_severity_low_on_additions_only():
    diff = SchemaDiff(added_fields={"users": ["nickname"]})
    assert decision.drift_severity(diff) == "low"


# ─── health_verdict ──────────────────────────────────────────────────────────

def test_health_verdict_healthy():
    v = decision.health_verdict(_schema(), _quality(overall=95.0), _pii())
    assert v["status"] == "healthy"
    assert v["score"] >= decision.HEALTH_HEALTHY_MIN
    assert v["drivers"]


def test_health_verdict_risk_on_low_dqi():
    v = decision.health_verdict(_schema(), _quality(overall=40.0), _pii())
    assert v["status"] == "risk"


def test_health_verdict_capped_to_attention_on_breaking_drift():
    diff = SchemaDiff(removed_fields={"users": ["email"]})
    v = decision.health_verdict(_schema(), _quality(overall=99.0), _pii(), diff)
    # high DQI but breaking change → must not be 'healthy'
    assert v["status"] == "attention"


def test_health_verdict_pii_and_type_penalty_lowers_score():
    clean = decision.health_verdict(_schema(), _quality(overall=90.0), _pii())["score"]
    risky = decision.health_verdict(
        _schema(multi_type=4),
        _quality(overall=90.0),
        _pii(by_type={"ssn": 2}, high_risk=[{"object": "users", "field": "ssn", "type": "ssn",
                                             "confidence": 0.9}] * 2),
    )["score"]
    assert risky < clean


# ─── compliance_scorecard (ratio-based) ──────────────────────────────────────

def test_compliance_none_when_no_pii():
    sc = decision.compliance_scorecard(_pii(), total_fields=20)
    assert sc["risk"] == "none"
    assert sc["exposure_score"] == 0.0
    assert all(c["status"] == "pass" for c in sc["checklist"])


def test_compliance_is_ratio_based_not_count_based():
    # Same 2 sensitive fields, but very different denominators → different exposure.
    pii = _pii(by_type={"email": 2})
    small = decision.compliance_scorecard(pii, total_fields=4)["exposure_score"]
    large = decision.compliance_scorecard(pii, total_fields=200)["exposure_score"]
    assert small > large  # the small dataset is proportionally far more exposed


def test_compliance_high_sensitivity_must_mask():
    sc = decision.compliance_scorecard(
        _pii(by_type={"ssn": 1},
             high_risk=[{"object": "users", "field": "ssn", "type": "ssn", "confidence": 0.95}]),
        total_fields=5,
    )
    assert sc["must_mask"]
    assert sc["checklist"][0]["status"] == "fail"


def test_compliance_pii_field_ratio_capped():
    sc = decision.compliance_scorecard(_pii(by_type={"email": 50}), total_fields=10)
    assert sc["pii_field_ratio"] <= 1.0


# ─── fitness_for_use ─────────────────────────────────────────────────────────

def test_fitness_ready_for_reporting_and_ml():
    obj = _quality(overall=92.0, completeness=95.0, consistency=98.0)["objects"][0]
    badges = decision.fitness_for_use(obj, _pii())
    labels = [b["label"] for b in badges]
    assert "Ready for reporting" in labels
    assert "Ready for ML/AI" in labels


def test_fitness_ml_blocked_by_pii():
    obj = _quality(overall=92.0, completeness=95.0, consistency=98.0)["objects"][0]
    pii = _pii(high_risk=[{"object": "users", "field": "ssn", "type": "ssn", "confidence": 0.9}])
    badges = decision.fitness_for_use(obj, pii)
    labels = [b["label"] for b in badges]
    assert "ML/AI: mask PII first" in labels
    assert "Ready for ML/AI" not in labels


def test_fitness_needs_cleanup():
    obj = _quality(overall=55.0, completeness=40.0, consistency=70.0, problem_fields=6)["objects"][0]
    badges = decision.fitness_for_use(obj, _pii())
    assert any(b["label"] == "Needs cleanup" for b in badges)


# ─── business_impact / action_plan ───────────────────────────────────────────

def test_business_impact_high_severity_bumps_effort():
    bi = decision.business_impact({"category": "Identifiability", "severity": "high"})
    assert bi["effort"] == "medium"  # bumped from 'low'


def test_action_plan_sorted_by_severity_then_effort():
    insights = {"recommendations": [
        {"category": "Identifiability", "severity": "low", "action": "a"},
        {"category": "Consistency", "severity": "high", "action": "b"},
        {"category": "Completeness", "severity": "medium", "action": "c"},
    ]}
    plan = decision.action_plan(insights)
    assert plan[0]["severity"] == "high"
    assert plan[-1]["severity"] == "low"
    assert all("impact_text" in p and "effort" in p for p in plan)


# ─── functional_dependencies ─────────────────────────────────────────────────

def test_functional_dependencies_detects_co_null():
    schema = {"objects": [{
        "object": "users", "sampled": 100,
        "fields": [
            {"path": "addr.street", "presence_count": 30, "null_empty_count": 0, "types": {"string": 30}},
            {"path": "addr.city", "presence_count": 30, "null_empty_count": 0, "types": {"string": 30}},
            {"path": "id", "presence_count": 100, "null_empty_count": 0, "types": {"string": 100}},
        ],
    }]}
    hints = decision.functional_dependencies({}, schema)
    co_null = [h for h in hints if h["kind"] == "co_null"]
    assert co_null
    assert set(co_null[0]["fields"]) == {"users.addr.street", "users.addr.city"}


def test_functional_dependencies_reuses_joins():
    joins = {
        "intra_duplicates": [{"object": "users", "field_a": "name", "field_b": "fullName",
                              "kind": "value_duplicate", "confidence": 0.9, "evidence": []}],
        "value_overlap": [{"left": "orders.user_id", "right": "users.id",
                           "confidence": 0.8, "evidence": []}],
    }
    hints = decision.functional_dependencies(joins, _schema())
    kinds = {h["kind"] for h in hints}
    assert "value_duplicate" in kinds
    assert "value_overlap" in kinds


# ─── build_decision_layer (orchestrator) ─────────────────────────────────────

def test_build_decision_layer_shape():
    result = _FakeResult(
        schema_json=_schema(),
        quality=_quality(),
        pii_summary=_pii(by_type={"email": 1},
                         high_risk=[{"object": "users", "field": "f0", "type": "email",
                                     "confidence": 0.9}]),
        joins={},
        insights={"recommendations": [{"category": "Completeness", "severity": "medium",
                                       "action": "x"}]},
    )
    layer = decision.build_decision_layer(result, None)
    assert set(layer) == {
        "drift_severity", "health_verdict", "compliance_scorecard",
        "fitness_for_use", "action_plan", "top_actions", "functional_dependencies",
    }
    assert "users" in layer["fitness_for_use"]
    assert len(layer["top_actions"]) <= 3


def test_build_decision_layer_handles_missing_analytics():
    # Everything None except schema — must not raise.
    layer = decision.build_decision_layer(_FakeResult(schema_json=_schema()), None)
    assert layer["health_verdict"]["status"] in {"healthy", "attention", "risk"}
    assert layer["compliance_scorecard"]["risk"] == "none"
