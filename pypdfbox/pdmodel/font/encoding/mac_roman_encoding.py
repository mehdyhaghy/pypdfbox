from __future__ import annotations

from pypdfbox.cos import COSBase, COSName
from pypdfbox.fontbox.encoding.mac_roman_encoding import _TABLE

from .encoding import Encoding


class MacRomanEncoding(Encoding):
    """The Mac Roman Encoding.

    Mirrors ``org.apache.pdfbox.pdmodel.font.encoding.MacRomanEncoding``.
    """

    INSTANCE: MacRomanEncoding

    def __init__(self) -> None:
        super().__init__()
        for code, name in _TABLE:
            self.add(code, name)
        # PDFBOX-1611: upstream MacRomanEncoding overrides code 0312 (202) to
        # "nbspace" on top of the standard MacRoman table. The base fontbox
        # table maps 202 to "space"-class glyphs only implicitly; this explicit
        # entry makes code 202 resolve to U+00A0 via the glyph list (matters
        # for text extraction / to_unicode of MacRoman-encoded simple fonts).
        self.add(0o312, "nbspace")

    def get_cos_object(self) -> COSBase | None:
        # Upstream returns COSName.MAC_ROMAN_ENCODING directly.
        return COSName.get_pdf_name("MacRomanEncoding")

    def get_encoding_name(self) -> str:
        return "MacRomanEncoding"


MacRomanEncoding.INSTANCE = MacRomanEncoding()


__all__ = ["MacRomanEncoding"]
