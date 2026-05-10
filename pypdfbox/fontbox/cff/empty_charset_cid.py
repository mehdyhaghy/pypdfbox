"""Empty CID charset for malformed fonts.

Ported from the private inner class ``EmptyCharsetCID`` of
``org.apache.fontbox.cff.CFFParser`` (lines 1511-1529 of
``CFFParser.java``).

Used when a CID font has no usable charset; Adobe Reader treats CID as
GID in that case (PDFBOX-2571 p11), so we pre-populate identity
mappings up to ``num_char_strings``.
"""

from __future__ import annotations

from .cff_charset_cid import CFFCharsetCID


class EmptyCharsetCID(CFFCharsetCID):
    """Identity CID charset for malformed CID fonts."""

    def __init__(self, num_char_strings: int) -> None:
        super().__init__()
        # Upstream lines 1513-1521.
        self.add_cid(0, 0)  # .notdef
        for i in range(1, num_char_strings + 1):
            self.add_cid(i, i)

    def to_string(self) -> str:
        """PDFBox: ``CFFParser.EmptyCharsetCID.toString()``
        (``CFFParser.java`` lines 1524-1528) — returns the class name.

        Java's ``getClass().getName()`` produces a fully qualified name
        (package + class). Python's closest equivalent is the module path
        followed by the class name — we emit that for diff-clean parity.
        """
        return f"{type(self).__module__}.{type(self).__name__}"

    def __str__(self) -> str:
        return self.to_string()
