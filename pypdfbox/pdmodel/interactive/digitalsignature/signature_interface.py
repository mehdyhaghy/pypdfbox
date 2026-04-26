from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO


class SignatureInterface(ABC):
    """Callback contract for producing a detached PKCS#7 signature over the
    document bytes bracketed by ``/ByteRange``. Mirrors PDFBox's
    ``org.apache.pdfbox.pdmodel.interactive.digitalsignature.SignatureInterface``.

    The single :meth:`sign` callback receives a binary stream over the bytes
    that must be hashed and returns a PKCS#7 SignedData blob in DER form. The
    blob is what gets hex-encoded and spliced into the ``/Contents`` slot of
    the signature dictionary.

    Concrete implementations:

    - :class:`Pkcs7Signature` — RSA / EC signing via ``cryptography``'s
      ``PKCS7SignatureBuilder``.
    """

    @abstractmethod
    def sign(self, content: BinaryIO) -> bytes:
        """Return the DER-encoded PKCS#7 SignedData blob covering all bytes
        readable from ``content``. The returned bytes are what end up in the
        ``/Contents`` hex string after padding."""


__all__ = ["SignatureInterface"]
