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

    sample_strategy: str = "reservoir"
    """
    How records are picked when sample_size > 0 (file sources):
    - "reservoir": uniform random sample over the whole file (default; sees new rows
      appended at the end, needed for day-over-day drift).
    - "head": first N records (fastest; biased towards the oldest rows).
    - "tail": last N records (newest rows of append-only feeds).
    """

    sample_seed: int = 42
    """Random seed for reservoir sampling, so repeated runs on the same data are identical."""

    distinct_track_limit: int = 1_000_000
    """
    Exact distinct counting is kept per field up to this many distinct values
    (in memory only, as hashes). Beyond it the count is reported as a lower bound.
    """

    pii_ignore: list[str] = field(default_factory=list)
    """Field patterns ("object.path", wildcards allowed, e.g. "teams.name", "venues.*") never treated as PII."""

    pii_force: dict[str, str] = field(default_factory=dict)
    """Field patterns always treated as PII of the given type, e.g. {"players.contact": "email"}."""

    # Cardinality
    low_cardinality_threshold: int = 50
    """Fields with <= this many distinct values are flagged as low cardinality."""

    # Coverage drift thresholds (dataset/object/field-level %-point variance).
    # Empty dict = feature disabled (existing coverage_changes reporting is unaffected).
    coverage_thresholds: dict[str, Any] = field(default_factory=dict)
    """
    Coverage-change breach thresholds, most to least specific:
    {"dataset": 50.0, "objects": {"Obj": 40.0}, "fields": {"Obj": {"path": 20.0}}}
    """

    report_coverage_reduction_exceeds: bool = True
    """Flag fields whose coverage dropped beyond their resolved threshold."""

    report_coverage_increase_exceeds: bool = True
    """Flag fields whose coverage rose beyond their resolved threshold."""

    expected_schemas: list[str] = field(default_factory=list)
    """BYOS: expected JSON Schema files, "path.json" or "OBJECT=path.json" (see datalens.contract)."""

    drift: dict[str, Any] = field(default_factory=dict)
    """
    Drift rules and comparison mode (see datalens.drift.rules), e.g.
    {"compare_to": "rolling", "defaults": {"row_count": {"drop_pct": 20}},
     "objects": {"orders": {"fields": {"id": {"coverage": {"drop_pct": 5}}}}}}
    """

    # History retention (see history.store.HistoryStore.purge_expired)
    history_retention_days: int = 0
    """Delete saved .history runs older than this many days. 0 = keep forever."""

    history_protected_tags: list[str] = field(default_factory=lambda: ["baseline"])
    """Version tags exempt from retention pruning regardless of age (case-insensitive)."""

    # Output
    out_dir: str = "output"
    """Output directory for generated artifacts."""

    version_tag: str = ""
    """Version tag for this run. Empty = auto-generate timestamp."""

    run_date: str | None = None
    """Logical date of the data (--run-date). Orders history and anchors "1 day / 7 days / 1 month" deltas."""

    # PII
    pii_detection: bool = True
    """Detect PII (field names and values). Off = no PII findings, badges or masking; see docs/SETUP.md."""

    mask_pii: bool = True
    """Whether to mask detected PII in reports."""

    # AI
    ai_provider: str = ""
    """AI provider to use for insights. Empty = disabled."""

    ai_model: str = "auto"
    """
    Model for the AI provider. "auto" (default) lets the provider choose: CLI logins use
    their own default model; API providers use their current default. A model that the
    provider rejects is logged and the call is retried with "auto".
    """

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
        if os.environ.get("DATALENS_PII_DETECTION"):
            self.pii_detection = os.environ.get("DATALENS_PII_DETECTION", "").lower() in (
                "true",
                "1",
                "yes",
            )
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
    env: str | None = None,
    **overrides: Any,
) -> Config:
    """
    Load configuration from file with optional overrides.

    Precedence (lowest to highest):
    1. Defaults (Config dataclass defaults)
    2. Environment variables (DATALENS_* env vars)
    3. Config folder: config.yaml in --config-dir / $DATALENS_CONFIG_DIR, else
       .datalens/ then ~/.datalens/ (see ``datalens.config.home``)
    4. Env-swimlane overlay from the same folder: config-{env}.yaml
       (env = ``env`` arg, else DATALENS_ENV)
    5. Explicit --config file (YAML)
    6. CLI overrides (from --flags)

    Args:
        config_file: Path to YAML config file. None = use defaults.
        secrets_file: Path to YAML secrets file. None = skip secrets.
        connection_config_file: Path to connection config file. None = skip.
        env: Environment swimlane name (e.g. "dev", "staging", "prod"). Selects
            config-{env}.yaml as an overlay on top of the base config. Falls
            back to the DATALENS_ENV env var when not passed explicitly.
        **overrides: Additional overrides (from CLI flags, highest precedence).

    Returns:
        Configured Config instance.
    """
    config_data: dict[str, Any] = {}

    # Step 1: Create config with defaults
    config = Config()

    # Step 2: Apply environment variable overrides
    config.apply_env_overrides()

    # Step 3: Auto-discovered global config + env-swimlane overlay (both optional).
    # Mirrors the secrets auto-discovery below; explicit --config always wins over these.
    for key, value in _load_global_config_defaults().items():
        if hasattr(config, key):
            setattr(config, key, value)

    env = env or os.environ.get("DATALENS_ENV")
    if env:
        for key, value in _load_global_config_defaults(env=env).items():
            if hasattr(config, key):
                setattr(config, key, value)

    # Step 4: Load explicit --config file and merge (overrides everything above)
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

    # Step 5: Apply CLI overrides (highest precedence). A value of None means
    # "not explicitly provided" — skip it so the layers below (auto-discovered
    # config, env vars, dataclass default) aren't clobbered with None.
    for key, value in overrides.items():
        if value is not None and hasattr(config, key):
            setattr(config, key, value)

    if connection_config_file:
        config.connection_config_file = str(connection_config_file)

    return config


def _load_global_config_defaults(env: str | None = None) -> dict[str, Any]:
    """
    The app config from the config folder: ``config[-{env}].yaml`` in --config-dir /
    DATALENS_CONFIG_DIR if set, else ./.datalens/ then ~/.datalens/ (see ``datalens.config.home``).
    Returns {} if none exist. This is what powers env-swimlane config, e.g. config-prod.yaml.
    """
    from datalens.config.home import find_config_file

    suffix = f"-{env}" if env else ""
    path = find_config_file(f"config{suffix}.yaml")
    return _load_yaml(path) if path else {}


def _load_secrets_from_defaults() -> dict[str, Any]:
    """
    ``secrets.yaml`` from the config folder: --config-dir / DATALENS_CONFIG_DIR if set, else
    ./.datalens/ then ~/.datalens/. Returns the first found, or {} if none exist.
    """
    from datalens.config.home import find_config_file

    path = find_config_file("secrets.yaml")
    return _load_yaml(path) if path else {}


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML file, returning empty dict on error."""
    try:
        import yaml

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
