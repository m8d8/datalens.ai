"""
AIProvider ABC — interface for AI insight providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datalens.config import Config


class AIProvider(ABC):
    """
    Abstract base class for AI insight providers.

    Providers must implement:
    - is_available(): Check if the provider can be used
    - generate_insights(): Generate insights from schema analysis
    """

    def __init__(self, config: "Config") -> None:
        """
        Initialize the AI provider.

        Args:
            config: Configuration object with secrets and settings.
        """
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name (e.g., 'anthropic', 'openai', 'copilot')."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this provider is available and configured.

        Returns:
            True if the provider can be used, False otherwise.
        """
        ...

    @property
    def auth_mode(self) -> str:
        """Authentication mode: ``api_key`` or ``license``."""
        return "api_key"

    @abstractmethod
    def generate_insights(
        self,
        schema_json: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate AI-powered insights from schema analysis.

        Args:
            schema_json: The schema analysis JSON.
            context: Optional dict with patterns, quality, joins, pii, insights, decision.

        Returns:
            Dict with AI insights (see ``datalens.ai.response.normalize_insights_payload``).
        """
        ...

    def generate_insights_from_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Convenience: generate from a full analysis context dict."""
        schema = context.get("schema") or {}
        return self.generate_insights(schema, context=context)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(available={self.is_available()})"
