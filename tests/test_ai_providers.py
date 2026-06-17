"""Tests for AI providers, markdown output, registry, and HTML AI Insights tab."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from datalens.ai.markdown import generate_ai_insights_markdown
from datalens.ai.registry import get_ai_provider
from datalens.ai.response import extract_json_from_text, normalize_insights_payload
from datalens.ai.service import run_ai_insights
from datalens.config import Config
from datalens.core import analyze
from datalens.report import html_report as hr

_SAMPLE_AI_JSON = {
    "unique_id_patterns": "users.id is fully unique",
    "key_domain_fields": "email is a core contact field",
    "structural_value_patterns": "status is low-cardinality enum",
    "cross_object_patterns": "orders.user_id may join users.id",
    "domain_field_assessments": "email coverage is strong",
    "hidden_value_relationships": "created_at correlates with order dates",
    "data_story": "This is a small CRM-style dataset.",
    "quality_assessment": "Generally clean with minor nulls.",
    "recommendations": [
        {"category": "quality", "severity": "low", "action": "Document nullable fields"},
    ],
}

_SCHEMA = {
    "objects": [
        {
            "object": "users",
            "sampled": 10,
            "fields": [
                {
                    "path": "id",
                    "presence_count": 10,
                    "null_empty_count": 0,
                    "types": {"int": 10},
                    "examples": [1],
                    "distinct_count_in_sample": 10,
                },
                {
                    "path": "email",
                    "presence_count": 10,
                    "null_empty_count": 0,
                    "types": {"string": 10},
                    "examples": ["a@b.com"],
                    "distinct_count_in_sample": 10,
                },
            ],
        }
    ]
}


class _MockApiProvider:
    """Simulates an API-key provider."""

    name = "anthropic"
    auth_mode = "api_key"

    def __init__(self, config: Config) -> None:
        self.config = config

    def is_available(self) -> bool:
        return True

    def generate_insights_from_context(self, context: dict) -> dict:
        return normalize_insights_payload(
            _SAMPLE_AI_JSON,
            provider=self.name,
            model="test-model",
            auth_mode=self.auth_mode,
        )


class _MockLicenseProvider:
    """Simulates a license-based provider (e.g. cursor)."""

    name = "cursor"
    auth_mode = "license"

    def __init__(self, config: Config) -> None:
        self.config = config

    def is_available(self) -> bool:
        return True

    def generate_insights_from_context(self, context: dict) -> dict:
        payload = dict(_SAMPLE_AI_JSON)
        payload["data_story"] = "License-based Cursor analysis."
        return normalize_insights_payload(
            payload,
            provider=self.name,
            model="composer-2.5",
            auth_mode=self.auth_mode,
        )


def test_extract_json_from_fenced_block():
    text = 'Here is output:\n```json\n{"data_story": "hi"}\n```'
    parsed = extract_json_from_text(text)
    assert parsed is not None
    assert parsed["data_story"] == "hi"


def test_generate_ai_insights_markdown_sections():
    insights = normalize_insights_payload(
        _SAMPLE_AI_JSON,
        provider="anthropic",
        model="claude-test",
        auth_mode="api_key",
    )
    md = generate_ai_insights_markdown(insights)
    assert "# AI Insights" in md
    assert "anthropic" in md
    assert "## Unique ID Patterns" in md
    assert "## Recommendations" in md


def test_html_ai_insights_tab_renders():
    insights = normalize_insights_payload(
        _SAMPLE_AI_JSON,
        provider="cursor",
        model="composer-2.5",
        auth_mode="license",
    )
    html = hr._render_ai_insights_tab(insights)
    assert "AI-Generated" in html
    assert "cursor" in html
    assert "Unique ID Patterns" in html
    assert "AI Recommendations" in html


def test_html_report_includes_ai_insights_tab():
    insights = normalize_insights_payload(
        _SAMPLE_AI_JSON,
        provider="anthropic",
        auth_mode="api_key",
    )
    html = hr.generate_html_report(_SCHEMA, Config(), ai_insights=insights)
    assert 'id="ai-insights"' in html
    assert "AI Insights" in html


@pytest.mark.parametrize(
    "provider_cls,provider_name,ai_flag",
    [
        (_MockApiProvider, "anthropic", "anthropic"),
        (_MockLicenseProvider, "cursor", "cursor"),
    ],
)
def test_e2e_analyze_with_mock_providers(provider_cls, provider_name, ai_flag, tmp_path):
    """End-to-end: analyze → ai_insights dict → markdown → HTML tab."""
    config = Config(
        out_dir=str(tmp_path),
        ai_provider=ai_flag,
        secrets={"anthropic": {"api_key": "test"}} if ai_flag == "anthropic" else {},
    )

    with patch("datalens.core.get_connector") as m_conn, \
         patch("datalens.core.profile_source", return_value=_SCHEMA), \
         patch("datalens.ai.service.get_ai_provider") as m_get:
        connector = MagicMock()
        m_conn.return_value = connector
        m_get.return_value = provider_cls(config)

        result = analyze(
            {"source": "file", "path": str(tmp_path / "data.csv")},
            config,
        )

    assert result.ai_insights is not None
    assert result.ai_insights.get("enabled") is True
    assert result.ai_insights.get("provider") == provider_name
    assert result.ai_insights_md
    assert f"{provider_name}" in result.ai_insights_md or "AI Insights" in result.ai_insights_md
    assert 'id="ai-insights"' in result.html_report


def test_registry_anthropic_when_key_set():
    config = Config(ai_provider="anthropic", secrets={"anthropic": {"api_key": "sk-test"}})
    with patch.dict(os.environ, {}, clear=False):
        provider = get_ai_provider(config)
    assert provider.name == "anthropic"


@pytest.mark.integration
def test_live_anthropic_if_key_present():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")
    try:
        import anthropic  # noqa: F401
    except ImportError:
        pytest.skip("anthropic package not installed")

    config = Config(ai_provider="anthropic")
    provider = get_ai_provider(config)
    if not provider.is_available():
        pytest.skip("Anthropic provider not available")

    insights = provider.generate_insights(_SCHEMA)
    assert insights.get("enabled") is True
    assert insights.get("provider") == "anthropic"


@pytest.mark.integration
def test_live_cursor_license_if_cli_present():
    from datalens.ai.providers.cursor_login import CursorLoginProvider

    config = Config(ai_provider="cursor")
    provider = CursorLoginProvider(config)
    if not provider.is_available():
        pytest.skip("cursor-agent not logged in and no CURSOR_API_KEY")

    insights = provider.generate_insights(_SCHEMA)
    assert insights.get("provider") == "cursor"
    if insights.get("enabled"):
        assert insights.get("data_story") or insights.get("sections")


def test_run_ai_insights_disabled_returns_none():
    from datalens.core import AnalysisResult

    config = Config(ai_provider="off")
    result = AnalysisResult(
        schema_json=_SCHEMA,
        summary_md="",
        html_report="",
        version_tag="t",
        objects_analyzed=["users"],
        total_fields=2,
        total_sampled=10,
    )
    insights, md = run_ai_insights(result, config)
    assert insights is None
    assert md is None
