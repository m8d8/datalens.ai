"""Drift rules, rolling baseline, PSI math and the drift engine."""

from __future__ import annotations

import random

import pytest

from datalens.drift import DriftRules, build_drift_report, extract_metrics
from datalens.drift.baseline import learn_band, score_against_band
from datalens.drift.metrics import categorical_psi, metric_key, numeric_psi, psi_noise
from datalens.drift.rules import evaluate_change
from datalens.profiling.sampler import numeric_profile


def _schema(rows: int, *, coverage: float = 1.0, status_counts=None, extra_fields=(), sampled=None):
    sampled = sampled or rows
    present = int(sampled * coverage)
    status_counts = status_counts or {"paid": int(sampled * 0.7), "open": sampled - int(sampled * 0.7)}
    fields = [
        {"path": "order_id", "presence_count": sampled, "null_empty_count": 0, "types": {"string": sampled},
         "distinct_count_in_sample": sampled, "low_cardinality": False},
        {"path": "email", "presence_count": sampled, "null_empty_count": sampled - present,
         "types": {"string": present, "null": sampled - present}, "distinct_count_in_sample": present,
         "low_cardinality": False},
        {"path": "status", "presence_count": sampled, "null_empty_count": 0, "types": {"string": sampled},
         "distinct_count_in_sample": len(status_counts), "low_cardinality": True, "value_counts": status_counts},
    ]
    for path in extra_fields:
        fields.append({"path": path, "presence_count": sampled, "null_empty_count": 0,
                       "types": {"int": sampled}, "distinct_count_in_sample": 5, "low_cardinality": True,
                       "value_counts": {"1": sampled}})
    return {"objects": [{"object": "orders", "sampled": sampled, "total_rows": rows, "fields": fields}]}


def _report(ref, cur, **kw):
    rules = kw.pop("rules", DriftRules())
    return build_drift_report(cur, extract_metrics(cur), rules=rules, reference_schema=ref,
                              reference_metrics=extract_metrics(ref), **kw)


def _kinds(report, severity=None):
    return {(f["kind"], f.get("field", "")) for f in report["findings"]
            if severity is None or f["severity"] == severity}


# ── rules ───────────────────────────────────────────────────────────────────

def test_drop_and_increase_use_different_thresholds():
    rule = {"drop_pct": {"warn": 10, "fail": 25}, "increase_pct": {"warn": 50}}
    assert evaluate_change(rule, 100, 80, "builtin").severity == "warn"
    assert evaluate_change(rule, 100, 70, "builtin").severity == "fail"
    assert evaluate_change(rule, 100, 130, "builtin").severity == "ok"
    assert evaluate_change(rule, 100, 160, "builtin").severity == "warn"


def test_pct_is_relative_and_pts_is_absolute():
    assert evaluate_change({"drop_pct": 5}, 80, 76, "x").severity == "fail"   # -5% relative
    assert evaluate_change({"drop_pts": 5}, 80, 76, "x").severity == "ok"     # -4 pts
    assert evaluate_change({"change_pct": 20}, 50, 61, "x").severity == "fail"  # either way


def test_rule_resolution_field_over_object_over_default_with_wildcards():
    rules = DriftRules({
        "defaults": {"coverage": {"drop_pct": 40}},
        "objects": {"ord*": {"coverage": {"drop_pct": 20}, "fields": {"id": {"coverage": {"drop_pct": 5}}}}},
    })
    assert rules.resolve("coverage", "orders", "id") == ({"drop_pct": 5}, "field")
    assert rules.resolve("coverage", "orders", "title") == ({"drop_pct": 20}, "object")
    assert rules.resolve("coverage", "users", "x")[1] == "dataset"
    assert rules.resolve("row_count", "users")[1] == "builtin"


def test_custom_message_template():
    rules = DriftRules({"objects": {"orders": {"row_count": {
        "drop_pct": 10, "drop_message": "{object} feed truncated: {old} → {new} ({delta_pct})"}}}})
    report = _report(_schema(1000), _schema(500), rules=rules)
    msg = next(f["message"] for f in report["findings"] if f["kind"] == "row_count")
    assert msg == "orders feed truncated: 1,000 → 500 (-50.0%)"


# ── baseline ────────────────────────────────────────────────────────────────

def test_band_is_robust_to_one_outlier():
    band = learn_band([100, 102, 98, 101, 99, 100, 5000], k=3, rel_floor=0.0)
    assert band.median == 100
    assert score_against_band(100, band)[0] == "ok"


def test_band_learns_recurring_values_as_normal():
    band = learn_band([250, 252, 500, 249, 251, 496, 248], k=3, rel_floor=0.05)
    assert score_against_band(503, band)[0] == "ok"
    assert score_against_band(29, band)[0] == "fail"


# ── PSI ─────────────────────────────────────────────────────────────────────

def test_categorical_psi_and_new_vanished():
    score, new, gone = categorical_psi({"a": 50, "b": 50}, {"a": 50, "b": 40, "c": 10})
    assert new == ["c"] and gone == []
    assert score > 0.1
    assert categorical_psi({"a": 5, "b": 5}, {"a": 5, "b": 5})[0] == 0


def test_numeric_psi_detects_shift_but_not_resampling():
    rng = random.Random(1)
    base = numeric_profile([rng.gauss(100, 15) for _ in range(20000)], 20000)["quantiles"]
    same = numeric_profile([rng.gauss(100, 15) for _ in range(20000)], 20000)["quantiles"]
    moved = numeric_profile([rng.gauss(120, 15) for _ in range(20000)], 20000)["quantiles"]
    assert numeric_psi(base, same) < 0.1
    assert numeric_psi(base, moved) > 0.25


def test_numeric_psi_on_discrete_values_with_repeated_minimum():
    q = {f"p{p}": v for p, v in zip(range(0, 101, 5), [1, 1, 2, 2, 3, 5, 6, 8, 10, 11, 13, 17, 22, 26,
                                                        34, 43, 52, 70, 91, 116, 152])}
    assert numeric_psi(q, q) == 0
    assert numeric_psi(q, {**q, "p100": 153}) < 0.05


def test_psi_noise_floor_scales_with_sample_size():
    assert psi_noise(10, 250, 250) > psi_noise(10, 25000, 25000) * 50


# ── engine ──────────────────────────────────────────────────────────────────

def test_engine_reports_volume_coverage_categories_and_schema():
    ref = _schema(10_000)
    cur = _schema(6_000, coverage=0.6, status_counts={"paid": 3000, "open": 2000, "refunded": 1000},
                  extra_fields=("discount",))
    report = _report(ref, cur)
    fails = _kinds(report, "fail")
    assert ("row_count", "") in fails
    assert ("coverage", "email") in fails
    assert ("categories_new", "status") in _kinds(report)
    assert ("field_added", "discount") in _kinds(report, "info")
    assert report["status"] == "fail"
    assert all(f["rule"]["threshold"] or f["kind"] in ("field_added",) for f in report["findings"])


def test_engine_detects_rename():
    ref = _schema(1000, extra_fields=("amount",))
    cur = _schema(1000, extra_fields=("amount_usd",))
    renames = [f for f in _report(ref, cur)["findings"] if f["kind"] == "field_renamed"]
    assert renames and renames[0]["old"] == "amount" and renames[0]["new"] == "amount_usd"


def test_small_objects_are_not_judged_on_coverage():
    report = _report(_schema(3), _schema(3, coverage=0.34))
    assert ("coverage", "email") not in _kinds(report)
    assert report["notes"]


def test_coverage_change_within_sampling_noise_is_ignored():
    # 250 rows: 90% → 86% is < 3 standard errors
    report = _report(_schema(250, coverage=0.90), _schema(250, coverage=0.86),
                     rules=DriftRules({"defaults": {"coverage": {"drop_pts": 2}}}))
    assert ("coverage", "email") not in _kinds(report)


def test_rolling_mode_learns_and_flags_only_the_outlier():
    history = []
    for rows in (250, 500, 248, 251, 497, 252, 249):  # newest last
        history.insert(0, {"tag": str(rows), "metrics": extract_metrics(_schema(rows)), "breached": []})
    normal = build_drift_report(_schema(502), extract_metrics(_schema(502)), rules=DriftRules(),
                                mode="rolling", reference_schema=_schema(249), history=history)
    assert normal["status"] == "ok"
    broken = build_drift_report(_schema(40), extract_metrics(_schema(40)), rules=DriftRules(),
                                mode="rolling", reference_schema=_schema(249), history=history)
    row = next(f for f in broken["findings"] if f["kind"] == "row_count")
    assert row["severity"] == "fail" and row["rule"]["source"] == "rolling"
    assert row["band"]["n"] == 7


def test_rolling_cold_start_falls_back_to_rules():
    history = [{"tag": "a", "metrics": extract_metrics(_schema(1000)), "breached": []}]
    report = build_drift_report(_schema(500), extract_metrics(_schema(500)), rules=DriftRules(),
                                mode="rolling", reference_schema=_schema(1000), reference_metrics=history[0]["metrics"],
                                history=history)
    row = next(f for f in report["findings"] if f["kind"] == "row_count")
    assert row["rule"]["source"] == "rule"
    assert report["reference"]["rolling"]["metrics_cold_start"] > 0


def test_breached_runs_are_excluded_from_the_baseline():
    key = metric_key("row_count", "orders")
    history = [{"tag": "bad", "metrics": extract_metrics(_schema(10)), "breached": [key]}]
    for i in range(5):
        history.append({"tag": f"ok{i}", "metrics": extract_metrics(_schema(1000)), "breached": []})
    report = build_drift_report(_schema(12), extract_metrics(_schema(12)), rules=DriftRules(),
                                mode="rolling", reference_schema=_schema(10), history=history)
    row = next(f for f in report["findings"] if f["kind"] == "row_count")
    assert row["band"]["n"] == 5 and row["severity"] == "fail"


@pytest.mark.parametrize("mode", ["previous", "baseline:day1"])
def test_no_reference_means_no_report(mode):
    assert build_drift_report(_schema(1), {}, rules=DriftRules(), mode=mode) is None


def test_coverage_defaults_are_relative_25_drop_and_50_increase():
    assert evaluate_change(DriftRules().resolve("coverage")[0], 100, 70, "builtin").severity == "fail"   # -30%
    assert evaluate_change(DriftRules().resolve("coverage")[0], 94.3, 71.8, "builtin").severity == "ok"  # -23.9%
    assert evaluate_change(DriftRules().resolve("coverage")[0], 40, 63.2, "builtin").severity == "fail"  # +58%
    assert evaluate_change(DriftRules().resolve("coverage")[0], 50, 56, "builtin").severity == "ok"      # +12%


def test_coverage_shifts_and_rules_in_effect():
    def schema(cov_a, cov_b):
        fields = []
        for path, cov in (("a", cov_a), ("b", cov_b)):
            fields.append({"path": path, "presence_count": int(5000 * cov), "null_empty_count": 0,
                           "types": {"string": int(5000 * cov)}, "distinct_count_in_sample": 10})
        return {"objects": [{"object": "t", "sampled": 5000, "total_rows": 5000, "fields": fields}]}

    rules = DriftRules({"objects": {"t": {"fields": {"b": {"coverage": {"increase_pct": 5}}}}}})
    ref, cur = schema(0.40, 0.50), schema(0.632, 0.56)
    report = build_drift_report(cur, extract_metrics(cur), rules=rules, reference_schema=ref,
                                reference_metrics=extract_metrics(ref))
    shifts = {c["field"]: c for c in report["coverage_changes"]}
    assert shifts["a"]["severity"] == "fail" and shifts["a"]["scope"] == "builtin" and "increase ≥ 50%" in shifts["a"]["rule"]
    assert shifts["b"]["severity"] == "fail" and shifts["b"]["scope"] == "field"      # +12% vs field rule 5%
    fired = {(r["metric"], r["scope"]): r["fired"] for r in report["rules_in_effect"]}
    assert fired[("coverage", "builtin")] == 1 and fired[("coverage", "field")] == 1
    assert fired[("dqi", "builtin")] == 0
