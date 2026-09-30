"""The glossary drives tooltips and docs/METRICS.md — keep them in sync with the code."""

from pathlib import Path

from datalens.glossary import GLOSSARY, tip, to_markdown
from datalens.profiling.quality import DIMENSION_WEIGHTS


def test_metrics_doc_is_generated_from_glossary():
    doc = Path(__file__).resolve().parents[1] / "docs" / "METRICS.md"
    assert doc.read_text(encoding="utf-8").strip() == to_markdown().strip(), (
        "docs/METRICS.md is out of date: run `datalens glossary --markdown > docs/METRICS.md`"
    )


def test_every_dqi_dimension_is_explained():
    for dim in DIMENSION_WEIGHTS:
        assert dim in GLOSSARY and tip(dim)
        assert f"{DIMENSION_WEIGHTS[dim]:.2f}" in GLOSSARY[dim]["when"]


def test_entries_are_complete():
    for key, entry in GLOSSARY.items():
        assert entry["title"] and entry["short"] and entry["when"] and entry["how"], key
