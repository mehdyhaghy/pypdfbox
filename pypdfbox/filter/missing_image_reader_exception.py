from __future__ import annotations


class MissingImageReaderException(OSError):
    """
    Raised when a required image reader (JPEG / JPEG 2000 / CCITT / JBIG2)
    is unavailable for an image-bearing filter.

    Mirrors ``org.apache.pdfbox.filter.MissingImageReaderException``.
    Upstream extends ``IOException``; per CLAUDE.md test-porting table we
    map ``IOException`` to ``OSError`` in pypdfbox.

    The single-argument constructor mirrors upstream verbatim. The
    :class:`PDFStreamEngine` operator-exception triage demotes both
    :class:`MissingImageReaderException` and
    :class:`pypdfbox.pdmodel.MissingResourceException` to a log line so a
    single missing decoder does not abort the whole content stream.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
