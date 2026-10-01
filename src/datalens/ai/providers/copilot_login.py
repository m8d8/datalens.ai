"""
GitHub Copilot license provider.

Prefers the standalone GitHub Copilot CLI (``copilot``, ``npm i -g @github/copilot``),
which supports scripted prompts and model choice::

    copilot -p "<prompt>" -s --model auto --no-ask-user --no-custom-instructions

and falls back to ``gh copilot`` from the GitHub CLI. Either way the CLI runs in an
empty temporary folder with no tool permissions, so it can only answer — it can't
read or change local files.
"""

from __future__ import annotations

import tempfile
from typing import TYPE_CHECKING, Any

from datalens.ai.base import AUTO, AIProvider, is_model_error
from datalens.ai.context import build_analysis_context
from datalens.ai.prompt import build_cli_prompt
from datalens.ai.providers._cli import cli_status_ok, find_executable, run_cli_prompt
from datalens.ai.response import extract_json_from_text, normalize_insights_payload

if TYPE_CHECKING:
    from datalens.config import Config


class CopilotLoginProvider(AIProvider):
    """GitHub Copilot via the standalone `copilot` CLI (preferred) or `gh copilot` (license / subscription)."""

    def __init__(self, config: "Config") -> None:
        super().__init__(config)
        copilot_cfg = config.secrets.get("copilot", {})
        self._copilot_path = copilot_cfg.get("cli_path") or find_executable("copilot")
        self._gh_path = copilot_cfg.get("gh_path") or find_executable("gh")
        self._timeout = int(copilot_cfg.get("timeout", 300))
        self._requested_model = self.resolve_model(copilot_cfg.get("model"), "DATALENS_COPILOT_MODEL")
        self._available: bool | None = None
        if self._requested_model and not self._copilot_path:
            self.note_model_fallback(self._requested_model, "gh copilot does not accept a model option")
            self._requested_model = None

    @property
    def display_model(self) -> str:
        return self._requested_model or AUTO

    @property
    def name(self) -> str:
        return "copilot"

    @property
    def auth_mode(self) -> str:
        return "license"

    @property
    def cli(self) -> str:
        """Which CLI is used: "copilot" (standalone) or "gh copilot"."""
        return "copilot" if self._copilot_path else "gh copilot"

    def is_available(self) -> bool:
        if self._available is None:
            if self._copilot_path:
                ok, _, _ = run_cli_prompt([self._copilot_path, "--version"], timeout=20)
                self._available = ok
            elif self._gh_path:
                ok, _, _ = run_cli_prompt([self._gh_path, "auth", "status"], timeout=15)
                self._available = ok and cli_status_ok([self._gh_path, "copilot", "status"], timeout=15)
            else:
                self._available = False
        return bool(self._available)

    def _command(self, text: str, model: str | None) -> list[str]:
        if self._copilot_path:
            return [self._copilot_path, "-p", text, "-s", "--no-color", "--no-ask-user",
                    "--no-custom-instructions", "--model", model or AUTO]
        return [self._gh_path, "copilot", "-p", text]

    def _run(self, text: str) -> tuple[bool, str, str]:
        """Run one prompt in an empty sandbox folder; a rejected model is retried on auto."""
        with tempfile.TemporaryDirectory(prefix="datalens-copilot-") as sandbox:
            ok, out, err = run_cli_prompt(self._command(text, self._requested_model),
                                          timeout=self._timeout, cwd=sandbox)
            if not ok and self._requested_model and is_model_error(f"{err} {out}"):
                self.note_model_fallback(self._requested_model, err or out)
                self._requested_model = None
                ok, out, err = run_cli_prompt(self._command(text, None), timeout=self._timeout, cwd=sandbox)
        return ok, out, err

    def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 2048) -> tuple[bool, str]:
        if not self.is_available():
            return False, "GitHub Copilot CLI not available (npm i -g @github/copilot, then run `copilot` to log in)"
        text = f"{system}\n\n{prompt}" if system else prompt
        ok, stdout, stderr = self._run(text)
        return (True, stdout) if ok else (False, stderr or f"{self.cli} failed")

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
                "error": "GitHub Copilot not available: install the Copilot CLI (npm i -g @github/copilot) "
                         "and log in, or install gh and run `gh auth login`",
            }

        ctx = context or build_analysis_context(schema_json)
        ok, stdout, stderr = self._run(build_cli_prompt(ctx))
        if not ok:
            return {
                "enabled": False,
                "provider": self.name,
                "auth_mode": self.auth_mode,
                "error": stderr or f"{self.cli} failed",
            }

        parsed = extract_json_from_text(stdout)
        return normalize_insights_payload(
            parsed,
            provider=self.name,
            model=self.display_model,
            auth_mode=self.auth_mode,
            raw_response=stdout,
        )
