"""
Shopify Admin GraphQL

This module provides functions to make GraphQL requests to the Shopify Admin API.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx

from shopify_app.types import AppConfig, GQLResult, HttpLog, Log, RequestInput, Res
from shopify_app.utils import _get_user_agent, _to_res

from ..utils.http_client import AsyncHTTPClientContext, HTTPClientContext


def admin_graphql_request(
    query: str,
    shop: str,
    access_token: str,
    api_version: str,
    invalid_token_response: Optional[Union[Res, dict]] = None,
    variables: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    max_retries: int = 2,
    app_config: Optional[AppConfig] = None,
    http_client: Optional[httpx.Client] = None,
) -> GQLResult:
    """
    Make a GraphQL request to the Shopify Admin API.

    Args:
        query (str): The GraphQL query or mutation string
        app_config (dict): App configuration (not currently used)
        http_client: Optional HTTP client for testing
        shop (str): Shop domain (e.g., "example")
        access_token (str): Valid access token for the shop
        api_version (str): API version (e.g., "2024-01")
        invalid_token_response (Res | dict): Pre-built response to return if token is invalid (or None)
        variables (dict[str, Any]): Optional GraphQL variables
        headers (dict[str, str]): Optional additional HTTP headers
        max_retries (int): Optional custom retry count (default: 2)

    Returns:
        GQLResult: Result containing ok, shop, log, response, data, extensions, and http_logs
    """
    # Use parameters directly (already extracted from named args)
    if headers is None:
        headers = {}

    # Validate required parameters
    is_valid, error = _validate_graphql_params(shop, access_token, api_version, query)
    if not is_valid:
        if error is None:
            raise RuntimeError("_validate_graphql_params returned invalid but no error")
        return error

    # Store original shop for return value
    original_shop = shop

    endpoint = f"https://{shop}.myshopify.com/admin/api/{api_version}/graphql.json"

    request_headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token,
        "User-Agent": _get_user_agent(),
        **headers,
    }

    request_body: Dict[str, Any] = {"query": query}
    if variables:
        request_body["variables"] = variables

    # Execute request with retry logic
    attempt = 0
    logs: List[HttpLog] = []

    # Use injected client or create one via context manager
    if http_client is not None:
        # Testing path - use injected client directly
        context_manager = HTTPClientContext(http_client)
    else:
        # Production path - context manager will create and cleanup client
        context_manager = HTTPClientContext()

    with context_manager as client:
        while attempt <= max_retries:
            try:
                response = client.post(
                    endpoint,
                    headers=request_headers,
                    json=request_body,
                )

                status_code = response.status_code
                response_body = response.text
                response_headers = dict(response.headers)

                req: RequestInput = {
                    "url": endpoint,
                    "method": "POST",
                    "headers": request_headers,
                    "body": json.dumps(request_body),
                }

                res = Res(
                    status=status_code, body=response_body, headers=response_headers
                )

                # Handle 200 success (but check for GraphQL errors)
                if status_code == 200:
                    try:
                        response_data = response.json()
                    except json.JSONDecodeError:
                        response_data = {}

                    # Check for GraphQL errors
                    if response_data.get("errors"):
                        logs.append(
                            HttpLog(
                                code="graphql_errors",
                                detail="GraphQL request returned errors",
                                req=req,
                                res=res,
                            )
                        )
                        return GQLResult(
                            ok=False,
                            shop=None,
                            log=Log(
                                code="graphql_errors",
                                detail="GraphQL request returned errors",
                            ),
                            http_logs=logs,
                            response=res,
                            data=None,
                            extensions=None,
                        )

                    # Success
                    logs.append(
                        HttpLog(
                            code="success",
                            detail="GraphQL request successful. Proceed with business logic.",
                            req=req,
                            res=res,
                        )
                    )
                    return GQLResult(
                        ok=True,
                        shop=original_shop,
                        log=Log(
                            code="success",
                            detail="GraphQL request successful. Proceed with business logic.",
                        ),
                        http_logs=logs,
                        response=res,
                        data=response_data.get("data"),
                        extensions=response_data.get("extensions"),
                    )

                # Handle 401 unauthorized
                if status_code == 401:
                    return _handle_401_response(invalid_token_response, req, res)

                # Handle 429 rate limit with retry helper
                should_retry, should_return, return_value = _handle_429_retry_sync(
                    status_code, attempt, max_retries, response_headers, logs, req, res
                )
                if should_return:
                    if return_value is None:
                        raise RuntimeError(
                            "_handle_429_retry_sync returned should_return=True but no return_value"
                        )
                    return return_value
                if should_retry:
                    attempt += 1
                    continue

                # Handle 5xx errors with retry helper
                should_retry, should_return, return_value = _handle_5xx_retry_sync(
                    status_code, attempt, max_retries, logs, req, res
                )
                if should_return:
                    if return_value is None:
                        raise RuntimeError(
                            "_handle_5xx_retry_sync returned should_return=True but no return_value"
                        )
                    return return_value
                if should_retry:
                    attempt += 1
                    continue

                # Handle non-retryable errors
                if status_code == 400:
                    return GQLResult(
                        ok=False,
                        shop=None,
                        log=Log(
                            code="http_error_400",
                            detail="GraphQL query syntax is invalid. Do not retry.",
                        ),
                        http_logs=[
                            HttpLog(
                                code="http_error_400",
                                detail="GraphQL query syntax is invalid. Do not retry.",
                                req=req,
                                res=res,
                            )
                        ],
                        response=res,
                        data=None,
                        extensions=None,
                    )

                if status_code == 403:
                    return GQLResult(
                        ok=False,
                        shop=None,
                        log=Log(
                            code="http_error_403",
                            detail="Access token lacks required permissions. Do not retry.",
                        ),
                        http_logs=[
                            HttpLog(
                                code="http_error_403",
                                detail="Access token lacks required permissions. Do not retry.",
                                req=req,
                                res=res,
                            )
                        ],
                        response=res,
                        data=None,
                        extensions=None,
                    )

                # Other HTTP errors
                return GQLResult(
                    ok=False,
                    shop=None,
                    log=Log(
                        code=f"http_error_{status_code}",
                        detail=f"HTTP error {status_code}",
                    ),
                    http_logs=[
                        HttpLog(
                            code=f"http_error_{status_code}",
                            detail=f"HTTP error {status_code}",
                            req=req,
                            res=res,
                        )
                    ],
                    response=res,
                    data=None,
                    extensions=None,
                )

            except (httpx.RequestError, httpx.ConnectError, httpx.TimeoutException):
                # Network/connection errors - return immediately without retry
                # Use the req already defined above, create new res for error
                error_req: RequestInput = {
                    "url": endpoint,
                    "method": "POST",
                    "headers": request_headers,
                    "body": json.dumps(request_body),
                }
                error_res = Res(status=0, body="", headers={})
                return GQLResult(
                    ok=False,
                    shop=None,
                    log=Log(
                        code="network_error",
                        detail="Network error occurred during GraphQL request",
                    ),
                    http_logs=[
                        HttpLog(
                            code="network_error",
                            detail="Network error occurred during GraphQL request",
                            req=error_req,
                            res=error_res,
                        )
                    ],
                    response=error_res,
                    data=None,
                    extensions=None,
                )

    # Should never reach here due to while loop logic
    raise AssertionError("unreachable: while loop should always return")


def _validate_graphql_params(
    shop: str,
    access_token: str,
    api_version: str,
    query: str,
) -> Tuple[bool, Optional[GQLResult]]:
    """Validate all required GraphQL parameters.

    Args:
        shop: Shop domain
        access_token: Access token for authentication
        api_version: API version string
        query: GraphQL query string

    Returns:
        tuple: (is_valid: bool, error_response: GQLResult or None)
    """
    if not shop:
        return (
            False,
            GQLResult(
                ok=False,
                shop=None,
                log=Log(code="missing_shop", detail="Shop domain is required"),
                response=Res(status=400, body="", headers={}),
                data=None,
                extensions=None,
                http_logs=[],
            ),
        )

    if not access_token:
        return (
            False,
            GQLResult(
                ok=False,
                shop=None,
                log=Log(code="missing_access_token", detail="Access token is required"),
                response=Res(status=400, body="", headers={}),
                data=None,
                extensions=None,
                http_logs=[],
            ),
        )

    if not api_version:
        return (
            False,
            GQLResult(
                ok=False,
                shop=None,
                log=Log(code="missing_api_version", detail="API version is required"),
                response=Res(status=400, body="", headers={}),
                data=None,
                extensions=None,
                http_logs=[],
            ),
        )

    if not query:
        return (
            False,
            GQLResult(
                ok=False,
                shop=None,
                log=Log(code="missing_query", detail="GraphQL query is required"),
                response=Res(status=400, body="", headers={}),
                data=None,
                extensions=None,
                http_logs=[],
            ),
        )

    return (True, None)


def _get_status_text(status_code):
    """Get status text for HTTP status code."""
    status_texts = {
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }
    return status_texts.get(status_code, "Error")


def _handle_429_retry_sync(
    status_code: int,
    attempt: int,
    max_retries: int,
    response_headers: Dict[str, Any],
    logs: List[HttpLog],
    req: RequestInput,
    res: Res,
) -> Tuple[bool, bool, Optional[GQLResult]]:
    """Handle 429 rate limit retry for sync GraphQL requests."""
    if status_code == 429 and attempt < max_retries:
        retry_after = response_headers.get("Retry-After", "1")
        logs.append(
            HttpLog(
                code="rate_limited_retry",
                detail=f"Rate limited. Retrying after {retry_after} seconds (attempt {attempt + 1} of {max_retries + 1}).",
                req=req,
                res=res,
            )
        )
        time.sleep(int(retry_after))
        return (True, False, None)

    if status_code == 429 and attempt == max_retries:
        logs.append(
            HttpLog(
                code="rate_limited",
                detail="Max retries reached after rate limiting. Return 429 Too Many Requests.",
                req=req,
                res=res,
            )
        )
        return (
            False,
            True,
            GQLResult(
                ok=False,
                shop=None,
                log=Log(
                    code="rate_limited",
                    detail="Max retries reached after rate limiting. Return 429 Too Many Requests.",
                ),
                http_logs=logs,
                response=Res(
                    status=429,
                    body='{"error":"Too many requests"}',
                    headers={"Content-Type": "application/json"},
                ),
                data=None,
                extensions=None,
            ),
        )

    return (False, False, None)


async def _handle_429_retry_async(
    status_code: int,
    attempt: int,
    max_retries: int,
    response_headers: Dict[str, Any],
    logs: List[HttpLog],
    req: RequestInput,
    res: Res,
) -> Tuple[bool, bool, Optional[GQLResult]]:
    """Handle 429 rate limit retry for async GraphQL requests."""
    if status_code == 429 and attempt < max_retries:
        retry_after = response_headers.get("Retry-After", "1")
        logs.append(
            HttpLog(
                code="rate_limited_retry",
                detail=f"Rate limited. Retrying after {retry_after} seconds (attempt {attempt + 1} of {max_retries + 1}).",
                req=req,
                res=res,
            )
        )
        await asyncio.sleep(int(retry_after))
        return (True, False, None)

    if status_code == 429 and attempt == max_retries:
        logs.append(
            HttpLog(
                code="rate_limited",
                detail="Max retries reached after rate limiting. Return 429 Too Many Requests.",
                req=req,
                res=res,
            )
        )
        return (
            False,
            True,
            GQLResult(
                ok=False,
                shop=None,
                log=Log(
                    code="rate_limited",
                    detail="Max retries reached after rate limiting. Return 429 Too Many Requests.",
                ),
                http_logs=logs,
                response=Res(
                    status=429,
                    body='{"error":"Too many requests"}',
                    headers={"Content-Type": "application/json"},
                ),
                data=None,
                extensions=None,
            ),
        )

    return (False, False, None)


def _handle_5xx_retry_sync(
    status_code: int,
    attempt: int,
    max_retries: int,
    logs: List[HttpLog],
    req: RequestInput,
    res: Res,
) -> Tuple[bool, bool, Optional[GQLResult]]:
    """Handle 5xx retry with exponential backoff for sync requests."""
    if status_code in [502, 503, 504] and attempt < max_retries:
        base_delay = 1
        delay = base_delay * (2**attempt) + (random.randint(0, 100) / 1000)
        logs.append(
            HttpLog(
                code=f"http_error_{status_code}_retry",
                detail=f"HTTP {status_code} error. Retrying with exponential backoff (attempt {attempt + 1} of {max_retries + 1}).",
                req=req,
                res=res,
            )
        )
        time.sleep(delay)
        return (True, False, None)

    if status_code in [502, 503, 504] and attempt == max_retries:
        logs.append(
            HttpLog(
                code=f"http_error_{status_code}",
                detail=f"Max retries reached for transient error. Return {status_code} {_get_status_text(status_code)}.",
                req=req,
                res=res,
            )
        )
        return (
            False,
            True,
            GQLResult(
                ok=False,
                shop=None,
                log=Log(
                    code=f"http_error_{status_code}",
                    detail=f"Max retries reached for transient error. Return {status_code} {_get_status_text(status_code)}.",
                ),
                http_logs=logs,
                response=Res(status=status_code, body="", headers={}),
                data=None,
                extensions=None,
            ),
        )

    return (False, False, None)


async def _handle_5xx_retry_async(
    status_code: int,
    attempt: int,
    max_retries: int,
    logs: List[HttpLog],
    req: RequestInput,
    res: Res,
) -> Tuple[bool, bool, Optional[GQLResult]]:
    """Handle 5xx retry with exponential backoff for async requests."""
    if status_code in [502, 503, 504] and attempt < max_retries:
        base_delay = 1
        delay = base_delay * (2**attempt) + (random.randint(0, 100) / 1000)
        logs.append(
            HttpLog(
                code=f"http_error_{status_code}_retry",
                detail=f"HTTP {status_code} error. Retrying with exponential backoff (attempt {attempt + 1} of {max_retries + 1}).",
                req=req,
                res=res,
            )
        )
        await asyncio.sleep(delay)
        return (True, False, None)

    if status_code in [502, 503, 504] and attempt == max_retries:
        logs.append(
            HttpLog(
                code=f"http_error_{status_code}",
                detail=f"Max retries reached for transient error. Return {status_code} {_get_status_text(status_code)}.",
                req=req,
                res=res,
            )
        )
        return (
            False,
            True,
            GQLResult(
                ok=False,
                shop=None,
                log=Log(
                    code=f"http_error_{status_code}",
                    detail=f"Max retries reached for transient error. Return {status_code} {_get_status_text(status_code)}.",
                ),
                http_logs=logs,
                response=Res(status=status_code, body="", headers={}),
                data=None,
                extensions=None,
            ),
        )

    return (False, False, None)


def _handle_401_response(
    invalid_token_response: Optional[Union[Res, dict]],
    req: RequestInput,
    res: Res,
) -> GQLResult:
    """Handle 401 unauthorized responses."""
    # If invalidTokenResponse provided, return it (convert dict to Res if needed)
    response = _to_res(invalid_token_response)
    if response is None:
        # No retry mechanism, return plain 401
        response = Res(status=401, body="", headers={})

    return GQLResult(
        ok=False,
        shop=None,
        log=Log(
            code="unauthorized", detail="Access token is invalid or has been revoked."
        ),
        response=response,
        data=None,
        extensions=None,
        http_logs=[
            HttpLog(
                code="unauthorized",
                detail="Access token is invalid or has been revoked.",
                req=req,
                res=res,
            )
        ],
    )


async def admin_graphql_request_async(
    query: str,
    shop: str,
    access_token: str,
    api_version: str,
    invalid_token_response: Optional[Union[Res, dict]] = None,
    variables: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    max_retries: int = 2,
    app_config: Optional[AppConfig] = None,
    http_client: Optional[httpx.AsyncClient] = None,
) -> GQLResult:
    """
    Make an async GraphQL request to the Shopify Admin API.

    This is the async version of admin_graphql_request. Use this when you need
    to make non-blocking GraphQL requests in async code.

    Args:
        query (str): The GraphQL query or mutation string
        app_config (dict): App configuration (not currently used)
        http_client: Optional async HTTP client for testing (httpx.AsyncClient)
        shop (str): Shop domain (e.g., "example")
        access_token (str): Valid access token for the shop
        api_version (str): API version (e.g., "2024-01")
        invalid_token_response (Res | dict): Pre-built response to return if token is invalid (or None)
        variables (dict[str, Any]): Optional GraphQL variables
        headers (dict[str, str]): Optional additional HTTP headers
        max_retries (int): Optional custom retry count (default: 2)

    Returns:
        GQLResult: Result containing ok, logs, response, data, and extensions
    """
    if headers is None:
        headers = {}

    # Validate required parameters
    is_valid, error = _validate_graphql_params(shop, access_token, api_version, query)
    if not is_valid:
        if error is None:
            raise RuntimeError("_validate_graphql_params returned invalid but no error")
        return error

    # Store original shop for return value
    original_shop = shop

    endpoint = f"https://{shop}.myshopify.com/admin/api/{api_version}/graphql.json"

    request_headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token,
        "User-Agent": _get_user_agent(),
        **headers,
    }

    request_body: Dict[str, Any] = {"query": query}
    if variables:
        request_body["variables"] = variables

    # Execute request with retry logic
    attempt = 0
    logs: List[HttpLog] = []

    async with AsyncHTTPClientContext(http_client) as client:
        while attempt <= max_retries:
            try:
                response = await client.post(
                    endpoint,
                    headers=request_headers,
                    json=request_body,
                )

                status_code = response.status_code
                response_body = response.text
                response_headers = dict(response.headers)

                req: RequestInput = {
                    "url": endpoint,
                    "method": "POST",
                    "headers": request_headers,
                    "body": json.dumps(request_body),
                }

                res = Res(
                    status=status_code, body=response_body, headers=response_headers
                )

                # Handle 200 success (but check for GraphQL errors)
                if status_code == 200:
                    try:
                        response_data = response.json()
                    except json.JSONDecodeError:
                        response_data = {}

                    # Check for GraphQL errors
                    if response_data.get("errors"):
                        logs.append(
                            HttpLog(
                                code="graphql_errors",
                                detail="GraphQL request returned errors",
                                req=req,
                                res=res,
                            )
                        )
                        return GQLResult(
                            ok=False,
                            shop=None,
                            log=Log(
                                code="graphql_errors",
                                detail="GraphQL request returned errors",
                            ),
                            http_logs=logs,
                            response=res,
                            data=None,
                            extensions=None,
                        )

                    # Success
                    logs.append(
                        HttpLog(
                            code="success",
                            detail="GraphQL request successful. Proceed with business logic.",
                            req=req,
                            res=res,
                        )
                    )
                    return GQLResult(
                        ok=True,
                        shop=original_shop,
                        log=Log(
                            code="success",
                            detail="GraphQL request successful. Proceed with business logic.",
                        ),
                        http_logs=logs,
                        response=res,
                        data=response_data.get("data"),
                        extensions=response_data.get("extensions"),
                    )

                # Handle 401 unauthorized
                if status_code == 401:
                    return _handle_401_response(invalid_token_response, req, res)

                # Handle 429 rate limit with retry helper
                should_retry, should_return, return_value = (
                    await _handle_429_retry_async(
                        status_code,
                        attempt,
                        max_retries,
                        response_headers,
                        logs,
                        req,
                        res,
                    )
                )
                if should_return:
                    if return_value is None:
                        raise RuntimeError(
                            "_handle_429_retry_async returned should_return=True but no return_value"
                        )
                    return return_value
                if should_retry:
                    attempt += 1
                    continue

                # Handle 5xx errors with retry helper
                should_retry, should_return, return_value = (
                    await _handle_5xx_retry_async(
                        status_code, attempt, max_retries, logs, req, res
                    )
                )
                if should_return:
                    if return_value is None:
                        raise RuntimeError(
                            "_handle_5xx_retry_async returned should_return=True but no return_value"
                        )
                    return return_value
                if should_retry:
                    attempt += 1
                    continue

                # Handle non-retryable errors
                if status_code == 400:
                    return GQLResult(
                        ok=False,
                        shop=None,
                        log=Log(
                            code="http_error_400",
                            detail="GraphQL query syntax is invalid. Do not retry.",
                        ),
                        http_logs=[
                            HttpLog(
                                code="http_error_400",
                                detail="GraphQL query syntax is invalid. Do not retry.",
                                req=req,
                                res=res,
                            )
                        ],
                        response=res,
                        data=None,
                        extensions=None,
                    )

                if status_code == 403:
                    return GQLResult(
                        ok=False,
                        shop=None,
                        log=Log(
                            code="http_error_403",
                            detail="Access token lacks required permissions. Do not retry.",
                        ),
                        http_logs=[
                            HttpLog(
                                code="http_error_403",
                                detail="Access token lacks required permissions. Do not retry.",
                                req=req,
                                res=res,
                            )
                        ],
                        response=res,
                        data=None,
                        extensions=None,
                    )

                # Other HTTP errors
                return GQLResult(
                    ok=False,
                    shop=None,
                    log=Log(
                        code=f"http_error_{status_code}",
                        detail=f"HTTP error {status_code}",
                    ),
                    http_logs=[
                        HttpLog(
                            code=f"http_error_{status_code}",
                            detail=f"HTTP error {status_code}",
                            req=req,
                            res=res,
                        )
                    ],
                    response=res,
                    data=None,
                    extensions=None,
                )

            except (httpx.RequestError, httpx.ConnectError, httpx.TimeoutException):
                # Network/connection errors - return immediately without retry
                # Use different variable names to avoid redefinition
                error_req: RequestInput = {
                    "url": endpoint,
                    "method": "POST",
                    "headers": request_headers,
                    "body": json.dumps(request_body),
                }
                error_res = Res(status=0, body="", headers={})
                return GQLResult(
                    ok=False,
                    shop=None,
                    log=Log(
                        code="network_error",
                        detail="Network error occurred during GraphQL request",
                    ),
                    http_logs=[
                        HttpLog(
                            code="network_error",
                            detail="Network error occurred during GraphQL request",
                            req=error_req,
                            res=error_res,
                        )
                    ],
                    response=error_res,
                    data=None,
                    extensions=None,
                )

    # Should never reach here due to while loop logic
    raise AssertionError("unreachable: while loop should always return")
