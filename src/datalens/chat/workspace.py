"""
A finished run, opened for questions: its artifacts plus a read-only SQL view of the data.

The data is re-read from the source recorded in the run manifest (a sample, not
the whole source by default), flattened to one table per object with dotted
column names ("runs.batter"; arrays become JSON text), and PII fields that were
masked in the report are masked here too. Queries run in an in-memory SQLite
database with an authorizer that only allows reading, a time limit and a row cap.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from datalens.profiling.pii import PIIType, mask_value

MAX_ROWS = 200
QUERY_SECONDS = 5.0


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def flatten(record: dict[str, Any], prefix: str = "", out: dict[str, Any] | None = None) -> dict[str, Any]:
    out = {} if out is None else out
    for key, value in record.items():
        if key == "_id":
            continue
        col = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flatten(value, col, out)
        elif isinstance(value, (list, tuple)):
            out[col] = json.dumps(value, default=str)
        elif isinstance(value, bool):
            out[col] = int(value)
        elif value is None or isinstance(value, (int, float, str)):
            out[col] = value
        else:
            out[col] = str(value)
    return out


class RunWorkspace:
    """Artifacts of one run directory, plus (lazily) the queryable data."""

    def __init__(self, run_dir: str | Path, *, sample_size: int = 20000) -> None:
        self.run_dir = Path(run_dir)
        if not self.run_dir.is_dir():
            raise FileNotFoundError(f"Run directory not found: {self.run_dir}")
        self.sample_size = sample_size

        def artifact(suffix: str) -> Path | None:
            matches = sorted(self.run_dir.glob(f"*-datalens-{suffix}"))
            return matches[0] if matches else None

        self.report_path = artifact("report.html")
        self.summary = _load_json(artifact("run-summary.json") or Path("-")) or {}
        self.drift = _load_json(artifact("drift-report.json") or Path("-"))
        self.contract = _load_json(artifact("contract.json") or Path("-"))
        self.schema = _load_json(artifact("schema.json") or Path("-")) or {"objects": []}
        self.manifest = _load_json(artifact("run-manifest.json") or Path("-")) or {}
        ai_md = artifact("ai-insights.md")
        self.ai_md = ai_md.read_text(encoding="utf-8") if ai_md else ""
        self._db: sqlite3.Connection | None = None
        self.tables: dict[str, list[str]] = {}
        self.load_error: str | None = None

    # ── data ─────────────────────────────────────────────────────────────
    def _masked_fields(self) -> dict[str, dict[str, PIIType]]:
        out: dict[str, dict[str, PIIType]] = {}
        for obj in self.schema.get("objects", []):
            for f in obj.get("fields", []):
                if f.get("masked"):
                    try:
                        out.setdefault(obj["object"], {})[f["path"]] = PIIType(f["masked"])
                    except ValueError:
                        out.setdefault(obj["object"], {})[f["path"]] = PIIType.NAME
        return out

    def connection(self) -> sqlite3.Connection | None:
        """In-memory SQLite with one table per object (None when the source can't be re-read)."""
        if self._db is not None or self.load_error:
            return self._db
        spec = (self.manifest or {}).get("source_spec")
        if not spec:
            self.load_error = "This run has no run-manifest.json (re-run `datalens analyze` to enable SQL questions)."
            return None
        try:
            from datalens.config import load_config
            from datalens.connectors.registry import get_connector

            if self.manifest.get("connection_config"):
                from datalens.cli import _merge_connection_config

                spec = _merge_connection_config(dict(spec), self.manifest["connection_config"])
            config = load_config(sample_size=self.sample_size)
            connector = get_connector(spec, config)
            connector.connect()
            masked = self._masked_fields()
            db = sqlite3.connect(":memory:", check_same_thread=False)
            try:
                for obj in connector.list_objects():
                    rows = [flatten(r) for r in connector.sample(obj, sample_size=self.sample_size)]
                    for path, pii_type in masked.get(obj.name, {}).items():
                        for row in rows:
                            if row.get(path) is not None:
                                row[path] = mask_value(row[path], pii_type)
                    self._create_table(db, obj.name, rows)
            finally:
                connector.close()
            db.execute("PRAGMA query_only = ON")
            db.set_authorizer(_read_only_authorizer)
            self._db = db
        except Exception as e:  # the chat still works on artifacts alone
            self.load_error = f"Could not load data for SQL: {e}"
        return self._db

    def _create_table(self, db: sqlite3.Connection, name: str, rows: list[dict[str, Any]]) -> None:
        columns: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for col in row:
                if col not in seen:
                    seen.add(col)
                    columns.append(col)
        table = _ident(name)
        if not columns:
            db.execute(f"CREATE TABLE {table} (_empty INTEGER)")
            self.tables[name] = []
            return
        db.execute(f"CREATE TABLE {table} ({', '.join(_ident(c) for c in columns)})")
        placeholders = ", ".join("?" for _ in columns)
        db.executemany(f"INSERT INTO {table} VALUES ({placeholders})",
                       [tuple(row.get(c) for c in columns) for row in rows])
        self.tables[name] = columns

    def query(self, sql: str) -> dict[str, Any]:
        """Run one read-only SELECT; returns {columns, rows, truncated} or {error}."""
        db = self.connection()
        if db is None:
            return {"error": self.load_error or "data not available"}
        statement = sql.strip().rstrip(";")
        if not statement.lower().startswith(("select", "with")) or ";" in statement:
            return {"error": "Only a single SELECT (or WITH … SELECT) statement is allowed."}
        deadline = time.monotonic() + QUERY_SECONDS
        db.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        try:
            cur = db.execute(statement)
            columns = [d[0] for d in cur.description or []]
            rows = cur.fetchmany(MAX_ROWS + 1)
        except sqlite3.Error as e:
            return {"error": f"SQL error: {e}"}
        finally:
            db.set_progress_handler(None, 0)
        return {"columns": columns, "rows": [list(r) for r in rows[:MAX_ROWS]], "truncated": len(rows) > MAX_ROWS}

    # ── context for the model ────────────────────────────────────────────
    def context_text(self, *, max_fields: int = 40) -> str:
        """Compact, masked description of the run for the model's system prompt."""
        s = self.summary
        lines = [f"Run {s.get('version_tag')} — status {s.get('status')}, scores {json.dumps(s.get('scores'))}"]
        for name, obj in (s.get("objects") or {}).items():
            lines.append(f"- object {name}: {obj.get('rows')} rows, dqi {obj.get('dqi')}, fitness {obj.get('fitness')}")
        lines.append("\nFields (path: types, % non-empty, distinct; [PII] = masked):")
        for obj in self.schema.get("objects", []):
            sampled = obj.get("sampled") or 1
            for f in obj.get("fields", [])[:max_fields]:
                filled = max(0, f.get("presence_count", 0) - f.get("null_empty_count", 0)) / sampled * 100
                types = ",".join(t for t in f.get("types", {}) if t != "null")
                pii = " [PII]" if f.get("masked") else ""
                lines.append(f"  {obj['object']}.{f['path']}: {types}, {filled:.0f}%, {f.get('distinct_count_in_sample')}{pii}")
        if self.drift:
            lines.append(f"\nDrift ({self.drift.get('mode')} vs {(self.drift.get('reference') or {}).get('tag')}): "
                         f"{json.dumps(self.drift.get('summary'))}")
            for f in self.drift.get("findings", [])[:25]:
                lines.append(f"  [{f['severity']}] {f['message']}")
        if self.contract:
            lines.append(f"\nExpected schema conformance {self.contract.get('conformance_pct')}%:")
            for o in self.contract.get("objects", []):
                for c in o["checks"]:
                    if c["status"] in ("fail", "warn"):
                        lines.append(f"  [{c['status']}] {c['message']}")
        actions = s.get("top_actions") or []
        if actions:
            lines.append("\nTop actions: " + "; ".join(a.get("action", "") for a in actions))
        if self.ai_md:
            lines.append("\nEarlier AI review (excerpt):\n" + self.ai_md[:3000])
        return "\n".join(lines)

    def tables_text(self) -> str:
        db = self.connection()
        if db is None:
            return f"(SQL unavailable: {self.load_error})"
        return "\n".join(
            f"  table {_ident(name)} ({len(cols)} columns): " + ", ".join(_ident(c) for c in cols[:60])
            for name, cols in self.tables.items()
        )


def _ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
                    getattr(sqlite3, "SQLITE_RECURSIVE", 33)}


def _read_only_authorizer(action: int, arg1: Any, arg2: Any, db_name: Any, source: Any) -> int:
    """Allow reading only: no writes, no ATTACH, no PRAGMA, no schema changes."""
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY
