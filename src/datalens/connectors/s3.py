"""
S3 Cloud Connector for Datalens.

Read JSON/JSONL data from Amazon S3 buckets.
Supports prefix-based listing, glob patterns, and streaming for large files.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator

logger = logging.getLogger(__name__)


def s3_available() -> bool:
    """Check if boto3 is available."""
    try:
        import boto3  # noqa: F401
        return True
    except ImportError:
        return False


class S3Connector:
    """
    Connector for reading data from Amazon S3.
    
    Supports:
    - Single file reads (.json, .jsonl)
    - Prefix-based listing (all files under a prefix)
    - Glob patterns for file matching
    - Streaming for memory-efficient large file handling
    """
    
    def __init__(
        self,
        bucket: str,
        *,
        region: str | None = None,
        profile: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        endpoint_url: str | None = None,
    ):
        """
        Initialize S3 connector.
        
        Args:
            bucket: S3 bucket name
            region: AWS region (optional, uses default if not specified)
            profile: AWS profile name (optional)
            access_key: AWS access key ID (optional, uses credentials chain if not specified)
            secret_key: AWS secret access key (optional)
            endpoint_url: Custom endpoint URL (for S3-compatible services like MinIO)
        """
        if not s3_available():
            raise ImportError(
                "boto3 is required for S3 connector. "
                "Install with: uv add boto3"
            )
        
        import boto3
        from botocore.config import Config
        
        self.bucket = bucket
        self.region = region
        
        # Build session kwargs
        session_kwargs: dict[str, Any] = {}
        if profile:
            session_kwargs["profile_name"] = profile
        if region:
            session_kwargs["region_name"] = region
        
        session = boto3.Session(**session_kwargs)
        
        # Build client kwargs
        client_kwargs: dict[str, Any] = {
            "config": Config(
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=30,
                read_timeout=60,
            )
        }
        
        if access_key and secret_key:
            client_kwargs["aws_access_key_id"] = access_key
            client_kwargs["aws_secret_access_key"] = secret_key
        
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        
        self._client = session.client("s3", **client_kwargs)
        logger.info(f"Initialized S3 connector for bucket: {bucket}")
    
    def list_keys(
        self,
        prefix: str = "",
        suffix: str | None = None,
        max_keys: int | None = None,
    ) -> list[str]:
        """
        List object keys in the bucket.
        
        Args:
            prefix: Filter keys starting with this prefix
            suffix: Filter keys ending with this suffix (e.g., ".json")
            max_keys: Maximum number of keys to return
        
        Returns:
            List of object keys
        """
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        
        page_config: dict[str, Any] = {"Bucket": self.bucket}
        if prefix:
            page_config["Prefix"] = prefix
        
        for page in paginator.paginate(**page_config):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                
                # Filter by suffix
                if suffix and not key.endswith(suffix):
                    continue
                
                keys.append(key)
                
                if max_keys and len(keys) >= max_keys:
                    return keys
        
        logger.info(f"Found {len(keys)} keys with prefix='{prefix}', suffix='{suffix}'")
        return keys
    
    def read_json(self, key: str) -> Any:
        """
        Read and parse a JSON file from S3.
        
        Args:
            key: S3 object key
        
        Returns:
            Parsed JSON data
        """
        logger.debug(f"Reading JSON from s3://{self.bucket}/{key}")
        
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        body = response["Body"].read()
        return json.loads(body.decode("utf-8"))
    
    def read_jsonl(self, key: str, max_records: int | None = None) -> list[dict]:
        """
        Read and parse a JSONL file from S3.
        
        Args:
            key: S3 object key
            max_records: Maximum number of records to read
        
        Returns:
            List of parsed records
        """
        logger.debug(f"Reading JSONL from s3://{self.bucket}/{key}")
        
        records: list[dict] = []
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        
        for line in response["Body"].iter_lines():
            if not line:
                continue
            records.append(json.loads(line.decode("utf-8")))
            
            if max_records and len(records) >= max_records:
                break
        
        logger.info(f"Read {len(records)} records from {key}")
        return records
    
    def stream_jsonl(self, key: str) -> Iterator[dict]:
        """
        Stream records from a JSONL file (memory-efficient for large files).
        
        Args:
            key: S3 object key
        
        Yields:
            Parsed records one at a time
        """
        logger.debug(f"Streaming JSONL from s3://{self.bucket}/{key}")
        
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        
        for line in response["Body"].iter_lines():
            if line:
                yield json.loads(line.decode("utf-8"))
    
    def read_records(
        self,
        key: str | None = None,
        prefix: str | None = None,
        suffix: str = ".json",
        max_records: int | None = None,
    ) -> list[dict]:
        """
        Read records from S3, supporting single file or multiple files.
        
        Args:
            key: Specific object key to read
            prefix: Prefix to list and read all matching files
            suffix: File suffix filter when using prefix
            max_records: Maximum total records to return
        
        Returns:
            List of records
        """
        records: list[dict] = []
        
        if key:
            # Read single file
            if key.endswith(".jsonl"):
                records = self.read_jsonl(key, max_records)
            else:
                data = self.read_json(key)
                if isinstance(data, list):
                    records = data[:max_records] if max_records else data
                else:
                    records = [data]
        elif prefix:
            # Read all matching files
            keys = self.list_keys(prefix=prefix, suffix=suffix)
            
            for k in keys:
                if max_records and len(records) >= max_records:
                    break
                
                remaining = max_records - len(records) if max_records else None
                
                if k.endswith(".jsonl"):
                    batch = self.read_jsonl(k, remaining)
                else:
                    data = self.read_json(k)
                    if isinstance(data, list):
                        batch = data[:remaining] if remaining else data
                    else:
                        batch = [data]
                
                records.extend(batch)
        
        logger.info(f"Total records read from S3: {len(records)}")
        return records
    
    def get_metadata(self, key: str) -> dict[str, Any]:
        """
        Get object metadata.
        
        Args:
            key: S3 object key
        
        Returns:
            Object metadata dict
        """
        response = self._client.head_object(Bucket=self.bucket, Key=key)
        return {
            "content_type": response.get("ContentType"),
            "content_length": response.get("ContentLength"),
            "last_modified": response.get("LastModified"),
            "etag": response.get("ETag"),
            "metadata": response.get("Metadata", {}),
        }
