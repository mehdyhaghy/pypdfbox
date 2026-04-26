from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream

_R: COSName = COSName.get_pdf_name("R")
_BC: COSName = COSName.get_pdf_name("BC")
_BG: COSName = COSName.get_pdf_name("BG")
_CA: COSName = COSName.get_pdf_name("CA")
_RC: COSName = COSName.get_pdf_name("RC")
_AC: COSName = COSName.get_pdf_name("AC")
_I: COSName = COSName.get_pdf_name("I")
_RI: COSName = COSName.get_pdf_name("RI")
_IX: COSName = COSName.get_pdf_name("IX")
_TP: COSName = COSName.get_pdf_name("TP")


class PDAppearanceCharacteristicsDictionary:
    """
    Appearance characteristics dictionary (``/MK``) for widget annotations.
    Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceCharacteristicsDictionary``
    (PDF 32000-1:2008 §12.5.6.19, Table 189).

    Lite cluster: ``/BC`` / ``/BG`` are exposed as raw ``COSArray`` (typed
    ``PDColor`` deferred), and ``/I`` / ``/RI`` / ``/IX`` are exposed as raw
    ``COSStream`` (typed ``PDFormXObject`` deferred).
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /R (rotation) ----------

    def get_rotation(self) -> int:
        """Multiple of 90, default 0."""
        return self._dict.get_int(_R, 0)

    def set_rotation(self, rotation: int) -> None:
        self._dict.set_int(_R, rotation)

    # ---------- /BC (border colour, raw COSArray) ----------

    def get_border_colour(self) -> COSArray | None:
        value = self._dict.get_dictionary_object(_BC)
        if isinstance(value, COSArray):
            return value
        return None

    def set_border_colour(self, c: COSArray | None) -> None:
        if c is None:
            self._dict.remove_item(_BC)
            return
        self._dict.set_item(_BC, c)

    # ---------- /BG (background colour, raw COSArray) ----------

    def get_background(self) -> COSArray | None:
        value = self._dict.get_dictionary_object(_BG)
        if isinstance(value, COSArray):
            return value
        return None

    def set_background(self, c: COSArray | None) -> None:
        if c is None:
            self._dict.remove_item(_BG)
            return
        self._dict.set_item(_BG, c)

    # ---------- /CA (normal caption) ----------

    def get_normal_caption(self) -> str | None:
        return self._dict.get_string(_CA)

    def set_normal_caption(self, caption: str | None) -> None:
        self._dict.set_string(_CA, caption)

    # ---------- /RC (rollover caption) ----------

    def get_rollover_caption(self) -> str | None:
        return self._dict.get_string(_RC)

    def set_rollover_caption(self, caption: str | None) -> None:
        self._dict.set_string(_RC, caption)

    # ---------- /AC (alternate caption) ----------

    def get_alternate_caption(self) -> str | None:
        return self._dict.get_string(_AC)

    def set_alternate_caption(self, caption: str | None) -> None:
        self._dict.set_string(_AC, caption)

    # ---------- /I (normal icon, raw COSStream) ----------

    def get_normal_icon(self) -> COSStream | None:
        value = self._dict.get_dictionary_object(_I)
        if isinstance(value, COSStream):
            return value
        return None

    def set_normal_icon(self, stream: COSStream | None) -> None:
        if stream is None:
            self._dict.remove_item(_I)
            return
        self._dict.set_item(_I, stream)

    # ---------- /RI (rollover icon, raw COSStream) ----------

    def get_rollover_icon(self) -> COSStream | None:
        value = self._dict.get_dictionary_object(_RI)
        if isinstance(value, COSStream):
            return value
        return None

    def set_rollover_icon(self, stream: COSStream | None) -> None:
        if stream is None:
            self._dict.remove_item(_RI)
            return
        self._dict.set_item(_RI, stream)

    # ---------- /IX (alternate icon, raw COSStream) ----------

    def get_alternate_icon(self) -> COSStream | None:
        value = self._dict.get_dictionary_object(_IX)
        if isinstance(value, COSStream):
            return value
        return None

    def set_alternate_icon(self, stream: COSStream | None) -> None:
        if stream is None:
            self._dict.remove_item(_IX)
            return
        self._dict.set_item(_IX, stream)

    # ---------- /TP (text position) ----------

    def get_text_position(self) -> int:
        """Caption-vs-icon position code, default 0 (caption only)."""
        return self._dict.get_int(_TP, 0)

    def set_text_position(self, tp: int) -> None:
        self._dict.set_int(_TP, tp)


__all__ = ["PDAppearanceCharacteristicsDictionary"]
