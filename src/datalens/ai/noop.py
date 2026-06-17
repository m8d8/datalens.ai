"""
NoOp AI Provider — default when no AI is configured.

Returns empty insights without any API calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from datalens.ai.base import AIProvider

if TYPE_CHECKING:
    from datalens.config import Config


class NoOpProvider(AIProvider):
    """
    No-operation AI provider.

    Used when AI is disabled or no provider is configured.
    All methods are safe no-ops that don't make any API calls.
    """

    @property
    def name(self) -> str:
        return "noop"

    def is_available(self) -> bool:
        """NoOp is always 'available' as a fallback."""
        return True

    def generate_insights(
        self,
        schema_json: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return empty insights structure."""
        return {
            "enabled": False,
            "provider": None,
            "data_story": None,
            "recommendations": [],
            "patterns": [],
            "quality_assessment": None,
        }
