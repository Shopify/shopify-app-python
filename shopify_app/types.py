"""
Shopify App Python SDK Types

This module provides frozen dataclass types for all SDK return values.
All types use snake_case for field names following Python conventions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, TypedDict

# =============================================================================
# Configuration Types
# =============================================================================


class AppConfig(TypedDict):
    """
    App configuration dictionary.

    Attributes:
        client_id: The Shopify app client ID (required)
        client_secret: The Shopify app client secret (required)
        old_client_secret: Previous client secret for rotation (value can be None)
    """

    client_id: str
    client_secret: str
    old_client_secret: Optional[str]


class RequestInput(TypedDict):
    """
    HTTP request input for verification functions.

    Attributes:
        method: HTTP method (e.g., "GET", "POST")
        headers: HTTP headers as key-value pairs
        url: Full request URL
        body: Request body as string
    """

    method: str
    headers: Dict[str, str]
    url: str
    body: str


# =============================================================================
# Core Types
# =============================================================================


@dataclass(frozen=True)
class Res:
    """Response object returned by SDK functions."""

    status: int
    body: str
    headers: Dict[str, str]


@dataclass(frozen=True)
class Log:
    """
    Log object describing the state of a request.

    Attributes:
        code: A unique log code (e.g., "missing_id_token")
        detail: A short description of the state and what to do with the response
    """

    code: str
    detail: str


@dataclass(frozen=True)
class LogWithReq:
    """
    Log object with request details for verification results.

    Used by request verification functions where the request context
    is always available and should be included in the log.

    Attributes:
        code: A unique log code (e.g., "missing_id_token")
        detail: A short description of the state and what to do with the response
        req: Full request object for debugging
    """

    code: str
    detail: str
    req: "RequestInput"


@dataclass(frozen=True)
class HttpLog:
    """
    Describes a request the function made and the response it received.

    Used by exchange and GraphQL functions to log HTTP interactions.

    Attributes:
        code: A unique log code (e.g., "retry_request", "success")
        detail: A description of what happened and what should happen next
        req: The request the function made (matches RequestInput structure)
        res: The response the function received
    """

    code: str
    detail: str
    req: RequestInput
    res: "Res"


# =============================================================================
# Token Types
# =============================================================================


@dataclass(frozen=True)
class IdTokenDetails:
    """
    ID token details from verification.

    Attributes:
        exchangeable: Whether this token can be exchanged for an access token.
                      True for App Home, Admin UI Extension, POS UI Extension.
                      False for Checkout UI Extension, Customer Account UI Extension.
        token: The JWT token string
        claims: The decoded JWT claims as a dictionary
    """

    exchangeable: bool
    token: str
    claims: Dict[str, Any]


@dataclass(frozen=True)
class User:
    """
    User information for online access tokens.

    Attributes:
        id: User ID
        first_name: User's first name
        last_name: User's last name
        scope: User's granted scopes
        email: User's email address
        account_owner: Whether user is the account owner
        locale: User's locale
        collaborator: Whether user is a collaborator
        email_verified: Whether user's email is verified
    """

    id: int
    first_name: str
    last_name: str
    scope: str
    email: str
    account_owner: bool
    locale: str
    collaborator: bool
    email_verified: bool


@dataclass(frozen=True)
class TokenExchangeAccessToken:
    """
    Access token from token exchange (supports online and offline modes).

    Attributes:
        shop: The shop identifier (without .myshopify.com)
        token: The access token string
        expires: ISO 8601 timestamp when token expires (or None if never)
        scope: Granted scopes
        access_mode: Either "online" or "offline"
        refresh_token: Token used to refresh this access token
        refresh_token_expires: ISO 8601 timestamp when refresh token expires
        user: User info for online tokens (None for offline)
    """

    shop: str
    token: str
    expires: Optional[str]
    scope: str
    access_mode: Literal["online", "offline"]
    refresh_token: str
    refresh_token_expires: Optional[str]
    user: Optional[User]


@dataclass(frozen=True)
class ClientCredentialsAccessToken:
    """
    Access token from client credentials exchange (offline mode only).

    Attributes:
        shop: The shop identifier (without .myshopify.com)
        token: The access token string
        expires: ISO 8601 timestamp when token expires (or None if never)
        scope: Granted scopes
        access_mode: Always "offline" for client credentials
        user: Always None for client credentials (no user context)
    """

    shop: str
    token: str
    expires: Optional[str]
    scope: str
    access_mode: Literal["offline"]
    user: None


# =============================================================================
# Result Types
# =============================================================================


@dataclass(frozen=True)
class ResultForReq:
    """
    Result from verify_webhook_req and verify_flow_action_req.

    Attributes:
        ok: Whether verification succeeded
        shop: The shop identifier (without .myshopify.com), or None on failure
        log: LogWithReq object with verification details (includes the request)
        response: Suggested HTTP response to return
    """

    ok: bool
    shop: Optional[str]
    log: LogWithReq
    response: Res


@dataclass(frozen=True)
class ResultWithNonExchangeableIdToken:
    """
    Result from verify_checkout_ui_ext_req and verify_customer_account_ui_ext_req.

    Includes the same fields as ResultForReq, plus a non-exchangeable ID token.

    Attributes:
        ok: Whether verification succeeded
        shop: The shop identifier (without .myshopify.com), or None on failure
        log: LogWithReq object with verification details (includes the request)
        response: Suggested HTTP response to return
        id_token: ID token details (non-exchangeable), or None on failure
    """

    ok: bool
    shop: Optional[str]
    log: LogWithReq
    response: Res
    id_token: Optional[IdTokenDetails]


@dataclass(frozen=True)
class ResultWithExchangeableIdToken:
    """
    Result from verify_admin_ui_ext_req, verify_pos_ui_ext_req, and verify_app_home_req.

    Includes the same fields as ResultForReq, plus an exchangeable ID token and user info.

    Attributes:
        ok: Whether verification succeeded
        shop: The shop identifier (without .myshopify.com), or None on failure
        log: LogWithReq object with verification details (includes the request)
        response: Suggested HTTP response to return
        user_id: The user ID from the token's sub claim, or None on failure
        id_token: ID token details (exchangeable), or None on failure
        new_id_token_response: Pre-built response for token refresh scenarios
    """

    ok: bool
    shop: Optional[str]
    log: LogWithReq
    response: Res
    user_id: Optional[str]
    id_token: Optional[IdTokenDetails]
    new_id_token_response: Optional[Res]


@dataclass(frozen=True)
class ResultWithLoggedInCustomerId:
    """
    Result from verify_app_proxy_req.

    Includes the same fields as ResultForReq, plus logged_in_customer_id.

    Attributes:
        ok: Whether verification succeeded
        shop: The shop identifier (without .myshopify.com), or None on failure
        log: LogWithReq object with verification details (includes the request)
        response: Suggested HTTP response to return
        logged_in_customer_id: Customer ID if logged in, or None
    """

    ok: bool
    shop: Optional[str]
    log: LogWithReq
    response: Res
    logged_in_customer_id: Optional[str]


@dataclass(frozen=True)
class TokenExchangeResult:
    """
    Result from exchange_using_token_exchange and refresh_token_exchanged_access_token.

    Attributes:
        ok: Whether the exchange succeeded
        shop: The shop identifier (without .myshopify.com), or None on failure
        log: Log object with exchange details
        response: Suggested HTTP response to return
        access_token: The exchanged access token, or None on failure
        http_logs: List of HTTP interactions during the exchange
    """

    ok: bool
    shop: Optional[str]
    log: Log
    response: Res
    access_token: Optional[TokenExchangeAccessToken]
    http_logs: List[HttpLog]


@dataclass(frozen=True)
class ClientCredentialsExchangeResult:
    """
    Result from exchange_using_client_credentials.

    Attributes:
        ok: Whether the exchange succeeded
        shop: The shop identifier (without .myshopify.com), or None on failure
        log: Log object with exchange details
        response: Suggested HTTP response to return
        access_token: The exchanged access token (offline only), or None on failure
        http_logs: List of HTTP interactions during the exchange
    """

    ok: bool
    shop: Optional[str]
    log: Log
    response: Res
    access_token: Optional[ClientCredentialsAccessToken]
    http_logs: List[HttpLog]


@dataclass(frozen=True)
class GQLResult:
    """
    Result from admin_graphql_request.

    Attributes:
        ok: Whether the GraphQL request succeeded
        shop: The shop identifier (without .myshopify.com), or None on failure
        log: Log object with request details
        response: The HTTP response received
        data: GraphQL response data, or None on failure
        extensions: GraphQL response extensions, or None
        http_logs: List of HTTP interactions (including retries)
    """

    ok: bool
    shop: Optional[str]
    log: Log
    response: Res
    data: Optional[Dict[str, Any]]
    extensions: Optional[Dict[str, Any]]
    http_logs: List[HttpLog]


# =============================================================================
# Type Aliases for Convenience
# =============================================================================

# Access mode literal type
AccessMode = Literal["online", "offline"]
