"""Coverage-drift breach thresholds — dataset/object/field precedence, report flags,
and machine-readable JSON artifacts."""

from __future__ import annotations

from datalens.history.diff import (
    DEFAULT_COVERAGE_BREACH_THRESHOLD,
    compare_schemas,
    resolve_coverage_threshold,
)


def _schema(obj_name: str, path: str, presence_count: int, sampled: int = 100) -> dict:
    return {
        "objects": [{
            "object": obj_name,
            "sampled": sampled,
            "fields": [{
                "path": path,
                "presence_count": presence_count,
                "null_empty_count": 0,
                "types": {"string": presence_count},
            }],
        }]
    }


class TestResolveCoverageThreshold:
    def test_field_level_wins(self):
        thresholds = {
            "dataset": 50.0,
            "objects": {"Orders": 40.0},
            "fields": {"Orders": {"customer.email": 20.0}},
        }
        pct, scope = resolve_coverage_threshold(thresholds, "Orders", "customer.email")
        assert pct == 20.0
        assert scope == "field"

    def test_object_level_when_no_field_override(self):
        thresholds = {"dataset": 50.0, "objects": {"Orders": 40.0}}
        pct, scope = resolve_coverage_threshold(thresholds, "Orders", "customer.email")
        assert pct == 40.0
        assert scope == "object"

    def test_dataset_level_when_no_object_override(self):
        thresholds = {"dataset": 50.0}
        pct, scope = resolve_coverage_threshold(thresholds, "Orders", "customer.email")
        assert pct == 50.0
        assert scope == "dataset"

    def test_falls_back_to_default(self):
        pct, scope = resolve_coverage_threshold({}, "Orders", "customer.email")
        assert pct == DEFAULT_COVERAGE_BREACH_THRESHOLD
        assert scope == "default"


class TestBreachDetectionDisabledByDefault:
    def test_no_thresholds_means_no_breach_flag(self):
        old = _schema("Orders", "customer.email", presence_count=90)
        new = _schema("Orders", "customer.email", presence_count=10)
        diff = compare_schemas(old, new)
        assert len(diff.coverage_changes) == 1
        assert diff.coverage_changes[0]["breach"] is False
        assert diff.coverage_breaches == []


class TestBreachDetectionEnabled:
    def test_reduction_breach_flagged(self):
        old = _schema("Orders", "customer.email", presence_count=90)
        new = _schema("Orders", "customer.email", presence_count=10)  # -80 pts
        diff = compare_schemas(old, new, coverage_thresholds={"dataset": 50.0})
        assert len(diff.coverage_breaches) == 1
        breach = diff.coverage_breaches[0]
        assert breach["direction"] == "decrease"
        assert breach["threshold"] == 50.0
        assert breach["threshold_scope"] == "dataset"

    def test_increase_breach_flagged(self):
        old = _schema("Orders", "customer.email", presence_count=10)
        new = _schema("Orders", "customer.email", presence_count=90)  # +80 pts
        diff = compare_schemas(old, new, coverage_thresholds={"dataset": 50.0})
        assert len(diff.coverage_breaches) == 1
        assert diff.coverage_breaches[0]["direction"] == "increase"

    def test_below_threshold_is_not_a_breach(self):
        old = _schema("Orders", "customer.email", presence_count=90)
        new = _schema("Orders", "customer.email", presence_count=80)  # -10 pts
        diff = compare_schemas(old, new, coverage_thresholds={"dataset": 50.0})
        assert diff.coverage_breaches == []
        # Still reported as a normal coverage change (default floor is 10 pts).
        assert len(diff.coverage_changes) == 1
        assert diff.coverage_changes[0]["breach"] is False

    def test_field_level_threshold_overrides_dataset(self):
        old = _schema("Orders", "customer.email", presence_count=90)
        new = _schema("Orders", "customer.email", presence_count=80)  # -10 pts
        diff = compare_schemas(
            old,
            new,
            coverage_thresholds={
                "dataset": 50.0,
                "fields": {"Orders": {"customer.email": 5.0}},
            },
        )
        assert len(diff.coverage_breaches) == 1
        assert diff.coverage_breaches[0]["threshold_scope"] == "field"

    def test_report_reduction_exceeds_false_suppresses_reduction_breach(self):
        old = _schema("Orders", "customer.email", presence_count=90)
        new = _schema("Orders", "customer.email", presence_count=10)
        diff = compare_schemas(
            old, new, coverage_thresholds={"dataset": 50.0}, report_reduction_exceeds=False
        )
        assert diff.coverage_breaches == []

    def test_report_increase_exceeds_false_suppresses_increase_breach(self):
        old = _schema("Orders", "customer.email", presence_count=10)
        new = _schema("Orders", "customer.email", presence_count=90)
        diff = compare_schemas(
            old, new, coverage_thresholds={"dataset": 50.0}, report_increase_exceeds=False
        )
        assert diff.coverage_breaches == []

    def test_breach_forces_inclusion_even_below_reporting_floor(self):
        # Field-level threshold of 5 pts is below the generic 10-pt reporting floor,
        # so this change would otherwise be invisible — but a breach must still surface.
        old = _schema("Orders", "customer.email", presence_count=90)
        new = _schema("Orders", "customer.email", presence_count=83)  # -7 pts
        diff = compare_schemas(
            old,
            new,
            coverage_thresholds={"fields": {"Orders": {"customer.email": 5.0}}},
        )
        assert len(diff.coverage_changes) == 1
        assert diff.coverage_changes[0]["breach"] is True


class TestJSONArtifacts:
    def test_schema_drift_json_shape(self):
        old = {"objects": [{"object": "A", "sampled": 10, "fields": []}]}
        new = {"objects": [{"object": "A", "sampled": 10, "fields": []}, {"object": "B", "sampled": 5, "fields": []}]}
        diff = compare_schemas(old, new)
        artifact = diff.to_schema_drift_json()
        assert artifact["added_objects"] == ["B"]
        assert artifact["has_drift"] is True
        assert "coverage_changes" not in artifact

    def test_coverage_drift_json_summary(self):
        old = _schema("Orders", "customer.email", presence_count=90)
        new = _schema("Orders", "customer.email", presence_count=10)
        diff = compare_schemas(old, new, coverage_thresholds={"dataset": 50.0})
        artifact = diff.to_coverage_drift_json()
        assert artifact["summary"]["any_breach"] is True
        assert artifact["summary"]["reduction_breaches"] == 1
        assert artifact["summary"]["increase_breaches"] == 0
        assert len(artifact["breaches"]) == 1
