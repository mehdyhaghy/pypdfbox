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

from typing import BinaryIO

from .filter_factory import FilterFactory
from .lzw_decode import (
    CLEAR_TABLE,
    EOD,
    MAX_TABLE_SIZE,
    LZWDecode,
    _initial_code_table,
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

    @staticmethod
    def create_initial_code_table() -> list[bytes | None]:
        """Build a fresh code table seeded with the 256 single-byte
        literals plus placeholders for ``CLEAR_TABLE`` (256) and ``EOD``
        (257).

        Mirrors ``org.apache.pdfbox.filter.LZWFilter#createInitialCodeTable``
        (a ``private static`` upstream helper used to seed the cached
        ``INITIAL_CODE_TABLE`` field). Promoted to a public static so
        porters translating Java tests for the LZW codec can call it
        directly.
        """
        return _initial_code_table()

    @staticmethod
    def do_lzw_decode(
        encoded: BinaryIO, decoded: BinaryIO, early_change: bool
    ) -> None:
        """Decode an LZW-encoded byte stream into ``decoded``.

        Mirrors ``org.apache.pdfbox.filter.LZWFilter#doLZWDecode`` (a
        ``private static`` upstream helper). Promoted to a public static
        on :class:`LZWFilter` so callers can invoke the raw codec without
        going through :meth:`decode`'s decode-params plumbing.
        """
        LZWDecode._do_lzw_decode(encoded, decoded, early_change)


# Register the upstream-named subclass alongside the existing
# ``LZWDecode`` registration so ``FilterFactory.get("LZWFilter")``
# also resolves. The PDF ``/Filter`` name (``LZWDecode``) and its
# abbreviation (``LZW``) keep pointing at the original ``LZWDecode``
# instance — that registration is owned by ``lzw_decode.py``.
FilterFactory.register("LZWFilter", LZWFilter())
