"""BigQuery connector against a fake google.cloud.bigquery module (no GCP access needed)."""

from __future__ import annotations

import datetime as dt
import decimal
import sys
import types

import pytest

from datalens import analyze
from datalens.config.config import Config
from datalens.connectors.bigquery import BigQueryConnector, to_python


class FakeField:
    def __init__(self, name, field_type, mode="NULLABLE"):
        self.name, self.field_type, self.mode = name, field_type, mode


class FakeTable:
    def __init__(self, table_id, rows, table_type="TABLE"):
        self.table_id = table_id.split(".")[-1]
        self.table_type = table_type
        self.num_rows = len(rows)
        self.num_bytes = 1234
        self.schema = [FakeField(k, "STRING") for k in rows[0]] if rows else []
        self.time_partitioning = None


class FakeJob:
    def __init__(self, rows):
        self._rows = rows
        self.total_bytes_processed = 42

    def result(self):
        return iter(self._rows)


class FakeClient:
    instances: list["FakeClient"] = []

    def __init__(self, project=None, credentials=None, location=None):
        self.project = project or "default-proj"
        self.location = location
        self.queries: list[tuple[str, object]] = []
        self.tables = {
            "p.sales.orders": [{"order_id": f"o{i}", "customer_id": f"c{i % 40}",
                                "amount": decimal.Decimal("9.99"), "created": dt.datetime(2026, 5, 1, 12),
                                "items": [{"sku": "A", "qty": 1}], "ship": {"city": "Pune"}}
                               for i in range(500)],
            "p.sales.customers": [{"customer_id": f"c{i}", "tier": "gold" if i % 2 else "silver"} for i in range(40)],
        }
        FakeClient.instances.append(self)

    def get_table(self, table_id):
        return FakeTable(table_id, self.tables[table_id])

    def list_tables(self, dataset):
        return [FakeTable(t, rows) for t, rows in self.tables.items() if t.startswith(dataset + ".")]

    def query(self, sql, job_config=None):
        self.queries.append((sql, job_config))
        table = next(t for t in self.tables if f"`{t}`" in sql)
        rows = self.tables[table]
        if "LIMIT" in sql:
            rows = rows[: int(sql.rsplit("LIMIT", 1)[1])]
        return FakeJob(rows)


class FakeJobConfig:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.fixture
def fake_bigquery(monkeypatch):
    bigquery = types.ModuleType("google.cloud.bigquery")
    bigquery.Client = FakeClient
    bigquery.QueryJobConfig = FakeJobConfig
    cloud = types.ModuleType("google.cloud")
    cloud.bigquery = bigquery
    google = types.ModuleType("google")
    google.cloud = cloud
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.bigquery", bigquery)
    FakeClient.instances.clear()
    return bigquery


def _connector(spec, **cfg):
    conn = BigQueryConnector({"source": "bigquery", "project": "p", "dataset": "sales", **spec}, Config(**cfg))
    conn.connect()
    return conn


def test_lists_dataset_tables_and_samples_with_tablesample(fake_bigquery):
    conn = _connector({})
    names = [o.name for o in conn.list_objects()]
    assert names == ["orders", "customers"]
    orders = conn.list_objects()[0]
    sql = conn.build_query(orders, 100)
    assert "TABLESAMPLE SYSTEM" in sql and sql.endswith("LIMIT 100")
    rows = list(conn.sample(orders, sample_size=100))
    assert len(rows) == 100 and orders.metadata["total_rows"] == 500
    job_config = FakeClient.instances[-1].queries[-1][1]
    assert job_config.maximum_bytes_billed == 10 * 1024**3 and job_config.labels == {"tool": "datalens"}


def test_small_tables_and_head_strategy_use_limit_only(fake_bigquery):
    conn = _connector({"collections": "customers"})
    (customers,) = conn.list_objects()
    assert "TABLESAMPLE" not in conn.build_query(customers, 100)  # 40 rows < sample
    conn = _connector({"collections": "orders"}, sample_strategy="head")
    assert "TABLESAMPLE" not in conn.build_query(conn.list_objects()[0], 100)
    assert conn.build_query(conn.list_objects()[0], 0) == "SELECT * FROM `p.sales.orders`"


def test_object_specs_filters_queries_and_guard(fake_bigquery):
    conn = _connector({"objects": ["orders|amount > 5 -> big_orders", "query:SELECT * FROM `p.sales.orders` -> q"]})
    big, q = conn.list_objects()
    assert big.name == "big_orders" and "WHERE amount > 5" in conn.build_query(big, 10)
    assert conn.build_query(q, 10).startswith("SELECT * FROM (SELECT")
    with pytest.raises(ValueError):
        _connector({"objects": ["orders|1=1; DELETE FROM x WHERE true"]})
    with pytest.raises(ValueError):
        _connector({"objects": ["query:DELETE FROM `p.sales.orders` WHERE true"]})


def test_values_become_plain_json():
    assert to_python({"a": decimal.Decimal("1.5"), "t": dt.date(2026, 1, 2), "b": b"\x01", "n": float("nan"),
                      "xs": [dt.datetime(2026, 1, 1)]}) == {
        "a": 1.5, "t": "2026-01-02", "b": "AQ==", "n": None, "xs": ["2026-01-01T00:00:00"]}


def test_missing_extra_gives_a_clear_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "google.cloud.bigquery", None)
    conn = BigQueryConnector({"source": "bigquery", "dataset": "x"}, Config())
    with pytest.raises(ImportError, match="bigquery"):
        conn.connect()


def test_end_to_end_analysis_finds_keys_and_nested_fields(fake_bigquery):
    result = analyze({"source": "bigquery", "project": "p", "dataset": "sales"}, Config(sample_size=0))
    orders = next(o for o in result.schema_json["objects"] if o["object"] == "orders")
    paths = {f["path"] for f in orders["fields"]}
    assert {"ship.city", "items[].sku", "created"} <= paths
    assert orders["total_rows"] == 500
    links = {x["child"]: x["parent"] for x in result.joins["referential_integrity"]}
    assert links.get("orders.customer_id") == "customers.customer_id"
