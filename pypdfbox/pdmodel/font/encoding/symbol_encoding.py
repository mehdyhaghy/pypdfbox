from __future__ import annotations

from pypdfbox.cos import COSBase, COSName
from pypdfbox.fontbox.encoding.symbol_encoding import _TABLE

from .encoding import Encoding


class SymbolEncoding(Encoding):
    """The Adobe Symbol Encoding (greek letters and math symbols).

    Mirrors ``org.apache.pdfbox.pdmodel.font.encoding.SymbolEncoding``.
    """

    INSTANCE: SymbolEncoding

    def __init__(self) -> None:
        super().__init__()
        for code, name in _TABLE:
            self.add(code, name)

    def get_cos_object(self) -> COSBase:
        # Upstream returns COSName.getPDFName("SymbolEncoding").
        return COSName.get_pdf_name("SymbolEncoding")

    def get_encoding_name(self) -> str:
        return "SymbolEncoding"


SymbolEncoding.INSTANCE = SymbolEncoding()


__all__ = ["SymbolEncoding"]
