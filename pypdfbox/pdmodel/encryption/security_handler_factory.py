"""Singleton factory that picks a security handler from a /Filter name or policy.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.SecurityHandlerFactory``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption``
``/SecurityHandlerFactory.java``).
The existing ``security_provider.py`` already provides a free-function dispatch
surface; this class wraps that into the upstream-shaped ``INSTANCE`` singleton
plus ``register_handler`` / ``new_security_handler_for_*`` methods so callers
that follow the Java API get the same shape.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .protection_policy import ProtectionPolicy
    from .security_handler import SecurityHandler


class SecurityHandlerFactory:
    """Manages security handlers for the application. Singleton.

    Per upstream the only legal way to obtain an instance is the
    :attr:`INSTANCE` class attribute (mirrors ``SecurityHandlerFactory.INSTANCE``,
    Java line 37).
    """

    INSTANCE: SecurityHandlerFactory

    def __init__(self) -> None:
        self._name_to_handler: dict[str, type[SecurityHandler]] = {}
        self._policy_to_handler: dict[
            type[ProtectionPolicy], type[SecurityHandler]
        ] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        # Imported lazily to avoid a circular import at module load
        # (security_handler_factory → standard_security_handler →
        # security_handler).
        from .public_key_protection_policy import PublicKeyProtectionPolicy
        from .public_key_security_handler import PublicKeySecurityHandler
        from .standard_protection_policy import StandardProtectionPolicy
        from .standard_security_handler import StandardSecurityHandler

        self.register_handler(
            StandardSecurityHandler.FILTER,
            StandardSecurityHandler,
            StandardProtectionPolicy,
        )
        self.register_handler(
            PublicKeySecurityHandler.FILTER,
            PublicKeySecurityHandler,
            PublicKeyProtectionPolicy,
        )

    def register_handler(
        self,
        name: str,
        security_handler: type[SecurityHandler],
        protection_policy: type[ProtectionPolicy],
    ) -> None:
        """Register a security handler.

        Mirrors ``registerHandler`` (Java line 66). Raises if the name is
        already registered (upstream throws ``IllegalStateException``).
        """
        if name in self._name_to_handler:
            raise RuntimeError("The security handler name is already registered")
        self._name_to_handler[name] = security_handler
        self._policy_to_handler[protection_policy] = security_handler

    def new_security_handler(self, key: object) -> SecurityHandler | None:
        """Dispatcher mirroring upstream's ``newSecurityHandler`` overload —
        delegates to :meth:`new_security_handler_for_policy` when ``key`` is
        a :class:`ProtectionPolicy` instance, otherwise to
        :meth:`new_security_handler_for_filter`."""
        if isinstance(key, ProtectionPolicy):
            return self.new_security_handler_for_policy(key)
        return self.new_security_handler_for_filter(key)  # type: ignore[arg-type]

    def new_security_handler_for_policy(
        self, policy: ProtectionPolicy
    ) -> SecurityHandler | None:
        """Build a security handler for the given policy, or ``None``.

        Mirrors ``newSecurityHandlerForPolicy`` (Java line 84).
        """
        handler_cls = self._policy_to_handler.get(type(policy))
        if handler_cls is None:
            return None
        return handler_cls(policy)  # type: ignore[call-arg]

    def new_security_handler_for_filter(
        self, name: str
    ) -> SecurityHandler | None:
        """Build a security handler for the given /Filter name.

        Mirrors ``newSecurityHandlerForFilter`` (Java line 102).
        """
        handler_cls = self._name_to_handler.get(name)
        if handler_cls is None:
            return None
        return handler_cls()


SecurityHandlerFactory.INSTANCE = SecurityHandlerFactory()


__all__ = ["SecurityHandlerFactory"]
