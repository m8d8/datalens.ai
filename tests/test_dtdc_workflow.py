"""DTDC fixture workflow — real file profiling + AI artifact validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from datalens.config import Config
from datalens.core import analyze

DTDC_PATH = Path(__file__).resolve().parents[1] / "test_data" / "DTDC_Courier_Service.csv"

_SAMPLE_AI = {
    "unique_id_patterns": "Consignment No is unique per shipment",
    "key_domain_fields": "Origin, Destination, Chargeable Wt",
    "structural_value_patterns": "Mode is low-cardinality enum",
    "cross_object_patterns": "N/A single object",
    "domain_field_assessments": "GSTIN fields need format validation",
    "hidden_value_relationships": "Chargeable Wt >= Actual Wt pattern",
    "data_story": "DTDC courier consignment records.",
    "quality_assessment": "Strong coverage on core shipment fields.",
    "recommendations": [
        {"category": "keys", "severity": "medium", "action": "Enforce compound key on Booking Code + Consignment No"},
    ],
}


class _StubProvider:
    def __init__(self, name: str, auth_mode: str, config: Config) -> None:
        self.name = name
        self.auth_mode = auth_mode
        self.config = config

    def is_available(self) -> bool:
        return True

    def generate_insights_from_context(self, context: dict) -> dict:
        from datalens.ai.response import normalize_insights_payload

        payload = dict(_SAMPLE_AI)
        payload["data_story"] = f"DTDC analysis via {self.name}."
        return normalize_insights_payload(
            payload,
            provider=self.name,
            model="test",
            auth_mode=self.auth_mode,
        )


@pytest.mark.skipif(not DTDC_PATH.exists(), reason="DTDC fixture missing")
def test_dtdc_profiling_without_ai(tmp_path):
    """Real DTDC CSV — deterministic analysis only."""
    config = Config(out_dir=str(tmp_path), ai_provider="off", sample_size=200)
    result = analyze(
        {"source": "file", "path": str(DTDC_PATH)},
        config,
    )
    assert result.total_fields >= 40
    assert "DTDC_Courier_Service" in result.objects_analyzed
    assert result.ai_insights is None
    assert 'id="ai-insights"' not in result.html_report or "AI-Generated" not in result.html_report


@pytest.mark.skipif(not DTDC_PATH.exists(), reason="DTDC fixture missing")
@pytest.mark.parametrize(
    "provider_name,auth_mode",
    [("anthropic", "api_key"), ("cursor", "license")],
)
def test_dtdc_with_mock_ai_providers(tmp_path, provider_name, auth_mode):
    """E2E on DTDC fixture with mocked API-key and license providers."""
    config = Config(out_dir=str(tmp_path), ai_provider=provider_name, sample_size=200)
    stub = _StubProvider(provider_name, auth_mode, config)

    with patch("datalens.ai.service.get_ai_provider", return_value=stub):
        result = analyze({"source": "file", "path": str(DTDC_PATH)}, config)

    assert result.ai_insights is not None
    assert result.ai_insights.get("enabled") is True
    assert result.ai_insights.get("provider") == provider_name
    assert result.ai_insights.get("auth_mode") == auth_mode
    assert result.ai_insights_md
    assert "Consignment" in result.ai_insights_md or "DTDC" in result.ai_insights_md
    assert 'id="ai-insights"' in result.html_report
    assert "AI-Generated" in result.html_report
