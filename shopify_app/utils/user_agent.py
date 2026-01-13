"""User-Agent header utilities."""

from __future__ import annotations

import sys

from .._version import __version__

PACKAGE_NAME = "shopifyapp"


def _get_user_agent() -> str:
    """
    Get the User-Agent string for HTTP requests.

    Format: "{package-name} v{version} | Python {python_version}"
    Example: "shopifyapp v0.1.0 | Python 3.11.0"

    Returns:
        str: The formatted User-Agent string
    """
    python_version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    return f"{PACKAGE_NAME} v{__version__} | Python {python_version}"
