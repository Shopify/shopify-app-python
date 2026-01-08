"""HTTP client lifecycle management utilities.

This module provides context managers for managing HTTP client lifecycles
in both sync and async contexts.
"""

import httpx


class HTTPClientContext:
    """Manages sync HTTP client lifecycle.

    Usage:
        with HTTPClientContext(http_client) as client:
            response = client.post(...)
    """

    def __init__(self, injected_client=None, timeout=30.0):
        """Initialize HTTP client context.

        Args:
            injected_client: Optional pre-configured httpx.Client for testing
            timeout: Request timeout in seconds (default: 30.0)
        """
        self.injected_client = injected_client
        self.timeout = timeout
        self.client = None
        self.should_close = False

    def __enter__(self):
        """Enter context manager and return client."""
        if self.injected_client is not None:
            self.client = self.injected_client
            self.should_close = False
        else:
            self.client = httpx.Client(timeout=self.timeout)
            self.should_close = True
        return self.client

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and cleanup client if needed."""
        if self.should_close and self.client is not None:
            self.client.close()


class AsyncHTTPClientContext:
    """Manages async HTTP client lifecycle.

    Usage:
        async with AsyncHTTPClientContext(http_client) as client:
            response = await client.post(...)
    """

    def __init__(self, injected_client=None, timeout=30.0):
        """Initialize async HTTP client context.

        Args:
            injected_client: Optional pre-configured httpx.AsyncClient for testing
            timeout: Request timeout in seconds (default: 30.0)
        """
        self.injected_client = injected_client
        self.timeout = timeout
        self.client = None
        self.should_close = False

    async def __aenter__(self):
        """Enter async context manager and return client."""
        if self.injected_client is not None:
            self.client = self.injected_client
            self.should_close = False
        else:
            self.client = httpx.AsyncClient(timeout=self.timeout)
            self.should_close = True
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager and cleanup client if needed."""
        if self.should_close and self.client is not None:
            await self.client.aclose()
