"""
Config dataclass and loading utilities.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Config:
    """
    Configuration for Datalens analysis runs.

    All values have sensible defaults; override via:
    - Constructor kwargs (from CLI)
    - Config file (YAML)
    - Environment variables (DATALENS_*)
    """

    # Sampling
    sample_size: int = 10000
    """Number of records to sample per object. 0 = full scan (no sampling)."""

    max_depth: int = 10
    """Maximum nesting depth to traverse."""

    max_array_depth: int = 3
    """Maximum depth of nested arrays to traverse."""

    max_array_items: int = 100
    """Maximum array elements to process (0 = unlimited)."""

    max_distinct_values: int = 100
    """Maximum distinct values to track per field."""

    max_examples: int = 5
    """Maximum example values to store per field."""

    sample_records_count: int = 3
    """Number of full sample records to include in output."""

    # Cardinality
    low_cardinality_threshold: int = 50
    """Fields with <= this many distinct values are flagged as low cardinality."""

    # Output
    out_dir: str = "output"
    """Output directory for generated artifacts."""

    version_tag: str = ""
    """Version tag for this run. Empty = auto-generate timestamp."""

    # PII
    mask_pii: bool = True
    """Whether to mask detected PII in reports."""

    # AI
    ai_provider: str = ""
    """AI provider to use for insights. Empty = disabled."""

    # Connection config
    connection_config_file: str | None = None
    """Path to connection config file (for storing reusable credentials)."""

    # Secrets (loaded from secrets file, not stored in config file)
    secrets: dict[str, Any] = field(default_factory=dict)
    """Secrets (database credentials, API keys). Not persisted to config files."""

    # Debug
    debug: bool = False
    """Enable debug mode with verbose output."""

    def __post_init__(self) -> None:
        """Generate version_tag if needed. Env var overrides are applied via apply_env_overrides()."""
        # Generate version tag if not provided
        if not self.version_tag:
            self.version_tag = datetime.now().strftime("%Y%m%d_%H%M%S")

    def apply_env_overrides(self) -> None:
        """
        Apply environment variable overrides to current config.

        Env vars have lower precedence than constructor/config values.
        Use only if explicitly needed for env-based configuration.
        """
        # Only apply env var if key is not already set (check against defaults)
        if os.environ.get("DATALENS_SAMPLE_SIZE"):
            self.sample_size = int(os.environ.get("DATALENS_SAMPLE_SIZE"))
        if os.environ.get("DATALENS_MAX_DEPTH"):
            self.max_depth = int(os.environ.get("DATALENS_MAX_DEPTH"))
        if os.environ.get("DATALENS_MAX_DISTINCT"):
            self.max_distinct_values = int(os.environ.get("DATALENS_MAX_DISTINCT"))
        if os.environ.get("DATALENS_LOW_CARDINALITY_THRESHOLD"):
            self.low_cardinality_threshold = int(
                os.environ.get("DATALENS_LOW_CARDINALITY_THRESHOLD")
            )
        if os.environ.get("DATALENS_OUT_DIR"):
            self.out_dir = os.environ.get("DATALENS_OUT_DIR")
        if os.environ.get("DATALENS_MASK_PII"):
            self.mask_pii = os.environ.get("DATALENS_MASK_PII", "").lower() in (
                "true",
                "1",
                "yes",
            )
        if os.environ.get("DATALENS_AI_PROVIDER"):
            self.ai_provider = os.environ.get("DATALENS_AI_PROVIDER")
        if os.environ.get("DATALENS_DEBUG"):
            self.debug = os.environ.get("DATALENS_DEBUG", "").lower() in (
                "true",
                "1",
                "yes",
            )

    def get_output_path(self, *parts: str) -> Path:
        """Get a path within the output directory."""
        path = Path(self.out_dir)
        for part in parts:
            path = path / part
        return path


def load_config(
    config_file: str | Path | None = None,
    secrets_file: str | Path | None = None,
    connection_config_file: str | Path | None = None,
    **overrides: Any,
) -> Config:
    """
    Load configuration from file with optional overrides.

    Precedence (lowest to highest):
    1. Defaults (Config dataclass defaults)
    2. Environment variables (DATALENS_* env vars)
    3. Config file (YAML)
    4. CLI overrides (from --flags)

    Args:
        config_file: Path to YAML config file. None = use defaults.
        secrets_file: Path to YAML secrets file. None = skip secrets.
        connection_config_file: Path to connection config file. None = skip.
        **overrides: Additional overrides (from CLI flags, highest precedence).

    Returns:
        Configured Config instance.
    """
    config_data: dict[str, Any] = {}

    # Step 1: Create config with defaults
    config = Config()

    # Step 2: Apply environment variable overrides
    config.apply_env_overrides()

    # Step 3: Load config file and merge (overrides env vars)
    if config_file:
        config_path = Path(config_file)
        if config_path.exists():
            config_data = _load_yaml(config_path)
            # Update config with file values
            for key, value in config_data.items():
                if hasattr(config, key):
                    setattr(config, key, value)

    # Load secrets file (from provided path, or search standard locations)
    secrets: dict[str, Any] = {}
    if secrets_file:
        # Explicit path provided: use it or fail
        secrets_path = Path(secrets_file)
        if secrets_path.exists():
            secrets = _load_yaml(secrets_path)
    else:
        # Search standard locations
        secrets = _load_secrets_from_defaults()
    config.secrets = secrets

    # Step 4: Apply CLI overrides (highest precedence)
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)

    if connection_config_file:
        config.connection_config_file = str(connection_config_file)

    return config


def _load_secrets_from_defaults() -> dict[str, Any]:
    """
    Search for secrets file in standard locations (in order):
    1. .datalens/secrets.yaml (project-local)
    2. ~/.datalens/secrets.yaml (user-global)

    Returns first found, or empty dict if none exist.
    """
    search_paths = [
        Path(".datalens/secrets.yaml"),
        Path.home() / ".datalens" / "secrets.yaml",
    ]

    for path in search_paths:
        if path.exists():
            return _load_yaml(path)

    return {}


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML file, returning empty dict on error."""
    try:
        import yaml

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
