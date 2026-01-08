"""
Shopify Token Exchange

This module provides functions to exchange tokens for API access tokens.
"""

from __future__ import annotations

import asyncio
import dataclasses
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple, Union, cast

import httpx

from ..types import (
    AppConfig,
    HttpLog,
    IdTokenDetails,
    Log,
    RequestInput,
    Res,
    TokenExchangeAccessToken,
    TokenExchangeResult,
    User,
)
from ..utils import _get_attr, _get_user_agent, _to_res
from ..utils.http_client import AsyncHTTPClientContext, HTTPClientContext
from ._response_builders import build_network_error_response
from ._validation import validate_client_id


def _is_valid_id_token(obj: Any) -> bool:
    """Check if obj is a valid IdTokenDetails (dataclass or dict)."""
    if obj is None:
        return False
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return True
    if isinstance(obj, dict):
        return True
    return False


def token_exchange(
    access_mode: str,
    app_config: AppConfig,
    id_token: Optional[Union[IdTokenDetails, dict]] = None,
    invalid_token_response: Optional[Union[Res, dict]] = None,
    http_client: Optional[httpx.Client] = None,
) -> TokenExchangeResult:
    """
    Exchange a pre-validated ID token for an API access token using OAuth 2.0 Token Exchange.

    Args:
        access_mode (str): Either "online" or "offline"
        app_config (AppConfig): App configuration containing:
            - client_id: The Shopify app client ID
            - client_secret: The app's client secret
        id_token (IdTokenDetails | dict): IdTokenDetails object or dict with exchangeable, token, claims
        invalid_token_response (Res | dict): Pre-built response to return if token is invalid
        http_client: Optional HTTP client for testing

    Returns:
        TokenExchangeResult: Result containing ok, shop, access_token, log, http_logs, and response
    """
    client_id = app_config.get("client_id", "")
    client_secret = app_config.get("client_secret", "")

    # Validate required parameters
    is_valid, error = validate_client_id(client_id, result_type="token_exchange")
    if not is_valid:
        if error is None:
            raise RuntimeError("validate_client_id returned invalid but no error")
        return error

    is_valid, error = _validate_access_mode(access_mode)
    if not is_valid:
        if error is None:
            raise RuntimeError("_validate_access_mode returned invalid but no error")
        return error

    is_valid, error = _validate_id_token(id_token)
    if not is_valid:
        if error is None:
            raise RuntimeError("_validate_id_token returned invalid but no error")
        return error

    # Extract shop and JWT from validated id_token
    # Support both dict and dataclass
    claims: Dict[str, Any] = _get_attr(id_token, "claims", {})
    shop = claims.get("dest", "")
    jwt_string = _get_attr(id_token, "token", "")

    # Normalize shop URL for API request
    shop_url = shop if shop.startswith("https://") else f"https://{shop}"

    # Extract shop name (remove https:// and .myshopify.com)
    shop_name = (
        shop.replace("https://", "")
        .replace("http://", "")
        .replace(".myshopify.com", "")
    )

    # Build request
    token_endpoint, request_body, request_headers, req_obj = _build_request(
        client_id, client_secret, jwt_string, access_mode, shop_url
    )

    # Make the request with retry logic for 429 responses
    max_retries = 2
    attempt = 0
    http_logs: List[HttpLog] = []

    with HTTPClientContext(http_client) as client:
        while attempt <= max_retries:
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
                    http_logs.append(
                        HttpLog(
                            code="success",
                            detail="Token exchange successful. Store the access token and proceed with business logic.",
                            req=req_obj,
                            res=res_obj,
                        )
                    )
                    # Cast access_mode to Literal type
                    access_mode_literal = cast(
                        Literal["online", "offline"], access_mode
                    )
                    return _handle_success_response(
                        response_data, shop_name, access_mode_literal, http_logs
                    )

                # Handle 429 rate limit with retry helper
                should_retry, should_return, return_value = _handle_retry_after_sync(
                    status_code,
                    attempt,
                    max_retries,
                    response_headers,
                    http_logs,
                    req_obj,
                    res_obj,
                    shop_name,
                )
                if should_return:
                    if return_value is None:
                        raise RuntimeError(
                            "_handle_retry_after_sync returned should_return=True but no return_value"
                        )
                    return return_value
                if should_retry:
                    attempt += 1
                    continue

                # Handle error responses
                try:
                    response_data = response.json()
                except Exception:
                    response_data = {}

                return _handle_error_response(
                    response_data,
                    shop_name,
                    invalid_token_response,
                    http_logs,
                    req_obj,
                    res_obj,
                )

            except httpx.RequestError:
                return build_network_error_response(
                    shop_name, http_logs, req_obj, "token exchange", "token_exchange"
                )

    # Should never reach here due to while loop logic
    raise AssertionError("unreachable: while loop should always return")


def _validate_access_mode(
    access_mode: str,
    shop: Optional[str] = None,
) -> Tuple[bool, Optional[TokenExchangeResult]]:
    """Validate access_mode parameter."""
    if not access_mode:
        return (
            False,
            TokenExchangeResult(
                ok=False,
                shop=shop,
                access_token=None,
                log=Log(
                    code="configuration_error",
                    detail="Expected access mode to be 'online' or 'offline', but got ''",
                ),
                http_logs=[],
                response=Res(status=500, body="", headers={}),
            ),
        )

    if access_mode not in ["online", "offline"]:
        return (
            False,
            TokenExchangeResult(
                ok=False,
                shop=shop,
                access_token=None,
                log=Log(
                    code="configuration_error",
                    detail=f"Expected access mode to be 'online' or 'offline', but got '{access_mode}'",
                ),
                http_logs=[],
                response=Res(status=500, body="", headers={}),
            ),
        )

    return (True, None)


def _validate_id_token(
    id_token: Optional[Union[IdTokenDetails, dict]],
    shop: Optional[str] = None,
) -> Tuple[bool, Optional[TokenExchangeResult]]:
    """Validate id_token structure and contents."""
    if not _is_valid_id_token(id_token):
        return (
            False,
            TokenExchangeResult(
                ok=False,
                shop=shop,
                access_token=None,
                log=Log(
                    code="configuration_error",
                    detail="Expected idToken to be an object with exchangeable, token, and claims properties",
                ),
                http_logs=[],
                response=Res(status=500, body="", headers={}),
            ),
        )

    exchangeable = _get_attr(id_token, "exchangeable", False)
    if not exchangeable:
        return (
            False,
            TokenExchangeResult(
                ok=False,
                shop=shop,
                access_token=None,
                log=Log(
                    code="configuration_error",
                    detail="ID token is not exchangeable. Only App Home, Admin UI extension & POS UI Extension Id tokens can be exchanged.",
                ),
                http_logs=[],
                response=Res(status=500, body="", headers={}),
            ),
        )

    jwt_string = _get_attr(id_token, "token", None)
    if not jwt_string or not isinstance(jwt_string, str):
        return (
            False,
            TokenExchangeResult(
                ok=False,
                shop=shop,
                access_token=None,
                log=Log(
                    code="configuration_error",
                    detail="Expected idToken.token to be a non-empty string",
                ),
                http_logs=[],
                response=Res(status=500, body="", headers={}),
            ),
        )

    claims: Dict[str, Any] = _get_attr(id_token, "claims", {})
    shop_from_token = claims.get("dest", "")

    if not shop_from_token or not isinstance(shop_from_token, str):
        return (
            False,
            TokenExchangeResult(
                ok=False,
                shop=shop,
                access_token=None,
                log=Log(
                    code="configuration_error",
                    detail="Expected idToken.claims.dest to be a non-empty string",
                ),
                http_logs=[],
                response=Res(status=500, body="", headers={}),
            ),
        )

    if ".myshopify.com" not in shop_from_token:
        return (
            False,
            TokenExchangeResult(
                ok=False,
                shop=shop,
                access_token=None,
                log=Log(
                    code="configuration_error",
                    detail="Expected idToken.claims.dest to be a valid shop URL (e.g., 'https://shop.myshopify.com' or 'shop.myshopify.com')",
                ),
                http_logs=[],
                response=Res(status=500, body="", headers={}),
            ),
        )

    return (True, None)


def _build_request(client_id, client_secret, jwt_string, access_mode, shop_url):
    """Build token exchange request components."""
    import json

    requested_token_type = (
        f"urn:shopify:params:oauth:token-type:{access_mode}-access-token"
    )

    request_body = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": jwt_string,
        "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
        "requested_token_type": requested_token_type,
        "expiring": 1,
    }

    token_endpoint = f"{shop_url}/admin/oauth/access_token"

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


def _handle_retry_after_sync(
    status_code: int,
    attempt: int,
    max_retries: int,
    response_headers: dict,
    http_logs: List[HttpLog],
    req_obj: RequestInput,
    res_obj: Res,
    shop_name: str,
) -> Tuple[bool, bool, Optional[TokenExchangeResult]]:
    """Handle 429 rate limit retry logic for sync requests."""
    if status_code == 429 and attempt < max_retries:
        retry_after = int(response_headers.get("Retry-After", 1))
        http_logs.append(
            HttpLog(
                code="rate_limited_retry",
                detail=f"Rate limited. Retrying after {retry_after} seconds.",
                req=req_obj,
                res=res_obj,
            )
        )
        time.sleep(retry_after)
        return (True, False, None)  # should retry

    if status_code == 429 and attempt == max_retries:
        http_logs.append(
            HttpLog(
                code="rate_limit_exceeded",
                detail="Max retries reached after rate limiting. Respond 429 Too Many Requests using the provided response.",
                req=req_obj,
                res=res_obj,
            )
        )
        return (
            False,
            True,
            TokenExchangeResult(
                ok=False,
                shop=shop_name,
                access_token=None,
                log=Log(
                    code="rate_limit_exceeded",
                    detail="Max retries reached after rate limiting. Respond 429 Too Many Requests using the provided response.",
                ),
                http_logs=http_logs,
                response=Res(
                    status=429,
                    body='{"error":"Too many requests"}',
                    headers={"Content-Type": "application/json"},
                ),
            ),
        )

    return (False, False, None)


async def _handle_retry_after_async(
    status_code: int,
    attempt: int,
    max_retries: int,
    response_headers: dict,
    http_logs: List[HttpLog],
    req_obj: RequestInput,
    res_obj: Res,
    shop_name: str,
) -> Tuple[bool, bool, Optional[TokenExchangeResult]]:
    """Handle 429 rate limit retry logic for async requests."""
    if status_code == 429 and attempt < max_retries:
        retry_after = int(response_headers.get("Retry-After", 1))
        http_logs.append(
            HttpLog(
                code="rate_limited_retry",
                detail=f"Rate limited. Retrying after {retry_after} seconds.",
                req=req_obj,
                res=res_obj,
            )
        )
        await asyncio.sleep(retry_after)
        return (True, False, None)

    if status_code == 429 and attempt == max_retries:
        http_logs.append(
            HttpLog(
                code="rate_limit_exceeded",
                detail="Max retries reached after rate limiting. Respond 429 Too Many Requests using the provided response.",
                req=req_obj,
                res=res_obj,
            )
        )
        return (
            False,
            True,
            TokenExchangeResult(
                ok=False,
                shop=shop_name,
                access_token=None,
                log=Log(
                    code="rate_limit_exceeded",
                    detail="Max retries reached after rate limiting. Respond 429 Too Many Requests using the provided response.",
                ),
                http_logs=http_logs,
                response=Res(
                    status=429,
                    body='{"error":"Too many requests"}',
                    headers={"Content-Type": "application/json"},
                ),
            ),
        )

    return (False, False, None)


def _handle_success_response(
    response_data: dict,
    shop: str,
    access_mode: Literal["online", "offline"],
    http_logs: List[HttpLog],
) -> TokenExchangeResult:
    """Handle successful token exchange response."""
    access_token = response_data.get("access_token", "")
    expires_in = response_data.get("expires_in")
    scope = response_data.get("scope", "")
    refresh_token = response_data.get("refresh_token", "")
    refresh_token_expires_in = response_data.get("refresh_token_expires_in")
    associated_user = response_data.get("associated_user")
    associated_user_scope = response_data.get("associated_user_scope", "")

    # Calculate expiration timestamps
    # If expires_in is None, the token doesn't expire
    expires = (
        (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        if expires_in is not None
        else None
    )
    refresh_token_expires = (
        (
            datetime.now(timezone.utc) + timedelta(seconds=refresh_token_expires_in)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        if refresh_token_expires_in is not None
        else None
    )

    # Build user object for online tokens
    user: Optional[User] = None
    if access_mode == "online" and associated_user:
        user = User(
            id=associated_user.get("id", 0),
            first_name=associated_user.get("first_name", ""),
            last_name=associated_user.get("last_name", ""),
            scope=associated_user_scope,
            email=associated_user.get("email", ""),
            account_owner=associated_user.get("account_owner", False),
            locale=associated_user.get("locale", ""),
            collaborator=associated_user.get("collaborator", False),
            email_verified=associated_user.get("email_verified", False),
        )

    access_token_obj = TokenExchangeAccessToken(
        access_mode=access_mode,
        shop=shop,
        token=access_token,
        expires=expires,
        scope=scope,
        refresh_token=refresh_token,
        refresh_token_expires=refresh_token_expires,
        user=user,
    )

    return TokenExchangeResult(
        ok=True,
        shop=shop,
        access_token=access_token_obj,
        log=Log(
            code="success",
            detail="Token exchange successful. Store the access token and proceed with business logic.",
        ),
        http_logs=http_logs,
        response=Res(
            status=200,
            body="",
            headers={},
        ),
    )


def _handle_error_response(
    response_data: dict,
    shop: str,
    invalid_token_response: Optional[Union[Res, dict]],
    http_logs: List[HttpLog],
    req_obj: RequestInput,
    res_obj: Res,
) -> TokenExchangeResult:
    """Handle error responses from token exchange."""
    error = response_data.get("error", "unknown_error")

    # Handle invalid_subject_token
    if error == "invalid_subject_token":
        log = Log(
            code="invalid_subject_token",
            detail="The ID token is invalid. Respond 401 Unauthorized using the provided response.",
        )
        http_logs.append(
            HttpLog(
                code=log.code,
                detail=log.detail,
                req=req_obj,
                res=res_obj,
            )
        )

        # Convert invalid_token_response to Res (handles both dict and dataclass)
        response = _to_res(invalid_token_response) or Res(
            status=401, body="", headers={}
        )

        return TokenExchangeResult(
            ok=False,
            shop=shop,
            access_token=None,
            log=log,
            http_logs=http_logs,
            response=response,
        )

    # Handle invalid_client
    if error == "invalid_client":
        log = Log(
            code="invalid_client",
            detail="Client credentials are invalid or the app has been uninstalled. Respond 500 Internal Server Error using the provided response.",
        )
        http_logs.append(
            HttpLog(
                code=log.code,
                detail=log.detail,
                req=req_obj,
                res=res_obj,
            )
        )
        return TokenExchangeResult(
            ok=False,
            shop=shop,
            access_token=None,
            log=log,
            http_logs=http_logs,
            response=Res(
                status=500,
                body="",
                headers={},
            ),
        )

    # Fallback for other errors
    log = Log(
        code="exchange_error",
        detail=f"Token exchange failed with error: {error}. Respond 500 Internal Server Error using the provided response.",
    )
    http_logs.append(
        HttpLog(
            code=log.code,
            detail=log.detail,
            req=req_obj,
            res=res_obj,
        )
    )
    return TokenExchangeResult(
        ok=False,
        shop=shop,
        access_token=None,
        log=log,
        http_logs=http_logs,
        response=Res(
            status=500,
            body="",
            headers={},
        ),
    )


async def token_exchange_async(
    access_mode: str,
    app_config: AppConfig,
    id_token: Optional[Union[IdTokenDetails, dict]] = None,
    invalid_token_response: Optional[Union[Res, dict]] = None,
    http_client: Optional[httpx.AsyncClient] = None,
) -> TokenExchangeResult:
    """
    Async version of token_exchange.

    Exchange a pre-validated ID token for an API access token using OAuth 2.0 Token Exchange.
    Use this when you need non-blocking token exchange in async code.

    Args:
        access_mode (str): Either "online" or "offline"
        app_config (AppConfig): App configuration containing:
            - client_id: The Shopify app client ID
            - client_secret: The app's client secret
        id_token (IdTokenDetails | dict): IdTokenDetails object with:
            - exchangeable: bool (must be True)
            - token: str (the JWT string)
            - claims: dict (decoded JWT claims)
        invalid_token_response (Res | dict): Pre-built response to return if token is invalid
        http_client: Optional async HTTP client for testing (httpx.AsyncClient)

    Returns:
        TokenExchangeResult: Result containing ok, shop, access_token, log, http_logs, and response
    """
    client_id = app_config.get("client_id", "")
    client_secret = app_config.get("client_secret", "")

    # Validate required parameters
    is_valid, error = validate_client_id(client_id, result_type="token_exchange")
    if not is_valid:
        if error is None:
            raise RuntimeError("validate_client_id returned invalid but no error")
        return error

    is_valid, error = _validate_access_mode(access_mode)
    if not is_valid:
        if error is None:
            raise RuntimeError("_validate_access_mode returned invalid but no error")
        return error

    is_valid, error = _validate_id_token(id_token)
    if not is_valid:
        if error is None:
            raise RuntimeError("_validate_id_token returned invalid but no error")
        return error

    # Extract shop and JWT from validated id_token
    # Support both dict and dataclass
    claims: Dict[str, Any] = _get_attr(id_token, "claims", {})
    shop = claims.get("dest", "")
    jwt_string = _get_attr(id_token, "token", "")

    # Normalize shop URL for API request
    shop_url = shop if shop.startswith("https://") else f"https://{shop}"

    # Extract shop name (remove https:// and .myshopify.com)
    shop_name = (
        shop.replace("https://", "")
        .replace("http://", "")
        .replace(".myshopify.com", "")
    )

    # Build request
    token_endpoint, request_body, request_headers, req_obj = _build_request(
        client_id, client_secret, jwt_string, access_mode, shop_url
    )

    # Make the request with retry logic for 429 responses
    max_retries = 2
    attempt = 0
    http_logs: List[HttpLog] = []

    async with AsyncHTTPClientContext(http_client) as client:
        while attempt <= max_retries:
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
                    http_logs.append(
                        HttpLog(
                            code="success",
                            detail="Token exchange successful. Store the access token and proceed with business logic.",
                            req=req_obj,
                            res=res_obj,
                        )
                    )
                    # Cast access_mode to Literal type
                    access_mode_literal = cast(
                        Literal["online", "offline"], access_mode
                    )
                    return _handle_success_response(
                        response_data, shop_name, access_mode_literal, http_logs
                    )

                # Handle 429 rate limit with retry helper
                should_retry, should_return, return_value = (
                    await _handle_retry_after_async(
                        status_code,
                        attempt,
                        max_retries,
                        response_headers,
                        http_logs,
                        req_obj,
                        res_obj,
                        shop_name,
                    )
                )
                if should_return:
                    if return_value is None:
                        raise RuntimeError(
                            "_handle_retry_after_async returned should_return=True but no return_value"
                        )
                    return return_value
                if should_retry:
                    attempt += 1
                    continue

                # Handle error responses
                try:
                    response_data = response.json()
                except Exception:
                    response_data = {}

                return _handle_error_response(
                    response_data,
                    shop_name,
                    invalid_token_response,
                    http_logs,
                    req_obj,
                    res_obj,
                )

            except httpx.RequestError:
                return build_network_error_response(
                    shop_name, http_logs, req_obj, "token exchange", "token_exchange"
                )

    # Should never reach here due to while loop logic
    raise AssertionError("unreachable: while loop should always return")
