"""
Orchestrate AI insight generation for an analysis run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from datalens.ai.context import build_analysis_context
from datalens.ai.markdown import generate_ai_insights_markdown
from datalens.ai.registry import get_ai_provider, is_ai_available

if TYPE_CHECKING:
    from datalens.config import Config
    from datalens.core import AnalysisResult


def should_run_ai(config: "Config") -> bool:
    """
    True when AI is explicitly enabled or auto-detect is requested.

    Precedence: 'off'/'none'/'disabled' = False, 'auto' = True, empty = False (opt-in),
    other values = True (explicit provider).
    """
    name = (config.ai_provider or "").strip().lower()
    if name in ("off", "none", "disabled"):
        return False
    if not name:
        return False  # empty = opt-in (disabled by default)
    if name == "auto":
        return True  # explicit auto-detect
    return True  # explicit provider name


def run_ai_insights(result: "AnalysisResult", config: "Config") -> tuple[dict[str, Any] | None, str | None]:
    """
    Run the configured AI provider and return (insights dict, markdown).

    Returns (None, None) when AI is disabled or unavailable.
    """
    if not should_run_ai(config):
        return None, None

    provider = get_ai_provider(config)
    if provider.name == "noop" or not provider.is_available():
        return None, None

    context = build_analysis_context(
        result.schema_json,
        patterns=result.patterns,
        quality=result.quality,
        joins=result.joins,
        relationships=result.relationships,
        pii_summary=result.pii_summary,
        insights=result.insights,
        decision=result.decision,
    )

    ai_insights = provider.generate_insights_from_context(context)
    if not ai_insights.get("enabled"):
        return ai_insights, generate_ai_insights_markdown(ai_insights)

    md = generate_ai_insights_markdown(ai_insights)
    return ai_insights, md


def is_ai_enabled_for_config(config: "Config") -> bool:
    """Check if AI would run for this configuration."""
    return should_run_ai(config) and is_ai_available(config)
