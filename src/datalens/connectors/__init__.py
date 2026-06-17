"""
Connectors — pluggable data source adapters.

Each connector implements the Connector ABC to provide a consistent interface
for sampling records from any data source (files, databases, APIs).

Cloud connectors (S3, HTTP, FTP) are lazily imported to avoid requiring
their dependencies unless used.
"""

from datalens.connectors.base import Connector, ObjectRef, Record

# Lazy imports for cloud connectors with optional dependencies
def get_s3_connector():
    """Get S3 connector (requires boto3)."""
    from datalens.connectors.s3 import S3Connector, s3_available
    return S3Connector, s3_available

def get_http_connector():
    """Get HTTP connector (requires httpx)."""
    from datalens.connectors.http import HTTPConnector, httpx_available
    return HTTPConnector, httpx_available

def get_ftp_connectors():
    """Get FTP/SFTP connectors (SFTP requires paramiko)."""
    from datalens.connectors.ftp import FTPConnector, SFTPConnector, paramiko_available
    return FTPConnector, SFTPConnector, paramiko_available

__all__ = [
    "Connector",
    "ObjectRef", 
    "Record",
    "get_s3_connector",
    "get_http_connector",
    "get_ftp_connectors",
]
