from __future__ import annotations

from pypdfbox.cos import COSBase, COSName
from pypdfbox.fontbox.encoding.zapf_dingbats_encoding import _TABLE

from .encoding import Encoding


class ZapfDingbatsEncoding(Encoding):
    """The Zapf Dingbats Encoding.

    Mirrors ``org.apache.pdfbox.pdmodel.font.encoding.ZapfDingbatsEncoding``.
    """

    INSTANCE: ZapfDingbatsEncoding

    def __init__(self) -> None:
        super().__init__()
        for code, name in _TABLE:
            self.add(code, name)

    def get_cos_object(self) -> COSBase:
        # Upstream returns COSName.getPDFName("ZapfDingbatsEncoding").
        return COSName.get_pdf_name("ZapfDingbatsEncoding")

    def get_encoding_name(self) -> str:
        return "ZapfDingbatsEncoding"


ZapfDingbatsEncoding.INSTANCE = ZapfDingbatsEncoding()


__all__ = ["ZapfDingbatsEncoding"]
