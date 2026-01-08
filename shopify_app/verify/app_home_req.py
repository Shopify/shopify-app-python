"""
Shopify App Home Request Verification

This module provides functions to verify requests from Shopify App Home.
"""

from __future__ import annotations

from typing import Dict
from urllib.parse import ParseResult, parse_qs, quote, urlparse

import jwt
from jwt.exceptions import PyJWTError

from ..types import (
    AppConfig,
    IdTokenDetails,
    LogWithReq,
    RequestInput,
    Res,
    ResultWithExchangeableIdToken,
)
from ..utils.headers import _normalize_headers


def _build_patch_id_token_redirect(
    parsed_url: ParseResult,
    path: str,
    query_params: Dict[str, str],
    app_home_patch_id_token_path: str,
    request: RequestInput,
) -> ResultWithExchangeableIdToken:
    """
    Helper to build a response redirecting to the patch id token URL.

    Args:
        parsed_url: Parsed URL object from urlparse
        path: Request path
        query_params: Dictionary of query parameters
        app_home_patch_id_token_path: Path to the patch id token page
        request: The original request object

    Returns:
        ResultWithExchangeableIdToken: Redirect response with 302 status and Location header
    """
    clean_params = query_params.copy()
    clean_params.pop("id_token", None)

    # Build reload path with query string (preserve base64 = padding)
    reload_parts = [f"{key}={value}" for key, value in clean_params.items()]
    reload_query = "&".join(reload_parts)
    reload_path = path + ("?" + reload_query if reload_query else "")

    # Build patch id token URL with shopify-reload parameter
    patch_id_token_query_parts = [
        f"{key}={value}" for key, value in clean_params.items()
    ]
    patch_id_token_query_parts.append(f"shopify-reload={quote(reload_path, safe='')}")
    patch_id_token_query = "&".join(patch_id_token_query_parts)

    patch_id_token_location = f"{parsed_url.scheme}://{parsed_url.netloc}{app_home_patch_id_token_path}?{patch_id_token_query}"

    return ResultWithExchangeableIdToken(
        ok=False,
        shop=None,
        log=LogWithReq(
            code="redirect_to_patch_id_token_page",
            detail="Embedded app without id_token. Redirect to the patch ID token page to obtain a new token using the provided response.",
            req=request,
        ),
        response=Res(
            status=302,
            body="",
            headers={"Location": patch_id_token_location},
        ),
        user_id=None,
        id_token=None,
        new_id_token_response=None,
    )


def verify_app_home_req(
    request: RequestInput,
    config: AppConfig,
    app_home_patch_id_token_path: str,
) -> ResultWithExchangeableIdToken:
    """
    Verifies requests coming from Shopify App Home.

    Args:
        request (dict): The request object containing method, headers, url, and body
        config (dict): The app configuration with client_id, client_secret and optional old_client_secret
        app_home_patch_id_token_path (str): Path to the patch ID token page

    Returns:
        ResultWithExchangeableIdToken: Verification result with exchangeable ID token
    """
    # Validate app_home_patch_id_token_path
    if not isinstance(app_home_patch_id_token_path, str):
        return ResultWithExchangeableIdToken(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="configuration_error",
                detail="Expected appHomePatchIdTokenPath to be a non-empty string",
                req=request,
            ),
            response=Res(
                status=500,
                body="",
                headers={},
            ),
            user_id=None,
            id_token=None,
            new_id_token_response=None,
        )

    if app_home_patch_id_token_path == "":
        return ResultWithExchangeableIdToken(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="configuration_error",
                detail="Expected appHomePatchIdTokenPath to be a non-empty string, but got ''",
                req=request,
            ),
            response=Res(
                status=500,
                body="",
                headers={},
            ),
            user_id=None,
            id_token=None,
            new_id_token_response=None,
        )

    # Validate request object
    url = request.get("url")
    if not isinstance(url, str) or url == "":
        return ResultWithExchangeableIdToken(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="configuration_error",
                detail="Expected request.url to be a non-empty string",
                req=request,
            ),
            response=Res(
                status=500,
                body="",
                headers={},
            ),
            user_id=None,
            id_token=None,
            new_id_token_response=None,
        )

    headers = request.get("headers")
    if not isinstance(headers, dict):
        return ResultWithExchangeableIdToken(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="configuration_error",
                detail="Expected request.headers to be an object",
                req=request,
            ),
            response=Res(
                status=500,
                body="",
                headers={},
            ),
            user_id=None,
            id_token=None,
            new_id_token_response=None,
        )

    client_secret = config.get("client_secret", "")
    old_client_secret = config.get("old_client_secret")
    client_id = config.get("client_id", "")

    # Normalize headers for case-insensitive comparison
    normalized_headers = _normalize_headers(headers)

    # Parse URL for query parameters
    parsed_url = urlparse(url)
    path = parsed_url.path
    query_dict = parse_qs(parsed_url.query, keep_blank_values=True)

    # Flatten query params (parse_qs returns lists)
    query_params = {}
    for key, value_list in query_dict.items():
        query_params[key] = value_list[0] if value_list else ""

    # Check for Authorization header to determine request type
    auth_header = normalized_headers.get("authorization", "")
    has_authorization_header = bool(auth_header)

    id_token = None

    # If no Authorization header, check if this is a document request
    if not has_authorization_header:
        id_token_param = query_params.get("id_token", "")

        # If no id_token, redirect to patch ID token page
        if not id_token_param:
            return _build_patch_id_token_redirect(
                parsed_url, path, query_params, app_home_patch_id_token_path, request
            )

        id_token = id_token_param
    else:
        if not auth_header.startswith("Bearer "):
            return ResultWithExchangeableIdToken(
                ok=False,
                shop=None,
                log=LogWithReq(
                    code="invalid_id_token",
                    detail="ID token verification failed. Respond 401 Unauthorized using the provided response.",
                    req=request,
                ),
                response=Res(
                    status=401,
                    body="Unauthorized",
                    headers={
                        "X-Shopify-Retry-Invalid-Session-Request": "1",
                    },
                ),
                user_id=None,
                id_token=None,
                new_id_token_response=None,
            )
        id_token = auth_header[7:]  # Remove "Bearer " prefix

    if not id_token:
        return ResultWithExchangeableIdToken(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="missing_authorization_and_id_token",
                detail="Neither Authorization header nor id_token query parameter present. Respond 401 Unauthorized using the provided response.",
                req=request,
            ),
            response=Res(
                status=401,
                body="Unauthorized",
                headers={},
            ),
            user_id=None,
            id_token=None,
            new_id_token_response=None,
        )

    payload = None
    verification_error = None

    secrets_to_try = []
    if old_client_secret:
        secrets_to_try.append(old_client_secret)
    secrets_to_try.append(client_secret)

    for secret in secrets_to_try:
        try:
            payload = jwt.decode(
                id_token,
                secret,
                algorithms=["HS256"],
                leeway=10,  # Clock tolerance of 10 seconds
                options={
                    "verify_aud": False,
                },
            )
            break
        except PyJWTError as e:
            verification_error = e
            continue  # Try next secret

    if payload is None:
        # For document requests with invalid/stale tokens, redirect to patch ID token page
        if not has_authorization_header:
            return _build_patch_id_token_redirect(
                parsed_url, path, query_params, app_home_patch_id_token_path, request
            )

        # For fetch requests, return 401 with retry header
        error_code = "invalid_id_token"
        if verification_error and "expired" in str(verification_error).lower():
            error_code = "expired_id_token"
            detail_msg = "ID token has expired. Respond 401 Unauthorized using the provided response."
        else:
            detail_msg = "ID token verification failed. Respond 401 Unauthorized using the provided response."

        return ResultWithExchangeableIdToken(
            ok=False,
            shop=None,
            log=LogWithReq(
                code=error_code,
                detail=detail_msg,
                req=request,
            ),
            response=Res(
                status=401,
                body="Unauthorized",
                headers={
                    "X-Shopify-Retry-Invalid-Session-Request": "1",
                },
            ),
            user_id=None,
            id_token=None,
            new_id_token_response=None,
        )

    # Verify the audience (aud) matches the clientId
    token_aud = payload.get("aud", "")
    if token_aud != client_id:
        # For Authorization header requests, include retry header
        response_headers = {}
        if has_authorization_header:
            response_headers = {
                "X-Shopify-Retry-Invalid-Session-Request": "1",
            }

        return ResultWithExchangeableIdToken(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="invalid_aud",
                detail="ID token audience (aud) claim does not match clientId. Respond 401 Unauthorized using the provided response.",
                req=request,
            ),
            response=Res(
                status=401,
                body="Unauthorized",
                headers=response_headers,
            ),
            user_id=None,
            id_token=None,
            new_id_token_response=None,
        )

    # Extract shop from dest claim (parse as URL and get hostname)
    dest = payload.get("dest", "")
    dest_parts = urlparse(dest)
    shop_hostname = dest_parts.hostname if dest_parts.hostname else dest
    shop = shop_hostname.replace(".myshopify.com", "")

    # Extract user_id from sub claim
    user_id = payload.get("sub")

    # For document requests, add security and preload headers
    response_headers = {}
    if not has_authorization_header:
        response_headers = {
            "Content-Security-Policy": f"frame-ancestors https://{shop_hostname} https://admin.shopify.com;",
            "Link": '<https://cdn.shopify.com>; rel="preconnect", <https://cdn.shopify.com/shopifycloud/app-bridge.js>; rel="preload"; as="script", <https://cdn.shopify.com/shopifycloud/polaris.js>; rel="preload"; as="script"',
        }

    # Build new_id_token_response
    new_id_token_response = None
    if not has_authorization_header:
        # Document request - build patch ID token URL
        clean_params = query_params.copy()
        clean_params.pop("id_token", None)

        reload_parts = [f"{key}={value}" for key, value in clean_params.items()]
        reload_query = "&".join(reload_parts)
        reload_path = path + ("?" + reload_query if reload_query else "")

        patch_id_token_query_parts = [
            f"{key}={value}" for key, value in clean_params.items()
        ]
        patch_id_token_query_parts.append(
            f"shopify-reload={quote(reload_path, safe='')}"
        )
        patch_id_token_query = "&".join(patch_id_token_query_parts)

        patch_id_token_location = f"{parsed_url.scheme}://{parsed_url.netloc}{app_home_patch_id_token_path}?{patch_id_token_query}"

        new_id_token_response = Res(
            status=302,
            body="",
            headers={
                "Location": patch_id_token_location,
            },
        )
    else:
        # Fetch request
        new_id_token_response = Res(
            status=401,
            body="",
            headers={
                "X-Shopify-Retry-Invalid-Session-Request": "1",
            },
        )

    # Build log detail message
    log_detail = "App Home request verified. Proceed with business logic."
    if not has_authorization_header:
        log_detail += "  Include the headers in the provided response."

    return ResultWithExchangeableIdToken(
        ok=True,
        shop=shop,
        log=LogWithReq(
            code="verified",
            detail=log_detail,
            req=request,
        ),
        response=Res(
            status=200,
            body="",
            headers=response_headers,
        ),
        user_id=user_id,
        id_token=IdTokenDetails(
            exchangeable=True,
            token=id_token,
            claims=payload,
        ),
        new_id_token_response=new_id_token_response,
    )
