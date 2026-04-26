from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSFloat, COSInteger, COSName

from .pd_font import PDFont

_FIRST_CHAR: COSName = COSName.get_pdf_name("FirstChar")
_LAST_CHAR: COSName = COSName.get_pdf_name("LastChar")
_WIDTHS: COSName = COSName.get_pdf_name("Widths")
_ENCODING: COSName = COSName.get_pdf_name("Encoding")


class PDSimpleFont(PDFont):
    """Abstract intermediate base for Type1 / TrueType / Type3 fonts.

    Mirrors PDFBox ``PDSimpleFont``. Adds ``/FirstChar``, ``/LastChar``,
    ``/Widths``, and ``/Encoding`` accessors. Encoding is returned as the
    raw ``COSBase`` for now — a typed ``Encoding`` wrapper is deferred.
    """

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)

    # ---------- char-range / widths ----------

    def get_first_char(self) -> int:
        return self._dict.get_int(_FIRST_CHAR, -1)

    def get_last_char(self) -> int:
        return self._dict.get_int(_LAST_CHAR, -1)

    def get_widths(self) -> list[float]:
        arr = self._dict.get_dictionary_object(_WIDTHS)
        if not isinstance(arr, COSArray):
            return []
        widths: list[float] = []
        for item in arr:
            if isinstance(item, (COSInteger, COSFloat)):
                widths.append(float(item.value))
        return widths

    # ---------- encoding (raw — typed Encoding deferred) ----------

    def get_encoding(self) -> COSBase | None:
        return self._dict.get_dictionary_object(_ENCODING)


__all__ = ["PDSimpleFont"]
