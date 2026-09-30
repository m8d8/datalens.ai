"""
Google BigQuery connector — profile tables, views and queries (read-only).

    datalens analyze --source bigquery --project my-proj --dataset sales --collections orders,customers
    datalens analyze --source bigquery --project my-proj --dataset sales \\
        --object "orders|order_date >= '2026-01-01' -> orders_2026" \\
        --object "query:SELECT * FROM sales.orders o JOIN sales.refunds r USING (order_id) -> refunds"

Source spec keys: ``project`` (default: the credentials' project), ``dataset``,
``collections`` / ``tables`` (comma list; default: every table and view in the
dataset), ``objects`` ("table|WHERE -> tag" or "query:SELECT … -> tag"),
``location``, ``credentials_file``, ``max_bytes_billed``.

Credentials, in order: ``credentials_file`` (spec) → ``secrets.bigquery.credentials_file``
→ ``GOOGLE_APPLICATION_CREDENTIALS`` / Application Default Credentials
(``gcloud auth application-default login``).

Cost and safety:
- Only SELECT jobs are issued, labelled ``tool=datalens``.
- Sampling uses ``TABLESAMPLE SYSTEM`` on tables, so BigQuery bills only the sampled
  blocks instead of the whole table. Views and queries use ``LIMIT``.
- Every job runs with ``maximum_bytes_billed`` (default 10 GiB; 0 disables the cap).
- Row counts come from table metadata (free), so volume drift uses the true count.

Requires the optional extra: ``pip install 'datalens-ai[bigquery]'``.
"""

from __future__ import annotations

import base64
import datetime as dt
import decimal
import math
import os
from typing import TYPE_CHECKING, Any, Iterator

from datalens.connectors.base import Connector, ObjectRef, Record

if TYPE_CHECKING:
    from datalens.config import Config

DEFAULT_MAX_BYTES_BILLED = 10 * 1024**3
SAMPLE_HEADROOM = 1.5
"""Sample this much more than needed via TABLESAMPLE, then LIMIT — block sampling is approximate."""


def to_python(value: Any) -> Any:
    """BigQuery row values → plain JSON-like Python (nested STRUCT → dict, REPEATED → list)."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, dict):
        return {k: to_python(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_python(v) for v in value]
    if hasattr(value, "items"):  # google.cloud.bigquery Row
        return {k: to_python(v) for k, v in value.items()}
    return str(value)


def _ident(name: str) -> str:
    return "`" + name.replace("`", "") + "`"


class BigQueryConnector(Connector):
    """Read-only connector for Google BigQuery."""

    def __init__(self, source_spec: dict[str, Any], config: "Config") -> None:
        super().__init__(source_spec, config)
        self._client: Any = None
        self._bq: Any = None
        self._objects: list[ObjectRef] = []

    # ── connection ──────────────────────────────────────────────────────
    def connect(self) -> None:
        try:
            from google.cloud import bigquery  # type: ignore[import-not-found]
        except ImportError as e:
            raise ImportError(
                "BigQuery support needs the optional extra: pip install 'datalens-ai[bigquery]' "
                "(or uv sync --extra bigquery)"
            ) from e
        self._bq = bigquery
        secrets = (self.config.secrets or {}).get("bigquery", {}) if self.config else {}
        creds_file = self.source_spec.get("credentials_file") or secrets.get("credentials_file")
        credentials = None
        if creds_file:
            from google.oauth2 import service_account  # type: ignore[import-not-found]

            credentials = service_account.Credentials.from_service_account_file(os.path.expanduser(creds_file))
        project = self.source_spec.get("project") or secrets.get("project") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        try:
            self._client = bigquery.Client(project=project, credentials=credentials,
                                           location=self.source_spec.get("location"))
        except Exception as e:
            raise ConnectionError(
                f"Could not create a BigQuery client ({e}). Set --project and credentials "
                "(gcloud auth application-default login, or a service-account credentials_file)."
            ) from e
        self._objects = self._parse_objects()
        self._connected = True

    @property
    def _project(self) -> str:
        return self.source_spec.get("project") or self._client.project

    def _dataset(self) -> str:
        dataset = self.source_spec.get("dataset") or self.source_spec.get("db")
        if not dataset:
            raise ValueError("BigQuery source needs 'dataset' (--dataset) unless every object is a query")
        return dataset

    def _table_id(self, table: str) -> str:
        parts = table.split(".")
        if len(parts) == 3:
            return table
        if len(parts) == 2:
            return f"{self._project}.{table}"
        return f"{self._project}.{self._dataset()}.{table}"

    # ── objects ─────────────────────────────────────────────────────────
    def _parse_objects(self) -> list[ObjectRef]:
        objects: list[ObjectRef] = []
        tables = self.source_spec.get("collections") or self.source_spec.get("tables")
        if isinstance(tables, str):
            tables = [t.strip() for t in tables.split(",") if t.strip()]
        for table in tables or []:
            objects.append(self._table_ref(table))
        specs = self.source_spec.get("objects") or []
        if isinstance(specs, str):
            specs = [specs]
        for spec in specs:
            objects.append(self._parse_spec(spec))
        if not objects:
            for item in self._client.list_tables(f"{self._project}.{self._dataset()}"):
                if getattr(item, "table_type", "TABLE") in ("TABLE", "VIEW", "MATERIALIZED_VIEW", "EXTERNAL"):
                    objects.append(self._table_ref(item.table_id))
        return objects

    def _parse_spec(self, spec: str) -> ObjectRef:
        """'table', 'table|WHERE clause', '… -> tag' or 'query:SELECT … -> tag'."""
        spec = spec.strip()
        if ";" in spec:
            # BigQuery runs multi-statement scripts: never let a spec smuggle a second statement.
            raise ValueError("BigQuery object specs must be a single statement (no ';')")
        label = None
        if " -> " in spec:
            spec, label = (p.strip() for p in spec.rsplit(" -> ", 1))
        if spec.lower().startswith("query:"):
            sql = spec[6:].strip()
            first = sql.split(None, 1)[0].lower() if sql else ""
            if first not in ("select", "with"):
                raise ValueError("BigQuery query objects must be a SELECT (or WITH … SELECT) statement")
            name = label or "query"
            return ObjectRef(name=name, label=label, metadata={"query": sql, "kind": "QUERY"})
        table, _, where = spec.partition("|")
        ref = self._table_ref(table.strip())
        if where.strip():
            ref.query_filter = {"where": where.strip()}
        if label:
            ref.label = label
            ref.name = label
        return ref

    def _table_ref(self, table: str) -> ObjectRef:
        table_id = self._table_id(table)
        meta: dict[str, Any] = {"table_id": table_id, "kind": "TABLE"}
        try:
            info = self._client.get_table(table_id)
            meta.update({
                "kind": getattr(info, "table_type", "TABLE") or "TABLE",
                "num_rows": getattr(info, "num_rows", None),
                "num_bytes": getattr(info, "num_bytes", None),
                "declared_schema": [
                    {"name": f.name, "type": f.field_type, "mode": f.mode} for f in (getattr(info, "schema", None) or [])
                ],
                "partitioning": getattr(getattr(info, "time_partitioning", None), "field", None),
            })
        except Exception as e:  # listing still works; the query will surface real errors
            meta["metadata_error"] = str(e)
        return ObjectRef(name=table.split(".")[-1], metadata=meta)

    def list_objects(self) -> list[ObjectRef]:
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._objects

    # ── sampling ────────────────────────────────────────────────────────
    def build_query(self, obj: ObjectRef, sample_size: int) -> str:
        """The SELECT used to read an object (exposed for tests and --debug)."""
        meta = obj.metadata or {}
        where = (obj.query_filter or {}).get("where")
        if meta.get("kind") == "QUERY":
            base = f"SELECT * FROM ({meta['query']})"
            return f"{base} LIMIT {int(sample_size)}" if sample_size else base
        table = _ident(meta["table_id"])
        clause = f" WHERE {where}" if where else ""
        if not sample_size:
            return f"SELECT * FROM {table}{clause}"
        rows = meta.get("num_rows")
        strategy = (getattr(self.config, "sample_strategy", "reservoir") or "reservoir").lower()
        can_tablesample = meta.get("kind") == "TABLE" and strategy != "head"
        if can_tablesample and rows and rows > sample_size:
            pct = min(100.0, max(0.001, sample_size / rows * 100 * SAMPLE_HEADROOM))
            return f"SELECT * FROM {table} TABLESAMPLE SYSTEM ({pct:.4f} PERCENT){clause} LIMIT {int(sample_size)}"
        return f"SELECT * FROM {table}{clause} LIMIT {int(sample_size)}"

    def sample(
        self,
        obj: ObjectRef,
        *,
        sample_size: int | None = None,
        max_depth: int | None = None,
    ) -> Iterator[Record]:
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")
        if sample_size is None:
            sample_size = self.config.sample_size
        sql = self.build_query(obj, sample_size)
        cap = self.source_spec.get("max_bytes_billed", DEFAULT_MAX_BYTES_BILLED)
        job_config = self._bq.QueryJobConfig(
            labels={"tool": "datalens"},
            maximum_bytes_billed=int(cap) if cap else None,
            use_query_cache=True,
        )
        job = self._client.query(sql, job_config=job_config)
        if obj.metadata.get("num_rows") is not None and not (obj.query_filter or {}).get("where"):
            obj.metadata["total_rows"] = int(obj.metadata["num_rows"])
        obj.metadata["bytes_processed"] = getattr(job, "total_bytes_processed", None)
        count = 0
        for row in job.result():
            count += 1
            yield to_python(row)
        if not sample_size:
            obj.metadata["total_rows"] = count

    def count(self, obj: ObjectRef) -> int | None:
        return (obj.metadata or {}).get("total_rows") or (obj.metadata or {}).get("num_rows")

    def close(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None
        self._connected = False
