"""Phase A regression: the report renders from pre-computed analytics and does
not recompute work the caller already did; legacy shim still works."""

from __future__ import annotations

from unittest.mock import patch

from datalens.config import Config
from datalens.report import html_report as hr


_SCHEMA = {
    "objects": [
        {
            "object": "users",
            "sampled": 50,
            "fields": [
                {"path": "id", "presence_count": 50, "null_empty_count": 0,
                 "types": {"int": 50}, "examples": [1, 2, 3],
                 "distinct_count_in_sample": 50},
                {"path": "email", "presence_count": 50, "null_empty_count": 0,
                 "types": {"string": 50}, "examples": ["a@b.com"],
                 "distinct_count_in_sample": 50},
            ],
        }
    ]
}


def test_report_does_not_recompute_when_analytics_supplied():
    cfg = Config()
    # Pre-compute the analytics the way core.analyze does.
    patterns = hr.analyze_patterns(_SCHEMA)
    quality = hr.compute_schema_quality(_SCHEMA, patterns_data=patterns)
    pii = hr.detect_pii_in_schema(_SCHEMA)
    pii_summary = hr.get_pii_summary(pii)
    rels = hr.analyze_relationships(_SCHEMA)
    stats = hr.compute_statistics_summary(_SCHEMA)
    joins = hr.analyze_joins(_SCHEMA)
    insights = hr.build_insights(_SCHEMA, quality, joins, patterns, pii_summary)

    # If anything is recomputed, these patched names would be called.
    with patch.object(hr, "analyze_patterns") as m_pat, \
         patch.object(hr, "compute_schema_quality") as m_q, \
         patch.object(hr, "detect_pii_in_schema") as m_pii, \
         patch.object(hr, "analyze_relationships") as m_rel, \
         patch.object(hr, "compute_statistics_summary") as m_stats, \
         patch.object(hr, "analyze_joins") as m_join, \
         patch.object(hr, "build_insights") as m_ins:
        html = hr.generate_html_report(
            _SCHEMA, cfg,
            patterns_data=patterns,
            quality_data=quality,
            pii_data=pii,
            pii_summary=pii_summary,
            relationships_data=rels,
            statistics_data=stats,
            joins_data=joins,
            insights_data=insights,
        )
        for m in (m_pat, m_q, m_pii, m_rel, m_stats, m_join, m_ins):
            m.assert_not_called()

    assert "<html" in html.lower()


def test_legacy_shim_still_computes():
    """Calling with only (schema, config) must still produce a full report."""
    html = hr.generate_html_report(_SCHEMA, Config())
    assert "<html" in html.lower()
    assert "users" in html


def test_report_accepts_diff_and_decision_kwargs():
    """New optional kwargs are accepted without error (rendering lands in Phase D)."""
    from datalens.history.diff import compare_schemas
    diff = compare_schemas(_SCHEMA, _SCHEMA)
    html = hr.generate_html_report(_SCHEMA, Config(), diff=diff, decision={"x": 1})
    assert "<html" in html.lower()
