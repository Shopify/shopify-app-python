"""Shared response building utilities for exchange operations.

This module contains ONLY response builders that are used by multiple exchange modules.
File-specific response builders should be private functions in their respective files.

Shared response builders:
- build_network_error_response: Used by all 3 exchange modules
"""

from __future__ import annotations

from typing import List, Literal, Optional, Union, overload

from ..types import (
    ClientCredentialsExchangeResult,
    HttpLog,
    Log,
    RequestInput,
    Res,
    TokenExchangeResult,
)


@overload
def build_network_error_response(
    shop: Optional[str],
    http_logs: List[HttpLog],
    req_obj: RequestInput,
    operation_type: str = ...,
    result_type: Literal["token_exchange"] = ...,
) -> TokenExchangeResult: ...


@overload
def build_network_error_response(
    shop: Optional[str],
    http_logs: List[HttpLog],
    req_obj: RequestInput,
    operation_type: str = ...,
    result_type: Literal["client_credentials"] = ...,
) -> ClientCredentialsExchangeResult: ...


def build_network_error_response(
    shop: Optional[str],
    http_logs: List[HttpLog],
    req_obj: RequestInput,
    operation_type: str = "token exchange",
    result_type: Literal["token_exchange", "client_credentials"] = "token_exchange",
) -> Union[TokenExchangeResult, ClientCredentialsExchangeResult]:
    """Build standardized network error response.

    Used by: client_credentials.py, refresh_token.py, token_exchange.py

    Args:
        shop: Shop name
        http_logs: List of HTTP logs to append to
        req_obj: Request object for logging
        operation_type: Type of operation (for error message)
        result_type: "token_exchange" or "client_credentials" to determine return type

    Returns:
        Dataclass: Standardized error response (TokenExchangeResult or ClientCredentialsExchangeResult)
    """
    res_obj = Res(status=0, body="", headers={})
    log = Log(
        code="network_error",
        detail=f"Network error occurred during {operation_type}. Respond 500 Internal Server Error using the provided response.",
    )
    http_logs.append(
        HttpLog(
            code=log.code,
            detail=log.detail,
            req=req_obj,
            res=res_obj,
        )
    )
    response = Res(status=500, body="", headers={})

    if result_type == "client_credentials":
        return ClientCredentialsExchangeResult(
            ok=False,
            shop=shop,
            access_token=None,
            log=log,
            http_logs=http_logs,
            response=response,
        )
    else:
        return TokenExchangeResult(
            ok=False,
            shop=shop,
            access_token=None,
            log=log,
            http_logs=http_logs,
            response=response,
        )
