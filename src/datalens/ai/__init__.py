"""
AI — optional AI-powered insights.

AI is strictly opt-in and requires explicit configuration:
1. API key in secrets/environment (for Anthropic, OpenAI, Cursor API key)
2. Logged-in license detection (for Cursor, Copilot, Claude Desktop)

When no AI provider is configured, the tool works fully with deterministic analysis.
"""

from datalens.ai.base import AIProvider
from datalens.ai.markdown import generate_ai_insights_markdown
from datalens.ai.noop import NoOpProvider
from datalens.ai.registry import get_ai_provider, is_ai_available
from datalens.ai.service import is_ai_enabled_for_config, run_ai_insights

__all__ = [
    "AIProvider",
    "NoOpProvider",
    "generate_ai_insights_markdown",
    "get_ai_provider",
    "is_ai_available",
    "is_ai_enabled_for_config",
    "run_ai_insights",
]
