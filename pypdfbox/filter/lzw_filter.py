"""
Upstream-named module mirror for ``org.apache.pdfbox.filter.LZWFilter``.

PDFBox's class is ``LZWFilter`` (the ``Decode`` suffix appears in the PDF
``/Filter`` name, but Java's class is suffix-less). This module exposes
the same implementation as :mod:`pypdfbox.filter.lzw_decode` under the
upstream-faithful name :class:`LZWFilter`, so callers porting Java code
can write::

    from pypdfbox.filter.lzw_filter import LZWFilter

and have the symbol resolve to the same registered ``Filter`` instance
the rest of the codebase already uses via :class:`LZWDecode`.

The actual implementation lives in :mod:`pypdfbox.filter.lzw_decode`;
this module is a thin alias to avoid duplicating the codec.
"""

from __future__ import annotations

from .filter_factory import FilterFactory
from .lzw_decode import (
    CLEAR_TABLE,
    EOD,
    MAX_TABLE_SIZE,
    LZWDecode,
)

__all__ = [
    "CLEAR_TABLE",
    "EOD",
    "MAX_TABLE_SIZE",
    "LZWFilter",
]


class LZWFilter(LZWDecode):
    """Alias for :class:`LZWDecode` under the upstream-faithful name.

    Mirrors ``org.apache.pdfbox.filter.LZWFilter`` (PDFBox 3.0.x).
    Behavior, parameters and registry semantics are identical to
    :class:`LZWDecode`; this subclass exists purely so the upstream
    Java-style import path resolves.
    """


# Register the upstream-named subclass alongside the existing
# ``LZWDecode`` registration so ``FilterFactory.get("LZWFilter")``
# also resolves. The PDF ``/Filter`` name (``LZWDecode``) and its
# abbreviation (``LZW``) keep pointing at the original ``LZWDecode``
# instance — that registration is owned by ``lzw_decode.py``.
FilterFactory.register("LZWFilter", LZWFilter())
