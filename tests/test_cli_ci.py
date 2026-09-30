"""CLI behaviour that CI/CD pipelines depend on: exit codes, JSON output, gates, notify."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from datalens.cli import cli


def _data(dir_: Path, rows: int, *, null_every: int = 0) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    lines = []
    for i in range(rows):
        lines.append(json.dumps({"id": f"r{i}", "amount": i % 50,
                                 "note": None if null_every and i % null_every == 0 else "ok"}))
    (dir_ / "events.jsonl").write_text("\n".join(lines) + "\n")
    return dir_


def _run(runner, *args):
    result = runner.invoke(cli, ["analyze", "-s", "file", *args], catch_exceptions=False)
    return result


def test_json_output_and_exit_codes(tmp_path):
    runner = CliRunner()
    out = tmp_path / "out"
    first = _run(runner, "-p", str(_data(tmp_path / "d1", 1000)), "-o", str(out), "--version-tag", "d1",
                 "--format", "json")
    assert first.exit_code == 0
    summary = json.loads(first.stdout)
    assert summary["scores"]["health"] is not None and summary["drift"] is None

    second = _run(runner, "-p", str(_data(tmp_path / "d2", 500, null_every=2)), "-o", str(out),
                  "--version-tag", "d2", "--detect-drift", "--fail-on", "fail", "--format", "json",
                  "--notify", f"file:{tmp_path / 'alerts.jsonl'}")
    assert second.exit_code == 2
    summary = json.loads(second.stdout)
    assert summary["drift"]["status"] == "fail"
    assert any("row count" in h for h in summary["drift"]["highlights"])
    alert = json.loads((tmp_path / "alerts.jsonl").read_text().splitlines()[0])
    assert alert["exit_code"] == 2 and alert["gate_reasons"]

    never = _run(runner, "-p", str(_data(tmp_path / "d2", 500, null_every=2)), "-o", str(out),
                 "--version-tag", "d3", "--compare-to", "d1", "--format", "json")
    assert never.exit_code == 0  # --fail-on defaults to never


def test_score_gates(tmp_path):
    runner = CliRunner()
    result = _run(runner, "-p", str(_data(tmp_path / "d", 200)), "-o", str(tmp_path / "o"),
                  "--min-score", "health=101")
    assert result.exit_code == 2
    bad = _run(runner, "-p", str(_data(tmp_path / "d", 200)), "-o", str(tmp_path / "o"),
               "--min-score", "nonsense=1")
    assert bad.exit_code == 2 and "Invalid --min-score" in bad.output


def test_history_drift_and_scores_commands(tmp_path):
    runner = CliRunner()
    out = tmp_path / "out"
    _run(runner, "-p", str(_data(tmp_path / "d1", 1000)), "-o", str(out), "--version-tag", "d1")
    _run(runner, "-p", str(_data(tmp_path / "d2", 400)), "-o", str(out), "--version-tag", "d2")

    listing = runner.invoke(cli, ["history", "list", "-o", str(out), "--format", "json"])
    assert [r["tag"] for r in json.loads(listing.output)] == ["d2", "d1"]

    drift = runner.invoke(cli, ["drift", "-o", str(out), "--fail-on", "fail", "--format", "json"])
    assert drift.exit_code == 2
    assert json.loads(drift.output)["reference"]["tag"] == "d1"

    run_dir = next(p for p in out.iterdir() if p.is_dir() and not p.name.startswith("."))
    scores = runner.invoke(cli, ["scores", str(run_dir), "--format", "json"])
    assert scores.exit_code == 0 and "health" in json.loads(scores.output)["scores"]


def test_schema_infer_and_validate(tmp_path):
    runner = CliRunner()
    data = _data(tmp_path / "d", 300)
    schema_file = tmp_path / "expected.json"
    infer = runner.invoke(cli, ["schema", "infer", "-s", "file", "-p", str(data), "-o", str(schema_file)])
    assert infer.exit_code == 0 and schema_file.exists()
    ok = runner.invoke(cli, ["schema", "validate", "-s", "file", "-p", str(data), "--schema", str(schema_file)])
    assert ok.exit_code == 0
    broken = _data(tmp_path / "b", 300, null_every=1)
    bad = runner.invoke(cli, ["schema", "validate", "-s", "file", "-p", str(broken), "--schema", str(schema_file),
                              "--format", "json"])
    assert bad.exit_code == 2 and json.loads(bad.output)["status"] == "fail"
