"""Empty Type1 charset for malformed fonts.

Ported from the private inner class ``EmptyCharsetType1`` of
``org.apache.fontbox.cff.CFFParser`` (lines 1534-1546 of
``CFFParser.java``).

Used when a Type1 font has no usable charset; only ``.notdef`` is
populated.
"""

from __future__ import annotations

from .cff_charset_type1 import CFFCharsetType1


class EmptyCharsetType1(CFFCharsetType1):
    """Minimal Type1 charset that registers only ``.notdef``."""

    def __init__(self) -> None:
        super().__init__()
        # Upstream lines 1536-1539.
        self.add_sid(0, 0, ".notdef")

    def to_string(self) -> str:
        """PDFBox: ``CFFParser.EmptyCharsetType1.toString()``
        (``CFFParser.java`` lines 1541-1545) — returns the class name.

        Java's ``getClass().getName()`` produces a fully qualified name
        (package + class). Python's closest equivalent is the module path
        followed by the class name.
        """
        return f"{type(self).__module__}.{type(self).__name__}"

    def __str__(self) -> str:
        return self.to_string()
