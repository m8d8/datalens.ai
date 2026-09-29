"""Tests for the Config module."""

import os
import pytest
from datalens.config import Config, load_config


class TestConfig:
    """Tests for Config dataclass."""

    def test_default_values(self):
        config = Config()
        assert config.sample_size == 10000
        assert config.max_depth == 10
        assert config.max_distinct_values == 100
        assert config.low_cardinality_threshold == 50
        assert config.mask_pii is True
        assert config.ai_provider == ""
        assert config.debug is False

    def test_custom_values(self):
        config = Config(
            sample_size=500,
            max_depth=5,
            ai_provider="anthropic",
        )
        assert config.sample_size == 500
        assert config.max_depth == 5
        assert config.ai_provider == "anthropic"

    def test_version_tag_generated(self):
        config = Config()
        assert config.version_tag  # Should be auto-generated timestamp
        assert len(config.version_tag) > 0

    def test_explicit_version_tag(self):
        config = Config(version_tag="v1.0")
        assert config.version_tag == "v1.0"

    def test_get_output_path(self):
        config = Config(out_dir="my_output")
        path = config.get_output_path("subdir", "file.txt")
        assert str(path) == "my_output/subdir/file.txt"


class TestLoadConfig:
    """Tests for config loading."""

    def test_load_with_defaults(self, tmp_path, monkeypatch):
        # Isolate from any real .datalens/config.yaml in the ambient cwd (e.g. the
        # repo's own local dev config), which auto-discovery would otherwise pick up.
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DATALENS_ENV", raising=False)
        config = load_config()
        assert config.sample_size == 10000

    def test_load_with_overrides(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DATALENS_ENV", raising=False)
        config = load_config(sample_size=2000, debug=True)
        assert config.sample_size == 2000
        assert config.debug is True


class TestGlobalConfigSwimlanes:
    """Tests for auto-discovered .datalens/config[-{env}].yaml (Spring-Boot-style)."""

    def test_base_config_auto_discovered(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DATALENS_ENV", raising=False)
        (tmp_path / ".datalens").mkdir()
        (tmp_path / ".datalens" / "config.yaml").write_text("sample_size: 2500\n")

        config = load_config()
        assert config.sample_size == 2500

    def test_no_config_file_means_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DATALENS_ENV", raising=False)
        config = load_config()
        assert config.sample_size == 10000

    def test_env_overlay_wins_over_base(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DATALENS_ENV", raising=False)
        (tmp_path / ".datalens").mkdir()
        (tmp_path / ".datalens" / "config.yaml").write_text("sample_size: 2500\nmax_depth: 5\n")
        (tmp_path / ".datalens" / "config-prod.yaml").write_text("sample_size: 0\n")

        config = load_config(env="prod")
        assert config.sample_size == 0  # overlay wins
        assert config.max_depth == 5  # inherited from base (not in overlay)

    def test_env_from_environment_variable(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".datalens").mkdir()
        (tmp_path / ".datalens" / "config-staging.yaml").write_text("sample_size: 777\n")
        monkeypatch.setenv("DATALENS_ENV", "staging")

        config = load_config()
        assert config.sample_size == 777

    def test_explicit_config_file_wins_over_auto_discovered(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DATALENS_ENV", raising=False)
        (tmp_path / ".datalens").mkdir()
        (tmp_path / ".datalens" / "config.yaml").write_text("sample_size: 2500\n")
        explicit = tmp_path / "explicit.yaml"
        explicit.write_text("sample_size: 999\n")

        config = load_config(config_file=str(explicit))
        assert config.sample_size == 999

    def test_cli_override_wins_over_everything(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DATALENS_ENV", raising=False)
        (tmp_path / ".datalens").mkdir()
        (tmp_path / ".datalens" / "config.yaml").write_text("sample_size: 2500\n")

        config = load_config(sample_size=42)
        assert config.sample_size == 42

    def test_none_override_does_not_clobber_auto_discovered_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DATALENS_ENV", raising=False)
        (tmp_path / ".datalens").mkdir()
        (tmp_path / ".datalens" / "config.yaml").write_text("sample_size: 2500\n")

        # Simulates the CLI passing sample_size=None when the user didn't pass --sample-size.
        config = load_config(sample_size=None, max_depth=None)
        assert config.sample_size == 2500
