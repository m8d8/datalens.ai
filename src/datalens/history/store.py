"""
History Store — versioned storage of analysis artifacts.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


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

    def save(self, version_tag: str, schema_json: dict[str, Any]) -> Path:
        """
        Save a schema analysis run.

        Args:
            version_tag: Version identifier for this run.
            schema_json: The schema analysis JSON.

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
        metadata = {
            "version_tag": version_tag,
            "timestamp": datetime.now().isoformat(),
            "objects": [obj.get("object") for obj in schema_json.get("objects", [])],
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

        # Sort by timestamp, newest first
        versions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
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
