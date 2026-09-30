"""Report sections: timeline deltas and the collapsible AI review."""

from datalens.report.ai_review import render_ai_review
from datalens.report.sections import _render_timeline, delta_references


def _run(tag, date, rows, health):
    return {"tag": tag, "run_date": date, "metrics": {"row_count|orders|": rows, "health||": health}}


HISTORY = [  # newest first, as HistoryStore.load_runs() returns
    _run("d30", "2026-05-30", 250, 90.0),
    _run("d24", "2026-05-24", 500, 88.0),
    _run("d16", "2026-05-16", 240, 85.0),
]


def test_delta_windows_pick_the_newest_run_old_enough():
    refs = dict(delta_references(HISTORY, "2026-05-31"))
    assert refs["1 day"]["tag"] == "d30"
    assert refs["7 days"]["tag"] == "d24"
    assert "1 month" not in refs  # nothing 30+ days old yet


def test_timeline_shows_only_applicable_delta_columns():
    html = _render_timeline(HISTORY, {"row_count|orders|": 29.0, "health||": 70.0}, "2026-05-31")
    assert "Δ 1 day" in html and "Δ 7 days" in html and "Δ 1 month" not in html
    assert "Not enough history yet for: 1 month" in html
    assert "▼ -221 (-88.4%)" in html          # rows vs 1 day ago
    assert "▼ -20.0 pts" in html              # health vs 1 day ago
    assert "vs d24 (2026-05-24)" in html      # hover explains the reference
    assert 'style="color:var(--color-danger)" title="vs d30 (2026-05-30): 250">▼ -221' in html  # rows drop is red


def test_ai_review_sections_are_collapsed_with_a_preview():
    ai = {"enabled": True, "provider": "claude", "sections": {
        "quality_assessment": ["**Solid keys**: every object has a unique id.", "**Mixed seasons**: int and string."]},
        "recommendations": [{"severity": "high", "category": "x", "action": "Fix the orphaned bowler ids."}]}
    html = render_ai_review(ai)
    assert html.count('<details class="air-section"') == 2
    assert '<details class="air-section" open' not in html
    assert "Solid keys · Mixed seasons" in html and "Fix the orphaned bowler ids" in html


def test_drift_cards_become_open_collapsible_sections_with_icons():
    from datalens.report.html_report import _collapsible_card

    card = ('<div class="card">\n  <div class="card-header"><h3>Removed Fields <span class="badge">2</span></h3></div>'
            '\n  <div class="card-body">rows</div>\n</div>')
    out = _collapsible_card(card)
    assert out.startswith('<details class="card drift-card" open data-section="removed_fields"') and out.endswith("</details>")
    assert "minus-circle" not in out and "<svg" in out and "var(--color-danger)" in out
    assert "Removed Fields" in out and '<div class="card-body">rows</div>' in out
    assert _collapsible_card("<div>not a card</div>") == "<div>not a card</div>"


def test_change_summary_lists_every_breach_and_counts_match(tmp_path):
    import json
    from html import escape

    from datalens import analyze
    from datalens.config.config import Config

    data = tmp_path / "d"
    data.mkdir()
    (data / "orders.jsonl").write_text("".join(json.dumps({"id": f"o{i}", "status": "paid"}) + "\n" for i in range(400)))
    before = analyze({"source": "file", "path": str(data)}, Config(sample_size=0))
    (data / "orders.jsonl").write_text("".join(json.dumps({"id": f"o{i}", "status": 1}) + "\n" for i in range(100)))
    after = analyze({"source": "file", "path": str(data)}, Config(sample_size=0),
                    previous_schema=before.schema_json, reference_tag="v1",
                    history_runs=[{"tag": "v1", "metrics": before.metrics, "breached": []}])
    summ = after.drift_report["summary"]
    driver = next(d for d in after.decision["health_verdict"]["drivers"] if d.startswith("Drift vs"))
    assert f"{summ['fail']} breach(es), {summ['warn']} warning(s)" in driver
    html = after.html_report
    from datalens.report.html_report import _short_message

    assert "Change Summary" in html and "chg-table" in html
    assert 'id="trendsExportOptions"' in html and 'value="summary" checked' in html
    for f in after.drift_report["findings"]:
        assert escape(_short_message(f)) in html
        assert f'data-object="{escape(f.get("object") or "(dataset)")}"' in html
