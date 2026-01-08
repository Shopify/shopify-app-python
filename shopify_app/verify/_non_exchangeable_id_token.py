"""
Shared Non-Exchangeable ID Token Verification

This module provides the core ID token verification logic used by both
Checkout UI Extension and Customer Account UI Extension request verification,
where a non-exchangeable ID token is provided in the Authorization header.
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
    ResultWithNonExchangeableIdToken,
)
from ..utils.headers import _normalize_headers


def _verify_non_exchangeable_id_token(
    request: RequestInput, config: AppConfig, request_type: str
) -> ResultWithNonExchangeableIdToken:
    """
    Verifies non-exchangeable ID token requests from Shopify (Checkout UI Extensions, Customer Account UI Extensions, etc.)

    Args:
        request (dict): The request object containing method, headers, url, and body
        config (dict): The app configuration with client_id, client_secret and optional old_client_secret
        request_type (str): The type of request for log messages (e.g., "Checkout UI Extension", "Customer Account UI Extension")

    Returns:
        ResultWithNonExchangeableIdToken: Verification result with id_token details
    """
    # Validate request object
    method = request.get("method")
    if not isinstance(method, str) or method == "":
        return ResultWithNonExchangeableIdToken(
            ok=False,
            shop=None,
            id_token=None,
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
        )

    headers = request.get("headers")
    if not isinstance(headers, dict):
        return ResultWithNonExchangeableIdToken(
            ok=False,
            shop=None,
            id_token=None,
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
        )
    url = request.get("url", "")

    client_secret = config.get("client_secret", "")
    old_client_secret = config.get("old_client_secret")
    client_id = config.get("client_id", "")

    # Normalize headers for case-insensitive comparison
    normalized_headers = _normalize_headers(headers)

    # Handle OPTIONS requests for CORS preflight
    if method == "OPTIONS":
        origin = normalized_headers.get("origin", "")
        # If Origin is different from app URL, return CORS headers
        if origin and origin != url:
            return ResultWithNonExchangeableIdToken(
                ok=True,
                shop=None,
                id_token=None,
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
            )

    # Check for Authorization header
    if "authorization" not in normalized_headers:
        return ResultWithNonExchangeableIdToken(
            ok=False,
            shop=None,
            id_token=None,
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
        )

    # Extract the Bearer token
    auth_header = normalized_headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return ResultWithNonExchangeableIdToken(
            ok=False,
            shop=None,
            id_token=None,
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
                    "verify_aud": False,  # We'll verify manually below
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

        return ResultWithNonExchangeableIdToken(
            ok=False,
            shop=None,
            id_token=None,
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
        )

    # Verify the audience claim matches the clientId
    token_aud = payload.get("aud")
    if token_aud != client_id:
        return ResultWithNonExchangeableIdToken(
            ok=False,
            shop=None,
            id_token=None,
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
        )

    # Extract shop from dest claim
    dest = payload.get("dest", "")
    shop = dest.replace(".myshopify.com", "") if dest else ""

    return ResultWithNonExchangeableIdToken(
        ok=True,
        shop=shop,
        id_token=IdTokenDetails(
            exchangeable=False,
            token=id_token,
            claims=payload,
        ),
        log=LogWithReq(
            code="verified",
            detail=f"{request_type} request verified. Proceed with business logic.",
            req=request,
        ),
        response=Res(
            status=200,
            body="",
            headers={},
        ),
    )
