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
    array per side, in the order: top, right, bottom, left.

    The wrapper lazily materializes the four-slot envelope so callers may
    construct ``PDFourColours()`` and assign sides incrementally.
    """

    _SIDE_TOP: int = 0
    _SIDE_RIGHT: int = 1
    _SIDE_BOTTOM: int = 2
    _SIDE_LEFT: int = 3

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
