"""
MongoDB connector — high-performance, streaming schema analyzer.

Ported from the proven schema_collector.py, stripped of domain-specific concepts.
Supports:
- $sample aggregation for random sampling
- Optional query filters (client-side evaluation for unsupported operators)
- Flexible object specification: collections, "coll|query", "coll|query -> tag"
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, Iterator

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

from datalens.connectors.base import Connector, ObjectRef, Record

if TYPE_CHECKING:
    from datalens.config import Config


class MongoDBConnector(Connector):
    """Connector for MongoDB databases."""

    def __init__(self, source_spec: dict[str, Any], config: "Config") -> None:
        super().__init__(source_spec, config)
        self._client: MongoClient | None = None
        self._db: Any = None
        self._objects: list[ObjectRef] = []

    def connect(self) -> None:
        """Connect to MongoDB using connection string from config or environment."""
        # Get connection string (order: source_spec > env > config > default)
        uri = self.source_spec.get("uri")
        if not uri:
            uri = os.environ.get("DATALENS_MONGO_URI")
        if not uri:
            uri = os.environ.get("MDB_MCP_CONNECTION_STRING")
        if not uri:
            uri = self.config.secrets.get("mongodb", {}).get("uri")
        if not uri:
            # Build from components
            host = os.environ.get("MONGO_HOST", "localhost")
            port = os.environ.get("MONGO_PORT", "27017")
            uri = f"mongodb://{host}:{port}"

        db_name = self.source_spec.get("db")
        if not db_name:
            raise ValueError("MongoDB source requires 'db' in source_spec")

        try:
            self._client = MongoClient(
                uri,
                connectTimeoutMS=int(os.environ.get("MONGO_CONNECTION_TIMEOUT", 30000)),
                socketTimeoutMS=int(os.environ.get("MONGO_SOCKET_TIMEOUT", 60000)),
            )
            # Verify connection
            self._client.admin.command("ping")
            self._db = self._client[db_name]
            self._connected = True
        except (ConnectionFailure, OperationFailure) as e:
            raise ConnectionError(f"Failed to connect to MongoDB: {e}") from e

        # Parse objects from source_spec
        self._objects = self._parse_objects()

    def _parse_objects(self) -> list[ObjectRef]:
        """Parse object specifications from source_spec."""
        objects: list[ObjectRef] = []

        # Option 1: simple collection list
        collections = self.source_spec.get("collections")
        if collections:
            if isinstance(collections, str):
                collections = [c.strip() for c in collections.split(",")]
            for coll in collections:
                objects.append(ObjectRef(name=coll))
            return objects

        # Option 2: detailed object specs (supports "coll|query -> tag")
        obj_specs = self.source_spec.get("objects")
        if obj_specs:
            if isinstance(obj_specs, str):
                obj_specs = [obj_specs]
            for spec in obj_specs:
                obj_ref = self._parse_object_spec(spec)
                objects.append(obj_ref)
            return objects

        # Option 3: list all collections in database
        if self._db is not None:
            for coll_name in self._db.list_collection_names():
                if not coll_name.startswith("system."):
                    objects.append(ObjectRef(name=coll_name))

        return objects

    def _parse_object_spec(self, spec: str) -> ObjectRef:
        """
        Parse object spec string.

        Formats:
        - "collection_name"
        - "collection_name|{query_json}"
        - "collection_name|{query_json} -> tag_name"
        - "collection_name -> tag_name"
        """
        spec = spec.strip()
        label = None
        query_filter: dict[str, Any] = {}

        # Extract tag if present
        if " -> " in spec:
            spec, label = spec.rsplit(" -> ", 1)
            label = label.strip()
            spec = spec.strip()

        # Extract query if present
        if "|" in spec:
            coll_name, query_str = spec.split("|", 1)
            coll_name = coll_name.strip()
            query_str = query_str.strip()
            if query_str:
                try:
                    query_filter = json.loads(query_str)
                except json.JSONDecodeError:
                    pass  # Invalid JSON, ignore filter
        else:
            coll_name = spec

        return ObjectRef(name=coll_name, label=label, query_filter=query_filter or None)

    def list_objects(self) -> list[ObjectRef]:
        """Return list of collections/objects to analyze."""
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
        Yield sampled documents from the collection.

        Uses $sample aggregation for random sampling. If query_filter is specified
        and contains only server-supported operators, it's pushed to the server;
        otherwise, client-side filtering is applied.

        If sample_size is 0, performs a full scan (no sampling limit).
        """
        if not self._connected or self._db is None:
            raise RuntimeError("Not connected. Call connect() first.")

        # Get sample_size: None means use config default, 0 means full scan
        if sample_size is None:
            sample_size = self.config.sample_size

        collection = self._db[obj.name]
        query = obj.query_filter or {}

        # Full scan mode (sample_size=0): iterate all documents without $sample
        if sample_size == 0:
            if query:
                cursor = collection.find(query)
            else:
                cursor = collection.find({})

            for doc in cursor:
                # Remove MongoDB _id field
                doc.pop("_id", None)
                yield doc
            return

        # Sampling mode: use $sample aggregation
        # Determine if query can be pushed to server
        if query and self._is_server_supported_filter(query):
            # Push filter to server
            pipeline = [
                {"$match": query},
                {"$sample": {"size": sample_size}},
            ]
            cursor = collection.aggregate(pipeline)
        elif query:
            # Need client-side filtering
            pipeline = [{"$sample": {"size": sample_size * 3}}]  # Oversample
            cursor = collection.aggregate(pipeline)
        else:
            # No filter
            pipeline = [{"$sample": {"size": sample_size}}]
            cursor = collection.aggregate(pipeline)

        count = 0
        for doc in cursor:
            # Apply client-side filter if needed
            if query and not self._is_server_supported_filter(query):
                if not self._matches_filter(doc, query):
                    continue

            # Remove MongoDB _id field
            doc.pop("_id", None)

            yield doc
            count += 1
            if count >= sample_size:
                break

    def _is_server_supported_filter(self, query: dict[str, Any]) -> bool:
        """Check if query uses only server-supported operators."""
        # These operators work in $match stage
        supported_ops = {"$exists", "$in", "$nin", "$ne", "$eq", "$gt", "$gte", "$lt", "$lte"}

        for _key, value in query.items():
            if isinstance(value, dict):
                for op in value:
                    if op.startswith("$") and op not in supported_ops:
                        return False
            elif isinstance(value, (list, dict)):
                return False  # Complex value, filter client-side

        return True

    def _matches_filter(self, doc: dict[str, Any], query: dict[str, Any]) -> bool:
        """Evaluate query filter client-side."""
        for key, expected in query.items():
            actual = self._get_path_value(doc, key)

            if isinstance(expected, dict):
                for op, op_value in expected.items():
                    if not self._evaluate_operator(actual, op, op_value):
                        return False
            else:
                if actual != expected:
                    return False

        return True

    def _get_path_value(self, doc: Any, path: str) -> Any:
        """Get value at dotted path in document."""
        current = doc
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    def _evaluate_operator(self, actual: Any, operator: str, expected: Any) -> bool:
        """Evaluate a query operator."""
        if operator == "$exists":
            exists = actual is not None
            return exists is bool(expected)
        if operator == "$in":
            if isinstance(actual, list):
                return any(item in expected for item in actual)
            return actual in expected
        if operator == "$nin":
            if isinstance(actual, list):
                return all(item not in expected for item in actual)
            return actual not in expected
        if operator == "$ne":
            return actual != expected
        if operator == "$eq":
            return actual == expected
        if operator == "$gt":
            return actual is not None and actual > expected
        if operator == "$gte":
            return actual is not None and actual >= expected
        if operator == "$lt":
            return actual is not None and actual < expected
        if operator == "$lte":
            return actual is not None and actual <= expected
        return False

    def count(self, obj: ObjectRef) -> int | None:
        """Return estimated document count in collection."""
        if not self._connected or self._db is None:
            raise RuntimeError("Not connected. Call connect() first.")

        collection = self._db[obj.name]

        if obj.query_filter:
            # Count with filter (can be slow for large collections)
            return collection.count_documents(obj.query_filter, limit=1000000)
        else:
            # Fast estimated count
            return collection.estimated_document_count()

    def metadata(self, obj: ObjectRef) -> dict[str, Any]:
        """Return collection metadata (indexes, stats)."""
        if not self._connected or self._db is None:
            return {}

        collection = self._db[obj.name]
        result = dict(obj.metadata)

        try:
            # Get indexes
            indexes = list(collection.list_indexes())
            result["indexes"] = [
                {"name": idx.get("name"), "keys": list(idx.get("key", {}).keys())}
                for idx in indexes
            ]
        except Exception:
            pass

        try:
            # Get collection stats
            stats = self._db.command("collStats", obj.name)
            result["size_bytes"] = stats.get("size")
            result["doc_count"] = stats.get("count")
            result["avg_doc_size"] = stats.get("avgObjSize")
        except Exception:
            pass

        return result

    def close(self) -> None:
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
        self._db = None
        self._objects = []
        self._connected = False
