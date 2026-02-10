"""
Shopify Flow Action Request Verification

This module provides functions to verify Shopify Flow action requests.
"""

from __future__ import annotations

from ..types import AppConfig, RequestInput, ResultForReq
from ._body_hmac_in_header import _verify_body_hmac_in_header

_FLOW_HMAC_HEADER_NAMES = ("x-shopify-hmac-sha256",)
_FLOW_SHOP_HEADER_NAMES = ("x-shopify-shop-domain",)


def verify_flow_action_req(request: RequestInput, config: AppConfig) -> ResultForReq:
    """
    Verifies requests coming from Shopify Flow actions.

    Args:
        request (dict): The request object containing method, headers, and body
        config (dict): The app configuration with client_secret

    Returns:
        ResultForReq: Verification result with ok, shop, log, and response fields
    """
    return _verify_body_hmac_in_header(
        request,
        config,
        "Flow action",
        hmac_header_names=_FLOW_HMAC_HEADER_NAMES,
        shop_header_names=_FLOW_SHOP_HEADER_NAMES,
    )
