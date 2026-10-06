"""Regression tests for the trust fixes found by the Phase 0 cricket baseline."""

from __future__ import annotations

import json
from pathlib import Path

from datalens import analyze
from datalens.ai.context import build_analysis_context, summarize_analytics_for_prompt
from datalens.config.config import Config
from datalens.profiling.decision import compliance_scorecard
from datalens.profiling.pii import PIIType, detect_pii_in_field


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def _dataset(tmp_path: Path) -> Path:
    """Two related entities: 300 players (with emails) and 3000 events referencing them."""
    data = tmp_path / "data"
    data.mkdir()
    players = [
        {"player_id": f"p{i:04d}", "name": f"Player {i}", "contact_email": f"player{i}@example.com"}
        for i in range(300)
    ]
    events = [
        {
            "event_id": f"e{i:05d}",
            "batter_id": f"p{i % 300:04d}",
            "non_striker_id": f"p{(i + 7) % 300:04d}",
            # last 60 events reference players that don't exist (orphans), and
            # sit at the END of the file so head sampling would never see them
            "bowler_id": f"p{(i * 3) % 300:04d}" if i < 2940 else f"zz{i}",
            "runs": i % 7,
        }
        for i in range(3000)
    ]
    _write_jsonl(data / "players.jsonl", players)
    _write_jsonl(data / "events.jsonl", events)
    return data


def _run(data: Path, **overrides) -> "object":
    config = Config(**overrides)
    return analyze({"source": "file", "path": str(data)}, config)


def _obj(result, name):
    return next(o for o in result.schema_json["objects"] if o["object"] == name)


def _field(obj, path):
    return next(f for f in obj["fields"] if f["path"] == path)


def test_distinct_count_is_exact_beyond_display_cap(tmp_path):
    result = _run(_dataset(tmp_path), sample_size=0, max_distinct_values=100)
    events = _obj(result, "events")
    event_id = _field(events, "event_id")
    assert event_id["distinct_count_in_sample"] == 3000
    assert event_id["distinct_is_exact"] is True
    assert len(event_id["value_counts"]) <= 100  # display data stays capped


def test_primary_keys_found_on_large_objects(tmp_path):
    result = _run(_dataset(tmp_path), sample_size=0)
    pks = {pk["object"]: pk["fields"] for pk in result.joins["primary_keys"]}
    assert pks["events"] == ["event_id"]
    assert pks["players"] == ["player_id"]


def test_reservoir_sampling_sees_whole_file_and_counts_rows(tmp_path):
    result = _run(_dataset(tmp_path), sample_size=500)
    events = _obj(result, "events")
    assert events["sampled"] == 500
    assert events["total_rows"] == 3000
    assert result.schema_json["config"]["sample_strategy"] == "reservoir"
    # an orphan appended at the end of the file is reachable by the sample
    links = {x["child"]: x for x in result.joins["referential_integrity"]}
    assert "events.bowler_id" in links


def test_head_sampling_still_available(tmp_path):
    result = _run(_dataset(tmp_path), sample_size=500, sample_strategy="head")
    assert "total_rows" not in _obj(result, "events")


def test_referential_integrity_reports_orphans(tmp_path):
    result = _run(_dataset(tmp_path), sample_size=0)
    links = {x["child"]: x for x in result.joins["referential_integrity"]}
    assert links["events.batter_id"]["parent"] == "players.player_id"
    assert links["events.batter_id"]["orphan_pct"] == 0
    assert links["events.bowler_id"]["orphan_pct"] == 2.0
    assert links["events.bowler_id"]["orphan_distinct"] == 60


def test_role_playing_fields_are_not_duplicates(tmp_path):
    result = _run(_dataset(tmp_path), sample_size=0)
    dup_pairs = {(d["field_a"], d["field_b"]) for d in result.joins["intra_duplicates"]}
    assert ("batter_id", "non_striker_id") not in dup_pairs
    shared = {(d["field_a"], d["field_b"]) for d in result.joins["shared_domains"]}
    assert ("batter_id", "non_striker_id") in shared


def test_pii_token_matching_avoids_substring_false_positives():
    assert detect_pii_in_field("company", "string", []) == []
    assert detect_pii_in_field("hotel", "string", []) == []
    assert detect_pii_in_field("statement", "string", []) == []
    assert detect_pii_in_field("city", "string", ["Pune"]) == []
    (first,) = detect_pii_in_field("firstName", "string", [])
    assert first.pii_type == PIIType.NAME and first.confidence >= 0.75
    # A bare "name" (channel name, team name…) is not PII; a person's name is.
    assert detect_pii_in_field("name", "string", ["CNN Headlines"]) == []
    assert detect_pii_in_field("Channel Name", "string", ["CNN Headlines"]) == []
    (user,) = detect_pii_in_field("user_name", "string", [])
    assert user.pii_type == PIIType.NAME
    (owner,) = detect_pii_in_field("owner", "string", [])
    assert owner.confidence < 0.8  # possible, not high risk


def test_pii_bare_digit_ids_are_not_ssn_phone_or_card():
    ids = ["427517053", "429861982", "427517050"]
    assert detect_pii_in_field("Packaged Service Id", "string", ids) == []
    assert detect_pii_in_field("code", "string", ["4155551234", "4155551235"]) == []
    assert detect_pii_in_field("x", "string", ["1234567812345678"]) == []  # fails Luhn
    assert detect_pii_in_field("x", "string", ["900-12-3456"]) == []  # invalid SSN area
    # Real shapes still count
    assert [d.pii_type for d in detect_pii_in_field("x", "string", ["427-51-7053", "123-45-6789"])] == [PIIType.SSN]
    assert [d.pii_type for d in detect_pii_in_field("ssn", "string", ["427517053"])] == [PIIType.SSN]
    assert [d.pii_type for d in detect_pii_in_field("x", "string", ["4111111111111111"])] == [PIIType.CREDIT_CARD]


def test_pii_detection_can_be_disabled(tmp_path):
    result = _run(_dataset(tmp_path), sample_size=0, pii_detection=False)
    assert not result.pii_summary
    assert "player12@example.com" in json.dumps(result.schema_json)


def test_pii_value_detection_uses_values_under_neutral_name():
    dets = detect_pii_in_field("contact", "string", ["a@x.io", "b@y.io", "c@z.io"])
    assert [d.pii_type for d in dets] == [PIIType.EMAIL]
    assert dets[0].method == "value"


def test_pii_is_masked_in_every_output(tmp_path):
    result = _run(_dataset(tmp_path), sample_size=0)
    blobs = [json.dumps(result.schema_json), result.html_report, result.summary_md, json.dumps(result.joins)]
    for blob in blobs:
        assert "player12@example.com" not in blob
    masked = result.pii_summary["masked_fields"]
    assert {"object": "players", "field": "contact_email", "type": "email"} in masked


def test_pii_can_be_unmasked_explicitly(tmp_path):
    result = _run(_dataset(tmp_path), sample_size=0, mask_pii=False)
    assert "@example.com" in json.dumps(result.schema_json)
    check = result.decision["compliance_scorecard"]["checklist"][0]
    assert check["status"] == "fail"


def test_pii_ignore_and_force(tmp_path):
    result = _run(
        _dataset(tmp_path), sample_size=0,
        pii_ignore=["players.name"], pii_force={"events.event_id": "passport"},
    )
    fields = {(f["object"], f["field"]) for f in result.pii_summary["fields"]}
    assert ("players", "name") not in fields
    assert ("events", "event_id") in fields


def test_compliance_risk_floor_for_confirmed_identifier():
    summary = {
        "total_pii_fields": 1,
        "by_type": {"email": 1},
        "high_risk_fields": [{"object": "users", "field": "email", "type": "email", "confidence": 0.95}],
        "masked_fields": [],
    }
    card = compliance_scorecard(summary, total_fields=200)
    assert card["risk"] == "medium"
    assert "users.email" in card["risk_reason"]
    assert card["must_mask"] and card["checklist"][0]["status"] == "fail"


def test_ai_context_carries_keys_foreign_keys_and_drift(tmp_path):
    result = _run(_dataset(tmp_path), sample_size=0)
    ctx = build_analysis_context(
        result.schema_json,
        joins=result.joins,
        drift={"schema": {"removed_fields": {"events": ["runs"]}}, "coverage": {}},
    )
    text = summarize_analytics_for_prompt(ctx)
    assert "events: (event_id)" in text
    assert "events.bowler_id → players.player_id: 2.0% orphaned" in text
    assert "events: fields removed runs" in text
