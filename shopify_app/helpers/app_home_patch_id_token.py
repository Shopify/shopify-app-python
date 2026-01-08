"""
Shopify App Home Patch ID Token Page Rendering

This module provides a helper function to render the App Home Patch ID Token Page
HTML for embedded apps.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from ..types import AppConfig, LogWithReq, RequestInput, Res, ResultForReq


def app_home_patch_id_token(request: RequestInput, config: AppConfig) -> ResultForReq:
    """
    Renders the App Home Patch ID Token page  HTML.

    Generates a lightweight HTML page that loads the App Bridge script to obtain
    fresh session tokens for embedded apps.

    Args:
        request (dict): Request object with method, headers, url, and body
        config (dict): App configuration with client_id

    Returns:
        ResultForReq: Result with ok, shop, log, and response containing HTML and headers
    """
    client_id = config.get("client_id", "")

    # Check for missing client ID
    if not client_id:
        return ResultForReq(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="missing_client_id",
                detail="Client ID is required but was not provided. Check configuration and respond 500 Internal Server Error using the provided response.",
                req=request,
            ),
            response=Res(status=500, body="Internal Server Error", headers={}),
        )

    # Extract shop and shopify-reload from request query parameters
    url = request.get("url", "")

    if not url:
        return ResultForReq(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="missing_request_url",
                detail="Request URL is required but was not provided.",
                req=request,
            ),
            response=Res(status=400, body="Bad Request", headers={}),
        )

    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)

    # parse_qs returns lists, so get first value if present
    shop_list = query_params.get("shop", [])
    shop = shop_list[0] if shop_list else ""

    shopify_reload_list = query_params.get("shopify-reload", [])
    shopify_reload = shopify_reload_list[0] if shopify_reload_list else ""

    # Check for missing shop
    if not shop:
        return ResultForReq(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="missing_shop",
                detail="Shop parameter is required in request URL query string but was not provided. Respond 400 Bad Request using the provided response.",
                req=request,
            ),
            response=Res(status=400, body="Bad Request", headers={}),
        )

    # Check for missing shopify-reload
    if not shopify_reload:
        return ResultForReq(
            ok=False,
            shop=None,
            log=LogWithReq(
                code="missing_shopify_reload",
                detail="shopify-reload parameter is required in request URL query string but was not provided. Respond 400 Bad Request using the provided response.",
                req=request,
            ),
            response=Res(status=400, body="Bad Request", headers={}),
        )

    # Generate HTML with client ID from configuration
    html_body = f'<script data-api-key="{client_id}" src="https://cdn.shopify.com/shopifycloud/app-bridge.js"></script>'

    return ResultForReq(
        ok=True,
        shop=shop,
        log=LogWithReq(
            code="patch_id_token_page_success",
            detail="App Home Patch ID Token page Response constructed. Respond with the provided response and App Bridge will obtain an id token.",
            req=request,
        ),
        response=Res(
            status=200,
            body=html_body,
            headers={
                "Content-Type": "text/html",
                "Link": '<https://cdn.shopify.com/shopifycloud/app-bridge.js>; rel="preload"; as="script";',
                "Content-Security-Policy": f"frame-ancestors https://{shop} https://admin.shopify.com;",
            },
        ),
    )
