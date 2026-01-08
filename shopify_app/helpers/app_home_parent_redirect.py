"""
Shopify App Home Parent Redirect

This module provides a helper function to generate redirect responses that
break out of the app home iframe.
"""

from __future__ import annotations

import json
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse

from ..types import AppConfig, LogWithReq, RequestInput, Res, ResultForReq
from ..utils.headers import _normalize_headers

# Restricted params that should be stripped from Shopify domain redirects
RESTRICTED_PARAMS = frozenset(
    [
        "hmac",
        "locale",
        "protocol",
        "session",
        "id_token",
        "shop",
        "timestamp",
        "host",
        "embedded",
        "appLoadId",
    ]
)

LINK_HEADER = '<https://cdn.shopify.com>; rel="preconnect", <https://cdn.shopify.com/shopifycloud/app-bridge.js>; rel="preload"; as="script", <https://cdn.shopify.com/shopifycloud/polaris.js>; rel="preload"; as="script"'


def app_home_parent_redirect(
    request: RequestInput,
    config: AppConfig,
    redirect_url: str,
    shop: str,
    target: Optional[str] = None,
) -> ResultForReq:
    """
    Generate a redirect response that breaks out of the app home iframe.

    Args:
        request (RequestInput): Request dictionary with method, headers, url, and body
        config (AppConfig): App configuration with client_id
        redirect_url (str): The URL to redirect to
        shop (str): The shop domain (e.g., "test-shop")
        target (str, optional): Target window: "_top" or "_blank" (default: "_top")

    Returns:
        ResultForReq: Result with ok, shop, log, and response
    """
    client_id = config.get("client_id", "")
    shop_domain = f"{shop}.myshopify.com"

    # Validate request object
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
            response=Res(status=500, body="", headers={}),
        )

    url = request.get("url")
    if not isinstance(url, str) or url == "":
        return ResultForReq(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="configuration_error",
                detail="Expected request.url to be a non-empty string",
                req=request,
            ),
            response=Res(status=500, body="", headers={}),
        )

    # Default target to _top
    if target is None:
        target = "_top"

    # Validate target
    if target not in ("_top", "_blank"):
        return ResultForReq(
            ok=False,
            shop=shop,
            log=LogWithReq(
                code="invalid_target",
                detail=f"Target must be '_top' or '_blank'. Received {target}. Respond 400 Bad Request using the provided response.",
                req=request,
            ),
            response=Res(status=400, body="Bad Request", headers={}),
        )

    # Validate redirect URL scheme (must be http or https)
    parsed_redirect = urlparse(redirect_url)
    if parsed_redirect.scheme not in ("http", "https"):
        return ResultForReq(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="configuration_error",
                detail="Redirect URL must use http or https scheme",
                req=request,
            ),
            response=Res(status=500, body="", headers={}),
        )

    # Normalize headers for case-insensitive access
    normalized_headers = _normalize_headers(headers)

    # Determine request type
    has_auth_header = "authorization" in normalized_headers

    # Process redirect URL - strip restricted params if needed
    processed_redirect_url = _process_redirect_url(redirect_url)

    # Determine response based on request type
    if has_auth_header:
        # Fetch request - return 401 with reauthorize header
        return ResultForReq(
            ok=True,
            shop=shop,
            log=LogWithReq(
                code="app_home_parent_redirect_success",
                detail="App Home Parent Redirect response constructed. Respond with the provided response to redirect outside the app iframe.",
                req=request,
            ),
            response=Res(
                status=401,
                body="",
                headers={
                    "X-Shopify-API-Request-Failure-Reauthorize-Url": processed_redirect_url
                },
            ),
        )

    # JSON encode URL and target for safe embedding in JavaScript
    # Replace < and > with unicode escapes to prevent XSS
    encoded_url = _json_encode_for_js(processed_redirect_url)
    encoded_target = _json_encode_for_js(target)

    # Document request - return HTML response with App Bridge
    html = f'<script data-api-key="{client_id}" src="https://cdn.shopify.com/shopifycloud/app-bridge.js"></script>'
    html += f"<script>window.open({encoded_url}, {encoded_target});</script>"

    return ResultForReq(
        ok=True,
        shop=shop,
        log=LogWithReq(
            code="app_home_parent_redirect_success",
            detail="App Home Parent Redirect response constructed. Respond with the provided response to redirect outside the app iframe.",
            req=request,
        ),
        response=Res(
            status=200,
            body=html,
            headers={
                "Content-Type": "text/html",
                "Link": LINK_HEADER,
                "Content-Security-Policy": f"frame-ancestors https://{shop_domain} https://admin.shopify.com;",
            },
        ),
    )


def _process_redirect_url(redirect_url: str) -> str:
    """
    Process redirect URL by stripping restricted params if needed.

    Args:
        redirect_url (str): The original redirect URL

    Returns:
        str: The processed redirect URL
    """
    parsed = urlparse(redirect_url)
    host = parsed.hostname or ""

    # Check if we need to strip restricted params
    is_admin_shopify = host == "admin.shopify.com"
    is_myshopify_domain = host.endswith(".myshopify.com")

    if not is_admin_shopify and not is_myshopify_domain:
        return redirect_url

    # Parse and filter query params
    if not parsed.query:
        return redirect_url

    query_params = parse_qs(parsed.query, keep_blank_values=True)
    filtered_params = {}
    for key, values in query_params.items():
        if key not in RESTRICTED_PARAMS:
            # parse_qs returns lists, keep single values as single
            filtered_params[key] = values[0] if len(values) == 1 else values

    # Rebuild URL
    scheme = parsed.scheme or "https"
    path = parsed.path or ""
    fragment = f"#{parsed.fragment}" if parsed.fragment else ""

    new_url = f"{scheme}://{host}{path}"
    if filtered_params:
        new_url += "?" + urlencode(filtered_params, doseq=True)
    new_url += fragment

    return new_url


def _json_encode_for_js(value: str) -> str:
    """
    JSON encode a string for safe embedding in JavaScript.
    Escapes < and > as unicode escapes to prevent XSS.

    Args:
        value (str): The value to encode

    Returns:
        str: The JSON-encoded string (including surrounding quotes)
    """
    # JSON encode (escapes quotes, backslashes, etc.)
    encoded = json.dumps(value)
    # Replace < and > with unicode escapes to prevent script tag injection
    encoded = encoded.replace("<", "\\u003C").replace(">", "\\u003E")
    return encoded
