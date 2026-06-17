"""
HTTP connector wrapper that implements the Connector ABC.

Wraps the lower-level HTTPConnector class to provide a uniform interface.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Iterator

from datalens.connectors.base import Connector, ObjectRef, Record
from datalens.connectors.http import HTTPConnector as HTTPClient

if TYPE_CHECKING:
    from datalens.config import Config

logger = logging.getLogger(__name__)


class HTTPConnector(Connector):
    """HTTP/REST API connector implementing the Connector ABC."""

    def __init__(self, source_spec: dict[str, Any], config: "Config") -> None:
        super().__init__(source_spec, config)
        self._client: HTTPClient | None = None
        self._objects: list[ObjectRef] = []

    def connect(self) -> None:
        """Establish connection to HTTP API."""
        uri = self.source_spec.get("uri")
        if not uri:
            raise ValueError("HTTP source requires 'uri' in source_spec")

        # Extract auth params from source spec
        auth_type = self.source_spec.get("auth_type")
        auth_params = None
        if auth_type:
            auth_params = {
                "auth_type": auth_type,
                "username": self.source_spec.get("username"),
                "password": self.source_spec.get("password"),
                "auth_token": self.source_spec.get("auth_token"),
                "token": self.source_spec.get("token"),
                "api_key": self.source_spec.get("api_key"),
                "key": self.source_spec.get("key"),
                "api_key_header": self.source_spec.get("api_key_header"),
                "header_name": self.source_spec.get("header_name"),
            }
            # Remove None values
            auth_params = {k: v for k, v in auth_params.items() if v is not None}

        # Extract custom headers
        custom_headers = self.source_spec.get("custom_headers")

        # Create HTTP client
        self._client = HTTPClient(
            base_url=uri,
            timeout=float(self.source_spec.get("timeout", 30)),
            max_retries=int(self.source_spec.get("max_retries", 3)),
            auth_params=auth_params,
            custom_headers=custom_headers,
        )

        # Create a single object reference representing the API endpoint
        self._objects = [
            ObjectRef(
                name=uri.split("/")[-1] or "api",
                label=self.source_spec.get("label"),
                metadata={"uri": uri, "type": "http"},
            )
        ]

        self._connected = True
        logger.info(f"Connected to HTTP API: {uri}")

    def list_objects(self) -> list[ObjectRef]:
        """Return list of available objects (API endpoints)."""
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._objects

    def sample(
        self,
        obj: ObjectRef,
        *,
        sample_size: int | None = None,
        max_depth: int | None = None,
    ) -> Iterator[Record]:
        """
        Yield sampled records from HTTP API endpoint.

        For HTTP APIs, this makes a GET request and yields parsed JSON records.
        """
        if not self._client:
            raise RuntimeError("Not connected. Call connect() first.")

        sample_size = sample_size or self.config.sample_size
        path = self.source_spec.get("endpoint", "")

        try:
            # Fetch records from API
            records = self._client.read_records(
                path=path,
                data_key=self.source_spec.get("data_key"),
                max_records=sample_size,
                paginated=self.source_spec.get("paginated", False),
            )

            # Yield records one at a time
            for record in records:
                if isinstance(record, dict):
                    yield record
                else:
                    # Wrap non-dict records
                    yield {"value": record}

        except Exception as e:
            logger.error(f"Error fetching from HTTP API: {e}")
            raise

    def count(self, obj: ObjectRef) -> int | None:
        """Return count of records, if available."""
        # HTTP APIs don't typically provide record counts
        return None

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None
        self._connected = False
