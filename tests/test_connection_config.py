"""Tests for connection config loading and management."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from datalens.config import ConnectionConfig, ConnectionLoader


class TestConnectionLoader:
    """Tests for ConnectionLoader class."""

    def test_load_connection_from_project_dir(self, tmp_path: Path) -> None:
        """Test loading connection from .datalens/connections/ in project root."""
        # Create .datalens/connections/ structure
        project_connections = tmp_path / ".datalens" / "connections"
        project_connections.mkdir(parents=True)

        config_file = project_connections / "mydb.yaml"
        config_file.write_text(
            "name: mydb\n"
            "source_type: mongodb\n"
            "params:\n"
            "  uri: mongodb://localhost:27017\n"
            "  db: testdb\n"
        )

        loader = ConnectionLoader(project_root=tmp_path)
        config = loader.load_connection("mydb")

        assert config.name == "mydb"
        assert config.source_type == "mongodb"
        assert config.params["uri"] == "mongodb://localhost:27017"
        assert config.params["db"] == "testdb"

    def test_load_connection_from_full_path(self, tmp_path: Path) -> None:
        """Test loading connection from full file path."""
        config_file = tmp_path / "my_config.yaml"
        config_file.write_text(
            "name: test_config\n"
            "source_type: http\n"
            "params:\n"
            "  uri: https://api.example.com\n"
        )

        loader = ConnectionLoader()
        config = loader.load_connection(str(config_file))

        assert config.name == "test_config"
        assert config.source_type == "http"

    def test_load_connection_not_found_raises_error(self) -> None:
        """Test that loading non-existent connection raises FileNotFoundError."""
        loader = ConnectionLoader()
        with pytest.raises(FileNotFoundError, match="Connection config 'nonexistent' not found"):
            loader.load_connection("nonexistent")

    def test_load_connection_filename_mismatch_raises_error(self, tmp_path: Path) -> None:
        """Test that filename must match connection name."""
        project_connections = tmp_path / ".datalens" / "connections"
        project_connections.mkdir(parents=True)

        config_file = project_connections / "wrong_name.yaml"
        config_file.write_text(
            "name: mydb\n"
            "source_type: mongodb\n"
            "params:\n"
            "  uri: mongodb://localhost\n"
        )

        loader = ConnectionLoader(project_root=tmp_path)
        with pytest.raises(ValueError, match="filename .* doesn't match name"):
            loader.load_connection("wrong_name")

    def test_env_var_substitution_in_params(self, tmp_path: Path) -> None:
        """Test environment variable substitution in connection params."""
        os.environ["TEST_MONGO_URI"] = "mongodb+srv://prod:secret@cluster.mongodb.net"

        project_connections = tmp_path / ".datalens" / "connections"
        project_connections.mkdir(parents=True)

        config_file = project_connections / "mydb.yaml"
        config_file.write_text(
            "name: mydb\n"
            "source_type: mongodb\n"
            "params:\n"
            "  uri: ${TEST_MONGO_URI}\n"
            "  db: analytics\n"
        )

        loader = ConnectionLoader(project_root=tmp_path)
        config = loader.load_connection("mydb")

        assert config.params["uri"] == "mongodb+srv://prod:secret@cluster.mongodb.net"
        assert config.params["db"] == "analytics"

    def test_env_var_substitution_missing_raises_error(self, tmp_path: Path) -> None:
        """Test that missing environment variable raises helpful error."""
        project_connections = tmp_path / ".datalens" / "connections"
        project_connections.mkdir(parents=True)

        config_file = project_connections / "mydb.yaml"
        config_file.write_text(
            "name: mydb\n"
            "source_type: mongodb\n"
            "params:\n"
            "  uri: ${MISSING_VAR}\n"
        )

        loader = ConnectionLoader(project_root=tmp_path)
        with pytest.raises(ValueError, match="Environment variable 'MISSING_VAR' not found"):
            loader.load_connection("mydb")

    def test_list_connections_empty(self, tmp_path: Path) -> None:
        """Test listing connections when none exist."""
        loader = ConnectionLoader(project_root=tmp_path)
        connections = loader.list_connections()
        assert connections == []

    def test_list_connections_from_project_dir(self, tmp_path: Path) -> None:
        """Test listing connections from project directory."""
        project_connections = tmp_path / ".datalens" / "connections"
        project_connections.mkdir(parents=True)

        # Create two connection configs
        (project_connections / "mongo.yaml").write_text(
            "name: mongo\nsource_type: mongodb\nparams: {}"
        )
        (project_connections / "api.yaml").write_text(
            "name: api\nsource_type: http\nparams: {}"
        )

        loader = ConnectionLoader(project_root=tmp_path)
        connections = loader.list_connections()

        assert len(connections) == 2
        names = {c[0] for c in connections}
        assert names == {"mongo", "api"}

    def test_connection_config_with_metadata(self, tmp_path: Path) -> None:
        """Test loading connection config with metadata."""
        project_connections = tmp_path / ".datalens" / "connections"
        project_connections.mkdir(parents=True)

        config_file = project_connections / "mydb.yaml"
        config_file.write_text(
            "name: mydb\n"
            "source_type: mongodb\n"
            "params:\n"
            "  uri: mongodb://localhost\n"
            "metadata:\n"
            "  created: '2026-06-11'\n"
            "  tags:\n"
            "    - production\n"
            "    - analytics\n"
        )

        loader = ConnectionLoader(project_root=tmp_path)
        config = loader.load_connection("mydb")

        assert config.metadata["created"] == "2026-06-11"
        assert config.metadata["tags"] == ["production", "analytics"]

    def test_connection_config_recursive_env_var_substitution(
        self, tmp_path: Path
    ) -> None:
        """Test environment variable substitution in nested params."""
        os.environ["API_KEY"] = "secret_key_123"
        os.environ["API_URL"] = "https://api.example.com"

        project_connections = tmp_path / ".datalens" / "connections"
        project_connections.mkdir(parents=True)

        config_file = project_connections / "myapi.yaml"
        config_file.write_text(
            "name: myapi\n"
            "source_type: http\n"
            "params:\n"
            "  uri: ${API_URL}/data\n"
            "  auth_type: api_key\n"
            "  api_key: ${API_KEY}\n"
            "  custom_headers:\n"
            "    Authorization: Bearer ${API_KEY}\n"
        )

        loader = ConnectionLoader(project_root=tmp_path)
        config = loader.load_connection("myapi")

        assert config.params["uri"] == "https://api.example.com/data"
        assert config.params["api_key"] == "secret_key_123"
        assert config.params["custom_headers"]["Authorization"] == "Bearer secret_key_123"

    def test_connection_loader_caching(self, tmp_path: Path) -> None:
        """Test that ConnectionLoader caches loaded configs."""
        project_connections = tmp_path / ".datalens" / "connections"
        project_connections.mkdir(parents=True)

        config_file = project_connections / "mydb.yaml"
        config_file.write_text(
            "name: mydb\nsource_type: mongodb\nparams: {uri: mongodb://localhost}"
        )

        loader = ConnectionLoader(project_root=tmp_path)

        # Load twice - second should use cache
        config1 = loader.load_connection("mydb")
        config2 = loader.load_connection("mydb")

        assert config1 is config2  # Same object from cache

    def test_connection_with_type_alias(self, tmp_path: Path) -> None:
        """Test that 'type' key alias works for 'source_type'."""
        project_connections = tmp_path / ".datalens" / "connections"
        project_connections.mkdir(parents=True)

        config_file = project_connections / "mydb.yaml"
        config_file.write_text(
            "name: mydb\n"
            "type: mongodb\n"  # Using 'type' instead of 'source_type'
            "params:\n"
            "  uri: mongodb://localhost\n"
        )

        loader = ConnectionLoader(project_root=tmp_path)
        config = loader.load_connection("mydb")

        assert config.source_type == "mongodb"

    def test_invalid_yaml_raises_error(self, tmp_path: Path) -> None:
        """Test that invalid YAML raises helpful error."""
        project_connections = tmp_path / ".datalens" / "connections"
        project_connections.mkdir(parents=True)

        config_file = project_connections / "mydb.yaml"
        config_file.write_text(
            "name: mydb\n"
            "source_type: mongodb\n"
            "params: [unclosed bracket\n"
        )

        loader = ConnectionLoader(project_root=tmp_path)
        with pytest.raises(ValueError, match="Failed to parse"):
            loader.load_connection("mydb")

    def test_connection_config_missing_name_raises_error(self, tmp_path: Path) -> None:
        """Test that connection config missing 'name' raises error."""
        project_connections = tmp_path / ".datalens" / "connections"
        project_connections.mkdir(parents=True)

        config_file = project_connections / "mydb.yaml"
        config_file.write_text(
            "source_type: mongodb\n"
            "params:\n"
            "  uri: mongodb://localhost\n"
        )

        loader = ConnectionLoader(project_root=tmp_path)
        with pytest.raises(ValueError, match="missing 'name'"):
            loader.load_connection("mydb")

    def test_connection_config_missing_source_type_raises_error(self, tmp_path: Path) -> None:
        """Test that connection config missing 'source_type' raises error."""
        project_connections = tmp_path / ".datalens" / "connections"
        project_connections.mkdir(parents=True)

        config_file = project_connections / "mydb.yaml"
        config_file.write_text(
            "name: mydb\n"
            "params:\n"
            "  uri: mongodb://localhost\n"
        )

        loader = ConnectionLoader(project_root=tmp_path)
        with pytest.raises(ValueError, match="missing 'source_type'"):
            loader.load_connection("mydb")
