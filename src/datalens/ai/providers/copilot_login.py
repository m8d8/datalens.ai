"""
GitHub Copilot license provider — uses `gh copilot` when logged in via GitHub CLI.
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


class CopilotLoginProvider(AIProvider):
    """GitHub Copilot via gh CLI (license / subscription)."""

    def __init__(self, config: "Config") -> None:
        super().__init__(config)
        copilot_cfg = config.secrets.get("copilot", {})
        self._gh_path = copilot_cfg.get("gh_path") or find_executable("gh")
        self._timeout = int(copilot_cfg.get("timeout", 180))

    @property
    def name(self) -> str:
        return "copilot"

    @property
    def auth_mode(self) -> str:
        return "license"

    def is_available(self) -> bool:
        if not self._gh_path:
            return False
        ok, _, _ = run_cli_prompt([self._gh_path, "auth", "status"], timeout=15)
        if not ok:
            return False
        return cli_status_ok([self._gh_path, "copilot", "status"], timeout=15)

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
                "error": "GitHub Copilot not available: install gh CLI and run `gh auth login`",
            }

        ctx = context or build_analysis_context(schema_json)
        prompt = build_cli_prompt(ctx)
        cmd = [self._gh_path, "copilot", "-p", prompt]
        ok, stdout, stderr = run_cli_prompt(cmd, timeout=self._timeout)
        if not ok:
            return {
                "enabled": False,
                "provider": self.name,
                "auth_mode": self.auth_mode,
                "error": stderr or "gh copilot failed",
            }

        parsed = extract_json_from_text(stdout)
        return normalize_insights_payload(
            parsed,
            provider=self.name,
            auth_mode=self.auth_mode,
            raw_response=stdout,
        )
