"""
Connection configuration loading and management.

Supports loading connection configs from:
- Full file paths
- .datalens/connections/ (project-local, checked first)
- ~/.datalens/connections/ (user-global, fallback)

Environment variable substitution: ${VAR_NAME} syntax.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ConnectionConfig:
    """Loaded connection configuration."""

    name: str
    source_type: str
    params: dict[str, Any]
    metadata: dict[str, Any] | None = None


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
        1. If name_or_path contains '/', treat as full path
        2. Check .datalens/connections/{name}.yaml (project-local)
        3. Check ~/.datalens/connections/{name}.yaml (user-global)

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

        is_full_path = "/" in name_or_path or "\\" in name_or_path
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
        connections = []

        # Check project-local
        project_dir = self.project_root / ".datalens" / "connections"
        if project_dir.exists():
            for file in project_dir.glob("*.yaml"):
                if file.is_file() and not file.name.startswith("_"):
                    try:
                        config = self._load_connection_file(file)
                        connections.append((config.name, config.source_type))
                    except Exception:
                        pass

        # Check user-global
        user_dir = Path.home() / ".datalens" / "connections"
        if user_dir.exists():
            for file in user_dir.glob("*.yaml"):
                if file.is_file() and not file.name.startswith("_"):
                    try:
                        config = self._load_connection_file(file)
                        # Skip if already found in project-local
                        if not any(c[0] == config.name for c in connections):
                            connections.append((config.name, config.source_type))
                    except Exception:
                        pass

        return sorted(connections)

    def _resolve_config_path(self, name_or_path: str) -> Path | None:
        """Resolve config path from name or full path."""
        # If it contains /, treat as full path
        if "/" in name_or_path or "\\" in name_or_path:
            path = Path(name_or_path)
            return path if path.exists() else None

        # Try project-local
        project_path = self.project_root / ".datalens" / "connections" / f"{name_or_path}.yaml"
        if project_path.exists():
            return project_path

        # Try user-global
        user_path = Path.home() / ".datalens" / "connections" / f"{name_or_path}.yaml"
        if user_path.exists():
            return user_path

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

        return ConnectionConfig(name=name, source_type=source_type, params=params, metadata=metadata)

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
                # Check .env file in project root (optional)
                env_file = self.project_root / ".env"
                if env_file.exists():
                    value = self._load_env_file_var(env_file, var_name)
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
        project_path = self.project_root / ".datalens" / "connections" / f"{name_or_path}.yaml"
        user_path = Path.home() / ".datalens" / "connections" / f"{name_or_path}.yaml"

        msg = f"Connection config '{name_or_path}' not found.\n"
        msg += f"Create it at:\n"
        msg += f"  - {project_path} (project-local), or\n"
        msg += f"  - {user_path} (user-global)\n"
        msg += f"\nOr pass a full file path with --cc /path/to/config.yaml"

        raise FileNotFoundError(msg)
