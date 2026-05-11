"""Singleton helper that exposes the active cryptographic provider.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.SecurityProvider`` (PDFBox 3.x;
Java path ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/SecurityProvider.java``).

Also retains the legacy ``get_security_handler`` / ``register_security_handler``
free-function dispatch shim that pre-dates the upstream-named factory —
:mod:`pypdfbox.pdmodel.encryption.security_handler_factory` exposes the
class-shaped ``SecurityHandlerFactory.INSTANCE`` mirror; this module keeps the
provider singleton plus the legacy filter-name dispatch helpers intact.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .public_key_security_handler import PublicKeySecurityHandler
from .standard_security_handler import StandardSecurityHandler

if TYPE_CHECKING:
    from .security_handler import SecurityHandler


class SecurityProvider:
    """Singleton holding the active cryptographic provider object.

    Upstream this is the BouncyCastle ``Provider`` shim — PDFBox falls
    back to ``new BouncyCastleProvider()`` when none has been registered
    (Java line 48). Python doesn't have the JCA's pluggable Provider
    abstraction; instead this class exposes the same accessor surface
    but the provider is a generic object whose only contract is to be
    settable / gettable. Library-first: callers typically don't need to
    touch this at all because the ``cryptography`` package handles
    provider selection internally.
    """

    _provider: object | None = None

    def __init__(self) -> None:
        # Upstream constructor is private — mirror by raising.
        raise TypeError(
            "SecurityProvider is a singleton — use the classmethods"
        )

    @classmethod
    def get_provider(cls) -> object:
        """Return the provider, lazily defaulting to a marker object.

        Mirrors ``SecurityProvider.getProvider`` (Java line 43).
        """
        if cls._provider is None:
            cls._provider = _DefaultProvider()
        return cls._provider

    @classmethod
    def set_provider(cls, provider: object) -> None:
        """Replace the active provider.

        Mirrors ``SecurityProvider.setProvider`` (Java line 58).
        """
        cls._provider = provider


class _DefaultProvider:
    """Lightweight stand-in for the BouncyCastle provider.

    The Python port relies on the ``cryptography`` package, which selects
    its backend internally, so this object only needs to satisfy the
    "non-null provider" contract. Subclassing exists so callers wanting
    parity with the upstream ``Provider`` interface can identify it.
    """

    name = "pypdfbox-default"


_HANDLERS: dict[str, type[SecurityHandler]] = {
    PublicKeySecurityHandler.FILTER: PublicKeySecurityHandler,
    StandardSecurityHandler.FILTER: StandardSecurityHandler,
}


def get_security_handler(filter_name: str) -> SecurityHandler:
    """Instantiate the security handler registered for ``filter_name``."""
    cls = _HANDLERS.get(filter_name)
    if cls is None:
        raise ValueError(f"Unsupported security handler /Filter: {filter_name!r}")
    return cls()


def register_security_handler(
    filter_name: str, handler_cls: type[SecurityHandler]
) -> None:
    """Register a new security handler — used to plug in public-key handlers."""
    _HANDLERS[filter_name] = handler_cls


def is_registered(filter_name: str) -> bool:
    return filter_name in _HANDLERS


__all__ = [
    "SecurityProvider",
    "get_security_handler",
    "is_registered",
    "register_security_handler",
]
