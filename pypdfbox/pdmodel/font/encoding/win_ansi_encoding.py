from __future__ import annotations

from pypdfbox.cos import COSBase, COSName
from pypdfbox.fontbox.encoding.win_ansi_encoding import _TABLE

from .encoding import Encoding


class WinAnsiEncoding(Encoding):
    """The Windows ANSI Encoding (CP1252 superset).

    Mirrors ``org.apache.pdfbox.pdmodel.font.encoding.WinAnsiEncoding``. Per
    the PDF spec, all unused codes greater than 040 (octal) map to the
    ``bullet`` glyph — this fill-in is applied after the explicit table.
    """

    INSTANCE: "WinAnsiEncoding"

    def __init__(self) -> None:
        super().__init__()
        for code, name in _TABLE:
            self.add(code, name)
        for i in range(0o41, 256):
            if i not in self._code_to_name:
                self.add(i, "bullet")

    def get_cos_object(self) -> COSBase:
        # Upstream returns COSName.WIN_ANSI_ENCODING directly. The base-class
        # implementation arrives at the same interned COSName via the encoding
        # name, but mirroring the override keeps the surface explicit.
        return COSName.get_pdf_name("WinAnsiEncoding")

    def get_encoding_name(self) -> str:
        return "WinAnsiEncoding"


WinAnsiEncoding.INSTANCE = WinAnsiEncoding()


__all__ = ["WinAnsiEncoding"]
