from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger


class PDVertices:
    """Typed wrapper around the ``/Vertices`` flat float array of a
    ``/Subtype /Polygon`` or ``/Subtype /PolyLine`` annotation
    (PDF 32000-1:2008 §12.5.6.9).

    The wire format mirrors ``PDPathInfo``: a single ``COSArray`` of
    alternating ``x, y`` floats describing the polygon/polyline vertices.
    """

    def __init__(self, array: COSArray | None = None) -> None:
        self._array: COSArray = array if array is not None else COSArray()

    def get_cos_array(self) -> COSArray:
        return self._array

    def get_cos_object(self) -> COSArray:
        """Alias for :meth:`get_cos_array` matching the COSObjectable
        convention used by sibling annotation helpers."""
        return self._array

    def get_points(self) -> list[tuple[float, float]]:
        flat = self._array.to_float_array()
        n = (len(flat) // 2) * 2
        return [(flat[i], flat[i + 1]) for i in range(0, n, 2)]

    def set_points(self, points: list[tuple[float, float]]) -> None:
        new = COSArray()
        for x, y in points:
            new.add(COSFloat(float(x)))
            new.add(COSFloat(float(y)))
        self._array.clear()
        for i in range(new.size()):
            entry = new.get(i)
            assert isinstance(entry, (COSFloat, COSInteger))
            self._array.add(entry)

    def point_count(self) -> int:
        return self._array.size() // 2


__all__ = ["PDVertices"]
