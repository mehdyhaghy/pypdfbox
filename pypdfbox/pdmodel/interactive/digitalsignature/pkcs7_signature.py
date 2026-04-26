from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7

from .signature_interface import SignatureInterface

if TYPE_CHECKING:
    from cryptography import x509
    from cryptography.hazmat.primitives.asymmetric import ec, rsa


class Pkcs7Signature(SignatureInterface):
    """Detached PKCS#7 signer backed by the ``cryptography`` package
    (PyCA → OpenSSL).

    The signer reads the bracketed document bytes from the stream provided by
    :meth:`sign`, hashes them with ``hash_algorithm``, and returns a DER-encoded
    PKCS#7 SignedData blob suitable for splicing into the ``/Contents`` slot
    of a PDF signature dictionary. Mirrors the
    ``adbe.pkcs7.detached`` SubFilter (ISO 32000-1 §12.8.3.3).

    Library-first per :file:`CLAUDE.md`: we wrap PyCA's
    ``PKCS7SignatureBuilder`` instead of reimplementing CMS / ASN.1.
    """

    def __init__(
        self,
        certificate: x509.Certificate,
        private_key: rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey,
        *,
        hash_algorithm: hashes.HashAlgorithm | None = None,
        additional_certificates: list[x509.Certificate] | None = None,
    ) -> None:
        self._certificate = certificate
        self._private_key = private_key
        self._hash_algorithm = hash_algorithm or hashes.SHA256()
        self._additional_certificates = list(additional_certificates or [])

    @property
    def certificate(self) -> x509.Certificate:
        return self._certificate

    def sign(self, content: BinaryIO) -> bytes:
        """Return DER-encoded PKCS#7 detached SignedData over ``content``."""
        data = content.read()
        builder = pkcs7.PKCS7SignatureBuilder().set_data(data)
        builder = builder.add_signer(
            self._certificate, self._private_key, self._hash_algorithm
        )
        for extra in self._additional_certificates:
            builder = builder.add_certificate(extra)
        # ``DetachedSignature`` keeps the document bytes OUT of the SignedData
        # — required for PDF signing per ISO 32000-1 §12.8.3.3 (the digest is
        # over the bracketed bytes, NOT carried inside the signature blob).
        # ``Binary`` suppresses the SMIME-style CRLF rewriting that would
        # otherwise mangle the digest input.
        return builder.sign(
            serialization.Encoding.DER,
            [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary],
        )


__all__ = ["Pkcs7Signature"]
