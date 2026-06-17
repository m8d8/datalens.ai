"""
Parse and normalize AI provider responses into the standard insights dict.
"""

from __future__ import annotations

import json
import re
from typing import Any

from datalens.ai.prompt import INSIGHT_SECTION_KEYS


def extract_json_from_text(text: str) -> dict[str, Any] | None:
    """Try to parse JSON from model output (with or without fences)."""
    text = text.strip()
    if not text:
        return None

    # Direct parse
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass

    # ```json ... ``` block
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        try:
            data = json.loads(fence.group(1).strip())
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass

    # First { ... } object
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass

    return None


def normalize_insights_payload(
    raw: dict[str, Any] | None,
    *,
    provider: str,
    model: str | None = None,
    auth_mode: str = "api_key",
    raw_response: str | None = None,
) -> dict[str, Any]:
    """Map parsed JSON (or fallback) into the canonical ai_insights structure."""
    if not raw:
        return {
            "enabled": False,
            "provider": provider,
            "auth_mode": auth_mode,
            "model": model,
            "error": "Could not parse AI response as JSON",
            "raw_response": raw_response,
        }

    sections: dict[str, Any] = {}
    for key in INSIGHT_SECTION_KEYS:
        if key in raw:
            sections[key] = raw[key]

    recommendations = raw.get("recommendations", [])
    if isinstance(recommendations, str):
        recommendations = [{"category": "general", "severity": "medium", "action": recommendations}]

    return {
        "enabled": True,
        "provider": provider,
        "auth_mode": auth_mode,
        "model": model,
        "sections": sections,
        "data_story": raw.get("data_story"),
        "quality_assessment": raw.get("quality_assessment"),
        "recommendations": recommendations if isinstance(recommendations, list) else [],
        "patterns": raw.get("patterns", []),
        "unique_id_patterns": raw.get("unique_id_patterns"),
        "key_domain_fields": raw.get("key_domain_fields"),
        "structural_value_patterns": raw.get("structural_value_patterns"),
        "cross_object_patterns": raw.get("cross_object_patterns"),
        "domain_field_assessments": raw.get("domain_field_assessments"),
        "hidden_value_relationships": raw.get("hidden_value_relationships"),
        "raw_response": raw_response,
    }
