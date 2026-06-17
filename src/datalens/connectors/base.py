"""
Connector ABC — the extension point for adding new data sources.

To add a new source:
1. Create a new module in connectors/ (e.g., postgres.py)
2. Implement the Connector ABC
3. Register it in registry.py

All connectors MUST be:
- Read-only (never write, update, or delete data)
- Streaming (yield records, don't load all into memory)
- Safe (never log secrets or connection strings)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    from datalens.config import Config


@dataclass
class ObjectRef:
    """Reference to a data object (collection, table, file, sheet, etc.)."""

    name: str
    """Object name (collection name, table name, filename, sheet name)."""

    label: str | None = None
    """Optional display label/tag for grouping or identification."""

    query_filter: dict[str, Any] | None = None
    """Optional source-side filter (e.g., MongoDB query, SQL WHERE clause)."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata (indexes, declared types, sizes, etc.)."""


# A record is a dict representing a single document/row
Record = dict[str, Any]


class Connector(ABC):
    """
    Abstract base class for all data source connectors.

    Connectors provide a consistent interface for:
    - Connecting to a data source
    - Listing available objects (collections, tables, files)
    - Sampling records from objects
    - Retrieving counts and metadata
    """

    def __init__(self, source_spec: dict[str, Any], config: "Config") -> None:
        """
        Initialize the connector with source specification and config.

        Args:
            source_spec: Source-specific configuration (paths, URIs, credentials ref).
            config: Global configuration object.
        """
        self.source_spec = source_spec
        self.config = config
        self._connected = False

    @property
    def source_type(self) -> str:
        """Return the source type identifier (e.g., 'file', 'mongodb', 's3')."""
        return self.source_spec.get("source", "unknown")

    @abstractmethod
    def connect(self) -> None:
        """
        Establish connection to the data source.

        Raises:
            ConnectionError: If unable to connect.
        """
        ...

    @abstractmethod
    def list_objects(self) -> list[ObjectRef]:
        """
        List all available objects in the data source.

        For files: list of files/sheets
        For databases: list of collections/tables
        For APIs: list of endpoints/resources

        Returns:
            List of ObjectRef describing available objects.
        """
        ...

    @abstractmethod
    def sample(
        self,
        obj: ObjectRef,
        *,
        sample_size: int | None = None,
        max_depth: int | None = None,
    ) -> Iterator[Record]:
        """
        Yield sampled records from the specified object.

        MUST be:
        - Read-only (no modifications to source)
        - Streaming (yield records, don't buffer all in memory)
        - Bounded (respect sample_size limit)

        Args:
            obj: The object to sample from.
            sample_size: Maximum records to sample. None = use config default.
            max_depth: Maximum nesting depth for nested structures.

        Yields:
            Record dicts (flat or nested).
        """
        ...

    @abstractmethod
    def count(self, obj: ObjectRef) -> int | None:
        """
        Return the total count of records in the object, if available.

        Returns:
            Total record count, or None if count is unavailable/expensive.
        """
        ...

    def metadata(self, obj: ObjectRef) -> dict[str, Any]:
        """
        Return additional metadata about the object.

        Override to provide source-specific metadata (indexes, schema, sizes).

        Args:
            obj: The object to get metadata for.

        Returns:
            Dict of metadata. Empty dict if no metadata available.
        """
        return obj.metadata

    @abstractmethod
    def close(self) -> None:
        """
        Close the connection and release resources.
        """
        ...

    def __enter__(self) -> "Connector":
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
