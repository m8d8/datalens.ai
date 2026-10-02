"""
Where Datalens looks for its config folder.

A config folder has this layout (every file is optional)::

    <config dir>/
      config.yaml            app defaults (same keys as -c / --config)
      config-<env>.yaml      overlay for --env <env> (dev, staging, prod, ...)
      secrets.yaml           API keys and credentials (keep out of git)
      .env                   values for ${VAR} placeholders in connection configs
      connections/<name>.yaml  one file per data source (--cc <name>)

Lookup order:

1. ``--config-dir PATH`` or ``DATALENS_CONFIG_DIR``: **only** that folder is used, so a project's own
   ``.datalens/`` can't leak into the run.
2. Otherwise ``./.datalens/`` (project-local), then ``~/.datalens/`` (user-global). The first folder that
   has the file wins.

Single files can still be passed directly: ``-c config.yaml``, ``--secrets secrets.yaml``, ``--cc path.yaml``.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_VAR = "DATALENS_CONFIG_DIR"


def explicit_config_dir() -> Path | None:
    """The folder set with --config-dir / DATALENS_CONFIG_DIR, or None."""
    value = (os.environ.get(ENV_VAR) or "").strip()
    return Path(value).expanduser() if value else None


def config_dirs(project_root: Path | None = None) -> list[Path]:
    """Config folders to search, highest priority first."""
    explicit = explicit_config_dir()
    if explicit is not None:
        return [explicit]
    root = project_root or Path.cwd()
    return [root / ".datalens", Path.home() / ".datalens"]


def find_config_file(relative: str, project_root: Path | None = None) -> Path | None:
    """First existing ``<config dir>/<relative>`` in lookup order, or None."""
    for folder in config_dirs(project_root):
        path = folder / relative
        if path.is_file():
            return path
    return None


def default_init_dir() -> Path:
    """Where `datalens init` writes when no folder is given."""
    return explicit_config_dir() or Path.home() / ".datalens"
