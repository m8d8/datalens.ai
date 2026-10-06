"""
AIProvider ABC — interface for AI insight providers.
"""

from __future__ import annotations

import logging
import os
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

AUTO = "auto"

_MODEL_ERROR = re.compile(
    r"model.{0,80}(not[ _]found|not_found_error|invalid|unknown|does not exist|not available|unsupported|"
    r"not supported|no access|not allowed)|(invalid|unknown|unsupported)[ _]model|"
    r"does not support (this|the|that) model",
    re.IGNORECASE | re.DOTALL,
)


def is_model_error(message: str) -> bool:
    """True when a provider error says the requested model doesn't exist / isn't allowed."""
    return bool(_MODEL_ERROR.search(message or ""))

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
        self.model_note: str | None = None
        """Set when a configured model was rejected and the call fell back to auto."""

    def resolve_model(self, provider_model: str | None = None, env_var: str | None = None) -> str | None:
        """
        The model to request: config ``ai_model`` → provider secret → env var → auto.
        Returns None for auto (let the provider pick).
        """
        for candidate in (getattr(self.config, "ai_model", None), provider_model,
                          os.environ.get(env_var) if env_var else None):
            value = (candidate or "").strip()
            if value and value.lower() != AUTO:
                return value
        return None

    def note_model_fallback(self, requested: str, error: str) -> None:
        self.model_note = (f"Configured model '{requested}' was rejected by {self.name} "
                           f"({error.strip()[:160]}); switched to auto.")
        logger.warning(self.model_note)

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

    @property
    def display_model(self) -> str:
        """The model shown in reports and chat ("auto" when the provider picks)."""
        return AUTO

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

    def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 2048) -> tuple[bool, str]:
        """
        Plain text completion used by chat (``datalens serve`` / ``datalens ask``).

        Returns (ok, text or error). Providers override this; the default says
        chat isn't supported so callers can degrade gracefully.
        """
        return False, f"{self.name} does not support chat"

    def generate_insights_from_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Convenience: generate from a full analysis context dict."""
        schema = context.get("schema") or {}
        return self.generate_insights(schema, context=context)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(available={self.is_available()})"
