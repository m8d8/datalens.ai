"""
History Store — versioned storage of analysis artifacts.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


class HistoryStore:
    """
    Manages versioned storage of analysis runs.

    Each run is stored with its version tag and can be retrieved
    for comparison and drift detection.
    """

    def __init__(self, base_dir: str | Path = "history") -> None:
        """
        Initialize the history store.

        Args:
            base_dir: Base directory for storing history (git-ignored).
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        version_tag: str,
        schema_json: dict[str, Any],
        *,
        metrics: dict[str, float] | None = None,
        categories: dict[str, list[str]] | None = None,
        breached: list[str] | None = None,
        run_date: str | None = None,
        summary: dict[str, Any] | None = None,
    ) -> Path:
        """
        Save a schema analysis run.

        Args:
            version_tag: Version identifier for this run.
            schema_json: The schema analysis JSON (already PII-masked).
            metrics: Flat run metrics (``datalens.drift.extract_metrics``) — the
                series the rolling baseline learns from.
            breached: Metric keys that breached in this run; excluded from future
                rolling baselines so a bad day doesn't become "normal".
            run_date: Logical date of the data (``--run-date``); defaults to now.
                Runs are ordered by it, so back-filled days land in the right place.
            summary: Small run summary (scores, drift status) for ``history list``.

        Returns:
            Path to the saved file.
        """
        # Create version directory
        version_dir = self.base_dir / version_tag
        version_dir.mkdir(parents=True, exist_ok=True)

        # Save schema JSON
        schema_file = version_dir / "schema.json"
        schema_file.write_text(
            json.dumps(schema_json, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Save metadata
        if metrics is not None:
            (version_dir / "metrics.json").write_text(
                json.dumps({"metrics": metrics, "categories": categories or {}, "breached": breached or []},
                           indent=1),
                encoding="utf-8",
            )

        metadata = {
            "version_tag": version_tag,
            "timestamp": datetime.now().isoformat(),
            "run_date": run_date or datetime.now().isoformat(),
            "objects": [obj.get("object") for obj in schema_json.get("objects", [])],
            "summary": summary or {},
        }
        metadata_file = version_dir / "metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return schema_file

    def load(self, version_tag: str) -> dict[str, Any] | None:
        """
        Load a schema analysis run by version tag.

        Args:
            version_tag: Version identifier to load.

        Returns:
            Schema JSON dict, or None if not found.
        """
        schema_file = self.base_dir / version_tag / "schema.json"
        if not schema_file.exists():
            return None

        return json.loads(schema_file.read_text(encoding="utf-8"))

    def list_versions(self) -> list[dict[str, Any]]:
        """
        List all available versions.

        Returns:
            List of version metadata dicts, sorted by timestamp (newest first).
        """
        versions = []

        for version_dir in self.base_dir.iterdir():
            if not version_dir.is_dir():
                continue

            metadata_file = version_dir / "metadata.json"
            if metadata_file.exists():
                try:
                    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
                    versions.append(metadata)
                except Exception:
                    pass

        # Newest first, by the data's logical run date (falls back to save time).
        versions.sort(key=lambda x: (x.get("run_date") or x.get("timestamp", ""), x.get("timestamp", "")),
                      reverse=True)
        return versions

    def get_latest(self) -> dict[str, Any] | None:
        """
        Get the most recent schema analysis.

        Returns:
            Schema JSON dict, or None if no history exists.
        """
        versions = self.list_versions()
        if not versions:
            return None

        return self.load(versions[0]["version_tag"])

    def load_runs(self, *, exclude: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        """
        Earlier runs, newest first:
        ``{"tag", "timestamp", "run_date", "metrics", "categories", "breached", "summary"}``.

        Runs saved before metrics.json existed get their metrics derived from
        the stored schema (schema-level metrics only).
        """
        from datalens.drift.metrics import extract_categories, extract_metrics

        runs: list[dict[str, Any]] = []
        for meta in self.list_versions():
            tag = meta.get("version_tag", "")
            if not tag or tag == exclude:
                continue
            metrics_file = self.base_dir / tag / "metrics.json"
            if metrics_file.exists():
                data = json.loads(metrics_file.read_text(encoding="utf-8"))
                metrics, breached = data.get("metrics", {}), data.get("breached", [])
                categories = data.get("categories", {})
            else:
                schema = self.load(tag)
                metrics, breached = (extract_metrics(schema) if schema else {}), []
                categories = extract_categories(schema) if schema else {}
            runs.append({
                "tag": tag,
                "timestamp": meta.get("timestamp"),
                "run_date": meta.get("run_date") or meta.get("timestamp"),
                "metrics": metrics,
                "categories": categories,
                "breached": breached,
                "summary": meta.get("summary", {}),
            })
            if limit and len(runs) >= limit:
                break
        return runs

    def delete(self, version_tag: str) -> bool:
        """
        Delete a version from history.

        Args:
            version_tag: Version to delete.

        Returns:
            True if deleted, False if not found.
        """
        import shutil

        version_dir = self.base_dir / version_tag
        if version_dir.exists():
            shutil.rmtree(version_dir)
            return True
        return False

    def purge_expired(
        self,
        retention_days: int,
        protected_tags: Iterable[str] | None = None,
    ) -> list[str]:
        """
        Delete saved runs older than ``retention_days``, keeping protected tags forever.

        Args:
            retention_days: Runs saved more than this many days ago are deleted.
                0 (or negative) disables purging entirely (no-op).
            protected_tags: Version tags that are never purged regardless of age
                (case-insensitive), e.g. {"baseline"}.

        Returns:
            List of version tags that were deleted.
        """
        if retention_days <= 0:
            return []

        protected = {t.lower() for t in (protected_tags or ())}
        cutoff = datetime.now() - timedelta(days=retention_days)
        deleted: list[str] = []

        for version in self.list_versions():
            tag = version.get("version_tag", "")
            if not tag or tag.lower() in protected:
                continue

            timestamp_str = version.get("timestamp")
            if not timestamp_str:
                continue
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError:
                continue

            if timestamp < cutoff and self.delete(tag):
                deleted.append(tag)

        return deleted
