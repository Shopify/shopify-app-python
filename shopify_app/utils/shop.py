"""Shop name and shop domain validation."""

from __future__ import annotations

import re
from typing import Any

_SHOP_NAME_PATTERN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9\-]*")
_MYSHOPIFY_SUFFIX = ".myshopify.com"


def _is_valid_shop_name(value: Any) -> bool:
    """
    Check that a value is a valid shop name, e.g. "shop-name".

    Args:
        value: The value to check

    Returns:
        bool: True if the full value is a valid shop name
    """
    return isinstance(value, str) and _SHOP_NAME_PATTERN.fullmatch(value) is not None


def _is_valid_shop_domain(value: Any) -> bool:
    """
    Check that a value is a valid shop domain, e.g. "shop-name.myshopify.com".

    Args:
        value: The value to check

    Returns:
        bool: True if the value is a valid shop name followed by ".myshopify.com"
    """
    return (
        isinstance(value, str)
        and value.endswith(_MYSHOPIFY_SUFFIX)
        and _is_valid_shop_name(value[: -len(_MYSHOPIFY_SUFFIX)])
    )
