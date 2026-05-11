"""``BytesIO`` subclass that exposes the underlying buffer.

Mirrors the private inner class
``COSWriterObjectStream.DirectAccessByteArrayOutputStream``
(PDFBox 3.0, ``pdfbox/src/main/java/org/apache/pdfbox/pdfwriter/compress/
COSWriterObjectStream.java`` lines 397-409). Upstream hosts it as a nested
class; we expose it as a top-level module for easier reuse.

The point of this subclass is to avoid copying the buffer when sending it
to the next layer — ``get_raw_data`` returns the live underlying bytes.
"""

from __future__ import annotations

from io import BytesIO


class DirectAccessByteArrayOutputStream(BytesIO):
    """``BytesIO`` whose backing buffer is reachable via ``get_raw_data``."""

    def get_raw_data(self) -> bytes:
        """Return the buffered bytes without copying when possible."""
        # ``BytesIO.getvalue()`` returns a new bytes object in CPython, but
        # we expose the same shape for parity. Callers that mutate must use
        # ``getbuffer`` directly.
        return self.getvalue()

    def size(self) -> int:
        """Return the number of bytes currently buffered."""
        return len(self.getvalue())


__all__ = ["DirectAccessByteArrayOutputStream"]
