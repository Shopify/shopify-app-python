"""
Shopify Client Assertions

Create one signed JWT for client authentication on the ``client_credentials``
grant. This is a standalone helper: it needs no ``ShopifyApp`` instance, no
client secret, no ID token and no network access.

Asymmetric signing support is optional, so this module is never imported from
the package root. Import it explicitly and install the extra that provides the
signing support:

.. code-block:: bash

    pip install "shopifyapp[assertions]"

.. code-block:: python

    from shopify_app.assertions import create_client_assertion

    assertion = create_client_assertion(
        shop="shop-name",
        client_id=client_id,
        kid="registered-key-id",
        private_key=private_key,
    )
    result = shopify.exchange_using_client_credentials(
        shop="shop-name", client_assertion=assertion
    )
"""

from __future__ import annotations

import secrets
import time
from typing import TYPE_CHECKING, Dict, Union

import jwt

from .utils.shop import _is_valid_shop_name

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric import ec as _ec
    from cryptography.hazmat.primitives.asymmetric import rsa as _rsa

    NativePrivateSigningKey = Union[_rsa.RSAPrivateKey, _ec.EllipticCurvePrivateKey]
else:
    NativePrivateSigningKey = object

__all__ = [
    "ClientAssertionError",
    "ClientAssertionArgumentError",
    "ClientAssertionSigningError",
    "ClientAssertionSigningUnavailableError",
    "create_client_assertion",
]

DEFAULT_LIFETIME_SECONDS = 60
MAX_LIFETIME_SECONDS = 300

_MINIMUM_RSA_KEY_SIZE = 2048
_P256_CURVE_NAMES = frozenset({"secp256r1", "prime256v1", "p-256"})
_AUDIENCE_TEMPLATE = "https://{shop}.myshopify.com/admin/oauth/access_token"
_JTI_BYTES = 32
_SIGNING_EXTRA_MESSAGE = (
    "Asymmetric signing support is not installed. "
    'Install the optional signing support with: pip install "shopifyapp[assertions]"'
)


class ClientAssertionError(Exception):
    """Base class for this package's own client-assertion failures.

    Python raises TypeError for an unsupported or missing keyword argument,
    which is outside this hierarchy.
    """


class ClientAssertionArgumentError(ClientAssertionError, ValueError):
    """An input value is not valid for signing."""


class ClientAssertionSigningError(ClientAssertionError, RuntimeError):
    """The signing library could not perform the selected operation."""


class ClientAssertionSigningUnavailableError(ClientAssertionError, RuntimeError):
    """The optional asymmetric signing support is not installed or enabled."""


def create_client_assertion(
    *,
    shop: str,
    client_id: str,
    kid: str,
    private_key: "NativePrivateSigningKey",
    lifetime_seconds: int = DEFAULT_LIFETIME_SECONDS,
) -> str:
    """Create one signed client assertion for the client-credentials grant.

    Args:
        shop (str): The shop name before ``.myshopify.com`` (e.g., "shop-name").
        client_id (str): The app client ID. Used unchanged as ``iss`` and ``sub``.
        kid (str): The identifier registered for the public key.
        private_key: An already-loaded RSA (2048 bits or more) or EC P-256
            private key object. Serialized keys, JWKs, passphrases, shared
            secrets, public keys and signer callbacks are rejected.
        lifetime_seconds (int): Assertion lifetime in seconds. Default 60,
            minimum 1, maximum 300.

    Returns:
        str: The compact JWT to pass as ``client_assertion`` to one
        client-credentials exchange call.

    Raises:
        ClientAssertionArgumentError: An input or key is not valid.
        ClientAssertionSigningUnavailableError: Signing support is unavailable.
        ClientAssertionSigningError: The signing library failed.
        TypeError: An unsupported or missing keyword argument, raised by
            Python's argument binding before this function runs.
    """
    if not _is_valid_shop_name(shop):
        raise ClientAssertionArgumentError(
            "Expected shop to be a valid shop name (e.g., 'shop-name')"
        )

    validated_client_id = _validated_identity(client_id, "clientId")
    validated_kid = _validated_identity(kid, "kid")
    lifetime = _validated_lifetime_seconds(lifetime_seconds)
    algorithm = _algorithm_for_key(private_key)

    issued_at = int(time.time())
    claims: Dict[str, Union[str, int]] = {
        "iss": validated_client_id,
        "sub": validated_client_id,
        "aud": _AUDIENCE_TEMPLATE.format(shop=shop.lower()),
        "iat": issued_at,
        "exp": issued_at + lifetime,
        "jti": secrets.token_urlsafe(_JTI_BYTES),
    }

    try:
        return jwt.encode(
            claims,
            private_key,
            algorithm=algorithm,
            headers={"kid": validated_kid, "typ": "JWT"},
        )
    except Exception:
        # Chained exceptions also appear in ordinary traceback logging.
        raise ClientAssertionSigningError(
            "Failed to sign the client assertion with the supplied private key"
        ) from None


def _validated_identity(value: str, name: str) -> str:
    """Return a non-blank string value unchanged, or raise."""
    if not isinstance(value, str) or not value.strip():
        raise ClientAssertionArgumentError(
            "Expected {name} to be a non-empty string".format(name=name)
        )
    return value


def _validated_lifetime_seconds(value: object) -> int:
    """Return the validated lifetime in seconds, without coercing other types."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ClientAssertionArgumentError(
            "Expected lifetimeSeconds to be an integer from 1 to 300"
        )
    if value < 1 or value > MAX_LIFETIME_SECONDS:
        raise ClientAssertionArgumentError(
            "Expected lifetimeSeconds to be an integer from 1 to 300"
        )
    return value


def _algorithm_for_key(private_key: object) -> str:
    """Select the algorithm after validating the native private key."""
    try:
        from cryptography.hazmat.primitives.asymmetric import ec, rsa
    except ImportError:
        raise ClientAssertionSigningUnavailableError(_SIGNING_EXTRA_MESSAGE) from None

    if isinstance(private_key, rsa.RSAPrivateKey):
        if private_key.key_size < _MINIMUM_RSA_KEY_SIZE:
            raise ClientAssertionArgumentError(
                "Expected privateKey to be an RSA private key of at least " "2048 bits"
            )
        return "RS256"

    if isinstance(private_key, ec.EllipticCurvePrivateKey):
        if not (
            isinstance(private_key.curve, ec.SECP256R1)
            or private_key.curve.name.lower() in _P256_CURVE_NAMES
        ):
            raise ClientAssertionArgumentError(
                "Expected privateKey to be an EC private key on the P-256 curve"
            )
        return "ES256"

    raise ClientAssertionArgumentError(
        "Expected privateKey to be a native RSA or EC P-256 private key object"
    )
