"""
Claude Desktop / Claude Code license provider — uses `claude` CLI when authenticated.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from datalens.ai.base import AIProvider
from datalens.ai.context import build_analysis_context
from datalens.ai.prompt import build_cli_prompt
from datalens.ai.providers._cli import find_executable, run_cli_prompt
from datalens.ai.response import extract_json_from_text, normalize_insights_payload

if TYPE_CHECKING:
    from datalens.config import Config


class ClaudeLoginProvider(AIProvider):
    """Anthropic Claude via local CLI session (Claude Code / Desktop)."""

    def __init__(self, config: "Config") -> None:
        super().__init__(config)
        claude_cfg = config.secrets.get("claude", {})
        self._cli_path = claude_cfg.get("cli_path") or find_executable("claude")
        self._timeout = int(claude_cfg.get("timeout", 180))

    @property
    def name(self) -> str:
        return "claude"

    @property
    def auth_mode(self) -> str:
        return "license"

    def is_available(self) -> bool:
        if not self._cli_path:
            return False
        ok, _, _ = run_cli_prompt(
            [self._cli_path, "--version"],
            timeout=10,
        )
        return ok

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
                "error": "Claude CLI not available: install Claude Code and authenticate",
            }

        ctx = context or build_analysis_context(schema_json)
        prompt = build_cli_prompt(ctx)
        cmd = [self._cli_path, "-p", prompt, "--output-format", "text"]
        ok, stdout, stderr = run_cli_prompt(cmd, timeout=self._timeout)
        if not ok:
            return {
                "enabled": False,
                "provider": self.name,
                "auth_mode": self.auth_mode,
                "error": stderr or "claude CLI failed",
            }

        parsed = extract_json_from_text(stdout)
        return normalize_insights_payload(
            parsed,
            provider=self.name,
            auth_mode=self.auth_mode,
            raw_response=stdout,
        )
