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

    def test_load_with_defaults(self):
        config = load_config()
        assert config.sample_size == 10000

    def test_load_with_overrides(self):
        config = load_config(sample_size=2000, debug=True)
        assert config.sample_size == 2000
        assert config.debug is True
