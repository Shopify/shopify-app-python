"""Shared validation utilities for exchange operations.

This module contains ONLY validators that are used by multiple exchange modules.
File-specific validators should be private functions in their respective files.

Shared validators:
- validate_shop: Used by client_credentials.py AND refresh_token.py
- validate_client_id: Used by token_exchange.py AND refresh_token.py
"""

from __future__ import annotations

from typing import Literal, Optional, Tuple, Union, overload

from ..types import ClientCredentialsExchangeResult, Log, Res, TokenExchangeResult


@overload
def validate_client_id(
    client_id: str,
    shop: Optional[str] = ...,
    result_type: Literal["token_exchange"] = ...,
) -> Tuple[bool, Optional[TokenExchangeResult]]: ...


@overload
def validate_client_id(
    client_id: str,
    shop: Optional[str] = ...,
    result_type: Literal["client_credentials"] = ...,
) -> Tuple[bool, Optional[ClientCredentialsExchangeResult]]: ...


def validate_client_id(
    client_id: str,
    shop: Optional[str] = None,
    result_type: Literal["token_exchange", "client_credentials"] = "token_exchange",
) -> Tuple[bool, Optional[Union[TokenExchangeResult, ClientCredentialsExchangeResult]]]:
    """Validate client_id parameter.

    Used by: token_exchange.py, refresh_token.py

    Args:
        client_id: Client ID to validate
        shop: Optional shop name for error response
        result_type: "token_exchange" or "client_credentials" to determine return type

    Returns:
        tuple: (is_valid: bool, error_response: dataclass or None)
    """
    if not client_id:
        log = Log(
            code="configuration_error",
            detail="Expected clientId to be a non-empty string, but got ''",
        )
        response = Res(status=500, body="", headers={})

        if result_type == "client_credentials":
            return (
                False,
                ClientCredentialsExchangeResult(
                    ok=False,
                    shop=shop,
                    access_token=None,
                    log=log,
                    http_logs=[],
                    response=response,
                ),
            )
        else:
            return (
                False,
                TokenExchangeResult(
                    ok=False,
                    shop=shop,
                    access_token=None,
                    log=log,
                    http_logs=[],
                    response=response,
                ),
            )
    return (True, None)


@overload
def validate_shop(
    shop: str,
    result_type: Literal["token_exchange"] = ...,
) -> Tuple[bool, Optional[TokenExchangeResult]]: ...


@overload
def validate_shop(
    shop: str,
    result_type: Literal["client_credentials"] = ...,
) -> Tuple[bool, Optional[ClientCredentialsExchangeResult]]: ...


def validate_shop(
    shop: str,
    result_type: Literal["token_exchange", "client_credentials"] = "token_exchange",
) -> Tuple[bool, Optional[Union[TokenExchangeResult, ClientCredentialsExchangeResult]]]:
    """Validate shop parameter.

    Used by: client_credentials.py, refresh_token.py

    Args:
        shop: Shop string to validate
        result_type: "token_exchange" or "client_credentials" to determine return type

    Returns:
        tuple: (is_valid: bool, error_response: dataclass or None)
    """
    if not shop or not isinstance(shop, str):
        log = Log(
            code="configuration_error",
            detail="Expected shop to be a non-empty string, but got ''",
        )
        response = Res(status=500, body="", headers={})

        if result_type == "client_credentials":
            return (
                False,
                ClientCredentialsExchangeResult(
                    ok=False,
                    shop=None,
                    access_token=None,
                    log=log,
                    http_logs=[],
                    response=response,
                ),
            )
        else:
            return (
                False,
                TokenExchangeResult(
                    ok=False,
                    shop=None,
                    access_token=None,
                    log=log,
                    http_logs=[],
                    response=response,
                ),
            )
    return (True, None)
