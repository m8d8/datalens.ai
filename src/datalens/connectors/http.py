"""
HTTP/REST Connector for Datalens.

Read JSON data from HTTP/REST APIs with authentication, pagination, and retry support.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Iterator
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)


def httpx_available() -> bool:
    """Check if httpx is available."""
    try:
        import httpx  # noqa: F401
        return True
    except ImportError:
        return False


class HTTPConnector:
    """
    Connector for reading data from HTTP/REST APIs.
    
    Supports:
    - Multiple authentication methods (Basic, Bearer, API Key, OAuth2)
    - Automatic pagination (cursor, offset, page-based)
    - Retry with exponential backoff
    - Rate limiting
    - Request/response transforms
    """
    
    def __init__(
        self,
        base_url: str,
        *,
        headers: dict[str, str] | None = None,
        auth_type: str | None = None,
        auth_token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        api_key: str | None = None,
        api_key_header: str = "X-API-Key",
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        rate_limit: float | None = None,
        auth_params: dict[str, Any] | None = None,
        custom_headers: dict[str, str] | None = None,
    ):
        """
        Initialize HTTP connector.

        Args:
            base_url: Base URL for API requests
            headers: Additional headers to include in all requests
            auth_type: Authentication type: "basic", "bearer", "api_key", or None
            auth_token: Bearer token (for auth_type="bearer")
            username: Username (for auth_type="basic")
            password: Password (for auth_type="basic")
            api_key: API key value (for auth_type="api_key")
            api_key_header: Header name for API key (default: X-API-Key)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            retry_delay: Initial retry delay (exponential backoff)
            rate_limit: Minimum seconds between requests (rate limiting)
            auth_params: Dict with auth config from connection config
            custom_headers: Additional custom headers (alternative to headers param)
        """
        if not httpx_available():
            raise ImportError(
                "httpx is required for HTTP connector. "
                "Install with: uv add httpx"
            )
        
        import httpx
        
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limit = rate_limit
        self._last_request_time: float = 0
        
        # Build headers
        self._headers = headers.copy() if headers else {}
        if custom_headers:
            self._headers.update(custom_headers)
        self._headers.setdefault("Accept", "application/json")
        self._headers.setdefault("Content-Type", "application/json")

        # Setup auth from auth_params (connection config) or individual params
        self._auth = None
        if auth_params:
            self._setup_auth_from_params(auth_params, httpx)
        else:
            self._setup_auth(auth_type, auth_token, username, password, api_key, api_key_header, httpx)
        
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=self._headers,
            auth=self._auth,
            timeout=timeout,
            follow_redirects=True,
        )

        logger.info(f"Initialized HTTP connector for: {base_url}")

    def _setup_auth(
        self,
        auth_type: str | None,
        auth_token: str | None,
        username: str | None,
        password: str | None,
        api_key: str | None,
        api_key_header: str,
        httpx: Any,
    ) -> None:
        """Setup authentication from individual parameters."""
        if auth_type == "basic" and username and password:
            self._auth = httpx.BasicAuth(username, password)
        elif auth_type == "bearer" and auth_token:
            self._headers["Authorization"] = f"Bearer {auth_token}"
        elif auth_type == "api_key" and api_key:
            self._headers[api_key_header] = api_key

    def _setup_auth_from_params(
        self,
        auth_params: dict[str, Any],
        httpx: Any,
    ) -> None:
        """Setup authentication from connection config params dict."""
        auth_type = auth_params.get("auth_type")
        if not auth_type:
            return

        if auth_type == "basic":
            username = auth_params.get("username")
            password = auth_params.get("password")
            if username and password:
                self._auth = httpx.BasicAuth(username, password)
        elif auth_type == "bearer":
            token = auth_params.get("auth_token") or auth_params.get("token")
            if token:
                self._headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "api_key":
            api_key = auth_params.get("api_key") or auth_params.get("key")
            header_name = auth_params.get("api_key_header") or auth_params.get("header_name") or "X-API-Key"
            if api_key:
                self._headers[header_name] = api_key

    def _rate_limit_wait(self) -> None:
        """Wait for rate limiting if configured."""
        if self.rate_limit:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.rate_limit:
                sleep_time = self.rate_limit - elapsed
                logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
    
    def _request_with_retry(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """Make request with retry logic."""
        import httpx
        
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        
        for attempt in range(self.max_retries + 1):
            try:
                self._rate_limit_wait()
                
                response = self._client.request(method, url, **kwargs)
                self._last_request_time = time.time()
                
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 500, 502, 503, 504):
                    if attempt < self.max_retries:
                        delay = self.retry_delay * (2 ** attempt)
                        logger.warning(
                            f"Request failed ({e.response.status_code}), "
                            f"retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(delay)
                        continue
                raise
            except httpx.RequestError as e:
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Request error: {e}, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(delay)
                    continue
                raise
        
        raise RuntimeError(f"Request failed after {self.max_retries} retries")
    
    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """
        Make GET request.
        
        Args:
            path: API path (relative to base_url)
            params: Query parameters
        
        Returns:
            Parsed JSON response
        """
        return self._request_with_retry("GET", path, params=params)
    
    def post(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """
        Make POST request.
        
        Args:
            path: API path (relative to base_url)
            data: Request body (will be JSON-encoded)
            params: Query parameters
        
        Returns:
            Parsed JSON response
        """
        return self._request_with_retry("POST", path, json=data, params=params)
    
    def fetch_paginated(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data_key: str = "data",
        pagination_type: str = "offset",
        limit_param: str = "limit",
        offset_param: str = "offset",
        page_param: str = "page",
        cursor_param: str = "cursor",
        next_cursor_key: str = "next_cursor",
        page_size: int = 100,
        max_pages: int | None = None,
        max_records: int | None = None,
    ) -> list[dict]:
        """
        Fetch records with automatic pagination.
        
        Args:
            path: API path
            params: Base query parameters
            data_key: Key in response containing records (or None for root array)
            pagination_type: "offset", "page", or "cursor"
            limit_param: Parameter name for page size
            offset_param: Parameter name for offset (offset pagination)
            page_param: Parameter name for page number (page pagination)
            cursor_param: Parameter name for cursor (cursor pagination)
            next_cursor_key: Response key containing next cursor
            page_size: Records per page
            max_pages: Maximum pages to fetch
            max_records: Maximum total records to fetch
        
        Returns:
            List of all records
        """
        records: list[dict] = []
        params = params.copy() if params else {}
        params[limit_param] = page_size
        
        page = 0
        offset = 0
        cursor = None
        
        while True:
            # Check limits
            if max_pages and page >= max_pages:
                break
            if max_records and len(records) >= max_records:
                break
            
            # Set pagination params
            if pagination_type == "offset":
                params[offset_param] = offset
            elif pagination_type == "page":
                params[page_param] = page + 1  # Usually 1-indexed
            elif pagination_type == "cursor" and cursor:
                params[cursor_param] = cursor
            
            # Fetch page
            response = self.get(path, params=params)
            
            # Extract records
            if data_key:
                page_records = response.get(data_key, [])
            else:
                page_records = response if isinstance(response, list) else []
            
            if not page_records:
                break
            
            records.extend(page_records)
            logger.debug(f"Fetched page {page + 1}: {len(page_records)} records")
            
            # Update pagination state
            page += 1
            offset += len(page_records)
            
            if pagination_type == "cursor":
                cursor = response.get(next_cursor_key)
                if not cursor:
                    break
            elif len(page_records) < page_size:
                # Last page (partial)
                break
        
        logger.info(f"Total records fetched: {len(records)}")
        return records[:max_records] if max_records else records
    
    def stream_paginated(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data_key: str = "data",
        pagination_type: str = "offset",
        limit_param: str = "limit",
        offset_param: str = "offset",
        page_size: int = 100,
    ) -> Iterator[dict]:
        """
        Stream records with pagination (memory-efficient).
        
        Args:
            path: API path
            params: Base query parameters
            data_key: Key in response containing records
            pagination_type: "offset" or "page"
            limit_param: Parameter name for page size
            offset_param: Parameter name for offset
            page_size: Records per page
        
        Yields:
            Records one at a time
        """
        params = params.copy() if params else {}
        params[limit_param] = page_size
        offset = 0
        
        while True:
            if pagination_type == "offset":
                params[offset_param] = offset
            
            response = self.get(path, params=params)
            
            if data_key:
                page_records = response.get(data_key, [])
            else:
                page_records = response if isinstance(response, list) else []
            
            if not page_records:
                break
            
            for record in page_records:
                yield record
            
            offset += len(page_records)
            
            if len(page_records) < page_size:
                break
    
    def read_records(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data_key: str | None = "data",
        max_records: int | None = None,
        paginated: bool = False,
        **pagination_kwargs: Any,
    ) -> list[dict]:
        """
        Read records from API endpoint.
        
        Args:
            path: API path
            params: Query parameters
            data_key: Key in response containing records (None for root array)
            max_records: Maximum records to fetch
            paginated: Whether to use pagination
            **pagination_kwargs: Additional pagination arguments
        
        Returns:
            List of records
        """
        if paginated:
            return self.fetch_paginated(
                path,
                params=params,
                data_key=data_key or "data",
                max_records=max_records,
                **pagination_kwargs,
            )
        
        response = self.get(path, params=params)
        
        if data_key:
            records = response.get(data_key, [])
        elif isinstance(response, list):
            records = response
        else:
            records = [response]
        
        return records[:max_records] if max_records else records
    
    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
    
    def __enter__(self) -> "HTTPConnector":
        return self
    
    def __exit__(self, *args: Any) -> None:
        self.close()
