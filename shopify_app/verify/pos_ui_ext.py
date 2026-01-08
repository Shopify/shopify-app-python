"""
Shopify POS UI Extension Verification

This module provides functions to verify Shopify POS UI Extension requests.
"""

from __future__ import annotations

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


def verify_pos_ui_ext_req(
    request: RequestInput, config: AppConfig
) -> ResultWithExchangeableIdToken:
    """
    Verifies requests coming from Shopify POS UI Extensions.

    Args:
        request (dict): The request object containing method, headers, url, and body
        config (dict): The app configuration with client_id, client_secret and optional old_client_secret

    Returns:
        ResultWithExchangeableIdToken: Verification result with ok, shop, log, response, user_id, id_token, and new_id_token_response fields
    """
    # Validate request object
    method = request.get("method")
    if not isinstance(method, str) or method == "":
        return ResultWithExchangeableIdToken(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="configuration_error",
                detail="Expected request.method to be a non-empty string",
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

    client_id = config.get("client_id", "")
    client_secret = config.get("client_secret", "")
    old_client_secret = config.get("old_client_secret")

    # Normalize headers for case-insensitive comparison
    normalized_headers = _normalize_headers(headers)

    # Handle OPTIONS requests for CORS preflight
    if method == "OPTIONS":
        origin = normalized_headers.get("origin", "")
        # If Origin is different from app URL, return CORS headers
        if origin and origin != url:
            return ResultWithExchangeableIdToken(
                ok=True,
                shop=None,
                log=LogWithReq(
                    code="options_request",
                    detail="OPTIONS request handled for CORS preflight. Respond 204 No Content using the provided response.",
                    req=request,
                ),
                response=Res(
                    status=204,
                    body="",
                    headers={
                        "Access-Control-Max-Age": "7200",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Expose-Headers": "X-Shopify-API-Request-Failure-Reauthorize-Url",
                        "Access-Control-Allow-Headers": "Authorization, Content-Type",
                    },
                ),
                user_id=None,
                id_token=None,
                new_id_token_response=None,
            )

    # Check for Authorization header
    if "authorization" not in normalized_headers:
        return ResultWithExchangeableIdToken(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="missing_authorization_header",
                detail="Required `Authorization` header is missing. Respond 401 Unauthorized using the provided response.",
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

    # Extract the Bearer token
    auth_header = normalized_headers.get("authorization", "")
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
                headers={},
            ),
            user_id=None,
            id_token=None,
            new_id_token_response=None,
        )

    id_token = auth_header[7:]  # Remove "Bearer " prefix

    # Try to verify with old secret first (if provided), then new secret
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
            break  # Successfully decoded
        except PyJWTError as e:
            verification_error = e
            continue  # Try next secret

    if payload is None:
        # Determine if it was an expiration error
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
                headers={},
            ),
            user_id=None,
            id_token=None,
            new_id_token_response=None,
        )

    # Verify the audience (aud) matches clientId
    aud = payload.get("aud", "")
    if aud != client_id:
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
                headers={},
            ),
            user_id=None,
            id_token=None,
            new_id_token_response=None,
        )

    # Extract shop from dest claim (format: https://shop-name.myshopify.com)
    dest = payload.get("dest", "")
    shop = dest.replace("https://", "").replace(".myshopify.com", "") if dest else ""

    # Extract user_id from sub claim
    user_id = payload.get("sub")

    return ResultWithExchangeableIdToken(
        ok=True,
        shop=shop,
        log=LogWithReq(
            code="verified",
            detail="POS UI Extension request verified. Proceed with business logic.",
            req=request,
        ),
        response=Res(
            status=200,
            body="",
            headers={},
        ),
        user_id=user_id,
        id_token=IdTokenDetails(
            exchangeable=True,
            token=id_token,
            claims=payload,
        ),
        new_id_token_response=None,
    )
