"""
AI Provider Registry — manages available AI providers.

Supports multiple authentication modes:
1. API keys (Anthropic, OpenAI, Cursor API key) — configured via secrets or environment
2. Logged-in licenses (Cursor, Copilot, Claude Desktop) — auto-detected via CLI
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from datalens.ai.base import AIProvider
from datalens.ai.noop import NoOpProvider

if TYPE_CHECKING:
    from datalens.config import Config

# Providers that use subscription / IDE login (no API key required)
LICENSE_PROVIDERS = frozenset({"cursor", "cursor_login", "copilot", "copilot_login", "claude", "claude_login"})

# Providers that require an API key in secrets or environment
API_KEY_PROVIDERS = frozenset({"anthropic", "openai", "cursor"})  # cursor also supports license


def get_ai_provider(config: "Config") -> AIProvider:
    """
    Get the appropriate AI provider based on configuration.

    Priority order:
    1. Explicitly configured provider in config.ai_provider
    2. Auto-detect available providers (logged-in licenses first)
    3. Fall back to NoOpProvider

    Args:
        config: Configuration object.

    Returns:
        Configured AIProvider instance.
    """
    provider_name = (config.ai_provider or "").strip().lower()

    if provider_name in ("off", "none", "disabled"):
        return NoOpProvider(config)

    if provider_name in ("", "auto"):
        provider = _auto_detect_provider(config)
        return provider if provider else NoOpProvider(config)

    if provider_name == "anthropic":
        return _get_anthropic_provider(config)
    if provider_name == "openai":
        return _get_openai_provider(config)
    if provider_name in ("cursor", "cursor_login"):
        return _get_cursor_provider(config)
    if provider_name in ("copilot", "copilot_login"):
        return _get_copilot_provider(config)
    if provider_name in ("claude", "claude_login"):
        return _get_claude_login_provider(config)

    return NoOpProvider(config)


def is_ai_available(config: "Config") -> bool:
    """
    Check if any AI provider is available.

    Args:
        config: Configuration object.

    Returns:
        True if an AI provider (other than NoOp) is available.
    """
    provider = get_ai_provider(config)
    return provider.name != "noop" and provider.is_available()


def _auto_detect_provider(config: "Config") -> AIProvider | None:
    """
    Auto-detect available AI providers.

    Checks in order:
    1. Cursor login (cursor-agent)
    2. Copilot login (gh copilot)
    3. Claude login (claude CLI)
    4. Anthropic API key
    5. OpenAI API key
    6. Cursor API key (cursor-sdk)
    """
    cursor = _get_cursor_provider(config)
    if cursor.is_available():
        return cursor

    copilot = _get_copilot_provider(config)
    if copilot.is_available():
        return copilot

    claude = _get_claude_login_provider(config)
    if claude.is_available():
        return claude

    if _has_anthropic_key(config):
        anthropic = _get_anthropic_provider(config)
        if anthropic.is_available():
            return anthropic

    if _has_openai_key(config):
        openai = _get_openai_provider(config)
        if openai.is_available():
            return openai

    return None


def _has_anthropic_key(config: "Config") -> bool:
    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or config.secrets.get("anthropic", {}).get("api_key")
    )


def _has_openai_key(config: "Config") -> bool:
    return bool(
        os.environ.get("OPENAI_API_KEY")
        or config.secrets.get("openai", {}).get("api_key")
    )


def _get_anthropic_provider(config: "Config") -> AIProvider:
    try:
        from datalens.ai.providers.anthropic import AnthropicProvider
        return AnthropicProvider(config)
    except ImportError:
        return NoOpProvider(config)


def _get_openai_provider(config: "Config") -> AIProvider:
    try:
        from datalens.ai.providers.openai import OpenAIProvider
        return OpenAIProvider(config)
    except ImportError:
        return NoOpProvider(config)


def _get_cursor_provider(config: "Config") -> AIProvider:
    try:
        from datalens.ai.providers.cursor_login import CursorLoginProvider
        return CursorLoginProvider(config)
    except ImportError:
        return NoOpProvider(config)


def _get_copilot_provider(config: "Config") -> AIProvider:
    try:
        from datalens.ai.providers.copilot_login import CopilotLoginProvider
        return CopilotLoginProvider(config)
    except ImportError:
        return NoOpProvider(config)


def _get_claude_login_provider(config: "Config") -> AIProvider:
    try:
        from datalens.ai.providers.claude_login import ClaudeLoginProvider
        return ClaudeLoginProvider(config)
    except ImportError:
        return NoOpProvider(config)
