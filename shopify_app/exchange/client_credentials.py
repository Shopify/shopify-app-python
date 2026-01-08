"""
Shopify Client Credentials Exchange

This module provides functions to exchange client credentials for API access tokens.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import httpx

from ..types import (
    AppConfig,
    ClientCredentialsAccessToken,
    ClientCredentialsExchangeResult,
    HttpLog,
    Log,
    RequestInput,
    Res,
)
from ..utils import _get_user_agent
from ..utils.http_client import AsyncHTTPClientContext, HTTPClientContext
from ._response_builders import build_network_error_response
from ._validation import validate_shop


def exchange_using_client_credentials(
    shop: str,
    app_config: AppConfig,
    http_client: Optional[httpx.Client] = None,
) -> ClientCredentialsExchangeResult:
    """
    Exchange client credentials for an API access token.

    Args:
        shop (str): The shop domain (e.g., "shop-name")
        app_config (dict): App configuration containing:
            - client_id: The Shopify app client ID
            - client_secret: The app's client secret
        http_client: Optional HTTP client for testing

    Returns:
        ClientCredentialsExchangeResult: Result containing ok, shop, access_token, log, http_logs, and response
    """
    client_id = app_config.get("client_id", "")
    client_secret = app_config.get("client_secret", "")

    # Validate shop parameter
    is_valid, error = validate_shop(shop, result_type="client_credentials")
    if not is_valid:
        if error is None:
            raise RuntimeError("validate_shop returned invalid but no error")
        return error

    # Validate shop format
    is_valid, error = _validate_shop_format(shop)
    if not is_valid:
        if error is None:
            raise RuntimeError("_validate_shop_format returned invalid but no error")
        return error

    # Build request
    token_endpoint, request_body, request_headers, req_obj = _build_request(
        client_id, client_secret, shop
    )

    http_logs: List[HttpLog] = []

    # Use HTTP client context manager
    with HTTPClientContext(http_client) as client:
        try:
            response = client.post(
                token_endpoint,
                headers=request_headers,
                json=request_body,
            )

            status_code = response.status_code
            response_body = response.text

            # Build response object for logging
            response_headers = (
                dict(response.headers) if hasattr(response, "headers") else {}
            )
            res_obj = Res(
                status=status_code, body=response_body, headers=response_headers
            )

            # Handle 200 success
            if status_code == 200:
                response_data = response.json()
                return _handle_success_response(
                    response_data, shop, http_logs, req_obj, res_obj
                )

            # Handle error responses
            try:
                response_data = response.json()
            except Exception:
                response_data = {}

            return _handle_error_response(
                response_data, shop, http_logs, req_obj, res_obj
            )

        except httpx.RequestError:
            return build_network_error_response(
                shop,
                http_logs,
                req_obj,
                "client credentials exchange",
                "client_credentials",
            )


def _validate_shop_format(
    shop: str,
) -> Tuple[bool, Optional[ClientCredentialsExchangeResult]]:
    """Validate shop format (alphanumeric and hyphens only).

    Args:
        shop: Shop string to validate format

    Returns:
        tuple: (is_valid: bool, error_response: ClientCredentialsExchangeResult or None)
    """
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*$", shop):
        return (
            False,
            ClientCredentialsExchangeResult(
                ok=False,
                shop=None,
                access_token=None,
                log=Log(
                    code="configuration_error",
                    detail="Expected shop to be a valid shop domain (e.g., 'shop-name')",
                ),
                http_logs=[],
                response=Res(status=500, body="", headers={}),
            ),
        )
    return (True, None)


def _build_request(client_id, client_secret, shop):
    """Build client credentials request components.

    Args:
        client_id: OAuth client ID
        client_secret: OAuth client secret
        shop: Shop name (e.g., "shop-name")

    Returns:
        tuple: (endpoint, request_body, request_headers, req_obj)
    """
    token_endpoint = f"https://{shop}.myshopify.com/admin/oauth/access_token"

    request_body = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }

    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": _get_user_agent(),
    }

    req_obj = {
        "method": "POST",
        "url": token_endpoint,
        "headers": request_headers,
        "body": json.dumps(request_body),
    }

    return token_endpoint, request_body, request_headers, req_obj


def _handle_success_response(
    response_data: dict,
    shop: str,
    http_logs: List[HttpLog],
    req_obj: RequestInput,
    res_obj: Res,
) -> ClientCredentialsExchangeResult:
    """Handle successful client credentials exchange response."""
    access_token = response_data.get("access_token", "")
    expires_in = response_data.get("expires_in")
    scope = response_data.get("scope", "")

    # Calculate expiration timestamp
    expires = (
        (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        if expires_in is not None
        else None
    )

    access_token_obj = ClientCredentialsAccessToken(
        access_mode="offline",
        shop=shop,
        token=access_token,
        expires=expires,
        scope=scope,
        user=None,
    )

    http_logs.append(
        HttpLog(
            code="success",
            detail="Client credentials exchange successful. Store the access token and proceed with business logic.",
            req=req_obj,
            res=res_obj,
        )
    )

    return ClientCredentialsExchangeResult(
        ok=True,
        shop=shop,
        access_token=access_token_obj,
        log=Log(
            code="success",
            detail="Client credentials exchange successful. Store the access token and proceed with business logic.",
        ),
        http_logs=http_logs,
        response=Res(status=200, body="", headers={}),
    )


def _handle_error_response(
    response_data: dict,
    shop: str,
    http_logs: List[HttpLog],
    req_obj: RequestInput,
    res_obj: Res,
) -> ClientCredentialsExchangeResult:
    """Handle error responses from client credentials exchange."""
    error = response_data.get("error", "unknown_error")

    # Handle invalid_client
    if error == "invalid_client":
        http_logs.append(
            HttpLog(
                code="invalid_client",
                detail="Client credentials are invalid or the app has been uninstalled. Respond 500 Internal Server Error using the provided response.",
                req=req_obj,
                res=res_obj,
            )
        )
        return ClientCredentialsExchangeResult(
            ok=False,
            shop=shop,
            access_token=None,
            log=Log(
                code="invalid_client",
                detail="Client credentials are invalid or the app has been uninstalled. Respond 500 Internal Server Error using the provided response.",
            ),
            http_logs=http_logs,
            response=Res(status=500, body="", headers={}),
        )

    # Fallback for other errors
    http_logs.append(
        HttpLog(
            code="exchange_error",
            detail=f"Client credentials exchange failed with error: {error}. Respond 500 Internal Server Error using the provided response.",
            req=req_obj,
            res=res_obj,
        )
    )
    return ClientCredentialsExchangeResult(
        ok=False,
        shop=shop,
        access_token=None,
        log=Log(
            code="exchange_error",
            detail=f"Client credentials exchange failed with error: {error}. Respond 500 Internal Server Error using the provided response.",
        ),
        http_logs=http_logs,
        response=Res(status=500, body="", headers={}),
    )


async def exchange_using_client_credentials_async(
    shop: str,
    app_config: AppConfig,
    http_client: Optional[httpx.AsyncClient] = None,
) -> ClientCredentialsExchangeResult:
    """
    Async version of exchange_using_client_credentials.

    Exchange client credentials for an API access token.
    Use this when you need non-blocking client credentials exchange in async code.

    Args:
        shop (str): The shop domain (e.g., "shop-name")
        app_config (dict): App configuration containing:
            - client_id: The Shopify app client ID
            - client_secret: The app's client secret
        http_client: Optional async HTTP client for testing (httpx.AsyncClient)

    Returns:
        ClientCredentialsExchangeResult: Result containing ok, shop, access_token, log, http_logs, and response
    """
    if app_config is None:
        app_config = {}

    client_id = app_config.get("client_id", "")
    client_secret = app_config.get("client_secret", "")

    # Validate shop parameter
    is_valid, error = validate_shop(shop, result_type="client_credentials")
    if not is_valid:
        if error is None:
            raise RuntimeError("validate_shop returned invalid but no error")
        return error

    # Validate shop format
    is_valid, error = _validate_shop_format(shop)
    if not is_valid:
        if error is None:
            raise RuntimeError("_validate_shop_format returned invalid but no error")
        return error

    # Build request
    token_endpoint, request_body, request_headers, req_obj = _build_request(
        client_id, client_secret, shop
    )

    http_logs: List[HttpLog] = []

    # Use async HTTP client context manager
    async with AsyncHTTPClientContext(http_client) as client:
        try:
            response = await client.post(
                token_endpoint,
                headers=request_headers,
                json=request_body,
            )

            status_code = response.status_code
            response_body = response.text

            # Build response object for logging
            response_headers = (
                dict(response.headers) if hasattr(response, "headers") else {}
            )
            res_obj = Res(
                status=status_code, body=response_body, headers=response_headers
            )

            # Handle 200 success
            if status_code == 200:
                response_data = response.json()
                return _handle_success_response(
                    response_data, shop, http_logs, req_obj, res_obj
                )

            # Handle error responses
            try:
                response_data = response.json()
            except Exception:
                response_data = {}

            return _handle_error_response(
                response_data, shop, http_logs, req_obj, res_obj
            )

        except httpx.RequestError:
            return build_network_error_response(
                shop,
                http_logs,
                req_obj,
                "client credentials exchange",
                "client_credentials",
            )
