"""Visible-signature options bag (page, preferred size, embedded document).

Mirrors ``org.apache.pdfbox.pdmodel.interactive.digitalsignature.SignatureOptions``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/SignatureOptions.java``).
The :class:`SignatureOptions` class bundles the visual-signature
``COSDocument`` together with placement metadata (page index, preferred
size) used by :class:`PDDocument.add_signature`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    from pypdfbox.cos import COSDocument

    from .visible.pd_visible_sig_properties import PDVisibleSigProperties


DEFAULT_SIGNATURE_SIZE = 0x2500


class SignatureOptions:
    """Holds the visual signature, its preferred size, and the page.

    Implements ``Closeable`` semantics via the context-manager protocol
    so callers can use ``with SignatureOptions() as opts: ...``.
    """

    DEFAULT_SIGNATURE_SIZE = DEFAULT_SIGNATURE_SIZE

    def __init__(self) -> None:
        self._visual_signature: COSDocument | None = None
        self._preferred_signature_size: int = 0
        self._page_no: int = 0
        # ``RandomAccessRead`` analog — we hold whatever input source we
        # opened so :meth:`close` can release it. We store a generic
        # closeable (file handle or in-memory buffer) here.
        self._pdf_source: object | None = None

    def set_page(self, page_no: int) -> None:
        """Mirrors ``setPage`` (Java line 59). 0-based page index."""
        self._page_no = page_no

    def get_page(self) -> int:
        """Mirrors ``getPage`` (Java line 69)."""
        return self._page_no

    def set_visual_signature(
        self,
        source: str | Path | BinaryIO | PDVisibleSigProperties,
    ) -> None:
        """Mirrors the three ``setVisualSignature`` overloads (Java lines
        80 / 91 / 111). The Python port collapses them into one method
        that branches on argument type."""
        # The ``PDVisibleSigProperties`` overload forwards to the input-
        # stream form. We detect it ducktype-style to avoid the import-
        # cycle with the ``visible`` subpackage.
        from_props = getattr(source, "get_visible_signature", None)
        if from_props is not None:
            self.set_visual_signature(from_props())
            return
        if isinstance(source, (str, Path)):
            # The handle is intentionally not closed here — :meth:`close`
            # owns the lifecycle (mirrors upstream's ``Closeable`` shape).
            handle = Path(source).open("rb")  # noqa: SIM115
            self._init_from_input(handle)
            return
        # Treat as binary input stream.
        self._init_from_input(source)  # type: ignore[arg-type]

    def init_from_random_access_read(self, source: object) -> None:
        """Mirrors upstream
        ``SignatureOptions.initFromRandomAccessRead(RandomAccessRead)``
        (Java line 107) — parses an existing visual-signature PDF from a
        random-access source. Accepts any object exposing a ``read``
        method, or a ``RandomAccessRead`` exposing ``length()`` + ``read()``.
        """
        if hasattr(source, "length") and hasattr(source, "read"):
            import io as _io

            length = source.length()  # type: ignore[attr-defined]
            data = source.read(length)  # type: ignore[attr-defined]
            self._init_from_input(_io.BytesIO(data))
            return
        if hasattr(source, "read"):
            self._init_from_input(source)  # type: ignore[arg-type]
            return
        raise TypeError(
            "init_from_random_access_read expects a binary stream or a "
            "RandomAccessRead-like object"
        )

    def _init_from_input(self, handle: BinaryIO) -> None:
        # Use the existing PDF parser to read the visual signature
        # document. Import lazily to avoid a cycle at module-load.
        from pypdfbox.pdfparser.pdf_parser import PDFParser

        self._pdf_source = handle
        parser = PDFParser(handle)
        self._visual_signature = parser.parse().get_document()

    def get_visual_signature(self) -> COSDocument | None:
        """Mirrors ``getVisualSignature`` (Java line 121)."""
        return self._visual_signature

    def get_preferred_signature_size(self) -> int:
        """Mirrors ``getPreferredSignatureSize`` (Java line 131)."""
        return self._preferred_signature_size

    def set_preferred_signature_size(self, size: int) -> None:
        """Mirrors ``setPreferredSignatureSize`` (Java line 141).

        Per upstream, only positive values are accepted; non-positive
        sizes are silently ignored to preserve the default.
        """
        if size > 0:
            self._preferred_signature_size = size

    def close(self) -> None:
        """Release the visual signature COSDocument and any underlying
        source. Mirrors ``close`` (Java line 157)."""
        try:
            if self._visual_signature is not None:
                close = getattr(self._visual_signature, "close", None)
                if close is not None:
                    close()
        finally:
            if self._pdf_source is not None:
                close = getattr(self._pdf_source, "close", None)
                if close is not None:
                    close()

    def __enter__(self) -> SignatureOptions:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


__all__ = ["SignatureOptions", "DEFAULT_SIGNATURE_SIZE"]
