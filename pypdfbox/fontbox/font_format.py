"""Font file format enumeration.

Mirrors ``org.apache.pdfbox.pdmodel.font.FontFormat`` from PDFBox 3.0.

Three flavours of font program that pypdfbox/PDFBox cares about:

- :attr:`FontFormat.TTF` — TrueType outline font.
- :attr:`FontFormat.OTF` — OpenType (CFF-flavoured) font.
- :attr:`FontFormat.PFB` — Type 1 binary font.

Used by :class:`pypdfbox.fontbox.font_info.FontInfo` to advertise the
on-disk format of a system font without forcing callers to inspect
magic bytes themselves.

Upstream Java is a plain ``enum`` with no methods; we keep parity with
``str`` and ``Enum`` so callers can compare with either ``is`` (identity)
or string equality (``str(FontFormat.TTF) == "FontFormat.TTF"``).
"""

from __future__ import annotations

from enum import Enum


class FontFormat(Enum):
    """Three on-disk font program formats supported by FontProvider.

    Direct port of upstream Java enum; identity is the canonical
    comparison (``info.get_format() is FontFormat.TTF``). The enum
    values themselves are the lowercase format names so ``str`` /
    ``repr`` stay informative without further plumbing.
    """

    TTF = "TTF"
    OTF = "OTF"
    PFB = "PFB"

    def __str__(self) -> str:
        # Match the Java ``Enum.toString()`` output ("TTF" / "OTF" /
        # "PFB") so :meth:`FontInfo.__str__` formats identically to
        # upstream ``FontInfo.toString()``.
        return self.name


__all__ = ["FontFormat"]
