"""Public-key protection policy.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.PublicKeyProtectionPolicy``.
Carries the recipient list (each X.509 cert + its :class:`AccessPermission`)
that ``PublicKeySecurityHandler`` consumes when wrapping a document.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

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

    def addRecipient(self, recipient: PublicKeyRecipient) -> None:  # noqa: N802
        self.add_recipient(recipient)

    def remove_recipient(self, recipient: PublicKeyRecipient) -> bool:
        try:
            self._recipients.remove(recipient)
        except ValueError:
            return False
        return True

    def removeRecipient(self, recipient: PublicKeyRecipient) -> bool:  # noqa: N802
        return self.remove_recipient(recipient)

    def get_recipients(self) -> list[PublicKeyRecipient]:
        # Mirrors ``getRecipientsIterator`` — return the live list so callers
        # can iterate. Defensive copy avoided to match upstream semantics.
        return self._recipients

    def get_recipients_iterator(self) -> Iterator[PublicKeyRecipient]:
        """Mirror upstream ``getRecipientsIterator`` — return an iterator
        over the live recipient list. Java callers commonly walk the list
        through this rather than the underlying collection."""
        return iter(self._recipients)

    def getRecipientsIterator(self) -> Iterator[PublicKeyRecipient]:  # noqa: N802
        return self.get_recipients_iterator()

    def get_number_of_recipients(self) -> int:
        return len(self._recipients)

    def getNumberOfRecipients(self) -> int:  # noqa: N802
        return self.get_number_of_recipients()

    def get_recipients_number(self) -> int:
        """Legacy PDFBox 1.8 spelling kept as a compatibility alias."""
        return self.get_number_of_recipients()

    def getRecipientsNumber(self) -> int:  # noqa: N802
        return self.get_recipients_number()

    # ---------- decryption cert (optional) ----------

    def get_decryption_certificate(self) -> Certificate | None:
        return self._decryption_certificate

    def getDecryptionCertificate(self) -> Certificate | None:  # noqa: N802
        return self.get_decryption_certificate()

    def set_decryption_certificate(self, cert: Certificate | None) -> None:
        self._decryption_certificate = cert

    def setDecryptionCertificate(self, cert: Certificate | None) -> None:  # noqa: N802
        self.set_decryption_certificate(cert)


__all__ = ["PublicKeyProtectionPolicy"]
