"""
OpenAI AI Provider — GPT API integration.

Requires: pip install openai (or uv add openai --extra ai)
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


class OpenAIProvider(AIProvider):
    """OpenAI API provider (API key authentication)."""

    def __init__(self, config: "Config") -> None:
        super().__init__(config)
        self._client = None
        openai_cfg = config.secrets.get("openai", {})
        self._api_key = os.environ.get("OPENAI_API_KEY") or openai_cfg.get("api_key")
        self._requested_model = self.resolve_model(openai_cfg.get("model"), "DATALENS_OPENAI_MODEL")

    AUTO_MODEL = "gpt-4o-mini"

    @property
    def _model(self) -> str:
        return self._requested_model or self.AUTO_MODEL

    @property
    def display_model(self) -> str:
        return self._requested_model or f"auto ({self.AUTO_MODEL})"

    def _chat(self, **kwargs: Any) -> Any:
        """chat.completions.create; a rejected configured model falls back to auto once."""
        try:
            return self._get_client().chat.completions.create(model=self._model, **kwargs)
        except Exception as e:
            if self._requested_model and is_model_error(str(e)):
                self.note_model_fallback(self._requested_model, str(e))
                self._requested_model = None
                return self._get_client().chat.completions.create(model=self._model, **kwargs)
            raise

    @property
    def name(self) -> str:
        return "openai"

    @property
    def auth_mode(self) -> str:
        return "api_key"

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_client(self):
        if self._client is None:
            import openai
            self._client = openai.OpenAI(api_key=self._api_key)
        return self._client

    def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 2048) -> tuple[bool, str]:
        if not self.is_available():
            return False, "OpenAI API not available (set OPENAI_API_KEY and install the 'ai' extra)"
        try:
            messages = ([{"role": "system", "content": system}] if system else []) + [
                {"role": "user", "content": prompt}]
            response = self._chat(max_tokens=max_tokens, messages=messages)
            return True, response.choices[0].message.content or ""
        except Exception as e:
            return False, str(e)

    def generate_insights(
        self,
        schema_json: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_available():
            return normalize_insights_payload(
                None, provider=self.name, auth_mode=self.auth_mode,
                raw_response="OpenAI API not available",
            )

        ctx = context or build_analysis_context(schema_json)
        prompt = build_insights_prompt(ctx)

        try:
            response = self._chat(
                max_tokens=2048,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a data schema analyst. Respond with valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content or ""
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
