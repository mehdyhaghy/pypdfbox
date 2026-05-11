"""External-signing bridge that exposes the COSWriter's data-to-sign + setter.

Mirrors ``org.apache.pdfbox.pdmodel.interactive.digitalsignature.SigningSupport``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/SigningSupport.java``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    from pypdfbox.pdfwriter.cos_writer import COSWriter


class SigningSupport:
    """Bridges a :class:`COSWriter` to an external signer.

    The caller fetches the unsigned content via :meth:`get_content`,
    computes the CMS / PKCS#7 signature externally (e.g. by an HSM), and
    pushes the signature bytes back through :meth:`set_signature`. Per
    upstream the class also implements ``Closeable``; the Python port
    exposes the context-manager protocol so the typical usage is::

        with SigningSupport(writer) as sig:
            sig.set_signature(external_signer.sign(sig.get_content().read()))
    """

    def __init__(self, cos_writer: COSWriter) -> None:
        self._cos_writer: COSWriter | None = cos_writer

    def get_content(self) -> BinaryIO:
        """Return the byte range to be signed.

        Mirrors ``SigningSupport.getContent`` (Java line 40).
        """
        if self._cos_writer is None:
            raise RuntimeError("SigningSupport is closed")
        return self._cos_writer.get_data_to_sign()  # type: ignore[no-any-return]

    def set_signature(self, signature: bytes) -> None:
        """Install the external CMS / PKCS#7 signature bytes.

        Mirrors ``SigningSupport.setSignature`` (Java line 46).
        """
        if self._cos_writer is None:
            raise RuntimeError("SigningSupport is closed")
        self._cos_writer.write_external_signature(signature)

    def close(self) -> None:
        """Drop the COSWriter reference. Mirrors ``close`` (Java line 52)."""
        self._cos_writer = None

    def __enter__(self) -> SigningSupport:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


__all__ = ["SigningSupport"]
