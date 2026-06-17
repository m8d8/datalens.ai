"""Tests for HTTP download management."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from datalens.utils.download import (
    cleanup_old_downloads,
    detect_format,
    download_file,
    get_downloads_dir,
    validate_format,
)


class TestDownloadManagement:
    """Tests for download utility functions."""

    def test_get_downloads_dir_creates_directory(self, tmp_path: Path) -> None:
        """Test that downloads directory is created."""
        downloads_dir = get_downloads_dir(project_root=tmp_path)

        assert downloads_dir.exists()
        assert downloads_dir.name == "http"
        assert downloads_dir.parent.name == "downloads"
        assert downloads_dir.parent.parent.name == ".tmp"
        assert downloads_dir.parent.parent.parent.name == ".datalens"

    def test_detect_format_json_from_content(self) -> None:
        """Test JSON detection from content."""
        json_content = '{"key": "value"}'
        assert detect_format(json_content) == "json"

    def test_detect_format_jsonl_from_content(self) -> None:
        """Test JSONL detection from content."""
        jsonl_content = '{"key": "value1"}\n{"key": "value2"}\n{"key": "value3"}'
        assert detect_format(jsonl_content) == "jsonl"

    def test_detect_format_json_array(self) -> None:
        """Test JSON array detection."""
        json_array = '[{"id": 1}, {"id": 2}]'
        assert detect_format(json_array) == "json"

    def test_detect_format_xml_from_content(self) -> None:
        """Test XML detection from content."""
        xml_content = '<?xml version="1.0"?><root><item>value</item></root>'
        assert detect_format(xml_content) == "xml"

    def test_detect_format_csv_from_content(self) -> None:
        """Test CSV detection from content."""
        csv_content = "name,age,city\nAlice,30,NYC\nBob,25,LA"
        assert detect_format(csv_content) == "csv"

    def test_detect_format_from_filename_json(self) -> None:
        """Test format detection from filename."""
        content = "irrelevant"
        assert detect_format(content, filename="data.json") == "json"

    def test_detect_format_from_filename_jsonl(self) -> None:
        """Test JSONL detection from filename."""
        content = "irrelevant"
        assert detect_format(content, filename="data.jsonl") == "jsonl"

    def test_detect_format_from_mime_type(self) -> None:
        """Test format detection from MIME type."""
        content = "irrelevant"
        assert detect_format(content, content_type="application/json") == "json"
        assert detect_format(content, content_type="application/xml") == "xml"
        assert detect_format(content, content_type="text/csv") == "csv"

    def test_detect_format_unknown(self) -> None:
        """Test unknown format detection."""
        content = "random text that doesn't match any format"
        assert detect_format(content) == "unknown"

    def test_validate_format_json_valid(self) -> None:
        """Test JSON validation with valid content."""
        content = '{"key": "value"}'
        assert validate_format(content, "json") is True

    def test_validate_format_json_invalid(self) -> None:
        """Test JSON validation with invalid content."""
        content = '{"key": invalid}'
        with pytest.raises(ValueError, match="Invalid JSON"):
            validate_format(content, "json")

    def test_validate_format_jsonl_valid(self) -> None:
        """Test JSONL validation with valid content."""
        content = '{"id": 1}\n{"id": 2}\n{"id": 3}'
        assert validate_format(content, "jsonl") is True

    def test_validate_format_jsonl_with_empty_lines(self) -> None:
        """Test JSONL validation with empty lines (valid)."""
        content = '{"id": 1}\n\n{"id": 2}'
        assert validate_format(content, "jsonl") is True

    def test_validate_format_xml_valid(self) -> None:
        """Test XML validation with valid content."""
        content = '<?xml version="1.0"?><root><item>value</item></root>'
        assert validate_format(content, "xml") is True

    def test_validate_format_xml_invalid(self) -> None:
        """Test XML validation with invalid content."""
        content = '<root><item>unclosed'
        with pytest.raises(ValueError, match="Invalid XML"):
            validate_format(content, "xml")

    def test_validate_format_csv_valid(self) -> None:
        """Test CSV validation with valid content."""
        content = "name,age\nAlice,30\nBob,25"
        assert validate_format(content, "csv") is True

    def test_validate_format_bytes_input(self) -> None:
        """Test validation with bytes input."""
        content = b'{"key": "value"}'
        assert validate_format(content, "json") is True

    def test_cleanup_old_downloads_deletes_old_files(self, tmp_path: Path) -> None:
        """Test cleanup deletes old downloads."""
        downloads_dir = get_downloads_dir(project_root=tmp_path)

        # Create old file
        old_file = downloads_dir / "old_file.json"
        old_file.write_text('{"data": "old"}')

        # Set modification time to 8 days ago
        old_mtime = time.time() - (8 * 86400)
        old_file.stat()  # Ensure file exists
        import os
        os.utime(old_file, (old_mtime, old_mtime))

        # Create recent file
        recent_file = downloads_dir / "recent_file.json"
        recent_file.write_text('{"data": "recent"}')

        # Run cleanup
        deleted = cleanup_old_downloads(max_age_days=7, project_root=tmp_path)

        assert deleted == 1
        assert not old_file.exists()
        assert recent_file.exists()

    def test_cleanup_old_downloads_skips_recent_files(self, tmp_path: Path) -> None:
        """Test cleanup skips recent files."""
        downloads_dir = get_downloads_dir(project_root=tmp_path)

        # Create recent file
        recent_file = downloads_dir / "recent.json"
        recent_file.write_text('{"data": "recent"}')

        # Run cleanup
        deleted = cleanup_old_downloads(max_age_days=7, project_root=tmp_path)

        assert deleted == 0
        assert recent_file.exists()

    def test_cleanup_old_downloads_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test cleanup handles nonexistent directory gracefully."""
        deleted = cleanup_old_downloads(max_age_days=7, project_root=tmp_path)
        assert deleted == 0

    def test_detect_format_json_with_newlines(self) -> None:
        """Test JSON detection with multiple lines."""
        json_content = """
        {
            "key": "value",
            "nested": {
                "data": "here"
            }
        }
        """
        assert detect_format(json_content) == "json"

    def test_detect_format_priority_mime_over_content(self) -> None:
        """Test that MIME type takes priority over content."""
        # Content looks like XML, but MIME says JSON
        content = "<xml>not really</xml>"
        result = detect_format(content, content_type="application/json")
        assert result == "json"

    def test_detect_format_priority_filename_over_content(self) -> None:
        """Test that filename takes priority over content."""
        # Content looks like JSON, but filename says CSV
        content = '{"key": "value"}'
        result = detect_format(content, filename="data.csv")
        assert result == "csv"

    def test_validate_format_empty_jsonl_lines(self) -> None:
        """Test JSONL with only empty lines is valid."""
        content = "\n\n\n"
        # Should not raise - empty lines are acceptable
        assert validate_format(content, "jsonl") is True
