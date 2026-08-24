# Shopify App Package

Python package for building Shopify applications.

This package encodes the secure, correct way to build a Shopify app. Most of what you need is already handled for you. The guidance below is written so you use the built-in path and do not reimplement (less safely) things the package already does. If you are ever tempted to parse, verify, or refresh something yourself, check the [Common misuses to avoid](#common-misuses-to-avoid) section first.

> **Upgrading from [`ShopifyAPI`](https://github.com/Shopify/shopify_python_api)?** This is a new, framework-agnostic package with a different API, designed for incremental adoption. Adopt it gradually, one route at a time. Breaking changes between releases are listed in the [CHANGELOG](CHANGELOG.md).

## Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Requirements](#requirements)
- [Features](#features)
- [Principles](#principles)
- [Start here (the green path)](#start-here-the-green-path)
- [Setup steps](#setup-steps)
- [Using the package](#using-the-package)
  - [Initialization](#initialization)
  - [Converting a request](#converting-a-request)
  - [Converting a Shopify response](#converting-a-shopify-response)
  - [The verify result](#the-verify-result)
  - [Getting the shop](#getting-the-shop)
  - [Verifying requests with exchangeable ID tokens](#verifying-requests-with-exchangeable-id-tokens)
  - [Navigating inside and outside the App Home iframe](#navigating-inside-and-outside-the-app-home-iframe)
  - [GraphQL requests](#graphql-requests)
  - [Verifying requests without exchangeable ID tokens](#verifying-requests-without-exchangeable-id-tokens)
  - [Getting access tokens with client credentials](#getting-access-tokens-with-client-credentials)
  - [Async variants](#async-variants)
- [Common misuses to avoid](#common-misuses-to-avoid)
- [Contributing, issues, feedback and feature requests](#contributing-issues-feedback-and-feature-requests)

## Prerequisites

Before you start, make sure you have:

- A [Shopify Partner account](https://partners.shopify.com) and a development store
- The [Shopify CLI](https://shopify.dev/docs/api/shopify-cli#installation) installed
- Python 3.8+ and pip
- A web framework project (Django, Flask, or FastAPI)

## Installation

```bash
pip install --upgrade shopifyapp
```

## Requirements

- Python >= 3.8
- httpx for making HTTP requests
- pyjwt for JWT token handling

## Features

Each function encodes a piece of the secure green path. Use the listed function rather than building your own version.

Request Verification:

- `verify_admin_ui_ext_req`: Requests from Admin UI extensions
- `verify_app_home_req`: Requests for embedded app home that use App Bridge
- `verify_app_proxy_req`: Requests from storefronts via App Proxy
- `verify_checkout_ui_ext_req`: Requests from checkout UI extensions
- `verify_customer_account_ui_ext_req`: Requests from Customer account UI extensions
- `verify_flow_action_req`: Requests from Flow action extensions
- `verify_pos_ui_ext_req`: Requests from POS UI extensions
- `verify_webhook_req`: Webhook requests

Exchange:

- `exchange_using_token_exchange`: Use Token Exchange to exchange an ID token for an access token
- `exchange_using_client_credentials`: Get access tokens via client credentials
- `refresh_token_exchanged_access_token`: Refresh an access token that was created using Token Exchange. Checks if a token refresh can and should happen.

GraphQL:

- `admin_graphql_request`: Make Admin API GraphQL requests with automatic retry handling

Helpers:

- `app_home_patch_id_token`: Securely renders the HTML to refresh a stale ID token. Use this instead of your own logic.
- `app_home_parent_redirect`: Asks the parent (Shopify admin) to redirect to a new URL, breaking out of the iframe
- `app_home_redirect`: Redirects to a relative URL within the app home iframe

## Principles

1. **Built-in best practices:** This package encodes best practices for building Shopify apps as primitives. Use them correctly and you'll build secure, performant apps on the green-path.
2. **What most apps need most of the time:** This package does not intend to focus on some less common features of the Shopify app platform (e.g: Non Embedded apps).
3. **Framework agnostic:** Whether you're using Django, Flask, or FastAPI, this package won't force architectural decisions on you. We provide primitives. You compose them however you wish. We've prototyped extensively to make sure that composition can lead to idiomatic patterns.
4. **Language agnostic:** Whilst this is a Python package, its API is shared with a PHP package. This creates some interesting constraints, and sacrifices some idioms. But... the big benefit is that fixes in one community will benefit the other. As the PHP package evolves, so will the Python package (and vice-versa).

## Start here (the green path)

Most apps follow the same path on every request from Shopify:

1. Convert your framework's request into the package's request shape.
2. Verify the request with the matching `verify_...` function.
3. If `ok` is `False`, return the provided `response`.
4. Use `result.shop` to look up or store the shop's access token.
5. Exchange or refresh the token when needed.
6. Make Admin GraphQL calls, passing the retry response the package gave you.

Every step below has a built-in function. Use it. The recurring rule in this README: if the package already gives you a value or a response, use that value or response. Do not parse, craft, or re-verify it yourself.

## Setup steps

This section will focus on steps that are universal to any web framework. We'll provide examples for Django, FastAPI and Flask. But these examples are fairly universal and can be translated to other approaches.

### Initialize your web framework

- [Django quickstart](https://docs.djangoproject.com/en/stable/intro/tutorial01/)
- [Flask quickstart](https://flask.palletsprojects.com/en/latest/quickstart/)
- [FastAPI quickstart](https://fastapi.tiangolo.com/tutorial/)

### Setup the Shopify CLI

Inside the directory where you initialized your framework create a `shopify.app.toml` (This will be overwritten when you run `shopify app init --reset`):

```toml
client_id = ""
name = ""
application_url = ""
embedded = true

[access_scopes]
scopes = "write_products"

[webhooks]
api_version = "2025-01"
```

Make sure there is at-least a minimal `package.json`:

```json
{
  "name": "my-python-app",
  "scripts": {
    "start": "python manage.py runserver"
  }
}
```

Create a `shopify.web.toml`. The Shopify CLI needs this file to know how to serve your app during development. Set `roles` and the `dev` command so the CLI can serve and proxy your app.

```toml
name = "My Python App"
roles = ["frontend", "backend"]
webhooks_path = "/webhooks/app/uninstalled"

[commands]
dev = "[COMMAND]"
```

Replace `[COMMAND]` with the command to run your app in development mode. For example:

- Django: `python manage.py runserver`
- Flask: `flask run`
- FastAPI: `uvicorn main:app --reload`

### Configure the PORT

The Shopify CLI needs your web framework to run on a specific port. The CLI provides an environment variable. It's important you use this. Here are some examples.

Django (in `manage.py`):

```python
sys.argv.append(f"0.0.0.0:{os.getenv('PORT', '8000')}")
```

Flask (in `app.py`):

```python
app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
```

FastAPI (in `main.py`):

```python
uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
```

### Run your app

With these setup steps complete you should be able to run

```bash
shopify app dev --reset
```

Only use the `--reset` flag the first time.

## Using the package

### Initialization

`SHOPIFY_API_KEY` and `SHOPIFY_API_SECRET` are provided by the Shopify CLI.

```python
import os
from shopify_app import ShopifyApp

shopify = ShopifyApp(
    client_id=os.getenv("SHOPIFY_API_KEY"),
    client_secret=os.getenv("SHOPIFY_API_SECRET"),
)
```

For secret rotation, `old_client_secret` is an optional keyword argument. Since the CLI does not provide this env var, you will need to provide it manually. Requests signed with either the current or the old secret are accepted while you roll the secret out, so you avoid downtime during rotation. Read more about [secret rotation](https://shopify.dev/docs/apps/build/authentication-authorization/client-secrets/rotate-revoke-client-credentials).

```python
shopify = ShopifyApp(
    client_id=os.getenv("SHOPIFY_API_KEY"),
    client_secret=os.getenv("SHOPIFY_API_SECRET"),
    old_client_secret=os.getenv("SHOPIFY_OLD_API_SECRET"),
)
```

**Do** set `old_client_secret` while rotating a secret, then remove it once the rotation is complete.

**Don't** roll a secret without it. If you swap the secret in one step, in-flight requests signed with the previous secret will fail verification.

### Converting a request

So that the package can support multiple frameworks, your app must convert your framework's concept of a Request to the package's concept.

**Do** pass the raw request through unchanged: the method, all headers, the full URL including query string, and the unmodified body.

**Don't** filter headers, drop query parameters, or re-encode the body. Verification depends on the exact bytes Shopify sent. Altering them causes valid requests to fail verification.

Django Example:

```python
# Django passes the request to views and view decorators
def request_to_shopify_req(request):
    return {
        "method": request.method,
        "headers": dict(request.headers),
        "url": request.build_absolute_uri(),
        "body": request.body.decode("utf-8") if request.body else "",
    }
```

FastAPI Example:

```python
from fastapi import Request

async def request_to_shopify_req(request: Request):
    body = await request.body()
    return {
        "method": request.method,
        "headers": dict(request.headers),
        "url": str(request.url),
        "body": body.decode("utf-8") if body else "",
    }
```

Flask Example:

```python
from flask import request

def request_to_shopify_req():
    return {
        "method": request.method,
        "headers": dict(request.headers),
        "url": request.url,
        "body": request.get_data(as_text=True),
    }
```

### Converting a Shopify response

Your app must convert the package's concept of a Response to the framework's concept. The Result provided by the package's function also includes a `log` attribute with these properties:

- `code`: A short string describing the situation
- `detail`: Copy describing the state of the request and what you should do next.
- `req`: The Req that was passed to the function.

We recommend logging this information to help you debug.

**Do** return the package's `response` verbatim, including its `status`, `body`, and `headers`.

**Don't** build your own response for failures or drop the headers. The package's response carries the correct status and the security headers Shopify requires (see [Getting the shop](#getting-the-shop) and the App Home section for why this matters).

Django example:

```python
import logging
from django.http import HttpResponse

logger = logging.getLogger(__name__)

def shopify_result_to_response(result):
    logger.info("%s - %s", result.log.code, result.log.detail)

    return HttpResponse(
        result.response.body,
        status=result.response.status,
        headers=result.response.headers,
    )
```

FastAPI example:

```python
import logging
from fastapi.responses import Response

logger = logging.getLogger(__name__)

def shopify_result_to_response(result):
    logger.info("%s - %s", result.log.code, result.log.detail)

    return Response(
        content=result.response.body,
        status_code=result.response.status,
        headers=result.response.headers,
    )
```

Flask Example:

```python
import logging
from flask import Response

logger = logging.getLogger(__name__)

def shopify_result_to_response(result):
    logger.info("%s - %s", result.log.code, result.log.detail)

    return Response(
        response=result.response.body,
        status=result.response.status,
        headers=result.response.headers,
    )
```

### The verify result

Verifying a request returns a result dataclass. Results are similar across all verify functions, with some differences.

Common attributes (all verify functions):

| Attribute | Description | Nullable |
| --- | --- | --- |
| `ok` | Boolean indicating if the request passed verification. Respond with the Response if `False` | No |
| `shop` | The shop sub domain (e.g: `test-shop`, for `test-shop.myshopify.com`). `None` when verification fails. Already parsed correctly for the request type and verified. Always use this value. See [Getting the shop](#getting-the-shop). | Yes |
| `log` | LogWithReq with `code`, `detail`, and `req` attributes for debugging and monitoring. | No |
| `response` | Res with `status`, `body`, and `headers` attributes. Return this when `ok` is `False`. Carries required security headers. Return it as-is. | No |

Attributes for Exchangeable ID Token Requests (`verify_app_home_req`, `verify_admin_ui_ext_req`, `verify_pos_ui_ext_req`):

| Attribute | Description | Nullable |
| --- | --- | --- |
| `user_id` | The merchant user ID. `None` if `ok` is `False`. | Yes |
| `id_token` | IdTokenDetails with `exchangeable` (bool), `token` (str), and `claims` (dict) attributes. | Yes |
| `invalid_token_response` | Pre-built response for the invalid token retry flow. Pass it to `exchange_using_token_exchange` and `admin_graphql_request` so Shopify can retry requests with a fresh token. | Yes |

Attributes for App Proxy Requests (`verify_app_proxy_req`):

| Attribute | Description | Nullable |
| --- | --- | --- |
| `logged_in_customer_id` | The customer ID if logged in. `None` if not logged in. This is a customer ID, not a merchant user ID. | Yes |

### Getting the shop

**Do** use `shop` from the verify result. We securely parse it from the request, avoiding known attack vectors.

**Don't** read the shop from the request yourself (for example by decoding the ID token). That is fragile and skips that protection.

```python
shop = result.shop  # e.g. "test-shop"
```

### Verifying requests with exchangeable ID tokens

Some requests provide exchangeable ID tokens:

1. App home
2. Admin UI Extensions
3. POS UI Extensions

ID tokens from these requests can be exchanged for access tokens, which can be used to access the Admin GraphQL API. These verification methods provide a user id (merchant id) so you can look up an online access token in your database.

#### App Home

First we verify the request:

```python
from .shopify import shopify

def app_home(request):
    req = request_to_shopify_req(request)

    result = shopify.verify_app_home_req(
        req,
        app_home_patch_id_token_path="/auth/patch-id-token",
    )

    # The request should not be trusted
    if not result.ok:
        return shopify_result_to_response(result)
```

`app_home_patch_id_token_path` is required on every `verify_app_home_req` call. It points at your [token-refresh route](#add-the-token-refresh-route). When a page request arrives without a token, or with a stale one, verify redirects the browser there to get a fresh token, so it needs to know the path. Verify checks it on every call, so pass it even on routes that only ever receive `fetch` requests. An empty or missing value returns a configuration error (HTTP 500).

Then we check if there is an access token in the database. If there is one we check if it needs to be refreshed.

```python
    # Your database logic here
    access_token = get_access_token(shop=result.shop, mode="offline")

    if access_token:
        refresh_result = shopify.refresh_token_exchanged_access_token(access_token)

        if not refresh_result.ok:
            return shopify_result_to_response(refresh_result)

        if refresh_result.access_token:
            # Package returned a refreshed token, save it
            save_access_token(refresh_result.access_token)
```

**Do** call `refresh_token_exchanged_access_token` and save the token if one is returned.

**Don't** add your own checks before calling it. It already verifies whether a refresh token exists and whether it has expired, and returns a fresh token only when one is needed. Wrapping it with your own pre-checks just duplicates that logic and risks getting it wrong.

You will need to write the database code to get and save access tokens. The package returns access tokens as dataclasses with these attributes:

| Attribute | Type | Description |
| --- | --- | --- |
| `shop` | str | Shop sub domain (e.g., "test-shop") |
| `access_mode` | str | Access mode: "online" or "offline" |
| `token` | str | The access token |
| `scope` | str | Granted scopes |
| `refresh_token` | str or None | Token used to refresh the access token. `None` for non-expiring tokens. |
| `expires` | str or None | ISO 8601 datetime when access token expires. `None` for non-expiring tokens. |
| `refresh_token_expires` | str or None | ISO 8601 datetime when refresh token expires. `None` for non-expiring tokens. |
| `user` | User or None | User details (online mode only, `None` for offline) |

For the merchant user id, use `result.user_id` from the verify result. Online access tokens also include a `user` object with an `id`; offline tokens have no `user`.

When `access_mode` is "online", the `user` dataclass contains:

| Attribute        | Type | Description                                      |
| ---------------- | ---- | ------------------------------------------------ |
| `id`             | int  | A unique identifier for the user                 |
| `first_name`     | str  | User's first name                                |
| `last_name`      | str  | User's last name                                 |
| `email`          | str  | User's email address                             |
| `email_verified` | bool | Whether the email is verified                    |
| `account_owner`  | bool | Whether the user is the account owner            |
| `locale`         | str  | User's locale (e.g., "en")                       |
| `collaborator`   | bool | Whether the user is a collaborator               |
| `scope`          | str  | User-specific scopes (may differ from app scope) |

Note: For JSON serialization, use `dataclasses.asdict(result.access_token)` to convert to a dictionary.

If there is no access token in the database, use token exchange to get one:

```python
    if not access_token:
        exchange_result = shopify.exchange_using_token_exchange(
            access_mode="offline",
            id_token=result.id_token,
            invalid_token_response=result.invalid_token_response,
        )

        if not exchange_result.ok:
            return shopify_result_to_response(exchange_result)

        # Save the new token
        save_access_token(exchange_result.access_token)
```

Note:

- `exchange_using_token_exchange` receives `result.invalid_token_response` from the verify function. Passing it lets Shopify automatically retry the request if the id token has become stale. Whether you pass it depends on the request type (see the GraphQL section).
- Pass `expiring=False` to request a non-expiring token (no `refresh_token` or `refresh_token_expires`). Defaults to `True`.
- If using online access tokens, use the `user_id` provided by the verify `result`, not the access token.
- If your app has need to access the admin API outside of requests from App Home, Admin UI Extensions or POS UI Extensions you should also exchange and save an offline token.

##### Return the required App Home response headers

App home requests require [special Response headers](https://shopify.dev/docs/apps/build/security/set-up-iframe-protection) (for example, the `Content-Security-Policy` `frame-ancestors` directive). These headers are what allow your app to load securely inside the Shopify admin iframe.

**Do** copy the headers from the verify result onto your App Home response:

```python
# Copy headers from result to your response
for header, value in result.response.headers.items():
    response[header] = value
```

When `ok` is `False`, return the provided `response` as-is. When `ok` is `True`, copy `response.headers` onto your framework's response before rendering App Home.

App requests should also contain [App Bridge](https://shopify.dev/docs/api/app-bridge) and [Polaris Web Components](https://shopify.dev/docs/api/app-home/using-polaris-components) script tags so they remain secure and can look like Shopify:

```html
<script
  src="https://cdn.shopify.com/shopifycloud/app-bridge.js"
  data-api-key="{{ client_id }}"
></script>
<script src="https://cdn.shopify.com/shopifycloud/polaris.js"></script>
```

Replace `{{ client_id }}` with the `SHOPIFY_API_KEY` provided by the Shopify CLI.

##### Add the token-refresh route

Add a route that serves the token-refresh (patch ID token) page. This is what makes ordinary link and full-page navigation inside the App Home iframe work: when a navigation reaches your server without a session token, App Bridge uses this route to obtain a fresh one and retry the original request. Skipping it means in-app navigations that arrive without a token cannot recover.

**Do** use `app_home_patch_id_token` for this route:

```python
def patch_id_token(request):
    req = request_to_shopify_req(request)
    result = shopify.app_home_patch_id_token(req)

    return shopify_result_to_response(result)
```

**Don't** build your own token-refresh page. By using `app_home_patch_id_token`, your app stays secure against known attack vulnerabilities.

This route should match the path configured in `verify_app_home_req`:

```python
    result = shopify.verify_app_home_req(
        req,
        app_home_patch_id_token_path="/auth/patch-id-token",
    )
```

#### Admin UI Extensions

Admin UI Extension are very similar to App Home. You only need change the verify method:

```python
result = shopify.verify_admin_ui_ext_req(req)
```

Admin UI extensions do not need the app home patch id token route. They do not need special headers or Polaris and App Bridge.

#### POS UI Extension

POS UI Extension are very similar to App Home. You only need change the verify method:

```python
result = shopify.verify_pos_ui_ext_req(req)
```

POS UI extensions do not need the app home patch id token route. They do not need special headers or Polaris and App Bridge.

### Navigating inside and outside the App Home iframe

App Home renders inside a cross-origin iframe. Because of this, ordinary links and redirects need care: the iframe cannot rely on cookies, and every authenticated request needs a session token. Use the helpers below rather than building redirects by hand.

#### Redirecting outside the App Home iframe

Use `app_home_parent_redirect` when you need to redirect the merchant to an external URL, breaking out of the app iframe:

```python
def some_handler(request):
    req = request_to_shopify_req(request)

    result = shopify.verify_app_home_req(req, app_home_patch_id_token_path="/auth/patch-id-token")
    if not result.ok:
        return shopify_result_to_response(result)

    # Redirect to an external URL
    redirect_result = shopify.app_home_parent_redirect(
        req,
        redirect_url="https://example.com",
        shop=result.shop,
    )

    return shopify_result_to_response(redirect_result)
```

For navigating to admin pages, we recommend using [Admin Intents](https://shopify.dev/docs/apps/build/admin/admin-intents) as this provides the best merchant experience. However, if this is not possible, you can redirect to Shopify admin pages using the `shop` value from the verify result (e.g., `f"https://admin.shopify.com/store/{result.shop}/products"`).

#### Redirecting within the App Home iframe

Use `app_home_redirect` when you need to redirect to another route within your app, staying inside the app iframe:

```python
def some_handler(request):
    req = request_to_shopify_req(request)

    result = shopify.verify_app_home_req(req, app_home_patch_id_token_path="/auth/patch-id-token")
    if not result.ok:
        return shopify_result_to_response(result)

    # Redirect to another route within the app
    redirect_result = shopify.app_home_redirect(
        req,
        redirect_url="/dashboard",
        shop=result.shop,
    )

    return shopify_result_to_response(redirect_result)
```

Note: The redirect URL must be a relative path starting with `/`. URL parameters from the original request are automatically merged into the redirect URL.

#### Authenticated navigation between your own pages

App Bridge attaches the session token to `fetch` and `XMLHttpRequest`, and it intercepts link clicks on `a`, `s-link`, `s-button`, and `s-clickable` elements. It does not intercept same-origin navigations that target the current frame, so an ordinary link or full-page navigation to one of your own pages reaches your server without a session token, and the destination cannot verify the request.

You do not need a single-page app to handle this. As long as you wire the [token-refresh route](#add-the-token-refresh-route) and pass `app_home_patch_id_token_path` to every `verify_app_home_req` call, the package recovers automatically: when a navigation arrives without a token, verify returns a response that redirects to the patch ID token page, App Bridge re-requests the same URL with a fresh token, and the retried request verifies. Standard multi-page apps work this way.

Do not pass the ID token as a URL parameter to work around this. The token expires after about a minute, so it goes stale on any later navigation, and tokens in URLs leak into logs, referrers, and browser history.

For more detail, see the [App Home documentation](https://shopify.dev/docs/api/app-home).

### GraphQL requests

The package provides a method for making Admin GraphQL requests. Note, there may be a better more performant way to access data using Shopify's infrastructure rather than your own:

- App Home has [Direct API](https://shopify.dev/docs/api/app-home#direct-api-access).
- Admin UI Extensions have [the Query API](https://shopify.dev/docs/api/admin-extensions/latest/api/target-apis/standard-api#standardapi-propertydetail-query)
- POS UI Extensions have [Direct API](https://shopify.dev/docs/api/pos-ui-extensions/latest#direct-api-access)
- Customer Account UI Extensions can query [the Customer Account API](https://shopify.dev/docs/api/customer-account-ui-extensions/latest/apis/customer-account-api), the [Storefront API](https://shopify.dev/docs/api/customer-account-ui-extensions/latest/apis/storefront-api) and the [Order Status API](https://shopify.dev/docs/api/customer-account-ui-extensions/latest/apis/order-status-api/addresses).
- Checkout UI Extensions can query the [Storefront API](https://shopify.dev/docs/api/checkout-ui-extensions/latest/apis/storefront-api) directly.

**Do** prefer the surface-specific data APIs above when you can. **Don't** route data through your own server with `admin_graphql_request` when a faster first-party option exists for that surface.

If you do wish to access the Admin GraphQL API on your server, here is how:

#### When responding to a request from Shopify

Here is how to make a GraphQL request in the context of a request from Shopify. Important notes about this example:

1. This example will use an app home request, but it applies to multiple verify methods
2. This example assumes the request is idempotent
3. This example assumes, that in the event of a failure, you just want Shopify to retry the request.

More details on points 2 & 3 after the code example.

```python
def app_home_handler(request):
    req = request_to_shopify_req(request)

    result = shopify.verify_app_home_req(req, app_home_patch_id_token_path="/auth/patch-id-token")
    if not result.ok:
        return shopify_result_to_response(result)

    # Your database logic here
    access_token = get_access_token(shop=result.shop, mode="offline")

    # If there is no stored token (for example after a delete & retry, where the token
    # was just deleted), exchange one before using it. Otherwise `access_token` is None
    # and the request below crashes.
    if not access_token:
        exchange_result = shopify.exchange_using_token_exchange(
            access_mode="offline",
            id_token=result.id_token,
            invalid_token_response=result.invalid_token_response,
        )
        if not exchange_result.ok:
            return shopify_result_to_response(exchange_result)
        save_access_token(exchange_result.access_token)
        access_token = exchange_result.access_token

    graphql_result = shopify.admin_graphql_request(
        """
        {
            shop {
                id
            }
        }
        """,
        shop=result.shop,
        access_token=access_token.token,
        api_version="2025-01",
        # Passing `result.invalid_token_response` from the verify function
        # tells `admin_graphql_request` in what context the GraphQL request is being made.
        # This becomes important if the GraphQL request fails and you wish for Shopify to retry the request.
        invalid_token_response=result.invalid_token_response,
    )

    # The GraphQL failed
    if not graphql_result.ok:

        # The access_token is invalid
        # In this example we take the simplest possible approach
        # But depending on your logic, you may want a more complex approach
        # Options are detailed below
        if graphql_result.log.code == "unauthorized":
            delete_access_token(shop=result.shop, mode="offline")

        return shopify_result_to_response(graphql_result)

    shop_id = graphql_result.data["shop"]["id"]
```

**Do** branch on the `log` `code` the package returns, as shown above.

**Don't** invent your own error codes or parse error messages. Branch on the `log` `code` the package returns.

Some failures are unrecoverable (for example the app was uninstalled), in which case the merchant must reinstall. If the token is valid but the merchant has not approved a required scope, they must approve it (do not retry). If the token is revoked or invalid, you can recover; the options are below.

For a revoked or invalid token, there are different approaches you can take:

| Option | Steps | Use when |
| --- | --- | --- |
| 1. Delete & retry (shown above) | Delete token, return retry response | Request is idempotent. OK for Shopify to auto-retry |
| 2. Exchange & update with retry fallback | Token exchange, update token, retry GraphQL, (on fail) delete token, return retry response | Request is not idempotent. You can revert prior operations. OK for Shopify to auto-retry |
| 3. Exchange with no fallback | Token exchange, update token, retry GraphQL, (on fail) delete token, return non-retry 401 response | Request is not idempotent. It is not OK for Shopify to auto-retry |

**Note on "Delete & retry":** after you delete the token and return the retry response, App Bridge retries the _same_ request with a fresh session token. That retried request no longer has a stored access token, so the route it lands on must be able to obtain one again (exchange `id_token` from the verify result). If the route only reads a stored token, the retry will fail. The App Home flow above already handles this: it exchanges a token when none is stored.

#### In a background job

When making GraphQL requests in a background job (e.g., processing a webhook, scheduled task) pass `None` for `invalid_token_response`. If the access token is invalid, the request will simply fail.

**Do** pass `None` here. In a background job there is no live request for Shopify to retry, so there is nothing for a retry response to attach to.

```python
def process_job(shop):
    # Your database logic here
    access_token = get_access_token(shop=shop, mode="offline")

    graphql_result = shopify.admin_graphql_request(
        """
        {
            shop {
                id
            }
        }
        """,
        shop=shop,
        access_token=access_token.token,
        api_version="2025-01",
        invalid_token_response=None,
    )

    if not graphql_result.ok:
        return

    shop_id = graphql_result.data["shop"]["id"]
```

#### Customizing GraphQL Requests

`admin_graphql_request` has the following options to customize the GraphQL Request:

- `shop`: Shop domain (e.g., "test-shop").
- `access_token`: Valid access token for the shop.
- `api_version`: API version (e.g., "2025-01")
- `variables`: Optional dictionary of GraphQL variables to pass with your query
- `headers`: Optional dictionary of additional HTTP headers to include in the request
- `max_retries`: Optional custom retry count for rate-limited or transient errors (default: 2)
- `invalid_token_response`: From verification result. If provided, enables retry response when token is invalid (Admin UI Extension or App Home with idempotent operation). If `None`, only fail response is available (requests without ID tokens, background jobs, requires user input before retry)

#### The GraphQL Result

`admin_graphql_request` returns a result dataclass with these attributes:

- `ok`: Boolean indicating if the request was successful.
- `shop`: The shop domain, or `None` if the request failed.
- `log`: Log with `code` and `detail` attributes describing the result state.
- `response`: Res with `status`, `body`, and `headers` attributes.
- `http_logs`: List of HttpLog dataclasses for debugging and monitoring.
- `data`: The GraphQL response data (dict), or `None` if the request failed.
- `extensions`: The GraphQL extensions (dict, e.g., cost information), or `None` if not present.

### Verifying requests without exchangeable ID tokens

The following requests do not provide the required information for token exchange:

- Webhooks
- App Proxy
- Customer Account UI Extension
- Checkout UI Extension

Webhook and App Proxy requests do not provide an id token. Customer Account and Checkout UI Extensions provide an id token, but it is not exchangeable. None of these requests provide a merchant user ID.

If you require access to the Shopify Admin GraphQL API during these requests you must load an offline access token that was exchanged from an App Home, Admin UI or POS UI Extension request.

In every case below, use `result.shop` to look up the stored token. Do not parse the shop yourself (see [Getting the shop](#getting-the-shop)).

#### Webhooks

```python
def webhook_handler(request):
    req = request_to_shopify_req(request)

    result = shopify.verify_webhook_req(req)
    if not result.ok:
        return shopify_result_to_response(result)

    # Your database logic here
    access_token = get_access_token(shop=result.shop, mode="offline")
```

#### App Proxy

App proxy is very similar to webhooks:

```python
result = shopify.verify_app_proxy_req(req)
logged_in_customer_id = result.logged_in_customer_id
```

If the customer is not logged in, the `logged_in_customer_id` will be `None`. Do not confuse this with a `user_id` stored with an online token, which are merchant IDs, not customer IDs.

#### Customer Account UI Extension

Customer Account UI Extensions are almost identical to webhooks:

```python
result = shopify.verify_customer_account_ui_ext_req(req)
```

#### Checkout UI Extension

Checkout UI Extensions are almost identical to webhooks:

```python
result = shopify.verify_checkout_ui_ext_req(req)
```

#### Flow actions

Flow Action requests are almost identical to webhooks:

```python
result = shopify.verify_flow_action_req(req)
```

### Getting access tokens with client credentials

[Client credentials exchange](https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens/client-credentials-grant) allows you to obtain an access token using only your app's client ID and client secret, without requiring an ID token. This is designed for trusted, server-to-server integrations (for example, internal automation or back-office services).

**Do** use this for trusted server-to-server work where there is no merchant request.

**Don't** use it to authenticate a request coming from App Home or an extension. Those requests carry an ID token, and you should verify them and exchange that token instead.

```python
def get_or_refresh_access_token(shop):
    # Check if we have a valid token
    existing_token = get_access_token(shop)
    if existing_token and not is_expired(existing_token.expires):
        return existing_token

    # Get a new token using client credentials
    result = shopify.exchange_using_client_credentials(shop=shop)

    if not result.ok:
        # Log the error
        logger.error(f"{result.log.code} - {result.log.detail}")
        return None

    # Save the new token
    save_access_token(result.access_token)
    return result.access_token
```

The `access_token` dataclass contains:

| Attribute     | Description                                         |
| ------------- | --------------------------------------------------- |
| `shop`        | The shop sub domain (e.g., "test-shop")             |
| `access_mode` | Always "offline"                                    |
| `token`       | The access token string                             |
| `scope`       | The granted scopes                                  |
| `expires`     | ISO 8601 datetime when the token expires (24 hours) |
| `user`        | Always `None` for client credentials                |

Note: Client credentials tokens expire after 24 hours and do not include a refresh token. When the token expires, request a new one using `exchange_using_client_credentials` with the same credentials.

### Async variants

Every network call has an async version with the same signature and an `_async` suffix: `exchange_using_token_exchange_async`, `refresh_token_exchanged_access_token_async`, `exchange_using_client_credentials_async`, and `admin_graphql_request_async`. Use these in async frameworks (for example FastAPI) so you do not block the event loop.

## Common misuses to avoid

The package already handles these for you. Rebuilding them yourself is slower, and in the security-sensitive cases it is genuinely risky. Use the built-in path.

| Don't | Do instead | Why |
| --- | --- | --- |
| Parse the shop from the ID token or request | Use `result.shop` | It is already parsed correctly per request type and verified against spoofing. The shop decides which store's token is used. |
| Build your own token-refresh page | Use `app_home_patch_id_token` | It returns a complete, safe response. Custom pages that render request values are a common injection risk. |
| Render App Home without the response headers | Copy `result.response.headers` onto your response | These are the required iframe-protection headers (for example CSP `frame-ancestors`). |
| Craft your own response on a failed verify | Return `result.response` as-is | It has the correct status and the security headers already set. |
| Alter headers, query string, or body before verifying | Pass the raw request through unchanged | Verification depends on the exact bytes Shopify sent. |
| Add the ID token to the URL, or reach for a single-page app, to keep navigation authenticated | Wire the token-refresh route and pass `app_home_patch_id_token_path` on every verify | Same-origin link and full-page navigations arrive without a session token. The route lets App Bridge re-request with a fresh one, so multi-page apps work without tokens in URLs. |

## Contributing, issues, feedback and feature requests

This package does not accept contributions, but we'd love to hear your feedback.

To report a bug, request a feature, or share feedback, [post in the Shopify dev community forums](https://community.shopify.dev/new-topic?title=[Feedback%20for%20python%20package]&category=shopify-cli-libraries&tags=python-library&domain=Python%20Library). Please don’t open pull requests or GitHub issues here; They will be closed automatically.

We triage and discuss work in the forums. Please see [CONTRIBUTING.md](https://github.com/Shopify/shopify-app-python?tab=contributing-ov-file) for details.

## Created a template?

We've confirmed that AI can scaffold an app using this README. If you create an app template and you'd like to open source it, we'd love to hear from you. Perhaps it can benefit other Python developers.
