from __future__ import annotations

from collections.abc import Sequence

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSNumber, COSObject

from .fdf_annotation import FDFAnnotation, _float_values

_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_L: COSName = COSName.get_pdf_name("L")
_LE: COSName = COSName.get_pdf_name("LE")
_IC: COSName = COSName.get_pdf_name("IC")
_LL: COSName = COSName.get_pdf_name("LL")
_LLE: COSName = COSName.get_pdf_name("LLE")
_LLO: COSName = COSName.get_pdf_name("LLO")
_CAP: COSName = COSName.get_pdf_name("Cap")
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

    def get_line(self) -> list[float] | None:
        """Return the 4-element ``[x1, y1, x2, y2]`` line coordinate array."""
        arr = self._get_l_array()
        if arr is not None and arr.size() >= 4:
            values = _float_values(arr, 4)
            if values is not None:
                return list(values)
        return None

    def set_line(self, line: Sequence[float]) -> None:
        """Set ``/L`` to ``[x1, y1, x2, y2]`` coordinates."""
        if len(line) != 4:
            raise ValueError(
                f"/L must be a 4-element [x1 y1 x2 y2] array; got {len(line)} elements"
            )
        self._annot.set_item(_L, COSArray([COSFloat(float(c)) for c in line]))

    def get_start_point(self) -> tuple[float, float] | None:
        line = self.get_line()
        if line is not None:
            return (line[0], line[1])
        return None

    def set_start_point(self, x: float, y: float) -> None:
        arr = self._ensure_l_array()
        arr.set(0, COSFloat(float(x)))
        arr.set(1, COSFloat(float(y)))

    def get_end_point(self) -> tuple[float, float] | None:
        line = self.get_line()
        if line is not None:
            return (line[2], line[3])
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
            values = _float_values(v, 3)
            if values is not None:
                return (values[0], values[1], values[2])
        return None

    def has_interior_color(self) -> bool:
        return self.get_interior_color() is not None

    def clear_interior_color(self) -> None:
        self.set_interior_color(None)

    def set_interior_color(self, color: tuple[float, float, float] | None) -> None:
        if color is None:
            self._annot.remove_item(_IC)
            return
        arr = COSArray()
        for v in color:
            arr.add(COSFloat(float(v)))
        self._annot.set_item(_IC, arr)

    # ---------- /LL leader line length ----------

    def get_leader_length(self) -> float:
        """Length of the leader line (``/LL``).

        Mirrors upstream ``getLeaderLength()`` (Java line 289).
        """
        return self._annot.get_float(_LL, 0.0)

    def set_leader_length(self, leader_length: float) -> None:
        """Set the leader line length (``/LL``).

        Mirrors upstream ``setLeaderLength(float)`` (Java line 299).
        """
        self._annot.set_float(_LL, float(leader_length))

    # ---------- /LLE leader line extension ----------

    def get_leader_extend(self) -> float:
        """Length of the leader line extensions (``/LLE``).

        Mirrors upstream ``getLeaderExtend()`` (Java line 309).
        """
        return self._annot.get_float(_LLE, 0.0)

    def set_leader_extend(self, leader_extend: float) -> None:
        """Set the leader line extensions length (``/LLE``).

        Mirrors upstream ``setLeaderExtend(float)`` (Java line 319).
        """
        self._annot.set_float(_LLE, float(leader_extend))

    # ---------- /LLO leader line offset ----------

    def get_leader_offset(self) -> float:
        """Length of the leader line offset (``/LLO``).

        Mirrors upstream ``getLeaderOffset()`` (Java line 329).
        """
        return self._annot.get_float(_LLO, 0.0)

    def set_leader_offset(self, leader_offset: float) -> None:
        """Set the leader line offset length (``/LLO``).

        Mirrors upstream ``setLeaderOffset(float)`` (Java line 339).
        """
        self._annot.set_float(_LLO, float(leader_offset))

    # ---------- /Cap caption flag ----------

    def get_caption(self) -> bool:
        return self._annot.get_boolean(_CAP, False)

    def set_caption(self, value: bool) -> None:
        self._annot.set_boolean(_CAP, bool(value))

    # ---------- /CP caption positioning ("Inline" / "Top") ----------

    def get_caption_style(self) -> str | None:
        """Caption positioning string (``/CP``).

        Mirrors upstream ``getCaptionStyle()`` (Java line 349) which uses
        ``getString``; pypdfbox returns ``None`` for the absent case rather
        than the Java ``null``.
        """
        v = self._annot.get_dictionary_object(_CP)
        if isinstance(v, COSName):
            return v.name
        return self._annot.get_string(_CP)

    def set_caption_style(self, caption_style: str | None) -> None:
        """Set caption positioning (``/CP``). Allowed values: ``Inline``, ``Top``.

        Mirrors upstream ``setCaptionStyle(String)`` (Java line 359). Upstream
        uses ``setString``; pypdfbox writes a ``COSName`` to keep round-trip
        parity with prior pypdfbox releases (PDF readers accept either form).
        ``None`` removes the entry.
        """
        if caption_style is None:
            self._annot.remove_item(_CP)
        else:
            self._annot.set_item(_CP, COSName.get_pdf_name(caption_style))

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
    if isinstance(v, COSObject):
        resolved = v.get_object()
        if resolved is None:
            return 0.0
        v = resolved
    if isinstance(v, COSNumber):
        return v.float_value()
    return 0.0


__all__ = ["FDFAnnotationLine"]
