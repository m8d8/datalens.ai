"""Coverage means the same thing everywhere: rows with a real value (missing, null and empty excluded)."""

import json
import re

from datalens import analyze
from datalens.ai.context import summarize_schema_for_prompt
from datalens.compare.deep_diff import _compute_coverage
from datalens.config.config import Config
from datalens.drift import extract_metrics
from datalens.profiling.coverage import coverage_pct, missing_pct, null_empty_pct


def test_helper_definition():
    field = {"presence_count": 80, "null_empty_count": 30}  # 20 rows lack the key, 30 are null/empty
    assert coverage_pct(field, 100) == 50.0
    assert missing_pct(field, 100) == 20.0 and null_empty_pct(field, 100) == 30.0


def test_every_output_agrees(tmp_path):
    rows = [{"id": i, "speed": (120 + i % 30) if i % 10 == 0 else None, "note": "" if i % 2 else "x"}
            for i in range(200)]
    rows += [{"id": 200 + i} for i in range(50)]  # 'speed' and 'note' missing entirely
    path = tmp_path / "balls.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    result = analyze({"source": "file", "path": str(path)}, Config(sample_size=0))
    obj = result.schema_json["objects"][0]
    speed = next(f for f in obj["fields"] if f["path"] == "speed")
    expected = 20 / 250 * 100  # 20 real values over 250 rows = 8%

    assert coverage_pct(speed, obj["sampled"]) == expected
    assert extract_metrics(result.schema_json)["coverage|balls|speed"] == round(expected, 4)
    assert _compute_coverage(speed, obj["sampled"]) == expected
    assert "coverage=8%" in summarize_schema_for_prompt(result.schema_json["objects"])
    assert re.search(r"\| `speed` \| 8\.0% \|", result.summary_md)
    # Field Explorer, heatmap and drift tables render the same number
    html = result.html_report
    assert "8.0%" in html and "100.0%</span>" not in html.split('id="field-explorer"')[1].split("speed")[1][:400]
