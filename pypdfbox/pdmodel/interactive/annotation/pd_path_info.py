from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger


class PDPathInfo:
    """Typed wrapper around a single stroked path — a ``COSArray`` of
    alternating ``x, y`` float coordinates (PDF 32000-1:2008 §12.5.6.13).

    Used as the inner array element of ``/InkList`` (see ``PDInkList``).
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
        """Pair the flat ``[x0, y0, x1, y1, ...]`` floats into ``(x, y)``
        tuples. A trailing odd float is dropped."""
        flat = self._array.to_float_array()
        # Drop a trailing unpaired float defensively.
        n = (len(flat) // 2) * 2
        return [(flat[i], flat[i + 1]) for i in range(0, n, 2)]

    def set_points(self, points: list[tuple[float, float]]) -> None:
        """Replace the wrapped array with ``COSFloat`` entries flattened
        from ``points``."""
        new = COSArray()
        for x, y in points:
            new.add(COSFloat(float(x)))
            new.add(COSFloat(float(y)))
        # Mutate in place so external references to the COSArray remain valid.
        self._array.clear()
        for i in range(new.size()):
            entry = new.get(i)
            assert isinstance(entry, (COSFloat, COSInteger))
            self._array.add(entry)

    def point_count(self) -> int:
        return self._array.size() // 2


__all__ = ["PDPathInfo"]
