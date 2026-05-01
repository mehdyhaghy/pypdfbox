"""Public-key protection policy.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.PublicKeyProtectionPolicy``.
Carries the recipient list (each X.509 cert + its :class:`AccessPermission`)
that ``PublicKeySecurityHandler`` consumes when wrapping a document.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from .protection_policy import ProtectionPolicy

if TYPE_CHECKING:
    from cryptography.x509 import Certificate

    from .public_key_recipient import PublicKeyRecipient


class PublicKeyProtectionPolicy(ProtectionPolicy):
    """Lite port — recipient bookkeeping only.

    Encrypt-side wiring (key derivation + CMS envelope construction) is
    deferred. ``PublicKeySecurityHandler.prepare_document`` raises
    ``NotImplementedError`` until that arrives.
    """

    def __init__(self) -> None:
        super().__init__()
        self._recipients: list[PublicKeyRecipient] = []
        self._decryption_certificate: Certificate | None = None

    # ---------- recipient list ----------

    def add_recipient(self, recipient: PublicKeyRecipient) -> None:
        self._recipients.append(recipient)

    def remove_recipient(self, recipient: PublicKeyRecipient) -> bool:
        try:
            self._recipients.remove(recipient)
        except ValueError:
            return False
        return True

    def get_recipients(self) -> list[PublicKeyRecipient]:
        # Mirrors ``getRecipientsIterator`` — return the live list so callers
        # can iterate. Defensive copy avoided to match upstream semantics.
        return self._recipients

    def get_recipients_iterator(self) -> Iterator[PublicKeyRecipient]:
        """Mirror upstream ``getRecipientsIterator`` — return an iterator
        over the live recipient list. Java callers commonly walk the list
        through this rather than the underlying collection."""
        return iter(self._recipients)

    def get_number_of_recipients(self) -> int:
        return len(self._recipients)

    # ---------- decryption cert (optional) ----------

    def get_decryption_certificate(self) -> Certificate | None:
        return self._decryption_certificate

    def set_decryption_certificate(self, cert: Certificate | None) -> None:
        self._decryption_certificate = cert


__all__ = ["PublicKeyProtectionPolicy"]
