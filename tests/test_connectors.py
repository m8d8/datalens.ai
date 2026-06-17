"""Tests for the Connector ABC and registry."""

import pytest
from datalens.connectors.base import Connector, ObjectRef
from datalens.connectors.registry import get_connector, list_available_sources
from datalens.config import Config


class TestObjectRef:
    """Tests for ObjectRef dataclass."""

    def test_basic_creation(self):
        ref = ObjectRef(name="users")
        assert ref.name == "users"
        assert ref.label is None
        assert ref.query_filter is None

    def test_with_label_and_filter(self):
        ref = ObjectRef(
            name="orders",
            label="ActiveOrders",
            query_filter={"status": "active"},
        )
        assert ref.name == "orders"
        assert ref.label == "ActiveOrders"
        assert ref.query_filter == {"status": "active"}


class TestConnectorRegistry:
    """Tests for connector registry."""

    def test_list_available_sources(self):
        sources = list_available_sources()
        assert "file" in sources
        assert "mongodb" in sources

    def test_get_connector_file(self):
        config = Config()
        source_spec = {"source": "file", "path": "/tmp/test.csv"}
        connector = get_connector(source_spec, config)
        assert connector.source_type == "file"

    def test_get_connector_mongodb(self):
        config = Config()
        source_spec = {"source": "mongodb", "db": "testdb"}
        connector = get_connector(source_spec, config)
        assert connector.source_type == "mongodb"

    def test_get_connector_unknown_raises(self):
        config = Config()
        source_spec = {"source": "unknown_source"}
        with pytest.raises(ValueError, match="Unknown source type"):
            get_connector(source_spec, config)

    def test_get_connector_missing_source_raises(self):
        config = Config()
        source_spec = {}
        with pytest.raises(ValueError, match="must include a 'source' key"):
            get_connector(source_spec, config)
