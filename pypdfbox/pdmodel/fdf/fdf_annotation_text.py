from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .fdf_annotation import FDFAnnotation

_STATE: COSName = COSName.get_pdf_name("State")
_STATE_MODEL: COSName = COSName.get_pdf_name("StateModel")
_OPEN: COSName = COSName.get_pdf_name("Open")
_NAME: COSName = COSName.get_pdf_name("Name")
_ROTATION: COSName = COSName.get_pdf_name("Rotation")
_INKLIST: COSName = COSName.get_pdf_name("InkList")  # not used by Text but kept for parity
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")


class FDFAnnotationText(FDFAnnotation):
    """FDF text (sticky-note) annotation — ``/Subtype /Text``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotationText``.
    """

    SUBTYPE: str = "Text"

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)
        if annot is None or annot.get_dictionary_object(_SUBTYPE) is None:
            self.set_subtype(self.SUBTYPE)

    # ---------- /Open ----------

    def get_open(self) -> bool:
        return self._annot.get_boolean(_OPEN, False)

    def set_open(self, open_state: bool) -> None:
        self._annot.set_boolean(_OPEN, bool(open_state))

    # ---------- /Name (icon name) ----------

    def get_icon(self) -> str | None:
        v = self._annot.get_dictionary_object(_NAME)
        if isinstance(v, COSName):
            return v.name
        return None

    def set_icon(self, icon: str | None) -> None:
        if icon is None:
            self._annot.remove_item(_NAME)
        else:
            self._annot.set_item(_NAME, COSName.get_pdf_name(icon))

    # ---------- /State ----------

    def get_state(self) -> str | None:
        return self._annot.get_string(_STATE)

    def set_state(self, state: str | None) -> None:
        self._annot.set_string(_STATE, state)

    # ---------- /StateModel ----------

    def get_state_model(self) -> str | None:
        return self._annot.get_string(_STATE_MODEL)

    def set_state_model(self, model: str | None) -> None:
        self._annot.set_string(_STATE_MODEL, model)

    # ---------- /Rotation ----------

    def get_rotation(self) -> int:
        return self._annot.get_int(_ROTATION, 0)

    def set_rotation(self, rotation: int) -> None:
        self._annot.set_int(_ROTATION, int(rotation))


__all__ = ["FDFAnnotationText"]
