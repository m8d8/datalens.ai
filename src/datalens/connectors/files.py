"""
File connector — CSV, JSON, JSONL, XML, XLSX support.

Handles local files with:
- CSV: auto-infer headers, flag when missing (col_1..col_n)
- JSON: --root path to specify array/record root
- JSONL: one JSON record per line, streamed without loading the whole file
- XML: --root element to specify repeating record element
- XLSX: --sheets to select specific sheets (default: all)

'path' may point at a single file, or at a directory — in which case every
supported file underneath becomes its own object (like separate tables/sheets
in one report). Use 'pattern' to filter (e.g. "*.jsonl.gz") and 'recursive'
to also scan subdirectories.

Transparent decompression:
- .gz: gzip-compressed files, e.g. "data.jsonl.gz" (CSV/JSON/JSONL/XML only)
- .zip: zip archives containing a single data file, e.g. "data.csv.zip".
  If the archive holds multiple files, specify which one via the
  'member' source_spec key.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import logging
import xml.etree.ElementTree as ET
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

from datalens.connectors.base import Connector, ObjectRef, Record

if TYPE_CHECKING:
    from datalens.config import Config

logger = logging.getLogger(__name__)


class FileConnector(Connector):
    """Connector for local file sources (CSV, JSON, JSONL, XML, XLSX)."""

    SUPPORTED_EXTENSIONS = {".csv", ".json", ".jsonl", ".xml", ".xlsx", ".xls"}
    COMPRESSED_EXTENSIONS = {".gz", ".zip"}

    def __init__(self, source_spec: dict[str, Any], config: "Config") -> None:
        super().__init__(source_spec, config)
        self._path: Path | None = None
        self._file_type: str | None = None
        self._compression: str | None = None
        self._zip_member: str | None = None
        self._objects: list[ObjectRef] = []

    def connect(self) -> None:
        """Validate the path exists and build the list of objects to sample."""
        path_str = self.source_spec.get("path")
        if not path_str:
            raise ValueError("File source requires 'path' in source_spec")

        self._path = Path(path_str).expanduser().resolve()

        if not self._path.exists():
            raise FileNotFoundError(f"File not found: {self._path}")

        if self._path.is_dir():
            self._objects = self._list_directory_objects(self._path)
        else:
            inner_ext, compression, zip_member = self._classify(self._path, strict=True)
            self._objects = self._objects_for_file(self._path, inner_ext, compression, zip_member)

        self._connected = True

    def _list_directory_objects(self, directory: Path) -> list[ObjectRef]:
        """Build one ObjectRef per supported file found under a directory."""
        pattern = self.source_spec.get("pattern")
        recursive = bool(self.source_spec.get("recursive", False))

        if pattern:
            candidates = directory.glob(pattern)
        else:
            candidates = directory.rglob("*") if recursive else directory.glob("*")
        candidates = sorted(p for p in candidates if p.is_file())

        objects: list[ObjectRef] = []
        for path in candidates:
            classified = self._classify(path, strict=False)
            if classified is None:
                continue
            inner_ext, compression, zip_member = classified

            rel_dir = path.parent.relative_to(directory)
            for obj in self._objects_for_file(path, inner_ext, compression, zip_member):
                if str(rel_dir) != ".":
                    obj.name = f"{rel_dir.as_posix()}/{obj.name}"
                objects.append(obj)

        if not objects:
            raise ValueError(
                f"No supported data files found in directory: {directory} "
                f"(supported: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}, "
                "optionally .gz/.zip compressed)"
            )

        return objects

    def _classify(
        self, path: Path, *, strict: bool
    ) -> tuple[str, str | None, str | None] | None:
        """
        Determine (inner_extension, compression, zip_member) for a data file path.

        In strict mode (single-file source), unsupported/ambiguous files raise.
        Otherwise (directory scan) they are skipped by returning None.
        """
        outer_ext = path.suffix.lower()
        zip_member: str | None = None

        if outer_ext == ".gz":
            compression: str | None = "gzip"
            inner_ext = Path(path.stem).suffix.lower()
        elif outer_ext == ".zip":
            compression = "zip"
            zip_member = self._resolve_zip_member(path, strict=strict)
            if zip_member is None:
                return None
            inner_ext = Path(zip_member).suffix.lower()
        else:
            compression = None
            inner_ext = outer_ext

        if inner_ext not in self.SUPPORTED_EXTENSIONS:
            if not strict:
                logger.debug("Skipping unsupported file: %s", path)
                return None
            raise ValueError(
                f"Unsupported file type: {inner_ext or outer_ext}. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
            )

        if compression and inner_ext in {".xlsx", ".xls"}:
            if not strict:
                logger.debug("Skipping compressed Excel file: %s", path)
                return None
            raise ValueError("Compressed Excel files are not supported")

        return inner_ext, compression, zip_member

    def _resolve_zip_member(self, path: Path, *, strict: bool) -> str | None:
        """Pick which entry inside a zip archive to read as the data file."""
        requested_member = self.source_spec.get("member")
        with zipfile.ZipFile(path) as zf:
            members = [name for name in zf.namelist() if not name.endswith("/")]

        if not members:
            if not strict:
                logger.debug("Skipping empty zip archive: %s", path)
                return None
            raise ValueError(f"Zip archive is empty: {path}")

        if requested_member:
            if requested_member not in members:
                if not strict:
                    logger.debug("Member '%s' not found in %s", requested_member, path)
                    return None
                raise ValueError(
                    f"Member '{requested_member}' not found in zip archive. "
                    f"Available: {', '.join(members)}"
                )
            return requested_member

        if len(members) == 1:
            return members[0]

        if not strict:
            logger.warning(
                "Skipping zip archive with multiple entries (specify 'member' to read one): %s",
                path,
            )
            return None
        raise ValueError(
            f"Zip archive contains multiple files; specify one via 'member' "
            f"in source_spec. Available: {', '.join(members)}"
        )

    def _objects_for_file(
        self,
        path: Path,
        inner_ext: str,
        compression: str | None,
        zip_member: str | None,
    ) -> list[ObjectRef]:
        """Build the ObjectRef(s) produced by a single resolved data file."""
        if inner_ext in {".xlsx", ".xls"}:
            return self._list_excel_sheets(path)

        if compression == "gzip":
            name = Path(path.stem).stem
        elif compression == "zip" and zip_member:
            name = Path(zip_member).stem
        else:
            name = path.stem

        metadata: dict[str, Any] = {"path": str(path), "type": inner_ext}
        if compression:
            metadata["compression"] = compression
        if zip_member:
            metadata["zip_member"] = zip_member

        return [
            ObjectRef(
                name=name,
                label=self.source_spec.get("label"),
                metadata=metadata,
            )
        ]

    @contextmanager
    def _open_text(self, *, newline: str | None = None) -> Iterator[Any]:
        """Open the data file as a text stream, transparently decompressing gz/zip."""
        assert self._path is not None

        if self._compression == "gzip":
            with gzip.open(self._path, mode="rt", encoding="utf-8-sig", newline=newline) as f:
                yield f
        elif self._compression == "zip":
            assert self._zip_member is not None
            with zipfile.ZipFile(self._path) as zf, zf.open(self._zip_member) as raw:
                with io.TextIOWrapper(raw, encoding="utf-8-sig", newline=newline) as f:
                    yield f
        else:
            with open(self._path, encoding="utf-8-sig", newline=newline) as f:
                yield f

    def _list_excel_sheets(self, path: Path) -> list[ObjectRef]:
        """List sheets in an Excel file."""
        try:
            import openpyxl
        except ImportError:
            raise ImportError("openpyxl is required for Excel files: uv add openpyxl")

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        sheet_names = wb.sheetnames
        wb.close()

        # Filter to requested sheets if specified
        requested_sheets = self.source_spec.get("sheets")
        if requested_sheets:
            if isinstance(requested_sheets, str):
                requested_sheets = [s.strip() for s in requested_sheets.split(",")]
            sheet_names = [s for s in sheet_names if s in requested_sheets]

        return [
            ObjectRef(
                name=sheet,
                label=self.source_spec.get("label"),
                metadata={"path": str(path), "type": ".xlsx", "sheet": sheet},
            )
            for sheet in sheet_names
        ]

    def list_objects(self) -> list[ObjectRef]:
        """Return list of objects (files or sheets)."""
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
        """Yield records from the file/sheet. sample_size=0 means full scan."""
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        # Directory sources mix files with different types/compression, so each
        # object carries its own path — re-sync connector state before reading.
        self._path = Path(obj.metadata["path"])
        self._file_type = obj.metadata["type"]
        self._compression = obj.metadata.get("compression")
        self._zip_member = obj.metadata.get("zip_member")

        # Get sample_size: None means use config default, 0 means full scan
        if sample_size is None:
            sample_size = self.config.sample_size

        if self._file_type == ".csv":
            yield from self._sample_csv(sample_size)
        elif self._file_type == ".json":
            yield from self._sample_json(sample_size, max_depth)
        elif self._file_type == ".jsonl":
            yield from self._sample_jsonl(sample_size)
        elif self._file_type == ".xml":
            yield from self._sample_xml(sample_size)
        elif self._file_type in {".xlsx", ".xls"}:
            yield from self._sample_excel(obj, sample_size)

    def _sample_csv(self, sample_size: int) -> Iterator[Record]:
        """Sample records from CSV file."""
        with self._open_text(newline="") as f:
            # Sniff to detect dialect and headers
            sample_text = f.read(8192)
            f.seek(0)

            sniffer = csv.Sniffer()
            try:
                has_header = sniffer.has_header(sample_text)
            except csv.Error:
                has_header = True  # Assume header if detection fails

            dialect = csv.excel  # Default dialect
            try:
                dialect = sniffer.sniff(sample_text)
            except csv.Error:
                pass

            reader = csv.reader(f, dialect)

            if has_header:
                headers = next(reader)
            else:
                # Auto-generate headers
                first_row = next(reader)
                headers = [f"col_{i+1}" for i in range(len(first_row))]
                # Re-process first row as data
                yield dict(zip(headers, first_row))

            count = 1 if not has_header else 0
            for row in reader:
                # sample_size=0 means full scan (no limit)
                if sample_size > 0 and count >= sample_size:
                    break
                yield dict(zip(headers, row))
                count += 1

    def _sample_json(self, sample_size: int, max_depth: int | None) -> Iterator[Record]:
        """Sample records from JSON file."""
        with self._open_text() as f:
            data = json.load(f)

        # Navigate to root if specified
        root_path = self.source_spec.get("root")
        if root_path:
            for key in root_path.split("."):
                if isinstance(data, dict):
                    data = data.get(key, [])
                elif isinstance(data, list) and key.isdigit():
                    data = data[int(key)]
                else:
                    break

        # Ensure we have an iterable
        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            data = [{"value": data}]

        for i, record in enumerate(data):
            # sample_size=0 means full scan (no limit)
            if sample_size > 0 and i >= sample_size:
                break
            if isinstance(record, dict):
                yield record
            else:
                yield {"value": record}

    def _sample_jsonl(self, sample_size: int) -> Iterator[Record]:
        """Sample records from a JSONL (newline-delimited JSON) file, streaming line by line."""
        count = 0
        with self._open_text() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # sample_size=0 means full scan (no limit)
                if sample_size > 0 and count >= sample_size:
                    break
                record = json.loads(line)
                if isinstance(record, dict):
                    yield record
                else:
                    yield {"value": record}
                count += 1

    def _sample_xml(self, sample_size: int) -> Iterator[Record]:
        """Sample records from XML file."""
        root_element = self.source_spec.get("root", "*")

        with self._open_text() as f:
            tree = ET.parse(f)
        root = tree.getroot()

        # Find all elements matching the root pattern
        elements = root.findall(f".//{root_element}")

        for i, elem in enumerate(elements):
            # sample_size=0 means full scan (no limit)
            if sample_size > 0 and i >= sample_size:
                break
            yield self._xml_element_to_dict(elem)

    def _xml_element_to_dict(self, elem: ET.Element) -> dict[str, Any]:
        """Convert XML element to dict recursively."""
        result: dict[str, Any] = {}

        # Add attributes
        if elem.attrib:
            result["@attributes"] = dict(elem.attrib)

        # Add text content
        if elem.text and elem.text.strip():
            if len(elem) == 0:  # No children
                return elem.text.strip()  # type: ignore
            result["#text"] = elem.text.strip()

        # Add children
        for child in elem:
            child_data = self._xml_element_to_dict(child)
            tag = child.tag

            if tag in result:
                # Convert to list if multiple children with same tag
                if not isinstance(result[tag], list):
                    result[tag] = [result[tag]]
                result[tag].append(child_data)
            else:
                result[tag] = child_data

        return result

    def _sample_excel(self, obj: ObjectRef, sample_size: int) -> Iterator[Record]:
        """Sample records from Excel sheet."""
        assert self._path is not None

        try:
            import openpyxl
        except ImportError:
            raise ImportError("openpyxl is required for Excel files")

        wb = openpyxl.load_workbook(self._path, read_only=True, data_only=True)
        sheet_name = obj.metadata.get("sheet", obj.name)
        ws = wb[sheet_name]

        rows = ws.iter_rows(values_only=True)
        headers = next(rows, None)

        if not headers:
            wb.close()
            return

        # Clean headers (None -> col_N)
        headers = [h if h else f"col_{i+1}" for i, h in enumerate(headers)]

        count = 0
        for row in rows:
            # sample_size=0 means full scan (no limit)
            if sample_size > 0 and count >= sample_size:
                break
            if any(cell is not None for cell in row):  # Skip empty rows
                yield dict(zip(headers, row))
                count += 1

        wb.close()

    def count(self, obj: ObjectRef) -> int | None:
        """Return approximate count (may be expensive for large files)."""
        # For files, counting can be expensive; return None to indicate unknown
        return None

    def close(self) -> None:
        """Clean up resources."""
        self._connected = False
        self._path = None
        self._compression = None
        self._zip_member = None
        self._objects = []
