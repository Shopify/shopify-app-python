"""JavaScript encoding utilities."""

from __future__ import annotations

import json


def _json_encode_for_js(value: str) -> str:
    """
    JSON encode a string for safe embedding in JavaScript.
    Escapes < and > as unicode escapes to prevent XSS.

    Args:
        value (str): The value to encode

    Returns:
        str: The JSON-encoded string (including surrounding quotes)
    """
    # JSON encode (escapes quotes, backslashes, etc.)
    encoded = json.dumps(value)
    # Replace < and > with unicode escapes to prevent script tag injection
    encoded = encoded.replace("<", "\\u003C").replace(">", "\\u003E")
    return encoded
