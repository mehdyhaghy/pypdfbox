from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger


def _to_rgb_tuple(item: object) -> tuple[float, ...] | None:
    """Read an inner COSArray of numerics as a tuple of floats."""
    if not isinstance(item, COSArray):
        return None
    out: list[float] = []
    for index in range(item.size()):
        value = item.get_object(index)
        if isinstance(value, (COSInteger, COSFloat)):
            out.append(float(value.value))
        else:
            return None
    return tuple(out)


def _rgb_to_array(rgb: tuple[float, ...]) -> COSArray:
    inner = COSArray()
    for component in rgb:
        inner.add(COSFloat(float(component)))
    return inner


class PDFourColours:
    """Typed wrapper for a 4-side color array (e.g. ``/BorderColor``).

    Mirrors PDFBox ``PDFourColours`` (PDF 32000-1:2008 §14.8.5.4). The
    underlying ``COSArray`` holds exactly four entries — one inner color
    array per side. PDF 32000 names the four slots by edge role
    (before / after / start / end), while many callers prefer the
    geometric edge spelling (top / right / bottom / left). Both surface
    sets are exposed and refer to identical underlying slots:

    * index 0 — ``before`` / ``top``
    * index 1 — ``after``  / ``right``
    * index 2 — ``start``  / ``bottom``
    * index 3 — ``end``    / ``left``

    The ``Colour`` (British) spelling on the upstream-parity accessors
    matches Apache PDFBox ``PDFourColours`` exactly.

    The wrapper lazily materializes the four-slot envelope so callers may
    construct ``PDFourColours()`` and assign sides incrementally.
    """

    _SIDE_TOP: int = 0
    _SIDE_RIGHT: int = 1
    _SIDE_BOTTOM: int = 2
    _SIDE_LEFT: int = 3

    # Upstream-parity index aliases (PDF 32000-1 §14.8.5.4 edge order).
    _SIDE_BEFORE: int = 0
    _SIDE_AFTER: int = 1
    _SIDE_START: int = 2
    _SIDE_END: int = 3

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray()
        # Pad the envelope to four slots so set_* on a fresh instance is safe.
        while array.size() < 4:
            array.add(COSArray())
        self._array = array

    # ---------- COS surface ----------

    def get_cos_array(self) -> COSArray:
        return self._array

    def get_cos_object(self) -> COSArray:
        """Upstream-parity alias for :meth:`get_cos_array`."""
        return self._array

    # ---------- per-side accessors ----------

    def _get_side(self, index: int) -> tuple[float, ...] | None:
        item = self._array.get_object(index)
        return _to_rgb_tuple(item)

    def _set_side(self, index: int, rgb: tuple[float, ...]) -> None:
        self._array.set(index, _rgb_to_array(rgb))

    def get_top(self) -> tuple[float, ...] | None:
        return self._get_side(self._SIDE_TOP)

    def set_top(self, rgb: tuple[float, ...]) -> None:
        self._set_side(self._SIDE_TOP, rgb)

    def get_right(self) -> tuple[float, ...] | None:
        return self._get_side(self._SIDE_RIGHT)

    def set_right(self, rgb: tuple[float, ...]) -> None:
        self._set_side(self._SIDE_RIGHT, rgb)

    def get_bottom(self) -> tuple[float, ...] | None:
        return self._get_side(self._SIDE_BOTTOM)

    def set_bottom(self, rgb: tuple[float, ...]) -> None:
        self._set_side(self._SIDE_BOTTOM, rgb)

    def get_left(self) -> tuple[float, ...] | None:
        return self._get_side(self._SIDE_LEFT)

    def set_left(self, rgb: tuple[float, ...]) -> None:
        self._set_side(self._SIDE_LEFT, rgb)

    # ---------- upstream-parity (British-spelled) accessors ----------

    def get_before_colour(self) -> tuple[float, ...] | None:
        return self._get_side(self._SIDE_BEFORE)

    def set_before_colour(self, rgb: tuple[float, ...]) -> None:
        self._set_side(self._SIDE_BEFORE, rgb)

    def get_after_colour(self) -> tuple[float, ...] | None:
        return self._get_side(self._SIDE_AFTER)

    def set_after_colour(self, rgb: tuple[float, ...]) -> None:
        self._set_side(self._SIDE_AFTER, rgb)

    def get_start_colour(self) -> tuple[float, ...] | None:
        return self._get_side(self._SIDE_START)

    def set_start_colour(self, rgb: tuple[float, ...]) -> None:
        self._set_side(self._SIDE_START, rgb)

    def get_end_colour(self) -> tuple[float, ...] | None:
        return self._get_side(self._SIDE_END)

    def set_end_colour(self, rgb: tuple[float, ...]) -> None:
        self._set_side(self._SIDE_END, rgb)

    # ---------- index-based access ----------

    def get_colour_by_index(self, index: int) -> tuple[float, ...] | None:
        """Return the colour at slot ``index`` (0=before, 1=after, 2=start, 3=end)."""
        if not 0 <= index < 4:
            raise IndexError(f"PDFourColours index out of range: {index}")
        return self._get_side(index)

    def set_colour_by_index(self, index: int, rgb: tuple[float, ...]) -> None:
        """Set the colour at slot ``index`` (0=before, 1=after, 2=start, 3=end)."""
        if not 0 <= index < 4:
            raise IndexError(f"PDFourColours index out of range: {index}")
        self._set_side(index, rgb)

    # ---------- helpers ----------

    @staticmethod
    def single_color(rgb: tuple[float, ...]) -> PDFourColours:
        """Build a ``PDFourColours`` whose four sides share one color."""
        instance = PDFourColours()
        instance.set_top(rgb)
        instance.set_right(rgb)
        instance.set_bottom(rgb)
        instance.set_left(rgb)
        return instance


__all__ = ["PDFourColours"]
