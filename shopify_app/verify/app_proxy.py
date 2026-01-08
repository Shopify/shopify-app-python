"""
Shopify App Proxy Verification

This module provides functions to verify Shopify App Proxy requests.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Dict, List, Optional, Union
from urllib.parse import parse_qs, urlparse

from ..types import (
    AppConfig,
    LogWithReq,
    RequestInput,
    Res,
    ResultWithLoggedInCustomerId,
)


def verify_app_proxy_req(
    request: RequestInput, config: AppConfig
) -> ResultWithLoggedInCustomerId:
    """
    Verifies requests coming from Shopify App Proxy.

    Args:
        request (dict): The request object containing method, headers, url, and body
        config (dict): The app configuration with client_secret and optional old_client_secret

    Returns:
        ResultWithLoggedInCustomerId: Verification result with logged_in_customer_id
    """
    # Validate request object
    url = request.get("url")
    if not isinstance(url, str) or url == "":
        return ResultWithLoggedInCustomerId(
            ok=False,
            shop=None,
            logged_in_customer_id=None,
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
        )

    client_secret = config.get("client_secret", "")
    old_client_secret = config.get("old_client_secret")

    # Parse query parameters from URL
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query, keep_blank_values=True)

    # Convert lists to single values (parse_qs returns lists)
    # Keep arrays as arrays if they have multiple values
    params: Dict[str, Union[str, List[str]]] = {}
    for key, value in query_params.items():
        if len(value) == 1:
            params[key] = value[0]
        else:
            params[key] = value

    # Check for missing timestamp
    if "timestamp" not in params:
        return ResultWithLoggedInCustomerId(
            ok=False,
            shop=None,
            logged_in_customer_id=None,
            log=LogWithReq(
                code="missing_timestamp",
                detail="Required `timestamp` query parameter is missing. Respond 401 Unauthorized using the provided response.",
                req=request,
            ),
            response=Res(
                status=401,
                body="Unauthorized",
                headers={},
            ),
        )

    # Check timestamp is not too old (prevents replay attacks)
    try:
        timestamp_val = params["timestamp"]
        timestamp = int(
            timestamp_val if isinstance(timestamp_val, str) else timestamp_val[0]
        )
        current_time = int(time.time())
        time_diff = abs(current_time - timestamp)

        if time_diff > 90:
            return ResultWithLoggedInCustomerId(
                ok=False,
                shop=None,
                logged_in_customer_id=None,
                log=LogWithReq(
                    code="timestamp_too_old",
                    detail="The `timestamp` query parameter is more than 90 seconds old. Respond 401 Unauthorized using the provided response.",
                    req=request,
                ),
                response=Res(
                    status=401,
                    body="Unauthorized",
                    headers={},
                ),
            )
    except (ValueError, TypeError):
        return ResultWithLoggedInCustomerId(
            ok=False,
            shop=None,
            logged_in_customer_id=None,
            log=LogWithReq(
                code="invalid_timestamp",
                detail="The `timestamp` query parameter is not a valid integer. Respond 401 Unauthorized using the provided response.",
                req=request,
            ),
            response=Res(
                status=401,
                body="Unauthorized",
                headers={},
            ),
        )

    # Check for missing signature
    if "signature" not in params or not isinstance(params["signature"], str):
        return ResultWithLoggedInCustomerId(
            ok=False,
            shop=None,
            logged_in_customer_id=None,
            log=LogWithReq(
                code="missing_signature",
                detail="Required `signature` query parameter is missing. Respond 401 Unauthorized using the provided response.",
                req=request,
            ),
            response=Res(
                status=401,
                body="Unauthorized",
                headers={},
            ),
        )

    # Extract and remove signature from params
    sig_val = params.pop("signature")
    received_signature = sig_val if isinstance(sig_val, str) else sig_val[0]

    # Generate param string
    param_string = _generate_param_string(params)

    # Calculate HMAC
    def calculate_hmac_hex(secret: str) -> str:
        """Calculate HMAC-SHA256 in hexadecimal format."""
        return hmac.new(
            secret.encode("utf-8"), param_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    # Try current secret first
    calculated_hmac = calculate_hmac_hex(client_secret)
    signature_valid = hmac.compare_digest(received_signature, calculated_hmac)

    # If current secret fails and old secret is provided, try old secret
    if not signature_valid and old_client_secret:
        calculated_hmac_old = calculate_hmac_hex(old_client_secret)
        signature_valid = hmac.compare_digest(received_signature, calculated_hmac_old)

    if not signature_valid:
        return ResultWithLoggedInCustomerId(
            ok=False,
            shop=None,
            logged_in_customer_id=None,
            log=LogWithReq(
                code="invalid_signature",
                detail="`signature` query parameter does not match the expected HMAC. Respond 401 Unauthorized using the provided response.",
                req=request,
            ),
            response=Res(
                status=401,
                body="Unauthorized",
                headers={},
            ),
        )

    # Extract shop by removing .myshopify.com suffix from the shop param
    shop_domain = params.get("shop", "")
    shop: Optional[str] = (
        shop_domain.replace(".myshopify.com", "")
        if isinstance(shop_domain, str)
        else None
    )
    if not shop:
        shop = None

    # Extract logged in customer ID
    logged_in_customer_id_val = params.get("logged_in_customer_id")
    logged_in_customer_id: Optional[str] = (
        logged_in_customer_id_val
        if isinstance(logged_in_customer_id_val, str)
        else (logged_in_customer_id_val[0] if logged_in_customer_id_val else None)
    )

    return ResultWithLoggedInCustomerId(
        ok=True,
        shop=shop,
        logged_in_customer_id=logged_in_customer_id,
        log=LogWithReq(
            code="verified",
            detail="App Proxy request verified successfully. Proceed with business logic.",
            req=request,
        ),
        response=Res(
            status=200,
            body="",
            headers={},
        ),
    )


def _generate_param_string(params: Dict[str, Any]) -> str:
    """
    Generate the param string for HMAC calculation.

    Alphabetically sorts params and stringifies them according to Shopify's spec:
    - Separate key & value using =
    - No separators between key-value pairs
    - Array values are comma-separated

    Args:
        params (dict): Query parameters (without signature)

    Returns:
        str: Stringified params for HMAC calculation
    """
    # Sort params alphabetically by key
    sorted_params = sorted(params.items())

    # Build param string
    param_string = ""
    for key, value in sorted_params:
        if isinstance(value, list):
            # Arrays are stringified as comma-separated values
            param_string += f"{key}={','.join(value)}"
        else:
            param_string += f"{key}={value}"

    return param_string
