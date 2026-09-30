"""
Claude Desktop / Claude Code license provider — uses `claude` CLI when authenticated.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from datalens.ai.base import AIProvider, is_model_error
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
        self._requested_model = self.resolve_model(claude_cfg.get("model"), "DATALENS_CLAUDE_MODEL")

    @property
    def display_model(self) -> str:
        return self._requested_model or "auto"

    def _run(self, text: str, *, cwd: str | None = None) -> tuple[bool, str, str]:
        """`claude -p` with the configured model (if any); a rejected model is retried on auto."""
        base = [self._cli_path, "-p", text, "--output-format", "text"]
        if self._requested_model:
            ok, out, err = run_cli_prompt(base + ["--model", self._requested_model], timeout=self._timeout, cwd=cwd)
            if ok or not is_model_error(f"{err} {out}"):
                return ok, out, err
            self.note_model_fallback(self._requested_model, err or out)
            self._requested_model = None
        return run_cli_prompt(base, timeout=self._timeout, cwd=cwd)

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

    def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 2048) -> tuple[bool, str]:
        import tempfile

        if not self.is_available():
            return False, "Claude CLI not available"
        text = f"{system}\n\n{prompt}" if system else prompt
        with tempfile.TemporaryDirectory(prefix="datalens-chat-") as sandbox:
            ok, stdout, stderr = self._run(text, cwd=sandbox)
        return (True, stdout) if ok else (False, stderr or "Claude CLI failed")

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
        ok, stdout, stderr = self._run(prompt)
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
            model=self.display_model,
            auth_mode=self.auth_mode,
            raw_response=stdout,
        )
