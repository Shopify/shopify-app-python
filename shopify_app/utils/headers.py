"""Header normalization utilities."""

from __future__ import annotations

from typing import Dict


def _normalize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Normalize HTTP headers to lowercase for case-insensitive comparison.

    HTTP headers are case-insensitive per RFC 2616, but different frameworks
    and clients may send them with different casing. This function normalizes
    all header names to lowercase to ensure consistent access.

    Args:
        headers (dict): Dictionary of HTTP headers

    Returns:
        dict: Dictionary with lowercase header names
    """
    return {k.lower(): v for k, v in headers.items()}
