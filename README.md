# Shopify App Package

Python package for building Shopify applications.

## Installation

```bash
pip install --upgrade shopifyapp
```

## Requirements

- Python >= 3.8
- httpx for making HTTP requests
- pyjwt for JWT token handling

## Features

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
- `refresh_token_exchanged_access_token`: Refresh an access token that was created using Token Exchange.

GraphQL:

- `admin_graphql_request`: Make Admin API GraphQL requests with automatic retry handling

Helpers:

- `app_home_patch_id_token`: Render the patch ID token page for embedded apps
- `app_home_parent_redirect`: Asks the parent (Shopify admin) to redirect to a new URL, breaking out of the iframe
- `app_home_redirect`: Redirects to a relative URL within the app home iframe

## Principles

1. **Built-in best practices:** This package encodes best practices for building Shopify apps as primitives. Use them correctly and you'll build secure, performant apps on the green-path.
2. **What most apps need most of the time:** This package does not intend to focus on some less common features of the Shopify app platform (e.g: Non Embedded apps).
3. **Framework agnostic:** Whether you're using Django, Flask, or FastAPI, this package won't force architectural decisions on you. We provide primitives. You compose them however you wish. We've prototyped extensively to make sure that composition can lead to idiomatic patterns.
4. **Language agnostic:** Whilst this is a Python package, its API is shared with a PHP package. This creates some interesting constraints, and sacrifices some idioms. But... the big benefit is that fixes in one community will benefit the other. As the PHP package evolves, so will the Python package (and vice-versa).

## Setup steps

This section will focus on steps that are universal to any web framework. We'll provide examples for Django, FastAPI and Flask. But these examples are fairly universal and can be translated to other approaches.

### Install the Shopify CLI

This installs Shopify CLI globally on your system, so you can run shopify commands from any directory.

```
npm install -g @shopify/cli@latest
```

Please see [this guide](https://shopify.dev/docs/api/shopify-cli#installation) for using other JavaScript package managers

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

Create a `shopify.web.toml`:

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

For secret rotation, `old_client_secret` is an optional keyword argument. Since the CLI does not provide this env var, you will need to provide it manually. Read more about [secret rotation](https://shopify.dev/docs/apps/build/authentication-authorization/client-secrets/rotate-revoke-client-credentials).

### Converting a Request

So that the package can support multiple frameworks, your app must convert your frameworks concept of a Request to the package's concept.

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

Your app must convert the packages concept of a Response to the frameworks concept. The Result provided by the package's function also includes a `log` attribute with these properties:

- `code`: A short string describing the situation
- `detail`: Copy describing the state of the request and what you should do next.
- `req`: The Req that was passed to the function.

We recommend logging this information to help you debug.

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

### Verifying request result

Verifying a request returns a result dataclass. Results are similar across all verify functions, with some differences.

Common attributes (all verify functions):

| Attribute  | Description                                                                                            | Nullable |
| ---------- | ------------------------------------------------------------------------------------------------------ | -------- |
| `ok`       | Boolean indicating if the request passed verification. Respond with the Response if `False`            | No       |
| `shop`     | The shop sub domain (e.g: `test-shop`, for `test-shop.myshopify.com`). `None` when verification fails. | Yes      |
| `log`      | LogWithReq with `code`, `detail`, and `req` attributes for debugging and monitoring.                   | No       |
| `response` | Res with `status`, `body`, and `headers` attributes. Return this when `ok` is `False`.                 | No       |

Attributes for Exchangeable ID Token Requests (`verify_app_home_req`, `verify_admin_ui_ext_req`, `verify_pos_ui_ext_req`):

| Attribute               | Description                                                                               | Nullable |
| ----------------------- | ----------------------------------------------------------------------------------------- | -------- |
| `user_id`               | The merchant user ID. `None` if `ok` is `False`.                                          | Yes      |
| `id_token`              | IdTokenDetails with `exchangeable` (bool), `token` (str), and `claims` (dict) attributes. | Yes      |
| `new_id_token_response` | Pre-built response for invalid token retry flow.                                          | Yes      |

Attributes for App Proxy Requests (`verify_app_proxy_req`):

| Attribute               | Description                                                                                           | Nullable |
| ----------------------- | ----------------------------------------------------------------------------------------------------- | -------- |
| `logged_in_customer_id` | The customer ID if logged in. `None` if not logged in. This is a customer ID, not a merchant user ID. | Yes      |

### Verifying Requests with exchangeable ID Tokens

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

Then we check if there is an access token in the database. If there is one we check if it needs to be refreshed.

```python
    # Your database logic here
    access_token = get_access_token(shop=result.shop, mode="offline")

    if access_token:
        refresh_result = shopify.refresh_token_exchanged_access_token(access_token)

        if not refresh_result.ok:
            return shopify_result_to_response(refresh_result)

        if refresh_result.access_token:
            # Package returned a refreshed token — save it
            save_access_token(refresh_result.access_token)
```

You will need to write the database code to get and save access tokens. The package returns access tokens as dataclasses with these attributes:

| Attribute               | Type       | Description                                         |
| ----------------------- | ---------- | --------------------------------------------------- |
| `shop`                  | str        | Shop domain (e.g., "test-shop.myshopify.com")       |
| `access_mode`           | str        | Access mode: "online" or "offline"                  |
| `token`                 | str        | The access token                                    |
| `scope`                 | str        | Granted scopes                                      |
| `refresh_token`         | str        | Token used to refresh the access token              |
| `expires`               | str        | ISO 8601 datetime when access token expires         |
| `refresh_token_expires` | str        | ISO 8601 datetime when refresh token expires        |
| `user_id`               | str        | A unique identifier for the user                    |
| `user`                  | AccessUser | User details (online mode only, `None` for offline) |

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
            invalid_token_response=result.new_id_token_response,
        )

        if not exchange_result.ok:
            return shopify_result_to_response(exchange_result)

        # Save the new token
        save_access_token(exchange_result.access_token)
```

Note:

- `exchange_using_token_exchange` receives `result.new_id_token_response` from the verify function. This allows Shopify to automatically retry this request if the id token has become stale.
- If using online access tokens, use the `user_id` provided by the `result`.
- If your app has need to access the admin API outside of requests from App Home, Admin UI Extensions or POS UI Extensions you should also exchange and save an offline token.

App home requests require [special Response headers](https://shopify.dev/docs/apps/build/security/set-up-iframe-protection). The `result` provides a response that contains these headers. Copy them to your response:

```python
# Copy headers from result to your response
for header, value in result.response.headers.items():
    response[header] = value
```

App requests should also contain [App Bridge](https://shopify.dev/docs/api/app-bridge) and [Polaris Web Components](https://shopify.dev/docs/api/app-home/using-polaris-components) script tags so they remain secure and can look like Shopify:

```html
<script
  src="https://cdn.shopify.com/shopifycloud/app-bridge.js"
  data-api-key="{{ client_id }}"
></script>
<script src="https://cdn.shopify.com/shopifycloud/polaris.js"></script>
```

Replace `{{ client_id }}` with the `SHOPIFY_API_KEY` provided by the Shopify CLI.

Add a special route for handling some edge cases. Adding this route ensures the merchant experience is resilient:

```python
def patch_id_token(request):
    req = request_to_shopify_req(request)
    result = shopify.app_home_patch_id_token(req)

    return shopify_result_to_response(result)
```

This route should match the path configured here:

```python
    result = shopify.verify_app_home_req(
        req,
        app_home_patch_id_token_path="/auth/patch-id-token",
    )
```

#### Redirecting Outside the App Home Iframe

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

#### Redirecting Within the App Home Iframe

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

#### Admin UI Extensions

Admin UI Extension are very similar to App Home. You only need change the verify method:

```python
result = shopify.verify_admin_ui_ext_req(req)
```

Admin UI extensions do not need the app home patch id token route. They do not need special headers or Polaris and App Bridge

#### POS UI Extension

POS UI Extension are very similar to App Home. You only need change the verify method:

```python
result = shopify.verify_pos_ui_ext_req(req)
```

POS UI extensions do not need the app home patch id token route. They do not need special headers or Polaris and App Bridge

### GraphQL Requests

The package provides a method for making Admin GraphQL requests. Note, there may be a better more performant ways to access data using Shopify's infrastructure rather than your own:

- App Home has [Direct API](https://shopify.dev/docs/api/app-home#direct-api-access).
- Admin UI Extensions have [the Query API](https://shopify.dev/docs/api/admin-extensions/latest/api/target-apis/standard-api#standardapi-propertydetail-query)
- POS UI Extensions have [Direct API](https://shopify.dev/docs/api/pos-ui-extensions/latest#direct-api-access)
- Customer Account UI Extensions can query [the Customer Account API](https://shopify.dev/docs/api/customer-account-ui-extensions/latest/apis/customer-account-api), the [Storefront API](https://shopify.dev/docs/api/customer-account-ui-extensions/latest/apis/storefront-api) and the [Order Status API](https://shopify.dev/docs/api/customer-account-ui-extensions/latest/apis/order-status-api/addresses).
- Checkout UI Extensions can query the [Storefront API](https://shopify.dev/docs/api/checkout-ui-extensions/latest/apis/storefront-api) directly.

If you do wish to access the Admin GraphQL API on your server, here is how:

#### When responding to a request from Shopify

Here is how to make a GraphQL request in the context of a request from Shopify. Important notes about this example:

1. This example will use an app home request, but it applies to multiple verify methods
2. This example assumes the request is idempotent
3. This examples assumes, that in the event of a failure, you just want Shopify to retry the request.

More details on points 2 & 3 after the code example.

```python
def app_home_handler(request):
    req = request_to_shopify_req(request)

    result = shopify.verify_app_home_req(req)
    if not result.ok:
        return shopify_result_to_response(result)

    # Your database logic here
    access_token = get_access_token(shop=result.shop, mode="offline")

    graphql_result = shopify.admin_graphql_request(
        """
        {
            shop {
                id
            }
        }
        """,
        shop=result.shop,
        access_token=access_token,
        api_version="2025-01",
        # Passing `result.new_id_token_response` from the verify function
        # tells `admin_graphql_request` in what context the GraphQL request is being made.
        # This becomes important if the GraphQL request fails and you wish for Shopify to retry the request.
        invalid_token_response=result.new_id_token_response,
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

You will get an `unauthorized` log code if:

1. The app was uninstalled (unrecoverable)
2. Your app requested additional scopes, but the users has not yet approved them and you are making a graphQL operation that requires the additional scopes.
3. Your access token has been revoked

If 1 happens, the merchant needs to manually reinstall the app. If 2 or 3 happens there are different approaches you can take:

| Option                                   | Steps                                                                                                  | Use when                                                                                 |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| 1. Delete & retry (shown above)          | Delete token → return retry response                                                                   | Request is idempotent. OK for Shopify to auto-retry                                      |
| 2. Exchange & update with retry fallback | Token exchange → update token → retry GraphQL → (on fail) delete token → return retry response         | Request is not idempotent. You can revert prior operations. OK for Shopify to auto-retry |
| 3. Exchange with no fallback             | Token exchange → update token → retry GraphQL → (on fail) delete token → return non-retry 401 response | Request is not idempotent. It is not OK for Shopify to auto-retry                        |

#### In a background job

When making GraphQL requests in a background job (e.g., processing a webhook, scheduled task) pass `None` for `invalid_token_response`. if the access token is invalid, the request will simply fail.

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

### Verifying requests without exchangeable id tokens

The following requests do not provide the required information for token exchange:

- Webhooks
- App Proxy
- Customer Account UI Extension
- Checkout UI Extension

Webhook and App Proxy requests do not provide an id token. Customer Account and Checkout UI Extensions provide an id token, but it is not exchangeable. None of these requests provide a merchant user ID.

If you require access to the Shopify Admin GraphQL API during these requests you must load an offline access token that was exchanged from an App Home, Admin UI or POS UI Extension request.

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

If the customer is not logged in, the `logged_in_customer_id` will be `None`. Do not confuse this with a `user_id` stored with an online token which are merchant IDs, not customer IDs.

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

### Getting access tokens with Client Credentials

[Client credentials exchange](https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens/client-credentials-grant) allows you to obtain an access token using only your app's client ID and client secret, without requiring an ID token. This is designed for trusted, server-to-server integrations (for example, internal automation or back-office services).

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

| Attribute | Description                                         |
| --------- | --------------------------------------------------- |
| `shop`    | The shop domain                                     |
| `token`   | The access token string                             |
| `scope`   | The granted scopes                                  |
| `expires` | ISO 8601 datetime when the token expires (24 hours) |

Note: Client credentials tokens expire after 24 hours and do not include a refresh token. When the token expires, request a new one using `exchange_using_client_credentials` with the same credentials.

## Contributing, issues, feedback and feature requests

This package does not accept contributions, but we'd love to hear your feedback.

To report a bug, request a feature, or share feedback, post in the [Shopify dev community forums](https://community.shopify.dev/c/shopify-cli-libraries/14). Please don’t open pull requests or GitHub issues here; They will be closed automatically.

We triage and discuss work in the forums. Please see [CONTRIBUTING.md](https://github.com/Shopify/shopify-app-python?tab=contributing-ov-file) for details.

## Created a template?

We've confirmed that AI can scaffold an app using this README. If you create an app template and you'd like to open source it, we'd love to hear from you. Perhaps it can benefit other Python developers.
