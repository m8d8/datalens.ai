"""
Cursor license provider — uses cursor-agent CLI when logged into Cursor.

Requires: cursor-agent installed and authenticated (`cursor-agent login`).
Optional API key fallback via CURSOR_API_KEY or secrets.cursor.api_key (cursor-sdk).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from datalens.ai.base import AIProvider
from datalens.ai.context import build_analysis_context
from datalens.ai.prompt import build_cli_prompt
from datalens.ai.providers._cli import cli_status_ok, find_executable, run_cli_prompt
from datalens.ai.response import extract_json_from_text, normalize_insights_payload

if TYPE_CHECKING:
    from datalens.config import Config


class CursorLoginProvider(AIProvider):
    """
    Cursor provider: prefers logged-in cursor-agent (license), falls back to API key.
    """

    def __init__(self, config: "Config") -> None:
        super().__init__(config)
        cursor_cfg = config.secrets.get("cursor", {})
        self._api_key = (
            os.environ.get("CURSOR_API_KEY")
            or cursor_cfg.get("api_key")
        )
        self._cli_path = cursor_cfg.get("cli_path") or os.environ.get("DATALENS_CURSOR_CLI")
        self._model = cursor_cfg.get("model") or os.environ.get("DATALENS_CURSOR_MODEL", "composer-2.5")
        self._timeout = int(cursor_cfg.get("timeout", 180))

    @property
    def name(self) -> str:
        return "cursor"

    @property
    def auth_mode(self) -> str:
        if self._api_key and not self._cli_logged_in():
            return "api_key"
        return "license"

    def _resolve_cli(self) -> str | None:
        if self._cli_path and os.path.isfile(self._cli_path):
            return self._cli_path
        return find_executable("cursor-agent", "agent")

    def _cli_logged_in(self) -> bool:
        cli = self._resolve_cli()
        if not cli:
            return False
        return cli_status_ok([cli, "status"], timeout=20)

    def is_available(self) -> bool:
        if self._cli_logged_in():
            return True
        if self._api_key:
            try:
                import cursor_sdk  # noqa: F401
                return True
            except ImportError:
                pass
        return False

    def _generate_via_cli(self, ctx: dict[str, Any]) -> dict[str, Any]:
        cli = self._resolve_cli()
        if not cli:
            return normalize_insights_payload(
                None, provider=self.name, auth_mode="license",
                raw_response="cursor-agent not found on PATH",
            )

        prompt = build_cli_prompt(ctx)
        cmd = [
            cli,
            "-p",
            prompt,
            "--output-format",
            "text",
        ]
        if self._model:
            cmd.extend(["--model", self._model])

        ok, stdout, stderr = run_cli_prompt(cmd, timeout=self._timeout)
        if not ok:
            return {
                "enabled": False,
                "provider": self.name,
                "auth_mode": "license",
                "error": stderr or "cursor-agent failed",
            }

        parsed = extract_json_from_text(stdout)
        return normalize_insights_payload(
            parsed,
            provider=self.name,
            model=self._model,
            auth_mode="license",
            raw_response=stdout,
        )

    def _generate_via_sdk(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from cursor_sdk import Agent, AgentOptions, LocalAgentOptions

        prompt = build_cli_prompt(ctx)
        try:
            result = Agent.prompt(
                prompt,
                AgentOptions(
                    api_key=self._api_key,
                    model=self._model,
                    local=LocalAgentOptions(cwd=os.getcwd()),
                ),
            )
            text = getattr(result, "result", None) or getattr(result, "text", "") or str(result)
            parsed = extract_json_from_text(text)
            return normalize_insights_payload(
                parsed,
                provider=self.name,
                model=self._model,
                auth_mode="api_key",
                raw_response=text,
            )
        except Exception as e:
            return {
                "enabled": False,
                "provider": self.name,
                "auth_mode": "api_key",
                "error": str(e),
            }

    def generate_insights(
        self,
        schema_json: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ctx = context or build_analysis_context(schema_json)

        if self._cli_logged_in():
            return self._generate_via_cli(ctx)

        if self._api_key:
            return self._generate_via_sdk(ctx)

        return {
            "enabled": False,
            "provider": self.name,
            "error": "Cursor not available: run `cursor-agent login` or set CURSOR_API_KEY",
        }
