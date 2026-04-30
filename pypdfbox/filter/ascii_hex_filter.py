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


class ASCIIHexFilter(ASCIIHexDecode):
    """Alias for :class:`ASCIIHexDecode` under the upstream class name.

    Mirrors ``org.apache.pdfbox.filter.ASCIIHexFilter`` (PDFBox 3.0.x).
    Behavior, parameters and registry semantics are identical to
    :class:`ASCIIHexDecode`; this subclass exists purely so the upstream
    Java-style import path resolves.
    """


# Register the upstream-named subclass alongside the existing
# ``ASCIIHexDecode`` registration. The PDF ``/Filter`` name
# (``ASCIIHexDecode``) and its abbreviation (``AHx``) continue to
# resolve to the original ``ASCIIHexDecode`` instance owned by
# ``ascii_hex_decode.py``.
FilterFactory.register("ASCIIHexFilter", ASCIIHexFilter())
