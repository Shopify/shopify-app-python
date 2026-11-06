"""
Shopify Client Credentials Exchange

This module provides functions to exchange client credentials for API access tokens.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, TypedDict

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
from ..utils import _get_user_agent, redact_http_log, redact_http_response_body
from ..utils.http_client import AsyncHTTPClientContext, HTTPClientContext
from ._response_builders import build_network_error_response
from ._validation import validate_shop

# The assertion type is fixed by the OAuth JWT bearer profile. It is not a
# caller option.
CLIENT_ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"

# An assertion request authenticates with the assertion alone, so another
# credential on the same request is a configuration mistake.
_CONFLICTING_CREDENTIAL_HEADERS = frozenset({"authorization", "x-shopify-access-token"})


class _RequestOptions(TypedDict, total=False):
    auth: None
    follow_redirects: bool


def exchange_using_client_credentials(
    shop: str,
    app_config: AppConfig,
    http_client: Optional[httpx.Client] = None,
    *,
    client_assertion: Optional[str] = None,
) -> ClientCredentialsExchangeResult:
    """
    Exchange client credentials for an API access token.

    Args:
        shop (str): The shop domain (e.g., "shop-name")
        app_config (dict): App configuration containing:
            - client_id: The Shopify app client ID
            - client_secret: The app's client secret
        http_client: Optional HTTP client for testing
        client_assertion (str): Optional app-created JWT. When omitted or None,
            the request authenticates with the configured client secret.

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

    assertion_error = _validate_client_assertion(client_assertion, http_client)
    if assertion_error is not None:
        return assertion_error

    # Build request
    token_endpoint, request_body, request_headers, req_obj = _build_request(
        client_id, client_secret, shop, client_assertion
    )
    request_options = _request_options(client_assertion)

    http_logs: List[HttpLog] = []

    # Use HTTP client context manager
    with HTTPClientContext(http_client) as client:
        try:
            response = client.post(
                token_endpoint,
                headers=request_headers,
                json=request_body,
                **request_options,
            )

            status_code = response.status_code
            response_body = response.text

            # Build response object for logging
            response_headers = (
                dict(response.headers) if hasattr(response, "headers") else {}
            )
            # The token endpoint response carries the newly issued
            # credentials, so redact them before this goes into a log.
            res_obj = Res(
                status=status_code,
                body=redact_http_response_body(response_body),
                headers=response_headers,
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
                response_data,
                shop,
                http_logs,
                req_obj,
                res_obj,
            )

        except httpx.RequestError:
            return build_network_error_response(
                shop,
                http_logs,
                req_obj,
                "client credentials exchange",
                "client_credentials",
            )


def _validate_client_assertion(
    client_assertion: object,
    http_client: object,
) -> Optional[ClientCredentialsExchangeResult]:
    """Validate an optional client assertion and the credentials around it.

    Returns the configuration-error result when the assertion cannot be used,
    or None when the call may proceed. No HTTP request is made first, and a
    rejected assertion never falls back to client-secret authentication.
    """
    if client_assertion is None:
        return None

    if not isinstance(client_assertion, str) or not client_assertion.strip():
        return _configuration_error("Expected clientAssertion to be a non-empty string")

    if http_client is not None:
        if not isinstance(http_client, (httpx.Client, httpx.AsyncClient)):
            return _configuration_error(
                "Client assertion requests require an inspectable HTTP client"
            )
        if any(
            name.lower() in _CONFLICTING_CREDENTIAL_HEADERS
            for name in http_client.headers
        ):
            return _configuration_error(
                "Client assertion requests must not include other authentication credentials"
            )
        if http_client.params:
            return _configuration_error(
                "Client assertion requests must use the unmodified shop token endpoint"
            )

    return None


def _configuration_error(detail: str) -> ClientCredentialsExchangeResult:
    """Build the configuration-error result, which makes no HTTP request."""
    return ClientCredentialsExchangeResult(
        ok=False,
        shop=None,
        access_token=None,
        log=Log(code="configuration_error", detail=detail),
        http_logs=[],
        response=Res(status=500, body="", headers={}),
    )


def _request_options(client_assertion: Optional[str]) -> _RequestOptions:
    """Per-call controls; secret requests retain configured HTTP authentication."""
    if client_assertion is None:
        return {"follow_redirects": False}
    return {"auth": None, "follow_redirects": False}


def _build_request(
    client_id: str,
    client_secret: str,
    shop: str,
    client_assertion: Optional[str] = None,
) -> Tuple[str, Dict[str, str], Dict[str, str], RequestInput]:
    """Build client credentials request components.

    Args:
        client_id: OAuth client ID
        client_secret: OAuth client secret
        shop: Shop name (e.g., "shop-name")
        client_assertion: Optional app-created JWT. When supplied, the request
            authenticates with the assertion instead of the client secret.

    Returns:
        tuple: (endpoint, request_body, request_headers, req_obj)
    """
    request_body: Dict[str, str]
    if client_assertion is None:
        token_endpoint = f"https://{shop}.myshopify.com/admin/oauth/access_token"
        request_body = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        }
    else:
        # The assertion audience is the canonical lowercase shop host.
        token_endpoint = (
            f"https://{shop.lower()}.myshopify.com/admin/oauth/access_token"
        )
        # Exactly these four fields: no client secret, no scope, no other
        # authentication method. The assertion is opaque and sent unchanged.
        request_body = {
            "client_id": client_id,
            "grant_type": "client_credentials",
            "client_assertion_type": CLIENT_ASSERTION_TYPE,
            "client_assertion": client_assertion,
        }

    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": _get_user_agent(),
    }

    req_obj = redact_http_log(
        {
            "method": "POST",
            "url": token_endpoint,
            "headers": request_headers,
            "body": json.dumps(request_body),
        }
    )

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
    *,
    client_assertion: Optional[str] = None,
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
        client_assertion (str): Optional app-created JWT. When omitted or None,
            the request authenticates with the configured client secret.

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

    assertion_error = _validate_client_assertion(client_assertion, http_client)
    if assertion_error is not None:
        return assertion_error

    # Build request
    token_endpoint, request_body, request_headers, req_obj = _build_request(
        client_id, client_secret, shop, client_assertion
    )
    request_options = _request_options(client_assertion)

    http_logs: List[HttpLog] = []

    # Use async HTTP client context manager
    async with AsyncHTTPClientContext(http_client) as client:
        try:
            response = await client.post(
                token_endpoint,
                headers=request_headers,
                json=request_body,
                **request_options,
            )

            status_code = response.status_code
            response_body = response.text

            # Build response object for logging
            response_headers = (
                dict(response.headers) if hasattr(response, "headers") else {}
            )
            # The token endpoint response carries the newly issued
            # credentials, so redact them before this goes into a log.
            res_obj = Res(
                status=status_code,
                body=redact_http_response_body(response_body),
                headers=response_headers,
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
                response_data,
                shop,
                http_logs,
                req_obj,
                res_obj,
            )

        except httpx.RequestError:
            return build_network_error_response(
                shop,
                http_logs,
                req_obj,
                "client credentials exchange",
                "client_credentials",
            )
