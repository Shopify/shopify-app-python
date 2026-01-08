"""
Input conversion utilities for handling Union[DataClass, dict] inputs.

These helpers allow SDK functions to accept both dataclass instances and plain dicts,
providing flexibility for consumers while maintaining type safety internally.

Pattern:
- _get_attr(): Extract a single field from dataclass or dict (for specific field access)
- _to_res(): Convert dict or Res to Res dataclass (for passing whole objects through)

Note on typing: _get_attr() returns Any because Python's type system cannot express
"return the type of attribute X on object Y" without complex generics. Callers should
use typing.cast() when they need specific return types, or use isinstance() for type
narrowing before accessing attributes directly.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Optional, TypeVar, Union

from ..types import Res

T = TypeVar("T")


def _get_attr(obj: Any, key: str, default: T = None) -> Union[Any, T]:  # type: ignore[assignment]
    """
    Get a single attribute from a dataclass or dict.

    Use this when you need specific fields from a Union[DataClass, dict] input.
    Note: Returns Any because the return type depends on the attribute accessed.
    Use cast() or isinstance() for type narrowing when needed.

    Args:
        obj: A dataclass instance or dict
        key: The attribute/key name to retrieve
        default: Default value if the key doesn't exist

    Returns:
        The value of the attribute/key, or default if not found

    Example:
        shop = _get_attr(access_token, "shop", "")
        token = _get_attr(id_token, "token", "")
    """
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return getattr(obj, key, default)
    elif isinstance(obj, dict):
        return obj.get(key, default)
    return default


def _to_res(obj: Optional[Union[Res, dict]]) -> Optional[Res]:
    """
    Convert a dict or Res to a Res dataclass.

    Use this when passing a whole response object through unchanged.
    Returns the original if already a Res dataclass (efficient).

    Args:
        obj: A Res dataclass instance, dict, or None

    Returns:
        A Res dataclass instance, or None if input was None

    Example:
        response = _to_res(invalid_token_response) or Res(status=401, body="", headers={})
    """
    if obj is None:
        return None
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return obj
    if isinstance(obj, dict):
        return Res(
            status=obj.get("status", 0),
            body=obj.get("body", ""),
            headers=obj.get("headers", {}),
        )
    return None
