"""Tests for HistoryStore — versioned run storage and retention pruning."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from datalens.history.store import HistoryStore


def _save_with_timestamp(store: HistoryStore, tag: str, days_ago: int) -> None:
    """Save a run, then backdate its metadata.json timestamp for retention testing."""
    store.save(tag, {"objects": []})
    metadata_file = store.base_dir / tag / "metadata.json"
    metadata = json.loads(metadata_file.read_text())
    metadata["timestamp"] = (datetime.now() - timedelta(days=days_ago)).isoformat()
    metadata_file.write_text(json.dumps(metadata))


class TestSaveLoad:
    def test_save_and_load_round_trip(self, tmp_path):
        store = HistoryStore(tmp_path / "history")
        store.save("v1", {"objects": [{"object": "orders", "sampled": 10, "fields": []}]})

        loaded = store.load("v1")
        assert loaded is not None
        assert loaded["objects"][0]["object"] == "orders"

    def test_load_missing_version_returns_none(self, tmp_path):
        store = HistoryStore(tmp_path / "history")
        assert store.load("does-not-exist") is None

    def test_get_latest_returns_newest(self, tmp_path):
        store = HistoryStore(tmp_path / "history")
        _save_with_timestamp(store, "old", days_ago=5)
        _save_with_timestamp(store, "new", days_ago=0)

        versions = store.list_versions()
        assert versions[0]["version_tag"] == "new"


class TestPurgeExpired:
    def test_disabled_when_retention_days_is_zero(self, tmp_path):
        store = HistoryStore(tmp_path / "history")
        _save_with_timestamp(store, "ancient", days_ago=365)

        deleted = store.purge_expired(0)
        assert deleted == []
        assert store.load("ancient") is not None

    def test_deletes_runs_older_than_retention(self, tmp_path):
        store = HistoryStore(tmp_path / "history")
        _save_with_timestamp(store, "old_run", days_ago=10)
        _save_with_timestamp(store, "recent_run", days_ago=1)

        deleted = store.purge_expired(7)
        assert deleted == ["old_run"]
        assert store.load("old_run") is None
        assert store.load("recent_run") is not None

    def test_baseline_tag_is_never_deleted(self, tmp_path):
        store = HistoryStore(tmp_path / "history")
        _save_with_timestamp(store, "baseline", days_ago=365)
        _save_with_timestamp(store, "old_run", days_ago=10)

        deleted = store.purge_expired(7, protected_tags=["baseline"])
        assert deleted == ["old_run"]
        assert store.load("baseline") is not None

    def test_protected_tags_are_case_insensitive(self, tmp_path):
        store = HistoryStore(tmp_path / "history")
        _save_with_timestamp(store, "Baseline", days_ago=365)

        deleted = store.purge_expired(7, protected_tags=["baseline"])
        assert deleted == []
        assert store.load("Baseline") is not None

    def test_no_protected_tags_still_works(self, tmp_path):
        store = HistoryStore(tmp_path / "history")
        _save_with_timestamp(store, "old_run", days_ago=10)

        deleted = store.purge_expired(7)
        assert deleted == ["old_run"]
