"""
File connector — CSV, JSON, XML, XLSX support.

Handles local files with:
- CSV: auto-infer headers, flag when missing (col_1..col_n)
- JSON: --root path to specify array/record root
- XML: --root element to specify repeating record element
- XLSX: --sheets to select specific sheets (default: all)
"""

from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

from datalens.connectors.base import Connector, ObjectRef, Record

if TYPE_CHECKING:
    from datalens.config import Config


class FileConnector(Connector):
    """Connector for local file sources (CSV, JSON, XML, XLSX)."""

    SUPPORTED_EXTENSIONS = {".csv", ".json", ".xml", ".xlsx", ".xls"}

    def __init__(self, source_spec: dict[str, Any], config: "Config") -> None:
        super().__init__(source_spec, config)
        self._path: Path | None = None
        self._file_type: str | None = None
        self._objects: list[ObjectRef] = []

    def connect(self) -> None:
        """Validate file exists and determine type."""
        path_str = self.source_spec.get("path")
        if not path_str:
            raise ValueError("File source requires 'path' in source_spec")

        self._path = Path(path_str).expanduser().resolve()

        if not self._path.exists():
            raise FileNotFoundError(f"File not found: {self._path}")

        ext = self._path.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {ext}. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
            )

        self._file_type = ext
        self._connected = True

        # Build object list
        if ext in {".xlsx", ".xls"}:
            self._objects = self._list_excel_sheets()
        else:
            # Single object for CSV/JSON/XML
            self._objects = [
                ObjectRef(
                    name=self._path.stem,
                    label=self.source_spec.get("label"),
                    metadata={"path": str(self._path), "type": ext},
                )
            ]

    def _list_excel_sheets(self) -> list[ObjectRef]:
        """List sheets in an Excel file."""
        try:
            import openpyxl
        except ImportError:
            raise ImportError("openpyxl is required for Excel files: uv add openpyxl")

        wb = openpyxl.load_workbook(self._path, read_only=True, data_only=True)
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
                metadata={"path": str(self._path), "type": ".xlsx", "sheet": sheet},
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

        # Get sample_size: None means use config default, 0 means full scan
        if sample_size is None:
            sample_size = self.config.sample_size

        if self._file_type == ".csv":
            yield from self._sample_csv(sample_size)
        elif self._file_type == ".json":
            yield from self._sample_json(sample_size, max_depth)
        elif self._file_type == ".xml":
            yield from self._sample_xml(sample_size)
        elif self._file_type in {".xlsx", ".xls"}:
            yield from self._sample_excel(obj, sample_size)

    def _sample_csv(self, sample_size: int) -> Iterator[Record]:
        """Sample records from CSV file."""
        assert self._path is not None

        with open(self._path, newline="", encoding="utf-8-sig") as f:
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
        assert self._path is not None

        with open(self._path, encoding="utf-8") as f:
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

    def _sample_xml(self, sample_size: int) -> Iterator[Record]:
        """Sample records from XML file."""
        assert self._path is not None

        root_element = self.source_spec.get("root", "*")

        tree = ET.parse(self._path)
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
        self._objects = []
