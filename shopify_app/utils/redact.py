"""HTTP log redaction utilities."""

from __future__ import annotations

import json
import re
from typing import cast

from ..types import RequestInput

_REDACTED = "[REDACTED]"
_SENSITIVE_BODY_FIELDS = {
    "client_secret",
    "subject_token",
    "refresh_token",
    "access_token",
}
# Fields an OAuth token endpoint returns that are reusable credentials. A debug
# log is a lower-trust sink than the app runtime, so these must never reach it.
_SENSITIVE_RESPONSE_BODY_FIELDS = {
    "access_token",
    "refresh_token",
    "client_secret",
}
_SENSITIVE_HEADER_FIELDS = {
    "x-shopify-access-token",
    "authorization",
    "x-shopify-hmac-sha256",
    "shopify-hmac-sha256",
}
_SENSITIVE_URL_PARAMS = {"signature", "id_token", "hmac"}


def _sanitize_url(url: str) -> str:
    """Redact sensitive query parameter values in a URL string."""
    for param in _SENSITIVE_URL_PARAMS:
        url = re.sub(
            r"([?&]" + re.escape(param) + r"=)[^&]*",
            r"\g<1>" + _REDACTED,
            url,
            flags=re.IGNORECASE,
        )
    return url


def redact_http_log(req: RequestInput) -> RequestInput:
    """Redact sensitive values from a req object before including it in HTTP logs.

    Redacts:
    - Request body fields: client_secret, subject_token, refresh_token,
      access_token
    - Request headers: X-Shopify-Access-Token, Authorization (case-insensitive)
    - Request URL params: signature, id_token, hmac (case-insensitive)
    """
    # Work with a plain dict so we can preserve non-conforming runtime values
    # (TypedDict is not enforced at runtime; callers may pass invalid field types)
    result: dict = dict(req)

    if isinstance(result.get("headers"), dict):
        result["headers"] = {
            k: (_REDACTED if k.lower() in _SENSITIVE_HEADER_FIELDS else v)
            for k, v in result["headers"].items()
        }

    if isinstance(result.get("url"), str):
        result["url"] = _sanitize_url(result["url"])

    if isinstance(result.get("body"), str):
        try:
            body_dict = json.loads(result["body"])
            for field in _SENSITIVE_BODY_FIELDS:
                if field in body_dict:
                    body_dict[field] = _REDACTED
            result["body"] = json.dumps(body_dict, separators=(",", ":"))
        except (json.JSONDecodeError, TypeError):
            pass

    return cast(RequestInput, result)


def redact_http_response_body(body: str) -> str:
    """Redact issued OAuth credentials from a response body before logging it.

    A 200 from the OAuth token endpoint carries the ``access_token`` and
    ``refresh_token`` that were just issued. Both are reusable credentials, so
    logging the response verbatim would let anyone with log access replay them.
    Every other field is preserved so the log stays useful for debugging.

    The body is only re-serialized when something was actually redacted, so a
    body that carries no credentials keeps its original formatting.
    """
    if not isinstance(body, str):
        return body

    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return body

    if not isinstance(parsed, dict):
        return body

    modified = False
    for field in _SENSITIVE_RESPONSE_BODY_FIELDS:
        if field in parsed:
            parsed[field] = _REDACTED
            modified = True

    if not modified:
        return body

    return json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
