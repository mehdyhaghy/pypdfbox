from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .fdf_annotation import FDFAnnotation

_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_DA: COSName = COSName.get_pdf_name("DA")
_Q: COSName = COSName.get_pdf_name("Q")
_DS: COSName = COSName.get_pdf_name("DS")
_CL: COSName = COSName.get_pdf_name("CL")
_IT: COSName = COSName.get_pdf_name("IT")
_ROTATION: COSName = COSName.get_pdf_name("Rotation")
_LE: COSName = COSName.get_pdf_name("LE")
_RC: COSName = COSName.get_pdf_name("RC")


class FDFAnnotationFreeText(FDFAnnotation):
    """FDF free text annotation — ``/Subtype /FreeText``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotationFreeText``.
    """

    SUBTYPE: str = "FreeText"

    # /Q justification constants (PDF 32000-1 §12.7.3.3 Table 230)
    QUADDING_LEFT: int = 0
    QUADDING_CENTERED: int = 1
    QUADDING_RIGHT: int = 2

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)
        if annot is None or annot.get_dictionary_object(_SUBTYPE) is None:
            self.set_subtype(self.SUBTYPE)

    # ---------- /DA default appearance ----------

    def get_default_appearance(self) -> str | None:
        return self._annot.get_string(_DA)

    def set_default_appearance(self, da: str | None) -> None:
        self._annot.set_string(_DA, da)

    # ---------- /Q justification ----------

    def get_justification(self) -> int:
        return self._annot.get_int(_Q, 0)

    def set_justification(self, justification: int) -> None:
        self._annot.set_int(_Q, int(justification))

    # ---------- /DS default style string ----------

    def get_default_style(self) -> str | None:
        return self._annot.get_string(_DS)

    def set_default_style(self, style: str | None) -> None:
        # Forward-style annotation parity: stored as a literal PDF text string.
        self._annot.set_string(_DS, style)

    # ---------- /CL callout line (4- or 6-element float array) ----------

    def get_callout_line(self) -> list[float] | None:
        v = self._annot.get_dictionary_object(_CL)
        if isinstance(v, COSArray):
            return v.to_float_array()
        return None

    def set_callout_line(self, callout: list[float] | None) -> None:
        if callout is None:
            self._annot.remove_item(_CL)
            return
        arr = COSArray([COSFloat(float(c)) for c in callout])
        self._annot.set_item(_CL, arr)

    # ---------- /IT intent ----------

    def get_intent(self) -> str | None:
        v = self._annot.get_dictionary_object(_IT)
        if isinstance(v, COSName):
            return v.name
        return None

    def set_intent(self, intent: str | None) -> None:
        if intent is None:
            self._annot.remove_item(_IT)
        else:
            self._annot.set_item(_IT, COSName.get_pdf_name(intent))

    # ---------- /Rotation ----------

    def get_rotation(self) -> int:
        return self._annot.get_int(_ROTATION, 0)

    def set_rotation(self, rotation: int) -> None:
        self._annot.set_int(_ROTATION, int(rotation))

    # ---------- /LE line-ending style (single name on FreeText callouts) ----------

    def get_line_ending_style(self) -> str | None:
        v = self._annot.get_dictionary_object(_LE)
        if isinstance(v, COSName):
            return v.name
        return None

    def set_line_ending_style(self, style: str | None) -> None:
        if style is None:
            self._annot.remove_item(_LE)
        else:
            self._annot.set_item(_LE, COSName.get_pdf_name(style))

    # ---------- /RC rich contents ----------

    def get_rich_contents(self) -> str | None:
        return self._annot.get_string(_RC)

    def set_rich_contents(self, rc: str | None) -> None:
        self._annot.set_string(_RC, rc)


__all__ = ["FDFAnnotationFreeText"]
