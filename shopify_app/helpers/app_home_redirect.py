"""
Shopify App Home Redirect

This module provides a helper function to generate redirect responses that
stay within the app home iFrame.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse

from ..types import AppConfig, LogWithReq, RequestInput, Res, ResultForReq
from ..utils.headers import _normalize_headers

LINK_HEADER = '<https://cdn.shopify.com>; rel="preconnect", <https://cdn.shopify.com/shopifycloud/app-bridge.js>; rel="preload"; as="script", <https://cdn.shopify.com/shopifycloud/polaris.js>; rel="preload"; as="script"'


def app_home_redirect(
    request: RequestInput, config: AppConfig, redirect_url: str, shop: str
) -> ResultForReq:
    """
    Generate a redirect response that stays within the app home iFrame.

    Args:
        request (RequestInput): Request dictionary with method, headers, url, and body
        config (AppConfig): App configuration with client_id
        redirect_url (str): The relative URL to redirect to (must start with '/')
        shop (str): The shop domain (e.g., "test-shop")

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

    # Validate redirect URL is a relative path starting with /
    if not _is_valid_relative_url(redirect_url):
        return ResultForReq(
            ok=False,
            shop=shop,
            log=LogWithReq(
                code="invalid_redirect_url",
                detail=f"Redirect URL must be a relative path starting with '/'. Received {redirect_url}. Respond 400 Bad Request using the provided response.",
                req=request,
            ),
            response=Res(status=400, body="Bad Request", headers={}),
        )

    # Normalize headers for case-insensitive access
    normalized_headers = _normalize_headers(headers)

    # Determine request type
    has_auth_header = "authorization" in normalized_headers
    has_bounce_header = "x-shopify-bounce" in normalized_headers

    # Build redirect URL with merged params
    merged_url = _merge_url_params(url, redirect_url)

    # Determine response based on request type
    if has_auth_header and has_bounce_header:
        # Bounce request - return HTML response with App Bridge using _self
        html = f'<script data-api-key="{client_id}" src="https://cdn.shopify.com/shopifycloud/app-bridge.js"></script>'
        html += f"<script>window.open('{merged_url}', '_self');</script>"

        return ResultForReq(
            ok=True,
            shop=shop,
            log=LogWithReq(
                code="app_home_redirect_success",
                detail="App Home Redirect response constructed. Respond with the provided response to redirect within the app.",
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

    if has_auth_header:
        # Fetch request - return plain 302 redirect
        return ResultForReq(
            ok=True,
            shop=shop,
            log=LogWithReq(
                code="app_home_redirect_success",
                detail="App Home Redirect response constructed. Respond with the provided response to redirect within the app.",
                req=request,
            ),
            response=Res(
                status=302,
                body="",
                headers={
                    "Location": merged_url,
                },
            ),
        )

    # Document request - return 302 redirect with CSP and Link headers
    return ResultForReq(
        ok=True,
        shop=shop,
        log=LogWithReq(
            code="app_home_redirect_success",
            detail="App Home Redirect response constructed. Respond with the provided response to redirect within the app.",
            req=request,
        ),
        response=Res(
            status=302,
            body="",
            headers={
                "Location": merged_url,
                "Link": LINK_HEADER,
                "Content-Security-Policy": f"frame-ancestors https://{shop_domain} https://admin.shopify.com;",
            },
        ),
    )


def _is_valid_relative_url(redirect_url: str) -> bool:
    """
    Check if the redirect URL is a valid relative path starting with '/'.

    Args:
        redirect_url (str): The redirect URL to validate

    Returns:
        bool: True if valid relative URL, False otherwise
    """
    # Must be non-empty and start with /
    if not redirect_url or not redirect_url.startswith("/"):
        return False

    # Must not be protocol-relative (//evil.com)
    if redirect_url.startswith("//"):
        return False

    return True


def _merge_url_params(request_url: str, redirect_url: str) -> str:
    """
    Merge URL params from request URL into redirect URL.
    New params in redirect URL take precedence over existing ones.

    Args:
        request_url (str): The original request URL with params to copy
        redirect_url (str): The redirect URL (may have its own params)

    Returns:
        str: The redirect URL with merged params
    """
    # Parse request URL to get existing params
    parsed_request = urlparse(request_url)
    request_params = parse_qs(parsed_request.query, keep_blank_values=True)
    # Flatten single-value lists
    request_params_flat = {
        k: v[0] if len(v) == 1 else v for k, v in request_params.items()
    }

    # Parse redirect URL
    parsed_redirect = urlparse(redirect_url)
    redirect_params = parse_qs(parsed_redirect.query, keep_blank_values=True)
    # Flatten single-value lists
    redirect_params_flat = {
        k: v[0] if len(v) == 1 else v for k, v in redirect_params.items()
    }
    redirect_fragment = parsed_redirect.fragment

    # Merge params - redirect params take precedence (they overwrite request params)
    # Start with redirect params, then add request params that aren't already there
    merged_params = dict(redirect_params_flat)
    for key, value in request_params_flat.items():
        if key not in merged_params:
            merged_params[key] = value

    # Build the merged URL
    path = parsed_redirect.path
    if merged_params:
        # Use urlencode to build query string
        query_string = urlencode(merged_params, doseq=True)
        result = f"{path}?{query_string}"
    else:
        result = path

    # Append fragment if present
    if redirect_fragment:
        result = f"{result}#{redirect_fragment}"

    return result
