from __future__ import annotations

import re
from collections.abc import Iterable

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .fdf_annotation import ColorTuple, FDFAnnotation, _float_values

_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_VERTICES: COSName = COSName.get_pdf_name("Vertices")
_IC: COSName = COSName.get_pdf_name("IC")
_LE: COSName = COSName.get_pdf_name("LE")

# Mirrors ``PDAnnotationLine.LE_NONE``.
_LE_NONE: str = "None"


class FDFAnnotationPolyline(FDFAnnotation):
    """FDF Polyline annotation — ``/Subtype /Polyline``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotationPolyline`` (Java
    lines 40-239).
    """

    SUBTYPE: str = "Polyline"

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)
        if annot is None or annot.get_dictionary_object(_SUBTYPE) is None:
            self.set_subtype(self.SUBTYPE)

    # ---------- XFDF-style attribute initialisers ----------

    def init_vertices(self, vertices: str | None) -> None:
        """Initialise /Vertices from an XFDF ``vertices`` attribute string.

        Mirrors upstream ``initVertices(Element)`` (Java line 83). Accepts
        the attribute value directly (comma-or-semicolon separated floats);
        ``None`` / empty raises :class:`OSError` to match upstream's
        ``IOException`` parity.
        """
        if vertices is None or not vertices:
            raise OSError("Error: missing element 'vertices'")
        tokens = [tok for tok in re.split(r"[,;]", vertices) if tok]
        try:
            values = [float(tok) for tok in tokens]
        except ValueError as exc:
            raise OSError("Error: vertices values must be floats") from exc
        self.set_vertices(values)

    def init_styles(
        self,
        head: str | None = None,
        tail: str | None = None,
        interior_color: str | None = None,
    ) -> None:
        """Initialise line-ending styles and interior colour from XFDF
        attributes. Mirrors upstream ``initStyles(Element)`` (Java line 103).

        Each argument corresponds to one of the XFDF attributes: ``head``,
        ``tail``, ``interior-color``. Empty / ``None`` values are skipped
        so callers can forward ``element.getAttribute(...)`` directly.
        """
        if head:
            self.set_start_point_ending_style(head)
        if tail:
            self.set_end_point_ending_style(tail)
        if interior_color and len(interior_color) == 7 and interior_color[0] == "#":
            try:
                color_value = int(interior_color[1:7], 16)
            except ValueError:
                return
            red = ((color_value >> 16) & 0xFF) / 255.0
            green = ((color_value >> 8) & 0xFF) / 255.0
            blue = (color_value & 0xFF) / 255.0
            self.set_interior_color((red, green, blue))

    # ---------- /Vertices ----------

    def set_vertices(self, vertices: Iterable[float] | None) -> None:
        """Set the vertex coordinates (``/Vertices``).

        Mirrors upstream ``setVertices(float[])`` (Java line 129).
        """
        if vertices is None:
            self._annot.remove_item(_VERTICES)
            return
        new_vertices = COSArray()
        for value in vertices:
            new_vertices.add(COSFloat(float(value)))
        self._annot.set_item(_VERTICES, new_vertices)

    def get_vertices(self) -> list[float] | None:
        """Return the vertex coordinates, or ``None`` if absent.

        Mirrors upstream ``getVertices()`` (Java line 141).
        """
        array = self._annot.get_dictionary_object(_VERTICES)
        if isinstance(array, COSArray):
            return list(array.to_float_array())
        return None

    # ---------- /LE line-ending styles ----------

    def set_start_point_ending_style(self, style: str | None) -> None:
        """Set the line-ending style for the start point.

        Mirrors upstream ``setStartPointEndingStyle(String)`` (Java line 152).
        """
        actual_style = style if style is not None else _LE_NONE
        array = self._annot.get_dictionary_object(_LE)
        if not isinstance(array, COSArray):
            new_array = COSArray()
            new_array.add(COSName.get_pdf_name(actual_style))
            new_array.add(COSName.get_pdf_name(_LE_NONE))
            self._annot.set_item(_LE, new_array)
        else:
            array.set_name(0, actual_style)

    def get_start_point_ending_style(self) -> str:
        """Return the line-ending style for the start point.

        Mirrors upstream ``getStartPointEndingStyle()`` (Java line 174).
        """
        array = self._annot.get_dictionary_object(_LE)
        if isinstance(array, COSArray):
            name = array.get_name(0)
            if name is not None:
                return name
        return _LE_NONE

    def set_end_point_ending_style(self, style: str | None) -> None:
        """Set the line-ending style for the end point.

        Mirrors upstream ``setEndPointEndingStyle(String)`` (Java line 185).
        """
        actual_style = style if style is not None else _LE_NONE
        array = self._annot.get_dictionary_object(_LE)
        if not isinstance(array, COSArray):
            new_array = COSArray()
            new_array.add(COSName.get_pdf_name(_LE_NONE))
            new_array.add(COSName.get_pdf_name(actual_style))
            self._annot.set_item(_LE, new_array)
        else:
            array.set_name(1, actual_style)

    def get_end_point_ending_style(self) -> str:
        """Return the line-ending style for the end point.

        Mirrors upstream ``getEndPointEndingStyle()`` (Java line 207).
        """
        array = self._annot.get_dictionary_object(_LE)
        if isinstance(array, COSArray):
            name = array.get_name(1)
            if name is not None:
                return name
        return _LE_NONE

    # ---------- /IC interior colour ----------

    def set_interior_color(self, color: ColorTuple | None) -> None:
        """Set the interior colour of the line endings (``/IC``).

        Mirrors upstream ``setInteriorColor(Color)`` (Java line 218).
        """
        if color is None:
            self._annot.remove_item(_IC)
            return
        arr = COSArray()
        for value in color:
            arr.add(COSFloat(float(value)))
        self._annot.set_item(_IC, arr)

    def get_interior_color(self) -> ColorTuple | None:
        """Return the interior colour (``/IC``) RGB triple or ``None``.

        Mirrors upstream ``getInteriorColor()`` (Java line 235).
        """
        v = self._annot.get_dictionary_object(_IC)
        if isinstance(v, COSArray) and len(v) >= 3:
            values = _float_values(v, 3)
            if values is not None:
                return (values[0], values[1], values[2])
        return None


__all__ = ["FDFAnnotationPolyline"]
