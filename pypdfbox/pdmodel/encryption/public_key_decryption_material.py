"""Decryption material for the public-key security handler.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.PublicKeyDecryptionMaterial``.

The upstream version is keystore-driven (``java.security.KeyStore`` plus an
alias). Python has no direct KeyStore equivalent in stdlib, so this lite port
accepts already-loaded ``cryptography`` objects, or raw bytes (PEM/DER) that
we'll decode lazily via ``cryptography.hazmat.primitives.serialization`` —
matching the spirit of the upstream API while staying idiomatic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

from cryptography.hazmat.primitives import serialization
from cryptography.x509 import Certificate, load_der_x509_certificate, load_pem_x509_certificate

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes

    PrivateKeyLike = Union[PrivateKeyTypes, bytes, bytearray]
    CertificateLike = Union[Certificate, bytes, bytearray]


class PublicKeyDecryptionMaterial:
    """Lite port — holds a recipient certificate + matching private key.

    ``private_key`` may be supplied as a ready ``cryptography`` private-key
    object or as raw PEM/DER bytes; ``get_private_key`` lazily decodes the
    latter using ``password`` when needed.
    """

    def __init__(
        self,
        certificate: CertificateLike | None = None,
        private_key: PrivateKeyLike | None = None,
        password: bytes | None = None,
    ) -> None:
        self._certificate: Certificate | None = None
        self._private_key_raw: PrivateKeyLike | None = None
        self._password: bytes | None = password
        if certificate is not None:
            self.set_certificate(certificate)
        if private_key is not None:
            self.set_private_key(private_key)

    # ---------- certificate ----------

    def get_certificate(self) -> Certificate | None:
        return self._certificate

    def set_certificate(self, cert: CertificateLike) -> None:
        if isinstance(cert, Certificate):
            self._certificate = cert
            return
        if isinstance(cert, (bytes, bytearray)):
            data = bytes(cert)
            # Sniff PEM vs DER — PEM begins with "-----".
            if data.lstrip().startswith(b"-----"):
                self._certificate = load_pem_x509_certificate(data)
            else:
                self._certificate = load_der_x509_certificate(data)
            return
        raise TypeError(
            f"unsupported certificate type {type(cert).__name__}; "
            "expected Certificate or bytes (PEM/DER)"
        )

    # ---------- private key ----------

    def get_private_key(self) -> object | None:
        """Return the loaded private key, decoding lazily if necessary."""
        if self._private_key_raw is None:
            return None
        # Already a cryptography key object — no decoding required.
        if not isinstance(self._private_key_raw, (bytes, bytearray)):
            return self._private_key_raw
        data = bytes(self._private_key_raw)
        if data.lstrip().startswith(b"-----"):
            return serialization.load_pem_private_key(data, password=self._password)
        return serialization.load_der_private_key(data, password=self._password)

    def set_private_key(self, key: PrivateKeyLike) -> None:
        self._private_key_raw = key

    # ---------- password ----------

    def get_password(self) -> bytes | None:
        return self._password

    def set_password(self, password: bytes | None) -> None:
        self._password = password


__all__ = ["PublicKeyDecryptionMaterial"]
