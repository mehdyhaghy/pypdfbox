"""Public-key encryption recipient.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.PublicKeyRecipient``. Each
recipient is the pairing of an X.509 certificate with the
:class:`AccessPermission` granted to the holder of its private key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cryptography.x509 import Certificate

    from .access_permission import AccessPermission


class PublicKeyRecipient:
    """Lite port of ``PublicKeyRecipient`` — pure POPO holder."""

    def __init__(
        self,
        certificate: Certificate | None = None,
        permissions: AccessPermission | None = None,
    ) -> None:
        self._x509: Certificate | None = certificate
        self._permission: AccessPermission | None = permissions

    def get_x509(self) -> Certificate | None:
        return self._x509

    def set_x509(self, cert: Certificate | None) -> None:
        self._x509 = cert

    def get_permission(self) -> AccessPermission | None:
        return self._permission

    def set_permission(self, permissions: AccessPermission | None) -> None:
        self._permission = permissions


__all__ = ["PublicKeyRecipient"]
