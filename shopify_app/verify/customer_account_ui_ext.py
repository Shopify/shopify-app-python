"""
Shopify Customer Account UI Extension Verification

This module provides functions to verify Shopify Customer Account UI Extension requests.
"""

from __future__ import annotations

from ..types import AppConfig, RequestInput, ResultWithNonExchangeableIdToken
from ._non_exchangeable_id_token import _verify_non_exchangeable_id_token


def verify_customer_account_ui_ext_req(
    request: RequestInput, config: AppConfig
) -> ResultWithNonExchangeableIdToken:
    """
    Verifies requests coming from Shopify Customer Account UI Extensions.

    Args:
        request (dict): The request object containing method, headers, url, and body
        config (dict): The app configuration with client_id, client_secret and optional old_client_secret

    Returns:
        ResultWithNonExchangeableIdToken: Verification result with id_token details
    """
    return _verify_non_exchangeable_id_token(
        request, config, "Customer Account UI Extension"
    )
