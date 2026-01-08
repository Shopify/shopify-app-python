"""
Shopify Refresh Token

This module provides functions to refresh expired access tokens.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional, Tuple, Union, cast

import httpx

from ..types import (
    AppConfig,
    HttpLog,
    Log,
    RequestInput,
    Res,
    TokenExchangeAccessToken,
    TokenExchangeResult,
    User,
)
from ..utils import _get_attr, _get_user_agent
from ..utils.http_client import AsyncHTTPClientContext, HTTPClientContext
from ._response_builders import build_network_error_response
from ._validation import validate_client_id, validate_shop


def refresh_access_token(
    access_token: Union[TokenExchangeAccessToken, dict],
    app_config: AppConfig,
    http_client: Optional[httpx.Client] = None,
) -> TokenExchangeResult:
    """
    Refresh an expired access token using a refresh token.

    Args:
        access_token (TokenExchangeAccessToken | dict): TokenExchangeAccessToken object (requires: shop, refresh_token, expires, refresh_token_expires, access_mode)
        app_config (dict): App configuration containing:
            - client_id: The app's client ID
            - client_secret: The app's client secret
        http_client: Optional HTTP client for testing

    Returns:
        TokenExchangeResult: Result containing ok, shop, access_token, log, http_logs, and response
    """
    shop = _get_attr(access_token, "shop", "")
    refresh_token = _get_attr(access_token, "refresh_token", "")
    expires = _get_attr(access_token, "expires", "")
    refresh_token_expires = _get_attr(access_token, "refresh_token_expires", "")
    original_access_mode = _get_attr(access_token, "access_mode", "offline")
    original_user = _get_attr(access_token, "user", None)

    client_id = app_config.get("client_id", "")
    client_secret = app_config.get("client_secret", "")

    # Validate token expiration (returns early if token still valid or refresh token expired)
    should_continue, response = _validate_token_expiry(
        expires, refresh_token_expires, shop
    )
    if not should_continue:
        if response is None:
            raise RuntimeError(
                "_validate_token_expiry returned should_continue=False but no response"
            )
        return response

    # Validate required parameters
    is_valid, error = validate_shop(shop, result_type="token_exchange")
    if not is_valid:
        if error is None:
            raise RuntimeError("validate_shop returned invalid but no error")
        return error

    is_valid, error = validate_client_id(client_id, shop, result_type="token_exchange")
    if not is_valid:
        if error is None:
            raise RuntimeError("validate_client_id returned invalid but no error")
        return error

    is_valid, error = _validate_refresh_token(refresh_token, shop)
    if not is_valid:
        if error is None:
            raise RuntimeError("_validate_refresh_token returned invalid but no error")
        return error

    # Build request
    token_endpoint, request_body, request_headers = _build_request(
        client_id, client_secret, refresh_token, shop
    )

    # Make the request with retry logic for 5xx responses
    max_retries = 2
    attempt = 0
    http_logs: List[HttpLog] = []

    # Build the request object for logging
    req_log: RequestInput = {
        "url": token_endpoint,
        "method": "POST",
        "headers": request_headers,
        "body": "",  # Don't log sensitive body
    }

    with HTTPClientContext(http_client) as client:
        while attempt <= max_retries:
            try:
                http_response = client.post(
                    token_endpoint,
                    headers=request_headers,
                    json=request_body,
                )

                status_code = http_response.status_code
                response_headers = dict(http_response.headers)

                # Build response object for logging
                res_log = Res(status=status_code, body="", headers=response_headers)

                # Handle 200 success
                if status_code == 200:
                    response_data = http_response.json()
                    # Cast access_mode to Literal type - we've validated it's a valid value
                    access_mode_literal = cast(
                        Literal["online", "offline"], original_access_mode
                    )
                    return _handle_success_response(
                        response_data,
                        shop,
                        access_mode_literal,
                        original_user,
                        http_logs,
                        req_log,
                        res_log,
                    )

                # Handle 5xx server errors with retry
                if 500 <= status_code <= 504:
                    if attempt < max_retries:
                        http_logs.append(
                            HttpLog(
                                code="server_error_retry",
                                detail=f"Server error {status_code}, retrying (attempt {attempt + 1} of {max_retries}).",
                                req=req_log,
                                res=res_log,
                            )
                        )
                        attempt += 1
                        continue

                    http_logs.append(
                        HttpLog(
                            code="server_error",
                            detail="Max retries reached after server errors. Respond 500 Internal Server Error using the provided response.",
                            req=req_log,
                            res=res_log,
                        )
                    )
                    return TokenExchangeResult(
                        ok=False,
                        shop=shop,
                        access_token=None,
                        log=Log(
                            code="server_error",
                            detail="Max retries reached after server errors. Respond 500 Internal Server Error using the provided response.",
                        ),
                        http_logs=http_logs,
                        response=Res(status=500, body="", headers={}),
                    )

                # Handle error responses
                try:
                    response_data = http_response.json()
                except Exception:
                    response_data = {}

                return _handle_error_response(
                    response_data, shop, http_logs, req_log, res_log
                )

            except httpx.RequestError:
                return build_network_error_response(
                    shop, http_logs, req_log, "token refresh", "token_exchange"
                )

    # Should never reach here due to while loop logic
    raise AssertionError("unreachable: while loop should always return")


def _validate_refresh_token(
    refresh_token: str,
    shop: Optional[str] = None,
) -> Tuple[bool, Optional[TokenExchangeResult]]:
    """Validate refresh_token parameter.

    Args:
        refresh_token: Refresh token to validate
        shop: Optional shop name for error response

    Returns:
        tuple: (is_valid: bool, error_response: TokenExchangeResult or None)
    """
    if not refresh_token:
        return (
            False,
            TokenExchangeResult(
                ok=False,
                shop=None,
                access_token=None,
                log=Log(
                    code="configuration_error",
                    detail="Expected refresh token to be a non-empty string, but got ''",
                ),
                http_logs=[],
                response=Res(status=500, body="", headers={}),
            ),
        )
    return (True, None)


def _validate_token_expiry(
    expires: str,
    refresh_token_expires: str,
    shop: str,
) -> Tuple[bool, Optional[TokenExchangeResult]]:
    """Validate token expiration and determine if refresh is needed.

    Args:
        expires: Access token expiration timestamp (ISO format string)
        refresh_token_expires: Refresh token expiration timestamp (ISO format string)
        shop: Shop name for error response

    Returns:
        tuple: (should_continue: bool, response: TokenExchangeResult or None)
    """
    # Check refresh token expiration
    if refresh_token_expires:
        try:
            refresh_expiry = datetime.fromisoformat(
                refresh_token_expires.replace("Z", "+00:00")
            )
            if refresh_expiry <= datetime.now(timezone.utc):
                return (
                    False,
                    TokenExchangeResult(
                        ok=False,
                        shop=shop,
                        access_token=None,
                        log=Log(
                            code="refresh_token_expired",
                            detail="Refresh token has expired. User must re-authenticate. Respond 401 Unauthorized using the provided response.",
                        ),
                        http_logs=[],
                        response=Res(status=401, body="", headers={}),
                    ),
                )
        except ValueError:
            pass  # Invalid date format, continue with refresh

    # Check if access token is still valid (with 60-second buffer)
    if expires:
        try:
            expiry = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            if expiry > (datetime.now(timezone.utc) + timedelta(seconds=60)):
                return (
                    False,
                    TokenExchangeResult(
                        ok=True,
                        shop=shop,
                        access_token=None,
                        log=Log(
                            code="token_still_valid",
                            detail="Access token is still valid. No refresh needed. Proceed with business logic.",
                        ),
                        http_logs=[],
                        response=Res(status=200, body="", headers={}),
                    ),
                )
        except ValueError:
            pass  # Invalid date format, continue with refresh

    return (True, None)


def _build_request(client_id, client_secret, refresh_token, shop):
    """Build refresh token request components.

    Args:
        client_id: OAuth client ID
        client_secret: OAuth client secret
        refresh_token: Refresh token to use
        shop: Shop name (e.g., "shop-name")

    Returns:
        tuple: (endpoint, request_body, request_headers)
    """
    shop_url = f"https://{shop}.myshopify.com"

    request_body = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    token_endpoint = f"{shop_url}/admin/oauth/access_token"

    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": _get_user_agent(),
    }

    return token_endpoint, request_body, request_headers


def _handle_success_response(
    response_data: dict,
    shop: str,
    original_access_mode: Literal["online", "offline"],
    original_user: Optional[User],
    http_logs: List[HttpLog],
    req_log: RequestInput,
    res_log: Res,
) -> TokenExchangeResult:
    """Handle successful token refresh response."""
    access_token = response_data.get("access_token", "")
    expires_in = response_data.get("expires_in", 0)
    scope = response_data.get("scope", "")
    refresh_token = response_data.get("refresh_token", "")
    refresh_token_expires_in = response_data.get("refresh_token_expires_in", 0)

    # Calculate expiration timestamps
    expires = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    refresh_token_expires = (
        datetime.now(timezone.utc) + timedelta(seconds=refresh_token_expires_in)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    access_token_obj = TokenExchangeAccessToken(
        access_mode=original_access_mode,
        shop=shop,
        token=access_token,
        expires=expires,
        scope=scope,
        refresh_token=refresh_token,
        refresh_token_expires=refresh_token_expires,
        user=original_user,
    )

    http_logs.append(
        HttpLog(
            code="success",
            detail="Token refresh successful. Store the new access and refresh token then proceed with business logic.",
            req=req_log,
            res=res_log,
        )
    )

    return TokenExchangeResult(
        ok=True,
        shop=shop,
        access_token=access_token_obj,
        log=Log(
            code="success",
            detail="Token refresh successful. Store the new access and refresh token then proceed with business logic.",
        ),
        http_logs=http_logs,
        response=Res(status=200, body="", headers={}),
    )


def _handle_error_response(
    response_data: dict,
    shop: str,
    http_logs: List[HttpLog],
    req_log: RequestInput,
    res_log: Res,
) -> TokenExchangeResult:
    """Handle error responses from token refresh."""
    error = response_data.get("error", "unknown_error")

    # Handle invalid_grant
    if error == "invalid_grant":
        http_logs.append(
            HttpLog(
                code="invalid_grant",
                detail="Refresh token is invalid, expired, or has been revoked. User must re-authenticate. Respond 401 Unauthorized using the provided response.",
                req=req_log,
                res=res_log,
            )
        )
        return TokenExchangeResult(
            ok=False,
            shop=shop,
            access_token=None,
            log=Log(
                code="invalid_grant",
                detail="Refresh token is invalid, expired, or has been revoked. User must re-authenticate. Respond 401 Unauthorized using the provided response.",
            ),
            http_logs=http_logs,
            response=Res(status=401, body="", headers={}),
        )

    # Handle invalid_client
    if error == "invalid_client":
        http_logs.append(
            HttpLog(
                code="invalid_client",
                detail="Client credentials are invalid or app has been uninstalled. Respond 500 Internal Server Error using the provided response.",
                req=req_log,
                res=res_log,
            )
        )
        return TokenExchangeResult(
            ok=False,
            shop=shop,
            access_token=None,
            log=Log(
                code="invalid_client",
                detail="Client credentials are invalid or app has been uninstalled. Respond 500 Internal Server Error using the provided response.",
            ),
            http_logs=http_logs,
            response=Res(status=500, body="", headers={}),
        )

    # Fallback for other errors
    http_logs.append(
        HttpLog(
            code="refresh_error",
            detail=f"Token refresh failed with error: {error}. Respond 500 Internal Server Error using the provided response.",
            req=req_log,
            res=res_log,
        )
    )
    return TokenExchangeResult(
        ok=False,
        shop=shop,
        access_token=None,
        log=Log(
            code="refresh_error",
            detail=f"Token refresh failed with error: {error}. Respond 500 Internal Server Error using the provided response.",
        ),
        http_logs=http_logs,
        response=Res(status=500, body="", headers={}),
    )


async def refresh_access_token_async(
    access_token: Union[TokenExchangeAccessToken, dict],
    app_config: AppConfig,
    http_client: Optional[httpx.AsyncClient] = None,
) -> TokenExchangeResult:
    """
    Async version of refresh_access_token.

    Refresh an expired access token using a refresh token.
    Use this when you need non-blocking token refresh in async code.

    Args:
        access_token (TokenExchangeAccessToken | dict): TokenExchangeAccessToken object (requires: shop, refresh_token, expires, refresh_token_expires, access_mode)
        app_config (dict): App configuration containing:
            - client_id: The app's client ID
            - client_secret: The app's client secret
        http_client: Optional async HTTP client for testing (httpx.AsyncClient)

    Returns:
        TokenExchangeResult: Result containing ok, shop, access_token, log, http_logs, and response
    """
    shop = _get_attr(access_token, "shop", "")
    refresh_token = _get_attr(access_token, "refresh_token", "")
    expires = _get_attr(access_token, "expires", "")
    refresh_token_expires = _get_attr(access_token, "refresh_token_expires", "")
    original_access_mode = _get_attr(access_token, "access_mode", "offline")
    original_user = _get_attr(access_token, "user", None)

    client_id = app_config.get("client_id", "")
    client_secret = app_config.get("client_secret", "")

    # Validate token expiration (returns early if token still valid or refresh token expired)
    should_continue, response = _validate_token_expiry(
        expires, refresh_token_expires, shop
    )
    if not should_continue:
        if response is None:
            raise RuntimeError(
                "_validate_token_expiry returned should_continue=False but no response"
            )
        return response

    # Validate required parameters
    is_valid, error = validate_shop(shop, result_type="token_exchange")
    if not is_valid:
        if error is None:
            raise RuntimeError("validate_shop returned invalid but no error")
        return error

    is_valid, error = validate_client_id(client_id, shop, result_type="token_exchange")
    if not is_valid:
        if error is None:
            raise RuntimeError("validate_client_id returned invalid but no error")
        return error

    is_valid, error = _validate_refresh_token(refresh_token, shop)
    if not is_valid:
        if error is None:
            raise RuntimeError("_validate_refresh_token returned invalid but no error")
        return error

    # Build request
    token_endpoint, request_body, request_headers = _build_request(
        client_id, client_secret, refresh_token, shop
    )

    # Make the request with retry logic for 5xx responses
    max_retries = 2
    attempt = 0
    http_logs: List[HttpLog] = []

    # Build the request object for logging
    req_log: RequestInput = {
        "url": token_endpoint,
        "method": "POST",
        "headers": request_headers,
        "body": "",  # Don't log sensitive body
    }

    async with AsyncHTTPClientContext(http_client) as client:
        while attempt <= max_retries:
            try:
                http_response = await client.post(
                    token_endpoint,
                    headers=request_headers,
                    json=request_body,
                )

                status_code = http_response.status_code
                response_headers = dict(http_response.headers)

                # Build response object for logging
                res_log = Res(status=status_code, body="", headers=response_headers)

                # Handle 200 success
                if status_code == 200:
                    response_data = http_response.json()
                    # Cast access_mode to Literal type - we've validated it's a valid value
                    access_mode_literal = cast(
                        Literal["online", "offline"], original_access_mode
                    )
                    return _handle_success_response(
                        response_data,
                        shop,
                        access_mode_literal,
                        original_user,
                        http_logs,
                        req_log,
                        res_log,
                    )

                # Handle 5xx server errors with retry
                if 500 <= status_code <= 504:
                    if attempt < max_retries:
                        http_logs.append(
                            HttpLog(
                                code="server_error_retry",
                                detail=f"Server error {status_code}, retrying (attempt {attempt + 1} of {max_retries}).",
                                req=req_log,
                                res=res_log,
                            )
                        )
                        attempt += 1
                        continue

                    http_logs.append(
                        HttpLog(
                            code="server_error",
                            detail="Max retries reached after server errors. Respond 500 Internal Server Error using the provided response.",
                            req=req_log,
                            res=res_log,
                        )
                    )
                    return TokenExchangeResult(
                        ok=False,
                        shop=shop,
                        access_token=None,
                        log=Log(
                            code="server_error",
                            detail="Max retries reached after server errors. Respond 500 Internal Server Error using the provided response.",
                        ),
                        http_logs=http_logs,
                        response=Res(status=500, body="", headers={}),
                    )

                # Handle error responses
                try:
                    response_data = http_response.json()
                except Exception:
                    response_data = {}

                return _handle_error_response(
                    response_data, shop, http_logs, req_log, res_log
                )

            except httpx.RequestError:
                return build_network_error_response(
                    shop, http_logs, req_log, "token refresh", "token_exchange"
                )

    # Should never reach here due to while loop logic
    raise AssertionError("unreachable: while loop should always return")
