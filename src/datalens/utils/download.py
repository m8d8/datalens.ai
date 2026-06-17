"""
HTTP content download and format detection utility.

Handles downloading files from HTTP endpoints to .datalens/.tmp/ with:
- Automatic format detection (JSON, JSONL, XML, CSV)
- File validation
- Auto-cleanup of old downloads (>7 days)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


def get_downloads_dir(project_root: Path | None = None) -> Path:
    """Get the downloads directory, creating it if needed."""
    if project_root is None:
        project_root = Path.cwd()

    downloads_dir = project_root / ".datalens" / ".tmp" / "downloads" / "http"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    return downloads_dir


def cleanup_old_downloads(
    max_age_days: int = 7,
    project_root: Path | None = None,
) -> int:
    """
    Delete downloads older than max_age_days.

    Returns:
        Number of files deleted.
    """
    downloads_dir = get_downloads_dir(project_root)

    if not downloads_dir.exists():
        return 0

    deleted_count = 0
    cutoff_time = time.time() - (max_age_days * 86400)

    # Glob for all supported formats
    file_paths = list(downloads_dir.glob("*.json")) + list(downloads_dir.glob("*.csv")) + list(downloads_dir.glob("*.xml"))
    for file_path in file_paths:
        if file_path.stat().st_mtime < cutoff_time:
            try:
                file_path.unlink()
                deleted_count += 1
                logger.debug(f"Deleted old download: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete {file_path}: {e}")

    return deleted_count


def detect_format(
    content: str | bytes,
    content_type: str | None = None,
    filename: str | None = None,
) -> Literal["json", "jsonl", "xml", "csv", "unknown"]:
    """
    Detect file format from content, MIME type, or filename.

    Returns:
        Format type: 'json', 'jsonl', 'xml', 'csv', or 'unknown'
    """
    # Check MIME type first
    if content_type:
        if "json" in content_type.lower():
            return "json"
        elif "xml" in content_type.lower():
            return "xml"
        elif "csv" in content_type.lower():
            return "csv"

    # Check filename extension
    if filename:
        lower_name = filename.lower()
        if lower_name.endswith(".json"):
            return "json"
        elif lower_name.endswith(".jsonl"):
            return "jsonl"
        elif lower_name.endswith(".xml"):
            return "xml"
        elif lower_name.endswith(".csv"):
            return "csv"

    # Try parsing content
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8")
        except Exception:
            return "unknown"

    content = content.strip()

    # Try JSON
    if content.startswith("{") or content.startswith("["):
        try:
            json.loads(content)
            return "json"
        except Exception:
            pass

    # Try JSONL (line-delimited JSON)
    try:
        lines = content.split("\n")
        valid_lines = 0
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if not line:
                continue
            json.loads(line)
            valid_lines += 1
        if valid_lines >= 3:  # At least 3 valid JSON lines
            return "jsonl"
    except Exception:
        pass

    # Try XML
    if content.startswith("<"):
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(content)
            return "xml"
        except Exception:
            pass

    # Try CSV (simple check: has commas and newlines)
    if "," in content and "\n" in content:
        return "csv"

    return "unknown"


def validate_format(
    content: str | bytes,
    file_format: Literal["json", "jsonl", "xml", "csv"],
) -> bool:
    """
    Validate that content is valid for the given format.

    Raises:
        ValueError: If content is invalid for the format.
    """
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to decode content as UTF-8: {e}")

    if file_format == "json":
        try:
            json.loads(content)
            return True
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

    elif file_format == "jsonl":
        lines = content.split("\n")
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON at line {i + 1}: {e}")
        return True

    elif file_format == "xml":
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(content)
            return True
        except Exception as e:
            raise ValueError(f"Invalid XML: {e}")

    elif file_format == "csv":
        # Basic CSV validation: check structure
        import csv
        import io
        try:
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                # Just iterate to validate
                pass
            return True
        except Exception as e:
            raise ValueError(f"Invalid CSV: {e}")

    return False


def download_file(
    url: str,
    timeout: float = 30.0,
    project_root: Path | None = None,
) -> dict[str, str | Path]:
    """
    Download file from URL and return local path info.

    Args:
        url: URL to download from
        timeout: Request timeout in seconds
        project_root: Project root for .datalens/ directory

    Returns:
        Dict with:
        - path: Local file path (Path object)
        - format: Detected format ('json', 'csv', 'xml', 'unknown')
        - content_type: MIME type from response
        - size_bytes: File size in bytes
        - downloaded_at: Timestamp

    Raises:
        ValueError: If download fails or format is unsupported
    """
    try:
        import httpx
    except ImportError:
        raise ImportError("httpx is required for downloads. Install with: uv add httpx")

    # Cleanup old downloads before downloading new one
    cleanup_old_downloads(project_root=project_root)

    # Download
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
    except Exception as e:
        raise ValueError(f"Failed to download {url}: {e}")

    content = response.content
    content_type = response.headers.get("content-type", "")

    # Detect format
    detected_format = detect_format(
        content,
        content_type=content_type,
        filename=url.split("/")[-1],
    )

    if detected_format == "unknown":
        raise ValueError(
            f"Could not detect file format from {url}. "
            f"Supported: JSON, JSONL, XML, CSV. "
            f"Content-Type: {content_type}"
        )

    # Validate format
    try:
        validate_format(content, detected_format)
    except ValueError as e:
        raise ValueError(f"Downloaded file is invalid: {e}")

    # Save to .datalens/.tmp/downloads/http/
    downloads_dir = get_downloads_dir(project_root)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{url.split('/')[-1]}"
    if not filename.endswith(f".{detected_format}"):
        filename = f"{timestamp}_download.{detected_format}"

    file_path = downloads_dir / filename

    try:
        file_path.write_bytes(content)
    except Exception as e:
        raise ValueError(f"Failed to save download to {file_path}: {e}")

    logger.info(
        f"Downloaded {len(content)} bytes from {url} to {file_path} "
        f"(format: {detected_format})"
    )

    return {
        "path": file_path,
        "format": detected_format,
        "content_type": content_type,
        "size_bytes": len(content),
        "downloaded_at": timestamp,
    }
