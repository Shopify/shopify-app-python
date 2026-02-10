"""
Shared Body HMAC in Header Verification

This module provides the core HMAC verification logic used by both
webhook and flow action request verification, where the HMAC signature
of the request body is provided in a configurable header (e.g.
X-Shopify-Hmac-SHA256 or shopify-hmac-sha256 for webhooks).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Sequence

from ..types import AppConfig, LogWithReq, RequestInput, Res, ResultForReq
from ..utils.headers import _normalize_headers


def _first_header_value_and_name(
    normalized_headers: dict[str, str], names: Sequence[str]
) -> tuple[str, str]:
    """Return (value, matched_key) for the first header in names that is present. Empty strings when none."""
    for name in names:
        key = name.lower()
        if key in normalized_headers:
            return (normalized_headers[key], key)
    return ("", "")


def _verify_body_hmac_in_header(
    request: RequestInput,
    config: AppConfig,
    request_type: str,
    hmac_header_names: Sequence[str],
    shop_header_names: Sequence[str],
) -> ResultForReq:
    """
    Verifies HMAC-signed requests from Shopify (webhooks, flow actions, etc.)

    Args:
        request: The request object containing method, headers, and body
        config: The app configuration with client_secret
        request_type: The type of request for log messages (e.g., "Webhook", "Flow action")
        hmac_header_names: Header names to check for HMAC (e.g. ["x-shopify-hmac-sha256"]). First present value is used.
        shop_header_names: Header names to check for shop domain. First present value is used.

    Returns:
        ResultForReq: Verification result with ok, shop, log, and response fields
    """
    # Validate request object
    method = request.get("method")
    if not isinstance(method, str) or method == "":
        return ResultForReq(
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
        )

    headers = request.get("headers")
    if not isinstance(headers, dict):
        return ResultForReq(
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
        )

    body = request.get("body")
    if not isinstance(body, str):
        return ResultForReq(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="configuration_error",
                detail="Expected request.body to be a string",
                req=request,
            ),
            response=Res(
                status=500,
                body="",
                headers={},
            ),
        )

    client_secret = config.get("client_secret", "")
    old_client_secret = config.get("old_client_secret")

    # Request method validation
    if method != "POST":
        return ResultForReq(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="post_method_expected",
                detail=(
                    f"{request_type} requests are expected to use the POST method. "
                    "Respond 405 Method Not Allowed using the provided response."
                ),
                req=request,
            ),
            response=Res(
                status=405,
                body="Method not allowed",
                headers={},
            ),
        )

    # Normalize headers for case-insensitive comparison
    normalized_headers = _normalize_headers(headers)

    # Resolve HMAC and shop from configurable header names (first present wins)
    received_hmac, _ = _first_header_value_and_name(
        normalized_headers, hmac_header_names
    )

    # Check for HMAC header first (most important for security)
    if not received_hmac:
        return ResultForReq(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="missing_hmac_header",
                detail=(
                    "Required hmac header is missing. "
                    "Respond 400 Bad Request using the provided response."
                ),
                req=request,
            ),
            response=Res(
                status=400,
                body="Bad Request",
                headers={},
            ),
        )

    # HMAC validation
    def calculate_hmac(secret: str) -> str:
        """Calculate HMAC for a given secret."""
        digest = hmac.new(
            secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256
        ).digest()
        return base64.b64encode(digest).decode("utf-8")

    # Try current secret first
    calculated_hmac = calculate_hmac(client_secret)
    hmac_valid = hmac.compare_digest(received_hmac, calculated_hmac)

    # If current secret fails and old secret is provided, try old secret
    if not hmac_valid and old_client_secret:
        calculated_hmac_old = calculate_hmac(old_client_secret)
        hmac_valid = hmac.compare_digest(received_hmac, calculated_hmac_old)

    if not hmac_valid:
        return ResultForReq(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="invalid_hmac",
                detail=(
                    "hmac header value does not match the body's HMAC. "
                    "Respond 401 Unauthorized using the provided response."
                ),
                req=request,
            ),
            response=Res(
                status=401,
                body="Unauthorized",
                headers={},
            ),
        )

    # Extract shop from header (first configured name present)
    shop_domain, _ = _first_header_value_and_name(normalized_headers, shop_header_names)
    # Extract shop by removing .myshopify.com suffix
    shop = shop_domain.replace(".myshopify.com", "") if shop_domain else ""

    return ResultForReq(
        ok=True,
        shop=shop,
        log=LogWithReq(
            code="verified",
            detail=(
                f"{request_type} request verified successfully. "
                "Respond 200 OK using the provided response."
            ),
            req=request,
        ),
        response=Res(
            status=200,
            body="",
            headers={},
        ),
    )
