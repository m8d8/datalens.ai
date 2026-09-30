"""Tests for FileConnector — JSONL support and transparent gz/zip decompression."""

from __future__ import annotations

import gzip
import json
import zipfile

import pytest
from datalens.config import Config
from datalens.connectors.files import FileConnector

# Mock records used only to exercise the connector — unrelated to any real dataset.
RECORDS = [
    {"id": 1, "name": "Example A", "active": True},
    {"id": 2, "name": "Example B", "active": False},
    {"id": 3, "name": "Example C", "active": True},
]


def _jsonl_bytes(records: list[dict]) -> bytes:
    return ("\n".join(json.dumps(r) for r in records) + "\n").encode("utf-8")


class TestJSONLPlain:
    """Plain .jsonl files."""

    def test_sample_jsonl(self, tmp_path):
        path = tmp_path / "data.jsonl"
        path.write_bytes(_jsonl_bytes(RECORDS))

        connector = FileConnector({"source": "file", "path": str(path)}, Config())
        connector.connect()
        objs = connector.list_objects()
        assert len(objs) == 1

        records = list(connector.sample(objs[0], sample_size=0))
        assert records == RECORDS
        connector.close()

    def test_sample_jsonl_respects_sample_size(self, tmp_path):
        path = tmp_path / "data.jsonl"
        path.write_bytes(_jsonl_bytes(RECORDS))

        connector = FileConnector({"source": "file", "path": str(path)}, Config())
        connector.connect()
        records = list(connector.sample(connector.list_objects()[0], sample_size=2))
        assert len(records) == 2
        connector.close()

    def test_skips_blank_lines(self, tmp_path):
        path = tmp_path / "data.jsonl"
        content = _jsonl_bytes(RECORDS[:1]) + b"\n\n" + _jsonl_bytes(RECORDS[1:])
        path.write_bytes(content)

        connector = FileConnector({"source": "file", "path": str(path)}, Config())
        connector.connect()
        records = list(connector.sample(connector.list_objects()[0], sample_size=0))
        assert records == RECORDS
        connector.close()


class TestGzipDecompression:
    """.gz compressed files (any supported inner type)."""

    def test_sample_jsonl_gz(self, tmp_path):
        path = tmp_path / "data.jsonl.gz"
        with gzip.open(path, "wt", encoding="utf-8") as f:
            for r in RECORDS:
                f.write(json.dumps(r) + "\n")

        connector = FileConnector({"source": "file", "path": str(path)}, Config())
        connector.connect()

        objs = connector.list_objects()
        assert objs[0].name == "data"
        assert objs[0].metadata["compression"] == "gzip"

        records = list(connector.sample(objs[0], sample_size=0))
        assert records == RECORDS
        connector.close()

    def test_sample_csv_gz(self, tmp_path):
        path = tmp_path / "data.csv.gz"
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write("id,name\n1,Example A\n2,Example B\n")

        connector = FileConnector({"source": "file", "path": str(path)}, Config())
        connector.connect()
        records = list(connector.sample(connector.list_objects()[0], sample_size=0))
        assert records == [
            {"id": "1", "name": "Example A"},
            {"id": "2", "name": "Example B"},
        ]
        connector.close()

    def test_sample_json_gz(self, tmp_path):
        path = tmp_path / "data.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(json.dumps(RECORDS))

        connector = FileConnector({"source": "file", "path": str(path)}, Config())
        connector.connect()
        records = list(connector.sample(connector.list_objects()[0], sample_size=0))
        assert records == RECORDS
        connector.close()


class TestZipDecompression:
    """.zip archives (single entry, or explicit 'member' selection)."""

    def test_sample_jsonl_zip_single_entry(self, tmp_path):
        path = tmp_path / "data.jsonl.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("data.jsonl", _jsonl_bytes(RECORDS).decode("utf-8"))

        connector = FileConnector({"source": "file", "path": str(path)}, Config())
        connector.connect()
        records = list(connector.sample(connector.list_objects()[0], sample_size=0))
        assert records == RECORDS
        connector.close()

    def test_zip_multiple_entries_requires_member(self, tmp_path):
        path = tmp_path / "data.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("a.jsonl", _jsonl_bytes(RECORDS).decode("utf-8"))
            zf.writestr("b.jsonl", _jsonl_bytes(RECORDS).decode("utf-8"))

        connector = FileConnector({"source": "file", "path": str(path)}, Config())
        with pytest.raises(ValueError, match="specify one via 'member'"):
            connector.connect()

    def test_zip_multiple_entries_with_member(self, tmp_path):
        path = tmp_path / "data.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("a.jsonl", _jsonl_bytes(RECORDS[:1]).decode("utf-8"))
            zf.writestr("b.jsonl", _jsonl_bytes(RECORDS[1:]).decode("utf-8"))

        connector = FileConnector(
            {"source": "file", "path": str(path), "member": "b.jsonl"}, Config()
        )
        connector.connect()
        records = list(connector.sample(connector.list_objects()[0], sample_size=0))
        assert records == RECORDS[1:]
        connector.close()


class TestUnsupportedCases:
    def test_unsupported_extension_raises(self, tmp_path):
        path = tmp_path / "data.txt"
        path.write_text("hello")

        connector = FileConnector({"source": "file", "path": str(path)}, Config())
        with pytest.raises(ValueError, match="Unsupported file type"):
            connector.connect()

    def test_compressed_excel_raises(self, tmp_path):
        path = tmp_path / "data.xlsx.gz"
        with gzip.open(path, "wb") as f:
            f.write(b"not a real workbook")

        connector = FileConnector({"source": "file", "path": str(path)}, Config())
        with pytest.raises(ValueError, match="Compressed Excel files are not supported"):
            connector.connect()


class TestDirectoryScanning:
    """A directory of files, each becoming its own object."""

    def test_scans_top_level_files(self, tmp_path):
        (tmp_path / "a.jsonl").write_bytes(_jsonl_bytes(RECORDS[:1]))
        with gzip.open(tmp_path / "b.jsonl.gz", "wt", encoding="utf-8") as f:
            for r in RECORDS[1:]:
                f.write(json.dumps(r) + "\n")
        # Unsupported file in the same directory should be silently skipped.
        (tmp_path / "notes.txt").write_text("ignore me")

        connector = FileConnector({"source": "file", "path": str(tmp_path)}, Config())
        connector.connect()
        objs = {o.name: o for o in connector.list_objects()}
        assert set(objs) == {"a", "b"}

        a_records = list(connector.sample(objs["a"], sample_size=0))
        b_records = list(connector.sample(objs["b"], sample_size=0))
        assert a_records == RECORDS[:1]
        assert b_records == RECORDS[1:]
        connector.close()

    def test_pattern_filters_files(self, tmp_path):
        (tmp_path / "a.jsonl").write_bytes(_jsonl_bytes(RECORDS))
        (tmp_path / "b.csv").write_text("id,name\n1,Example A\n")

        connector = FileConnector(
            {"source": "file", "path": str(tmp_path), "pattern": "*.jsonl"}, Config()
        )
        connector.connect()
        assert [o.name for o in connector.list_objects()] == ["a"]
        connector.close()

    def test_non_recursive_by_default(self, tmp_path):
        (tmp_path / "top.jsonl").write_bytes(_jsonl_bytes(RECORDS[:1]))
        nested_dir = tmp_path / "nested"
        nested_dir.mkdir()
        (nested_dir / "inner.jsonl").write_bytes(_jsonl_bytes(RECORDS[1:]))

        connector = FileConnector({"source": "file", "path": str(tmp_path)}, Config())
        connector.connect()
        assert [o.name for o in connector.list_objects()] == ["top"]
        connector.close()

    def test_recursive_scans_subdirectories(self, tmp_path):
        (tmp_path / "top.jsonl").write_bytes(_jsonl_bytes(RECORDS[:1]))
        nested_dir = tmp_path / "nested"
        nested_dir.mkdir()
        (nested_dir / "inner.jsonl").write_bytes(_jsonl_bytes(RECORDS[1:]))

        connector = FileConnector(
            {"source": "file", "path": str(tmp_path), "recursive": True}, Config()
        )
        connector.connect()
        names = {o.name for o in connector.list_objects()}
        assert names == {"top", "nested/inner"}
        connector.close()

    def test_empty_directory_raises(self, tmp_path):
        connector = FileConnector({"source": "file", "path": str(tmp_path)}, Config())
        with pytest.raises(ValueError, match="No supported data files found"):
            connector.connect()

    def test_ambiguous_zip_is_skipped_not_fatal(self, tmp_path):
        (tmp_path / "a.jsonl").write_bytes(_jsonl_bytes(RECORDS))
        with zipfile.ZipFile(tmp_path / "ambiguous.zip", "w") as zf:
            zf.writestr("x.jsonl", "{}")
            zf.writestr("y.jsonl", "{}")

        connector = FileConnector({"source": "file", "path": str(tmp_path)}, Config())
        connector.connect()
        assert [o.name for o in connector.list_objects()] == ["a"]
        connector.close()

