"""Dispatch helper that picks a SecurityHandler subclass from a /Filter name.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.SecurityHandlerFactory`` (lite).
For now only the standard handler is registered; public-key handlers can be
added without changing call sites.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .standard_security_handler import StandardSecurityHandler

if TYPE_CHECKING:
    from .security_handler import SecurityHandler


_HANDLERS: dict[str, type[SecurityHandler]] = {
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


__all__ = ["get_security_handler", "is_registered", "register_security_handler"]
