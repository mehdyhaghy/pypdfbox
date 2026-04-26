"""Public-key security handler.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.PublicKeySecurityHandler``.

Lite slice: decrypt-side only. Walks the ``/Recipients`` CMS-enveloped blobs
on an ``/Encrypt`` dictionary, decrypts the first one that matches the
supplied private key (via ``cryptography.hazmat.primitives.serialization``
``pkcs7``), and derives the file-encryption key per PDF 32000-1 §7.6.5.

Encrypt-side wiring (envelope construction + recipient hash computation) is
deferred — :meth:`prepare_document` raises ``NotImplementedError``.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.serialization import pkcs7

from pypdfbox.cos import COSArray, COSString

from .security_handler import SecurityHandler

if TYPE_CHECKING:
    from .pd_encryption import PDEncryption
    from .public_key_decryption_material import PublicKeyDecryptionMaterial


# Per PDF 32000-1 §7.6.5: the seed prefix length for public-key key derivation.
_SEED_LENGTH = 20


class PublicKeySecurityHandler(SecurityHandler):
    """Lite port — decrypt path with a stub encrypt entry point."""

    FILTER: str = "Adobe.PubSec"

    SUBFILTER4: str = "adbe.pkcs7.s4"
    SUBFILTER5: str = "adbe.pkcs7.s5"

    def __init__(self) -> None:
        super().__init__()

    # ------------------------------------------------------------ decrypt

    def prepare_for_decryption(
        self,
        encryption: PDEncryption,
        document_id: bytes,  # noqa: ARG002 — kept for API parity (unused for pubsec)
        decryption_material: object,
    ) -> None:
        """Locate the recipient envelope addressed to ``decryption_material``,
        decrypt it, and derive the file-encryption key.

        The PDF 32000-1 §7.6.5 derivation is:
          1. The CMS envelope decrypts to ``seed (20 bytes) || perms (4 bytes)``.
          2. Concatenate ``seed`` with every recipient blob (in order) and,
             when ``EncryptMetadata`` is false, four 0xFF bytes.
          3. Hash the concatenation — SHA-1 for V=4, SHA-256 for V=5 — and
             truncate to the configured key length in bytes.
        """
        # Local import to avoid a hard cycle at module load.
        from .public_key_decryption_material import PublicKeyDecryptionMaterial  # noqa: PLC0415

        if not isinstance(decryption_material, PublicKeyDecryptionMaterial):
            raise TypeError(
                "prepare_for_decryption expects PublicKeyDecryptionMaterial, "
                f"got {type(decryption_material).__name__}"
            )

        cert = decryption_material.get_certificate()
        private_key = decryption_material.get_private_key()
        if cert is None or private_key is None:
            raise ValueError(
                "PublicKeyDecryptionMaterial is missing a certificate or private key"
            )

        recipients_array = encryption.get_recipients()
        if recipients_array is None or recipients_array.size() == 0:
            raise ValueError("/Recipients array missing or empty on /Encrypt dictionary")

        # Snapshot the recipient blobs in their array order — needed both for
        # the per-recipient decrypt attempt and the eventual hash composition.
        recipient_blobs: list[bytes] = []
        for i in range(recipients_array.size()):
            entry = recipients_array.get_object(i)
            if not isinstance(entry, COSString):
                raise ValueError(
                    f"/Recipients[{i}] is not a COSString (got {type(entry).__name__})"
                )
            recipient_blobs.append(entry.get_bytes())

        envelope_plaintext: bytes | None = None
        for blob in recipient_blobs:
            try:
                envelope_plaintext = pkcs7.pkcs7_decrypt_der(
                    blob, cert, private_key, options=[]
                )
            except Exception:  # noqa: BLE001 — try every recipient before giving up
                continue
            if envelope_plaintext is not None:
                break

        if envelope_plaintext is None:
            raise ValueError(
                "Supplied private key matched none of the /Recipients envelopes"
            )

        if len(envelope_plaintext) < _SEED_LENGTH:
            raise ValueError(
                "Decrypted recipient envelope shorter than the 20-byte seed"
            )
        seed = envelope_plaintext[:_SEED_LENGTH]

        version = encryption.get_v()
        revision = encryption.get_revision()
        key_length_bits = encryption.get_length() or 128
        key_length_bytes = key_length_bits // 8

        # Hash composition — see §7.6.5: seed || every recipient blob in order
        # || (when metadata is *not* encrypted) four 0xFF bytes.
        if version >= 5:
            digest = hashlib.sha256()
        else:
            digest = hashlib.sha1(usedforsecurity=False)
        digest.update(seed)
        for blob in recipient_blobs:
            digest.update(blob)
        if not encryption.is_encrypt_meta_data():
            digest.update(b"\xff\xff\xff\xff")
        encryption_key = digest.digest()[:key_length_bytes]

        self.set_encryption_key(encryption_key)
        self.set_key_length(key_length_bits)
        self.set_version(version)
        self.set_revision(revision)
        # Public-key handler always pairs with a crypt filter; AES is the
        # common case for V>=4 and required for V=5.
        self.set_aes(version >= 4)

    # ------------------------------------------------------------ encrypt

    def prepare_document(self, document: object) -> None:  # noqa: ARG002
        """Encrypt-side wiring — seed generation, CMS envelope construction,
        recipient hash composition — is **deferred**. Track in ``CHANGES.md``
        when implemented."""
        raise NotImplementedError(
            "PublicKeySecurityHandler.prepare_document is not implemented yet — "
            "encrypt path (seed + CMS envelope + /Recipients population) deferred."
        )

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _coerce_recipients(value: object) -> COSArray | None:
        # Defensive accessor — currently unused but mirrors the upstream
        # tolerance for either array form.
        if isinstance(value, COSArray):
            return value
        return None


__all__ = ["PublicKeySecurityHandler"]
