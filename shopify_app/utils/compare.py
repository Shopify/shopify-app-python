"""Constant-time comparison utilities."""

from __future__ import annotations

import hmac


def _constant_time_equals(a: str, b: str) -> bool:
    """
    Compare two strings in constant time.

    Compares the UTF-8 bytes, so values that contain characters that are not
    ASCII return False instead of raising TypeError.

    Args:
        a (str): The first value
        b (str): The second value

    Returns:
        bool: True if the values are equal
    """
    return hmac.compare_digest(
        a.encode("utf-8", "surrogatepass"), b.encode("utf-8", "surrogatepass")
    )
