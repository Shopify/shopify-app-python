"""
Shopify App Python SDK

This package provides Python implementations of Shopify app verification functions.
All functions return frozen dataclasses for type safety and IDE autocomplete support.
"""

from __future__ import annotations

from typing import Optional, Union

import httpx

from ._version import __version__
from .exchange.client_credentials import (
    exchange_using_client_credentials,
    exchange_using_client_credentials_async,
)
from .exchange.refresh_token import refresh_access_token, refresh_access_token_async
from .exchange.token_exchange import token_exchange, token_exchange_async
from .graphql.admin_graphql import admin_graphql_request, admin_graphql_request_async
from .helpers.app_home_parent_redirect import app_home_parent_redirect
from .helpers.app_home_patch_id_token import app_home_patch_id_token
from .helpers.app_home_redirect import app_home_redirect

# Export all public types
from .types import (  # Configuration types; Core types; Token types; Result types; Type aliases
    AccessMode,
    AppConfig,
    ClientCredentialsAccessToken,
    ClientCredentialsExchangeResult,
    GQLResult,
    HttpLog,
    IdTokenDetails,
    Log,
    LogWithReq,
    RequestInput,
    Res,
    ResultForReq,
    ResultWithExchangeableIdToken,
    ResultWithLoggedInCustomerId,
    ResultWithNonExchangeableIdToken,
    TokenExchangeAccessToken,
    TokenExchangeResult,
    User,
)
from .verify.admin_ui_ext import verify_admin_ui_ext_req
from .verify.app_home_req import verify_app_home_req
from .verify.app_proxy import verify_app_proxy_req
from .verify.checkout_ui_ext import verify_checkout_ui_ext_req
from .verify.customer_account_ui_ext import verify_customer_account_ui_ext_req
from .verify.flow_action import verify_flow_action_req
from .verify.pos_ui_ext import verify_pos_ui_ext_req
from .verify.webhook import verify_webhook_req


class ShopifyApp:
    """
    ShopifyApp class for verifying Shopify requests.

    Args:
        client_id (str): The Shopify app client ID
        client_secret (str): The Shopify app client secret
        old_client_secret (str, optional): Previous client secret for rotation
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        old_client_secret: Optional[str] = None,
    ):
        if not client_id:
            raise ValueError("client_id is required in ShopifyApp configuration")

        if not client_secret:
            raise ValueError("client_secret is required in ShopifyApp configuration")

        self.config: AppConfig = {
            "client_id": client_id,
            "client_secret": client_secret,
            "old_client_secret": old_client_secret,
        }

    def verify_webhook_req(self, request: RequestInput) -> ResultForReq:
        """
        Verify a webhook request from Shopify.

        Args:
            request (RequestInput): A RequestInput dict with method, headers, url, and body fields

        Returns:
            ResultForReq: Verification result with ok, shop, log, and response fields
        """
        return verify_webhook_req(request, self.config)

    def verify_flow_action_req(self, request: RequestInput) -> ResultForReq:
        """
        Verify a Flow action request from Shopify.

        Args:
            request (RequestInput): Request dictionary with method, headers, url, and body

        Returns:
            ResultForReq: Verification result with ok, shop, log, and response fields
        """
        return verify_flow_action_req(request, self.config)

    def verify_checkout_ui_ext_req(
        self, request: RequestInput
    ) -> ResultWithNonExchangeableIdToken:
        """
        Verify a Checkout UI Extension request from Shopify.

        Args:
            request (RequestInput): A RequestInput dict with method, headers, url, and body fields

        Returns:
            ResultWithNonExchangeableIdToken: Verification result with ok, shop, id_token, log, and response fields
        """
        return verify_checkout_ui_ext_req(request, self.config)

    def verify_pos_ui_ext_req(
        self, request: RequestInput
    ) -> ResultWithExchangeableIdToken:
        """
        Verify a POS UI Extension request from Shopify.

        Args:
            request (RequestInput): A RequestInput dict with method, headers, url, and body fields

        Returns:
            ResultWithExchangeableIdToken: Verification result with ok, shop, user_id, id_token, log, response, and new_id_token_response fields
        """
        return verify_pos_ui_ext_req(request, self.config)

    def verify_customer_account_ui_ext_req(
        self, request: RequestInput
    ) -> ResultWithNonExchangeableIdToken:
        """
        Verify a Customer Account UI Extension request from Shopify.

        Args:
            request (RequestInput): A RequestInput dict with method, headers, url, and body fields

        Returns:
            ResultWithNonExchangeableIdToken: Verification result with ok, shop, id_token, log, and response fields
        """
        return verify_customer_account_ui_ext_req(request, self.config)

    def verify_admin_ui_ext_req(
        self, request: RequestInput
    ) -> ResultWithExchangeableIdToken:
        """
        Verify an Admin UI Extension request from Shopify.

        Args:
            request (RequestInput): A RequestInput dict with method, headers, url, and body fields

        Returns:
            ResultWithExchangeableIdToken: Verification result with ok, shop, user_id, id_token, log, response, and new_id_token_response fields
        """
        return verify_admin_ui_ext_req(request, self.config)

    def verify_app_home_req(
        self, request: RequestInput, app_home_patch_id_token_path: str = ""
    ) -> ResultWithExchangeableIdToken:
        """
        Verify an App Home request from Shopify.

        Args:
            request (RequestInput): A RequestInput dict with method, headers, url, and body fields
            app_home_patch_id_token_path (str): Path to the patch ID token page

        Returns:
            ResultWithExchangeableIdToken: Verification result with ok, shop, user_id, id_token, log, response, and new_id_token_response fields
        """
        return verify_app_home_req(request, self.config, app_home_patch_id_token_path)

    def verify_app_proxy_req(
        self, request: RequestInput
    ) -> ResultWithLoggedInCustomerId:
        """
        Verify an App Proxy request from Shopify.

        Args:
            request (RequestInput): A RequestInput dict with method, headers, url, and body fields

        Returns:
            ResultWithLoggedInCustomerId: Verification result with ok, shop, logged_in_customer_id, log, and response fields
        """
        return verify_app_proxy_req(request, self.config)

    def app_home_patch_id_token(self, request: RequestInput) -> ResultForReq:
        """
        Render the App Home Patch ID Token page.

        Args:
            request (RequestInput): A RequestInput dict with method, headers, url, and body fields

        Returns:
            ResultForReq: Result with ok, shop, log, and response containing HTML and headers
        """
        return app_home_patch_id_token(request, self.config)

    def app_home_parent_redirect(
        self,
        request: RequestInput,
        redirect_url: str,
        shop: str,
        target: Optional[str] = None,
    ) -> ResultForReq:
        """
        Generate a redirect response that breaks out of the app home iframe.

        Args:
            request (RequestInput): A RequestInput dict with method, headers, url, and body fields
            redirect_url (str): The URL to redirect to
            shop (str): The shop domain (e.g., "test-shop")
            target (str, optional): Target window: "_top" or "_blank" (default: "_top")

        Returns:
            ResultForReq: Result with ok, shop, log, and response
        """
        return app_home_parent_redirect(
            request, self.config, redirect_url, shop, target
        )

    def app_home_redirect(
        self, request: RequestInput, redirect_url: str, shop: str
    ) -> ResultForReq:
        """
        Generate a redirect response that stays within the app home iFrame.

        Args:
            request (RequestInput): A RequestInput dict with method, headers, url, and body fields
            redirect_url (str): The relative URL to redirect to (must start with '/')
            shop (str): The shop domain (e.g., "test-shop")

        Returns:
            ResultForReq: Result with ok, shop, log, and response
        """
        return app_home_redirect(request, self.config, redirect_url, shop)

    def exchange_using_token_exchange(
        self,
        access_mode: str,
        id_token: Optional[Union[IdTokenDetails, dict]] = None,
        invalid_token_response: Optional[Union[Res, dict]] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> TokenExchangeResult:
        """
        Exchange a pre-validated ID token for an API access token using OAuth 2.0 Token Exchange.

        Args:
            access_mode (str): Either "online" or "offline"
            id_token (IdTokenDetails | dict): IdTokenDetails or dict with exchangeable, token, and claims
            invalid_token_response (Res | dict): Pre-built response to return if token is invalid (or None)
            http_client: Optional HTTP client for testing (undocumented)

        Returns:
            TokenExchangeResult: Result with ok, shop, access_token, log, response, and http_logs
        """
        return token_exchange(
            access_mode,
            self.config,
            id_token=id_token,
            invalid_token_response=invalid_token_response,
            http_client=http_client,
        )

    def refresh_token_exchanged_access_token(
        self,
        access_token: Union[TokenExchangeAccessToken, dict],
        http_client: Optional[httpx.Client] = None,
    ) -> TokenExchangeResult:
        """
        Refresh an expired access token using a refresh token.

        Args:
            access_token (TokenExchangeAccessToken | dict): TokenExchangeAccessToken or dict with shop, refresh_token, expires, and refresh_token_expires
            http_client: Optional HTTP client for testing (undocumented)

        Returns:
            TokenExchangeResult: Result with ok, shop, access_token, log, response, and http_logs
        """
        return refresh_access_token(access_token, self.config, http_client)

    def exchange_using_client_credentials(
        self,
        shop: str,
        http_client: Optional[httpx.Client] = None,
    ) -> ClientCredentialsExchangeResult:
        """
        Exchange client credentials for an API access token.

        Args:
            shop (str): The shop domain (e.g., "shop-name")
            http_client: Optional HTTP client for testing (undocumented)

        Returns:
            ClientCredentialsExchangeResult: Result with ok, shop, access_token, log, response, and http_logs
        """
        return exchange_using_client_credentials(
            shop=shop, app_config=self.config, http_client=http_client
        )

    def admin_graphql_request(
        self,
        query: str,
        shop: str,
        access_token: str,
        api_version: str,
        invalid_token_response: Optional[Union[Res, dict]] = None,
        variables: Optional[dict] = None,
        headers: Optional[dict] = None,
        max_retries: int = 2,
        http_client: Optional[httpx.Client] = None,
    ) -> GQLResult:
        """
        Make a GraphQL request to the Shopify Admin API.

        Args:
            query (str): The GraphQL query or mutation string
            shop (str): Shop domain (e.g., "example")
            access_token (str): Valid access token for the shop
            api_version (str): API version (e.g., "2024-01")
            invalid_token_response (Res | dict): Pre-built response to return if token is invalid
            variables (dict[str, Any]): Optional GraphQL variables
            headers (dict[str, str]): Optional additional HTTP headers
            max_retries (int): Maximum retry count (default: 2)
            http_client: Optional HTTP client for testing (undocumented)

        Returns:
            GQLResult: Result with ok, shop, log, response, data, extensions, and http_logs fields
        """
        return admin_graphql_request(
            query,
            shop=shop,
            access_token=access_token,
            api_version=api_version,
            invalid_token_response=invalid_token_response,
            variables=variables,
            headers=headers,
            max_retries=max_retries,
            app_config=self.config,
            http_client=http_client,
        )

    # Async methods

    async def exchange_using_token_exchange_async(
        self,
        access_mode: str,
        id_token: Optional[Union[IdTokenDetails, dict]] = None,
        invalid_token_response: Optional[Union[Res, dict]] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> TokenExchangeResult:
        """
        Async version of exchange_using_token_exchange.

        Exchange a pre-validated ID token for an API access token using OAuth 2.0 Token Exchange.

        Args:
            access_mode (str): Either "online" or "offline"
            id_token (IdTokenDetails | dict): IdTokenDetails or dict with exchangeable, token, and claims
            invalid_token_response (Res | dict): Pre-built response to return if token is invalid (or None)
            http_client: Optional async HTTP client for testing (httpx.AsyncClient)

        Returns:
            TokenExchangeResult: Result with ok, shop, access_token, log, response, and http_logs
        """
        return await token_exchange_async(
            access_mode,
            self.config,
            id_token=id_token,
            invalid_token_response=invalid_token_response,
            http_client=http_client,
        )

    async def refresh_token_exchanged_access_token_async(
        self,
        access_token: Union[TokenExchangeAccessToken, dict],
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> TokenExchangeResult:
        """
        Async version of refresh_token_exchanged_access_token.

        Refresh an expired access token using a refresh token.

        Args:
            access_token (TokenExchangeAccessToken | dict): TokenExchangeAccessToken or dict with shop, refresh_token, expires, and refresh_token_expires
            http_client: Optional async HTTP client for testing (httpx.AsyncClient)

        Returns:
            TokenExchangeResult: Result with ok, shop, access_token, log, response, and http_logs
        """
        return await refresh_access_token_async(access_token, self.config, http_client)

    async def exchange_using_client_credentials_async(
        self,
        shop: str,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> ClientCredentialsExchangeResult:
        """
        Async version of exchange_using_client_credentials.

        Exchange client credentials for an API access token.

        Args:
            shop (str): The shop domain (e.g., "shop-name")
            http_client: Optional async HTTP client for testing (httpx.AsyncClient)

        Returns:
            ClientCredentialsExchangeResult: Result with ok, shop, access_token, log, response, and http_logs
        """
        return await exchange_using_client_credentials_async(
            shop,
            self.config,
            http_client=http_client,
        )

    async def admin_graphql_request_async(
        self,
        query: str,
        shop: str,
        access_token: str,
        api_version: str,
        invalid_token_response: Optional[Union[Res, dict]] = None,
        variables: Optional[dict] = None,
        headers: Optional[dict] = None,
        max_retries: int = 2,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> GQLResult:
        """
        Async version of admin_graphql_request.

        Make an async GraphQL request to the Shopify Admin API.

        Args:
            query (str): The GraphQL query or mutation string
            shop (str): Shop domain (e.g., "example")
            access_token (str): Valid access token for the shop
            api_version (str): API version (e.g., "2024-01")
            invalid_token_response (Res | dict): Pre-built response to return if token is invalid
            variables (dict[str, Any]): Optional GraphQL variables
            headers (dict[str, str]): Optional additional HTTP headers
            max_retries (int): Maximum retry count (default: 2)
            http_client: Optional async HTTP client for testing (httpx.AsyncClient)

        Returns:
            GQLResult: Result with ok, shop, log, response, data, extensions, and http_logs
        """
        return await admin_graphql_request_async(
            query,
            shop=shop,
            access_token=access_token,
            api_version=api_version,
            invalid_token_response=invalid_token_response,
            variables=variables,
            headers=headers,
            max_retries=max_retries,
            app_config=self.config,
            http_client=http_client,
        )


__all__ = [
    "__version__",
    # Configuration types
    "ShopifyApp",
    "AppConfig",
    # Core types
    "RequestInput",
    "Res",
    "Log",
    "LogWithReq",
    "HttpLog",
    # Token types
    "IdTokenDetails",
    "User",
    "TokenExchangeAccessToken",
    "ClientCredentialsAccessToken",
    # Result types
    "ResultForReq",
    "ResultWithNonExchangeableIdToken",
    "ResultWithExchangeableIdToken",
    "ResultWithLoggedInCustomerId",
    "TokenExchangeResult",
    "ClientCredentialsExchangeResult",
    "GQLResult",
    # Type aliases
    "AccessMode",
]
