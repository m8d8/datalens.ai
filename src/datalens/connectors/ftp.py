"""
FTP/SFTP Connector for Datalens.

Read JSON/JSONL files from FTP and SFTP servers.
"""

from __future__ import annotations

import ftplib
import json
import logging
from io import BytesIO
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)


def paramiko_available() -> bool:
    """Check if paramiko is available for SFTP."""
    try:
        import paramiko  # noqa: F401
        return True
    except ImportError:
        return False


class FTPConnector:
    """
    Connector for reading data from FTP servers.
    
    Supports:
    - FTP and FTPS (FTP over TLS)
    - Directory listing with pattern matching
    - JSON/JSONL file reading
    - Passive and active modes
    """
    
    def __init__(
        self,
        host: str,
        *,
        port: int = 21,
        username: str = "anonymous",
        password: str = "",
        secure: bool = False,
        passive: bool = True,
        timeout: float = 30.0,
    ):
        """
        Initialize FTP connector.
        
        Args:
            host: FTP server hostname
            port: FTP server port (default: 21)
            username: FTP username
            password: FTP password
            secure: Use FTPS (FTP over TLS)
            passive: Use passive mode (recommended for firewalls)
            timeout: Connection timeout in seconds
        """
        self.host = host
        self.port = port
        self.username = username
        self.secure = secure
        
        # Create appropriate FTP client
        if secure:
            self._ftp = ftplib.FTP_TLS(timeout=timeout)
        else:
            self._ftp = ftplib.FTP(timeout=timeout)
        
        # Connect and login
        self._ftp.connect(host, port)
        self._ftp.login(username, password)
        
        # Enable TLS data channel for FTPS
        if secure:
            self._ftp.prot_p()
        
        # Set passive mode
        self._ftp.set_pasv(passive)
        
        logger.info(f"Connected to FTP{'S' if secure else ''}: {host}:{port}")
    
    def list_files(
        self,
        path: str = "/",
        pattern: str | None = None,
        recursive: bool = False,
    ) -> list[str]:
        """
        List files in a directory.
        
        Args:
            path: Directory path to list
            pattern: Filename pattern to match (e.g., "*.json")
            recursive: Whether to list recursively
        
        Returns:
            List of file paths
        """
        files: list[str] = []
        
        def _list_dir(directory: str) -> None:
            try:
                entries = self._ftp.nlst(directory)
            except ftplib.error_perm:
                return
            
            for entry in entries:
                # Check if entry is a directory
                try:
                    self._ftp.cwd(entry)
                    self._ftp.cwd("..")
                    if recursive:
                        _list_dir(entry)
                except ftplib.error_perm:
                    # It's a file
                    if pattern:
                        import fnmatch
                        filename = Path(entry).name
                        if fnmatch.fnmatch(filename, pattern):
                            files.append(entry)
                    else:
                        files.append(entry)
        
        _list_dir(path)
        logger.info(f"Found {len(files)} files in {path}")
        return files
    
    def read_file(self, path: str) -> bytes:
        """
        Read file contents.
        
        Args:
            path: File path
        
        Returns:
            File contents as bytes
        """
        buffer = BytesIO()
        self._ftp.retrbinary(f"RETR {path}", buffer.write)
        buffer.seek(0)
        return buffer.read()
    
    def read_json(self, path: str) -> Any:
        """
        Read and parse JSON file.
        
        Args:
            path: File path
        
        Returns:
            Parsed JSON data
        """
        content = self.read_file(path)
        return json.loads(content.decode("utf-8"))
    
    def read_jsonl(self, path: str, max_records: int | None = None) -> list[dict]:
        """
        Read and parse JSONL file.
        
        Args:
            path: File path
            max_records: Maximum records to read
        
        Returns:
            List of parsed records
        """
        content = self.read_file(path)
        records: list[dict] = []
        
        for line in content.decode("utf-8").splitlines():
            if not line.strip():
                continue
            records.append(json.loads(line))
            
            if max_records and len(records) >= max_records:
                break
        
        return records
    
    def read_records(
        self,
        path: str | None = None,
        directory: str | None = None,
        pattern: str = "*.json",
        max_records: int | None = None,
    ) -> list[dict]:
        """
        Read records from FTP.
        
        Args:
            path: Specific file path
            directory: Directory to read all matching files from
            pattern: File pattern when using directory
            max_records: Maximum total records
        
        Returns:
            List of records
        """
        records: list[dict] = []
        
        if path:
            if path.endswith(".jsonl"):
                records = self.read_jsonl(path, max_records)
            else:
                data = self.read_json(path)
                if isinstance(data, list):
                    records = data[:max_records] if max_records else data
                else:
                    records = [data]
        elif directory:
            files = self.list_files(directory, pattern=pattern)
            
            for f in files:
                if max_records and len(records) >= max_records:
                    break
                
                remaining = max_records - len(records) if max_records else None
                
                if f.endswith(".jsonl"):
                    batch = self.read_jsonl(f, remaining)
                else:
                    data = self.read_json(f)
                    if isinstance(data, list):
                        batch = data[:remaining] if remaining else data
                    else:
                        batch = [data]
                
                records.extend(batch)
        
        logger.info(f"Total records read from FTP: {len(records)}")
        return records
    
    def close(self) -> None:
        """Close the FTP connection."""
        try:
            self._ftp.quit()
        except Exception:
            self._ftp.close()
    
    def __enter__(self) -> "FTPConnector":
        return self
    
    def __exit__(self, *args: Any) -> None:
        self.close()


class SFTPConnector:
    """
    Connector for reading data from SFTP servers.
    
    Supports:
    - SSH key and password authentication
    - Directory listing with pattern matching
    - JSON/JSONL file reading
    """
    
    def __init__(
        self,
        host: str,
        *,
        port: int = 22,
        username: str,
        password: str | None = None,
        private_key_path: str | None = None,
        private_key_password: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize SFTP connector.
        
        Args:
            host: SFTP server hostname
            port: SFTP server port (default: 22)
            username: SSH username
            password: SSH password (if using password auth)
            private_key_path: Path to private key file (if using key auth)
            private_key_password: Password for encrypted private key
            timeout: Connection timeout in seconds
        """
        if not paramiko_available():
            raise ImportError(
                "paramiko is required for SFTP connector. "
                "Install with: uv add paramiko"
            )
        
        import paramiko
        
        self.host = host
        self.port = port
        self.username = username
        
        # Create transport
        self._transport = paramiko.Transport((host, port))
        
        # Authenticate
        if private_key_path:
            key = paramiko.RSAKey.from_private_key_file(
                private_key_path, password=private_key_password
            )
            self._transport.connect(username=username, pkey=key)
        elif password:
            self._transport.connect(username=username, password=password)
        else:
            raise ValueError("Either password or private_key_path must be provided")
        
        self._sftp = paramiko.SFTPClient.from_transport(self._transport)
        
        logger.info(f"Connected to SFTP: {host}:{port}")
    
    def list_files(
        self,
        path: str = "/",
        pattern: str | None = None,
        recursive: bool = False,
    ) -> list[str]:
        """
        List files in a directory.
        
        Args:
            path: Directory path to list
            pattern: Filename pattern to match (e.g., "*.json")
            recursive: Whether to list recursively
        
        Returns:
            List of file paths
        """
        import stat
        
        files: list[str] = []
        
        def _list_dir(directory: str) -> None:
            for entry in self._sftp.listdir_attr(directory):
                full_path = f"{directory.rstrip('/')}/{entry.filename}"
                
                if stat.S_ISDIR(entry.st_mode):
                    if recursive:
                        _list_dir(full_path)
                else:
                    if pattern:
                        import fnmatch
                        if fnmatch.fnmatch(entry.filename, pattern):
                            files.append(full_path)
                    else:
                        files.append(full_path)
        
        _list_dir(path)
        logger.info(f"Found {len(files)} files in {path}")
        return files
    
    def read_file(self, path: str) -> bytes:
        """
        Read file contents.
        
        Args:
            path: File path
        
        Returns:
            File contents as bytes
        """
        with self._sftp.open(path, "rb") as f:
            return f.read()
    
    def read_json(self, path: str) -> Any:
        """
        Read and parse JSON file.
        
        Args:
            path: File path
        
        Returns:
            Parsed JSON data
        """
        content = self.read_file(path)
        return json.loads(content.decode("utf-8"))
    
    def read_jsonl(self, path: str, max_records: int | None = None) -> list[dict]:
        """
        Read and parse JSONL file.
        
        Args:
            path: File path
            max_records: Maximum records to read
        
        Returns:
            List of parsed records
        """
        content = self.read_file(path)
        records: list[dict] = []
        
        for line in content.decode("utf-8").splitlines():
            if not line.strip():
                continue
            records.append(json.loads(line))
            
            if max_records and len(records) >= max_records:
                break
        
        return records
    
    def read_records(
        self,
        path: str | None = None,
        directory: str | None = None,
        pattern: str = "*.json",
        max_records: int | None = None,
    ) -> list[dict]:
        """
        Read records from SFTP.
        
        Args:
            path: Specific file path
            directory: Directory to read all matching files from
            pattern: File pattern when using directory
            max_records: Maximum total records
        
        Returns:
            List of records
        """
        records: list[dict] = []
        
        if path:
            if path.endswith(".jsonl"):
                records = self.read_jsonl(path, max_records)
            else:
                data = self.read_json(path)
                if isinstance(data, list):
                    records = data[:max_records] if max_records else data
                else:
                    records = [data]
        elif directory:
            files = self.list_files(directory, pattern=pattern)
            
            for f in files:
                if max_records and len(records) >= max_records:
                    break
                
                remaining = max_records - len(records) if max_records else None
                
                if f.endswith(".jsonl"):
                    batch = self.read_jsonl(f, remaining)
                else:
                    data = self.read_json(f)
                    if isinstance(data, list):
                        batch = data[:remaining] if remaining else data
                    else:
                        batch = [data]
                
                records.extend(batch)
        
        logger.info(f"Total records read from SFTP: {len(records)}")
        return records
    
    def close(self) -> None:
        """Close the SFTP connection."""
        self._sftp.close()
        self._transport.close()
    
    def __enter__(self) -> "SFTPConnector":
        return self
    
    def __exit__(self, *args: Any) -> None:
        self.close()
