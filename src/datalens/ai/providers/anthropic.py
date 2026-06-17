"""
Anthropic AI Provider — Claude API integration.

Requires: pip install anthropic (or uv add anthropic --extra ai)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from datalens.ai.base import AIProvider
from datalens.ai.context import build_analysis_context
from datalens.ai.prompt import build_insights_prompt
from datalens.ai.response import extract_json_from_text, normalize_insights_payload

if TYPE_CHECKING:
    from datalens.config import Config


class AnthropicProvider(AIProvider):
    """
    Anthropic (Claude) AI provider.

    Requires ANTHROPIC_API_KEY in environment or secrets.
    """

    def __init__(self, config: "Config") -> None:
        super().__init__(config)
        self._client = None
        anthropic_cfg = config.secrets.get("anthropic", {})
        self._api_key = os.environ.get("ANTHROPIC_API_KEY") or anthropic_cfg.get("api_key")
        self._model = (
            anthropic_cfg.get("model")
            or os.environ.get("DATALENS_ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        )

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def auth_mode(self) -> str:
        return "api_key"

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def generate_insights(
        self,
        schema_json: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_available():
            return {
                "enabled": False,
                "provider": self.name,
                "auth_mode": self.auth_mode,
                "error": "Anthropic API not available",
            }

        ctx = context or build_analysis_context(schema_json)
        prompt = build_insights_prompt(ctx)

        try:
            client = self._get_client()
            message = client.messages.create(
                model=self._model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            text = message.content[0].text
            parsed = extract_json_from_text(text)
            return normalize_insights_payload(
                parsed,
                provider=self.name,
                model=self._model,
                auth_mode=self.auth_mode,
                raw_response=text,
            )
        except Exception as e:
            return {
                "enabled": False,
                "provider": self.name,
                "auth_mode": self.auth_mode,
                "error": str(e),
            }
