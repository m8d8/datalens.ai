"""
Anthropic AI Provider — Claude API integration.

Requires: pip install anthropic (or uv add anthropic --extra ai)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from datalens.ai.base import AIProvider, is_model_error
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
        self._requested_model = self.resolve_model(anthropic_cfg.get("model"), "DATALENS_ANTHROPIC_MODEL")
        self._auto_model: str | None = None

    AUTO_FALLBACK_MODEL = "claude-sonnet-5-5"

    @property
    def _model(self) -> str:
        return self._requested_model or self._pick_auto_model()

    @property
    def display_model(self) -> str:
        return self._requested_model or f"auto ({self._pick_auto_model()})"

    def _pick_auto_model(self) -> str:
        """Auto: the newest Sonnet the account can use (models are listed newest first)."""
        if self._auto_model is None:
            self._auto_model = self.AUTO_FALLBACK_MODEL
            try:
                ids = [m.id for m in self._get_client().models.list(limit=50).data]
                self._auto_model = next((i for i in ids if "sonnet" in i), ids[0] if ids else self.AUTO_FALLBACK_MODEL)
            except Exception:
                pass
        return self._auto_model

    def _create(self, **kwargs: Any) -> Any:
        """messages.create with the resolved model; a rejected configured model falls back to auto once."""
        try:
            return self._get_client().messages.create(model=self._model, **kwargs)
        except Exception as e:
            if self._requested_model and is_model_error(str(e)):
                self.note_model_fallback(self._requested_model, str(e))
                self._requested_model = None
                return self._get_client().messages.create(model=self._model, **kwargs)
            raise

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

    def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 2048) -> tuple[bool, str]:
        if not self.is_available():
            return False, "Anthropic API not available (set ANTHROPIC_API_KEY and install the 'ai' extra)"
        try:
            kwargs: dict[str, Any] = {"max_tokens": max_tokens,
                                      "messages": [{"role": "user", "content": prompt}]}
            if system:
                kwargs["system"] = system
            message = self._create(**kwargs)
            return True, "".join(getattr(block, "text", "") for block in message.content)
        except Exception as e:
            return False, str(e)

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
            message = self._create(max_tokens=4096, messages=[{"role": "user", "content": prompt}])
            text = "".join(getattr(block, "text", "") for block in message.content)
            parsed = extract_json_from_text(text)
            return normalize_insights_payload(
                parsed,
                provider=self.name,
                model=self.display_model,
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
