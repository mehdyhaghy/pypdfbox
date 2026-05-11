from __future__ import annotations

from collections.abc import Iterable

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .fdf_annotation import ColorTuple, FDFAnnotation, _float_values

_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_VERTICES: COSName = COSName.get_pdf_name("Vertices")
_IC: COSName = COSName.get_pdf_name("IC")


class FDFAnnotationPolygon(FDFAnnotation):
    """FDF Polygon annotation — ``/Subtype /Polygon``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotationPolygon`` (Java
    lines 39-156).
    """

    SUBTYPE: str = "Polygon"

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)
        if annot is None or annot.get_dictionary_object(_SUBTYPE) is None:
            self.set_subtype(self.SUBTYPE)

    def init_vertices(self, vertices: str | None) -> None:
        """Mirrors upstream ``FDFAnnotationPolygon.initVertices(Element)``
        — initialise vertex coordinates from an XFDF ``vertices`` attribute
        of the form ``"x1,y1;x2,y2;..."``."""
        if vertices is None:
            return
        coords: list[float] = []
        for pair in vertices.split(";"):
            pair = pair.strip()
            if not pair:
                continue
            try:
                x_str, y_str = pair.split(",")
                coords.append(float(x_str))
                coords.append(float(y_str))
            except (ValueError, IndexError):
                # malformed pair — skip, mirroring upstream's lenient parse
                continue
        if coords:
            self.set_vertices(coords)

    # ---------- /Vertices ----------

    def set_vertices(self, vertices: Iterable[float] | None) -> None:
        """Set the vertex coordinates (``/Vertices``).

        Mirrors upstream ``setVertices(float[])`` (Java line 112).
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

        Mirrors upstream ``getVertices()`` (Java line 124).
        """
        array = self._annot.get_dictionary_object(_VERTICES)
        if isinstance(array, COSArray):
            return list(array.to_float_array())
        return None

    # ---------- /IC interior colour ----------

    def set_interior_color(self, color: ColorTuple | None) -> None:
        """Set the interior colour (``/IC``).

        Mirrors upstream ``setInteriorColor(Color)`` (Java line 135).
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

        Mirrors upstream ``getInteriorColor()`` (Java line 152).
        """
        v = self._annot.get_dictionary_object(_IC)
        if isinstance(v, COSArray) and len(v) >= 3:
            values = _float_values(v, 3)
            if values is not None:
                return (values[0], values[1], values[2])
        return None


__all__ = ["FDFAnnotationPolygon"]
