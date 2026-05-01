"""
Upstream-named module mirror for ``org.apache.pdfbox.filter.DCTFilter``.

The implementation lives in :mod:`pypdfbox.filter.dct_decode` and is
registered under the PDF ``/Filter`` name ``DCTDecode`` (and its
abbreviation ``DCT``). This module exposes the same codec under the
upstream-faithful Java class name :class:`DCTFilter`, so a direct port
from PDFBox source can write::

    from pypdfbox.filter.dct_filter import DCTFilter

and resolve the symbol without disturbing the existing registry wiring.
"""

from __future__ import annotations

from .dct_decode import DCTDecode
from .filter_factory import FilterFactory

__all__ = ["DCTFilter"]


class DCTFilter(DCTDecode):
    """Alias for :class:`DCTDecode` under the upstream class name.

    Mirrors ``org.apache.pdfbox.filter.DCTFilter`` (PDFBox 3.0.x).
    Behavior, parameters and registry semantics are identical to
    :class:`DCTDecode`; this subclass exists purely so the upstream
    Java-style import path resolves.
    """


# Register the upstream-named subclass alongside the existing
# ``DCTDecode`` registration. The PDF ``/Filter`` name (``DCTDecode``)
# and its abbreviation (``DCT``) continue to resolve to the original
# ``DCTDecode`` instance owned by ``dct_decode.py``.
FilterFactory.register("DCTFilter", DCTFilter())
