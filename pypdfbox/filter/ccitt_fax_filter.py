"""
Upstream-named module mirror for ``org.apache.pdfbox.filter.CCITTFaxFilter``.

The implementation lives in :mod:`pypdfbox.filter.ccitt_fax_decode` and
is registered under the PDF ``/Filter`` name ``CCITTFaxDecode`` (and its
abbreviation ``CCF``). This module exposes the same codec under the
upstream-faithful Java class name :class:`CCITTFaxFilter`, so a direct
port from PDFBox source can write::

    from pypdfbox.filter.ccitt_fax_filter import CCITTFaxFilter

and resolve the symbol without disturbing the existing registry wiring.
"""

from __future__ import annotations

from typing import BinaryIO

from .ccitt_fax_decode import CCITTFaxDecode
from .filter_factory import FilterFactory

__all__ = ["CCITTFaxFilter"]


class CCITTFaxFilter(CCITTFaxDecode):
    """Alias for :class:`CCITTFaxDecode` under the upstream class name.

    Mirrors ``org.apache.pdfbox.filter.CCITTFaxFilter`` (PDFBox 3.0.x).
    Behavior, parameters and registry semantics are identical to
    :class:`CCITTFaxDecode`; this subclass exists purely so the upstream
    Java-style import path resolves.

    Two upstream helpers — package-private ``readFromDecoderStream`` and
    ``private invertBitmap`` — are promoted to public methods/static
    methods so parity tests can exercise them directly, and so any
    future bitmap-invert / fill-read consumers can share the same logic
    as :meth:`CCITTFaxDecode.decode`.
    """

    @staticmethod
    def invert_bitmap(buffer_data: bytearray) -> None:
        """Invert every bit of ``buffer_data`` in place.

        Mirrors ``CCITTFaxFilter.invertBitmap`` (``CCITTFaxFilter.java``
        lines 187-193): each byte is replaced with ``~b & 0xFF``, which
        flips the bitmap polarity between BlackIs0 and BlackIs1. Operates
        on a :class:`bytearray` so the mutation is visible to the
        caller, matching Java's pass-by-reference semantics on
        ``byte[]``.
        """
        for i in range(len(buffer_data)):
            buffer_data[i] = (~buffer_data[i]) & 0xFF

    @staticmethod
    def read_from_decoder_stream(
        decoder_stream: BinaryIO, result: bytearray
    ) -> None:
        """Fill ``result`` from ``decoder_stream`` byte-by-byte.

        Mirrors ``CCITTFaxFilter.readFromDecoderStream`` (``CCITTFaxFilter.java``
        lines 172-185): repeatedly calls ``decoder_stream.read(...)`` until
        the buffer is full or the stream returns end-of-file. Short reads
        are tolerated — the loop simply keeps requesting more bytes — so
        any file-like object exposing a Python ``read(size)`` works
        whether or not it honours the requested size exactly.
        """
        pos = 0
        total = len(result)
        while pos < total:
            chunk = decoder_stream.read(total - pos)
            if not chunk:
                break
            n = len(chunk)
            result[pos : pos + n] = chunk
            pos += n


# Register the upstream-named subclass alongside the existing
# ``CCITTFaxDecode`` registration. The PDF ``/Filter`` name
# (``CCITTFaxDecode``) and its abbreviation (``CCF``) continue to
# resolve to the original ``CCITTFaxDecode`` instance owned by
# ``ccitt_fax_decode.py``.
FilterFactory.register("CCITTFaxFilter", CCITTFaxFilter())
