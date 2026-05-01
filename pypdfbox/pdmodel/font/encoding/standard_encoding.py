from __future__ import annotations

from pypdfbox.cos import COSBase, COSName
from pypdfbox.fontbox.encoding.standard_encoding import _TABLE

from .encoding import Encoding


class StandardEncoding(Encoding):
    """The Adobe Standard Encoding.

    Mirrors ``org.apache.pdfbox.pdmodel.font.encoding.StandardEncoding``. The
    256-entry code -> glyph-name table is sourced from the fontbox tier
    (``pypdfbox.fontbox.encoding.standard_encoding``) rather than duplicated
    here — fontbox is the canonical home of the PostScript encoding vectors.
    """

    INSTANCE: "StandardEncoding"

    def __init__(self) -> None:
        super().__init__()
        for code, name in _TABLE:
            self.add(code, name)

    def get_cos_object(self) -> COSBase:
        # Upstream returns COSName.STANDARD_ENCODING directly.
        return COSName.STANDARD_ENCODING  # type: ignore[attr-defined]

    def get_encoding_name(self) -> str:
        return "StandardEncoding"


StandardEncoding.INSTANCE = StandardEncoding()


__all__ = ["StandardEncoding"]
