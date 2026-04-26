from __future__ import annotations

import os
from typing import BinaryIO

from pypdfbox.cos import COSDocument
from pypdfbox.io import (
    RandomAccessRead,
    RandomAccessReadBuffer,
    RandomAccessReadBufferedFile,
)
from pypdfbox.pdfparser import PDFParseError, PDFParser

# Type alias for everything Loader.load_pdf accepts. Mirrors the overloads
# of org.apache.pdfbox.Loader.loadPDF (file, byte[], RandomAccessRead,
# InputStream).
PDFSource = (
    str
    | os.PathLike[str]
    | bytes
    | bytearray
    | memoryview
    | BinaryIO
    | RandomAccessRead
)


class Loader:
    """
    Top-level entry point for parsing a PDF — mirrors
    ``org.apache.pdfbox.Loader``.

    The PDFBox class exposes many overloads (paths, bytes, streams,
    ``RandomAccessRead``, plus password / ``MemoryUsageSetting`` knobs).
    This first port covers the four source forms; encryption and memory
    tuning will be added once the corresponding subsystems land.

    Lifecycle: when ``load_pdf`` is given a path, byte buffer, or stream,
    the Loader constructs the underlying ``RandomAccessRead`` itself and
    hands it to the resulting ``COSDocument`` as an owned resource —
    ``doc.close()`` then closes it. When the caller passes a
    ``RandomAccessRead`` directly, ownership stays with the caller.
    """

    @staticmethod
    def load_pdf(source: PDFSource, /) -> COSDocument:
        """Parse a PDF from one of the supported sources and return the
        populated ``COSDocument``."""
        access, owned = Loader._coerce_source(source)
        parser = PDFParser(access)
        try:
            document = parser.parse()
        except PDFParseError as e:
            if owned:
                access.close()
            # Mirror upstream Loader.loadPDF: malformed input surfaces as
            # an IOException-equivalent (OSError) at the Loader boundary.
            raise OSError(str(e)) from e
        except BaseException:
            if owned:
                access.close()
            raise
        if owned:
            # Hand ownership to the document so doc.close() releases it.
            document._source = access  # noqa: SLF001 — sibling-package handoff
        return document

    @staticmethod
    def _coerce_source(source: PDFSource) -> tuple[RandomAccessRead, bool]:
        """Return ``(random_access_read, loader_owns_it)``."""
        # Order matters: RandomAccessRead is checked first so a custom
        # subclass that also happens to expose ``.read`` doesn't get
        # routed through the BinaryIO branch.
        if isinstance(source, RandomAccessRead):
            return source, False
        if isinstance(source, (str, os.PathLike)):
            return RandomAccessReadBufferedFile(source), True
        if isinstance(source, (bytes, bytearray, memoryview)):
            return RandomAccessReadBuffer(source), True
        if hasattr(source, "read"):
            return RandomAccessReadBuffer(source), True
        raise TypeError(
            "Loader.load_pdf expected a path, bytes-like object, binary "
            f"stream, or RandomAccessRead; got {type(source).__name__}"
        )
