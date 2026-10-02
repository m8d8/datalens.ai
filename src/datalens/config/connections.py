"""
Connection configuration loading and management.

Supports loading connection configs from:
- File paths (--cc path/to/name.yaml)
- <config dir>/connections/<name>.yaml, where the config dir is --config-dir / $DATALENS_CONFIG_DIR
  if set, else .datalens/ (project-local) then ~/.datalens/ (user-global). See ``datalens.config.home``.

Environment variable substitution: ${VAR_NAME} syntax.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from datalens.config.home import config_dirs


@dataclass
class ConnectionConfig:
    """Loaded connection configuration."""

    name: str
    source_type: str
    params: dict[str, Any]
    metadata: dict[str, Any] | None = None
    profiling: dict[str, Any] | None = None
    drift: dict[str, Any] | None = None
    history: dict[str, Any] | None = None
    expected_schema: str | list[str] | None = None
    """BYOS: expected JSON Schema file(s) for this source ("path.json" or "OBJECT=path.json")."""

    def __post_init__(self) -> None:
        if self.profiling is None:
            self.profiling = {}
        if self.drift is None:
            self.drift = {}
        if self.history is None:
            self.history = {}


class ConnectionLoader:
    """Load and resolve connection configs from various locations."""

    def __init__(self, project_root: Path | None = None):
        """
        Initialize loader.

        Args:
            project_root: Project root for .datalens/ location. Defaults to cwd.
        """
        self.project_root = project_root or Path.cwd()
        self._cache: dict[str, ConnectionConfig] = {}

    def load_connection(self, name_or_path: str) -> ConnectionConfig:
        """
        Load a connection config.

        Lookup order:
        1. If name_or_path contains '/' (or ends in .yaml/.yml), treat as a file path
        2. <config dir>/connections/{name}.yaml, where the config dir is --config-dir /
           $DATALENS_CONFIG_DIR if set, else .datalens/ then ~/.datalens/

        Args:
            name_or_path: Connection name or full file path.

        Returns:
            Loaded ConnectionConfig.

        Raises:
            FileNotFoundError: Connection config not found.
            ValueError: Invalid connection config format.
        """
        if name_or_path in self._cache:
            return self._cache[name_or_path]

        is_full_path = self._is_path(name_or_path)
        path = self._resolve_config_path(name_or_path)
        if not path:
            self._raise_connection_not_found(name_or_path)

        # Only enforce strict filename checking for .datalens lookups, not full paths
        config = self._load_connection_file(path, strict_filename_check=not is_full_path)
        self._cache[name_or_path] = config
        return config

    def list_connections(self) -> list[tuple[str, str]]:
        """
        List available connections.

        Returns:
            List of (name, source_type) tuples.
        """
        connections: list[tuple[str, str]] = []
        for folder in config_dirs(self.project_root):
            conn_dir = folder / "connections"
            if not conn_dir.is_dir():
                continue
            for file in sorted(conn_dir.glob("*.yaml")):
                if file.is_file() and not file.name.startswith("_"):
                    # read name/type only: listing must not need ${VAR}s to be set
                    try:
                        import yaml

                        data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
                    except Exception:
                        continue
                    name, source_type = data.get("name"), data.get("source_type") or data.get("type")
                    # a name found in a higher-priority folder wins
                    if name and source_type and not any(c[0] == name for c in connections):
                        connections.append((name, source_type))

        return sorted(connections)

    @staticmethod
    def _is_path(name_or_path: str) -> bool:
        return ("/" in name_or_path or "\\" in name_or_path
                or name_or_path.endswith((".yaml", ".yml")))

    def _resolve_config_path(self, name_or_path: str) -> Path | None:
        """Resolve config path from name or file path."""
        if self._is_path(name_or_path):
            path = Path(name_or_path).expanduser()
            return path if path.exists() else None
        for folder in config_dirs(self.project_root):
            path = folder / "connections" / f"{name_or_path}.yaml"
            if path.exists():
                return path
        return None

    def _load_connection_file(self, path: Path, strict_filename_check: bool = True) -> ConnectionConfig:
        """Load connection config from YAML file.

        Args:
            path: Path to config file
            strict_filename_check: If True, filename must match config name.
                Only enforced for .datalens/ lookups.
        """
        import yaml

        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to parse {path}: {e}") from e

        if not isinstance(data, dict):
            raise ValueError(f"Connection config must be a YAML dict, got {type(data).__name__}")

        name = data.get("name")
        source_type = data.get("source_type") or data.get("type")
        params = data.get("params", {})
        metadata = data.get("metadata")
        profiling = data.get("profiling") or {}
        drift = data.get("drift") or {}
        history = data.get("history") or {}
        expected_schema = data.get("expected_schema") or data.get("schema")

        if not name:
            raise ValueError(f"Connection config {path} missing 'name'")
        if not source_type:
            raise ValueError(f"Connection config {path} missing 'source_type' or 'type'")

        # Filename must match name (without .yaml) only for strict checks
        if strict_filename_check and path.stem != name:
            raise ValueError(
                f"Connection config filename {path.name} doesn't match name '{name}'. "
                f"Rename file to {name}.yaml or change name in config."
            )

        # Substitute environment variables
        params = self._substitute_env_vars(params)

        return ConnectionConfig(
            name=name,
            source_type=source_type,
            params=params,
            metadata=metadata,
            profiling=profiling,
            drift=drift,
            history=history,
            expected_schema=self._substitute_env_vars(expected_schema) if expected_schema else None,
        )

    def _substitute_env_vars(self, obj: Any) -> Any:
        """Recursively substitute ${VAR} environment variables in object."""
        if isinstance(obj, str):
            return self._substitute_env_vars_in_string(obj)
        elif isinstance(obj, dict):
            return {k: self._substitute_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_env_vars(v) for v in obj]
        else:
            return obj

    def _substitute_env_vars_in_string(self, s: str) -> str:
        """Substitute ${VAR_NAME} with environment variable value."""

        def replacer(match: Any) -> str:
            var_name = match.group(1)
            value = os.environ.get(var_name)
            if value is None:
                # Check .env files (optional): the config folder(s), then the project root
                for env_file in [d / ".env" for d in config_dirs(self.project_root)] + [self.project_root / ".env"]:
                    if env_file.exists():
                        value = self._load_env_file_var(env_file, var_name)
                        if value is not None:
                            break
                if value is None:
                    raise ValueError(
                        f"Environment variable '{var_name}' not found. "
                        f"Set it with: export {var_name}=value"
                    )
            return value

        return re.sub(r"\$\{([^}]+)\}", replacer, s)

    def _load_env_file_var(self, env_file: Path, var_name: str) -> str | None:
        """Load variable from .env file."""
        try:
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#") or not line:
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        if key.strip() == var_name:
                            return value.strip()
        except Exception:
            pass
        return None

    def _raise_connection_not_found(self, name_or_path: str) -> None:
        """Raise helpful error for missing connection."""
        if self._is_path(name_or_path):
            raise FileNotFoundError(f"Connection config file not found: {name_or_path}")
        searched = "\n".join(f"  - {d / 'connections' / (name_or_path + '.yaml')}"
                              for d in config_dirs(self.project_root))
        raise FileNotFoundError(
            f"Connection config '{name_or_path}' not found. Looked in:\n{searched}\n\n"
            f"Create it with:  datalens connection-new {name_or_path} --source file --path <data>\n"
            f"Or pass a file path: --cc /path/to/{name_or_path}.yaml   ·   Folder in use: datalens config-show"
        )
