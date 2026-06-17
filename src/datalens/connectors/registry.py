"""
Connector registry — maps source types to connector classes.

Use get_connector() to get the appropriate connector for a source spec.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from datalens.connectors.base import Connector

if TYPE_CHECKING:
    from datalens.config import Config

# Registry of source type -> connector class
_CONNECTORS: dict[str, type[Connector]] = {}


def register_connector(source_type: str, connector_class: type[Connector]) -> None:
    """Register a connector class for a source type."""
    _CONNECTORS[source_type.lower()] = connector_class


def get_connector(source_spec: dict[str, Any], config: "Config") -> Connector:
    """
    Get the appropriate connector for a source specification.

    Args:
        source_spec: Dict with 'source' key and source-specific config.
        config: Global configuration object.

    Returns:
        Instantiated connector (not yet connected).

    Raises:
        ValueError: If source type is unknown or unsupported.
    """
    source_type = source_spec.get("source", "").lower()

    if not source_type:
        raise ValueError("source_spec must include a 'source' key (e.g., 'file', 'mongodb')")

    if source_type not in _CONNECTORS:
        available = ", ".join(sorted(_CONNECTORS.keys())) or "(none registered)"
        raise ValueError(f"Unknown source type: '{source_type}'. Available: {available}")

    connector_class = _CONNECTORS[source_type]
    return connector_class(source_spec, config)


def list_available_sources() -> list[str]:
    """Return list of registered source types."""
    return sorted(_CONNECTORS.keys())


# Auto-register built-in connectors on import
def _register_builtins() -> None:
    """Register built-in connectors."""
    # Import here to avoid circular imports
    from datalens.connectors.files import FileConnector
    from datalens.connectors.http_connector import HTTPConnector
    from datalens.connectors.mongodb import MongoDBConnector

    register_connector("file", FileConnector)
    register_connector("mongodb", MongoDBConnector)
    register_connector("http", HTTPConnector)


_register_builtins()
