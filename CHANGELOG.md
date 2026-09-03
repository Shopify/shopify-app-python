# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.2]

- Harden App Home Redirect URL handling.

## [1.0.1]

- Redact log response for exchange and refresh methods.

## [1.0.0]

- **Breaking:** rename the verify result field `new_id_token_response` to `invalid_token_response`, matching the `exchange_using_token_exchange` and `admin_graphql_request` parameters. Update any code that reads this field:

  ```diff
  - result.new_id_token_response
  + result.invalid_token_response
  ```

## [0.1.4]

- Verify the dest property is not a malicious URL before making a token exchange request
- Reject App Proxy requests with multiple `shop` query parameters with a 401 response.
- Refreshing a non-expiring token now returns a no-refresh-needed result instead of an error
- Checkout UI and Customer Account UI Extension requests now return `shop` without the `https://` prefix
- Update the README for the package

## [0.1.3]

- Add optional `expiring` parameter to `exchange_using_token_exchange`. Defaults to `True`. Pass `False` to request a non-expiring token (no `refresh_token` or `refresh_token_expires`). If `False`, `refresh_token` and `refresh_token_expires` will be `None` in result.

## [0.1.2]

- Redact sensitive information in `log` and `http_logs`

## [0.1.1]

- Update encoding of appHomeRedirectUrl.
- Verify webhooks now accepts multiple header formats.

## [0.1.0]

Initial release
