"""
Upstream-named module mirror for ``org.apache.pdfbox.filter.ASCIIHexFilter``.

The implementation lives in :mod:`pypdfbox.filter.ascii_hex_decode` and
is registered under the PDF ``/Filter`` name ``ASCIIHexDecode`` (and its
abbreviation ``AHx``). This module exposes the same codec under the
upstream-faithful Java class name :class:`ASCIIHexFilter`, so a direct
port from PDFBox source can write::

    from pypdfbox.filter.ascii_hex_filter import ASCIIHexFilter

and resolve the symbol without disturbing the existing registry wiring.
"""

from __future__ import annotations

from .ascii_hex_decode import ASCIIHexDecode
from .filter_factory import FilterFactory

__all__ = ["ASCIIHexFilter"]


# Whitespace bytes per PDF spec — the same set ``ASCIIHexFilter.isWhitespace``
# treats as ignorable in the upstream Java source (``ASCIIHexFilter.java``
# lines 114-128). Defined at module scope so :meth:`ASCIIHexFilter.is_whitespace`
# stays a constant-time membership test.
_WHITESPACE_BYTES: frozenset[int] = frozenset({0, 9, 10, 12, 13, 32})

# End-of-data marker byte: the ``>`` character terminates an
# ``/ASCIIHexDecode`` stream (``ASCIIHexFilter.java`` lines 130-133).
_EOD_BYTE: int = ord(">")


class ASCIIHexFilter(ASCIIHexDecode):
    """Alias for :class:`ASCIIHexDecode` under the upstream class name.

    Mirrors ``org.apache.pdfbox.filter.ASCIIHexFilter`` (PDFBox 3.0.x).
    Behavior, parameters and registry semantics are identical to
    :class:`ASCIIHexDecode`; this subclass exists purely so the upstream
    Java-style import path resolves.

    Two upstream private static helpers — ``isWhitespace`` and
    ``isEOD`` — are promoted to public ``staticmethod``s so parity tests
    can exercise them directly, and so other filter code can share the
    same byte classification.
    """

    @staticmethod
    def is_whitespace(c: int) -> bool:
        """Return ``True`` if ``c`` is a PDF whitespace byte.

        Mirrors ``ASCIIHexFilter.isWhitespace`` (``ASCIIHexFilter.java``
        lines 114-128). Accepts an integer byte value in the range
        ``0..255``; values of ``-1`` (Java EOF sentinel) and any other
        out-of-range value return ``False``.
        """
        return c in _WHITESPACE_BYTES

    @staticmethod
    def is_eod(c: int) -> bool:
        """Return ``True`` if ``c`` is the ASCII-hex end-of-data marker.

        Mirrors ``ASCIIHexFilter.isEOD`` (``ASCIIHexFilter.java`` lines
        130-133): the single byte ``>`` (0x3E) terminates the encoded
        stream.
        """
        return c == _EOD_BYTE


# Register the upstream-named subclass alongside the existing
# ``ASCIIHexDecode`` registration. The PDF ``/Filter`` name
# (``ASCIIHexDecode``) and its abbreviation (``AHx``) continue to
# resolve to the original ``ASCIIHexDecode`` instance owned by
# ``ascii_hex_decode.py``.
FilterFactory.register("ASCIIHexFilter", ASCIIHexFilter())
