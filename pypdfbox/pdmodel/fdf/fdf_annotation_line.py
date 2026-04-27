from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .fdf_annotation import FDFAnnotation

_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_L: COSName = COSName.get_pdf_name("L")
_LE: COSName = COSName.get_pdf_name("LE")
_IC: COSName = COSName.get_pdf_name("IC")
_LL: COSName = COSName.get_pdf_name("LL")
_LLE: COSName = COSName.get_pdf_name("LLE")
_LLO: COSName = COSName.get_pdf_name("LLO")
_CAP: COSName = COSName.get_pdf_name("Cap")
_IT: COSName = COSName.get_pdf_name("IT")
_CP: COSName = COSName.get_pdf_name("CP")
_CO: COSName = COSName.get_pdf_name("CO")


class FDFAnnotationLine(FDFAnnotation):
    """FDF line annotation — ``/Subtype /Line``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotationLine``.
    """

    SUBTYPE: str = "Line"

    # /LE line-ending style constants (PDF 32000-1 §12.5.6.7 Table 176)
    LE_NONE: str = "None"
    LE_SQUARE: str = "Square"
    LE_CIRCLE: str = "Circle"
    LE_DIAMOND: str = "Diamond"
    LE_OPEN_ARROW: str = "OpenArrow"
    LE_CLOSED_ARROW: str = "ClosedArrow"
    LE_BUTT: str = "Butt"
    LE_R_OPEN_ARROW: str = "ROpenArrow"
    LE_R_CLOSED_ARROW: str = "RClosedArrow"
    LE_SLASH: str = "Slash"

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)
        if annot is None or annot.get_dictionary_object(_SUBTYPE) is None:
            self.set_subtype(self.SUBTYPE)

    # ---------- /L start/end point pair ----------

    def _get_l_array(self) -> COSArray | None:
        v = self._annot.get_dictionary_object(_L)
        if isinstance(v, COSArray):
            return v
        return None

    def _ensure_l_array(self) -> COSArray:
        arr = self._get_l_array()
        if arr is None:
            arr = COSArray(
                [COSFloat(0.0), COSFloat(0.0), COSFloat(0.0), COSFloat(0.0)]
            )
            self._annot.set_item(_L, arr)
        while arr.size() < 4:
            arr.add(COSFloat(0.0))
        return arr

    def get_start_point(self) -> tuple[float, float] | None:
        arr = self._get_l_array()
        if arr is not None and arr.size() >= 4:
            return (_as_float(arr.get(0)), _as_float(arr.get(1)))
        return None

    def set_start_point(self, x: float, y: float) -> None:
        arr = self._ensure_l_array()
        arr.set(0, COSFloat(float(x)))
        arr.set(1, COSFloat(float(y)))

    def get_end_point(self) -> tuple[float, float] | None:
        arr = self._get_l_array()
        if arr is not None and arr.size() >= 4:
            return (_as_float(arr.get(2)), _as_float(arr.get(3)))
        return None

    def set_end_point(self, x: float, y: float) -> None:
        arr = self._ensure_l_array()
        arr.set(2, COSFloat(float(x)))
        arr.set(3, COSFloat(float(y)))

    # ---------- /LE line-ending styles ----------

    def _get_le_array(self) -> COSArray | None:
        v = self._annot.get_dictionary_object(_LE)
        if isinstance(v, COSArray):
            return v
        return None

    def _set_le_entry(self, index: int, style: str) -> None:
        arr = self._get_le_array()
        if arr is None:
            arr = COSArray(
                [
                    COSName.get_pdf_name(self.LE_NONE),
                    COSName.get_pdf_name(self.LE_NONE),
                ]
            )
            self._annot.set_item(_LE, arr)
        while arr.size() <= index:
            arr.add(COSName.get_pdf_name(self.LE_NONE))
        arr.set(index, COSName.get_pdf_name(style))

    def get_start_point_ending_style(self) -> str:
        arr = self._get_le_array()
        if arr is not None and arr.size() >= 1:
            entry = arr.get(0)
            if isinstance(entry, COSName):
                return entry.name
        return self.LE_NONE

    def set_start_point_ending_style(self, style: str) -> None:
        self._set_le_entry(0, style)

    def get_end_point_ending_style(self) -> str:
        arr = self._get_le_array()
        if arr is not None and arr.size() >= 2:
            entry = arr.get(1)
            if isinstance(entry, COSName):
                return entry.name
        return self.LE_NONE

    def set_end_point_ending_style(self, style: str) -> None:
        self._set_le_entry(1, style)

    # ---------- /IC interior colour ----------

    def get_interior_color(self) -> tuple[float, float, float] | None:
        v = self._annot.get_dictionary_object(_IC)
        if isinstance(v, COSArray) and len(v) == 3:
            return (
                _as_float(v[0]),
                _as_float(v[1]),
                _as_float(v[2]),
            )
        return None

    def set_interior_color(self, color: tuple[float, float, float] | None) -> None:
        if color is None:
            self._annot.remove_item(_IC)
            return
        arr = COSArray()
        for v in color:
            arr.add(COSFloat(float(v)))
        self._annot.set_item(_IC, arr)

    # ---------- /LL leader line length ----------

    def get_leader_line(self) -> float:
        return self._annot.get_float(_LL, 0.0)

    def set_leader_line(self, length: float) -> None:
        self._annot.set_float(_LL, float(length))

    # ---------- /LLE leader line extension ----------

    def get_leader_line_extension(self) -> float:
        return self._annot.get_float(_LLE, 0.0)

    def set_leader_line_extension(self, length: float) -> None:
        self._annot.set_float(_LLE, float(length))

    # ---------- /LLO leader line offset ----------

    def get_leader_line_offset(self) -> float:
        return self._annot.get_float(_LLO, 0.0)

    def set_leader_line_offset(self, length: float) -> None:
        self._annot.set_float(_LLO, float(length))

    # ---------- /Cap caption flag ----------

    def get_caption(self) -> bool:
        return self._annot.get_boolean(_CAP, False)

    def set_caption(self, value: bool) -> None:
        self._annot.set_boolean(_CAP, bool(value))

    # ---------- /IT intent (LineArrow / LineDimension) ----------

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

    # ---------- /CP caption position (Inline / Top) ----------

    def get_caption_position(self) -> str | None:
        v = self._annot.get_dictionary_object(_CP)
        if isinstance(v, COSName):
            return v.name
        return None

    def set_caption_position(self, position: str | None) -> None:
        if position is None:
            self._annot.remove_item(_CP)
        else:
            self._annot.set_item(_CP, COSName.get_pdf_name(position))

    # ---------- /CO caption offset (h, v) ----------

    def _get_co_array(self) -> COSArray | None:
        v = self._annot.get_dictionary_object(_CO)
        if isinstance(v, COSArray):
            return v
        return None

    def _set_co_entry(self, index: int, offset: float) -> None:
        arr = self._get_co_array()
        if arr is None:
            arr = COSArray([COSFloat(0.0), COSFloat(0.0)])
            self._annot.set_item(_CO, arr)
        while arr.size() <= index:
            arr.add(COSFloat(0.0))
        arr.set(index, COSFloat(float(offset)))

    def get_caption_horizontal_offset(self) -> float:
        arr = self._get_co_array()
        if arr is not None and arr.size() >= 1:
            return _as_float(arr.get(0))
        return 0.0

    def set_caption_horizontal_offset(self, offset: float) -> None:
        self._set_co_entry(0, offset)

    def get_caption_vertical_offset(self) -> float:
        arr = self._get_co_array()
        if arr is not None and arr.size() >= 2:
            return _as_float(arr.get(1))
        return 0.0

    def set_caption_vertical_offset(self, offset: float) -> None:
        self._set_co_entry(1, offset)


def _as_float(v: object) -> float:
    val = getattr(v, "value", None)
    if isinstance(val, (int, float)):
        return float(val)
    return 0.0


__all__ = ["FDFAnnotationLine"]
