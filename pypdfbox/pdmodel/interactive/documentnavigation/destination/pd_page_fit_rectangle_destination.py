from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSNull

from .pd_page_destination import PDPageDestination


class PDPageFitRectangleDestination(PDPageDestination):
    """Fit rectangle destination. Mirrors PDFBox ``PDPageFitRectangleDestination``.

    Per PDF 32000-1 §12.3.2.2 (Table 151), the array is
    ``[page /FitR left bottom right top]``. Any of the four edge
    coordinates may be ``null`` (or upstream sentinel ``-1``) meaning
    *retain the current viewer value for that coordinate*.
    """

    TYPE = "FitR"

    #: Slot indices for the four rectangle edges.
    _SLOT_LEFT: int = 2
    _SLOT_BOTTOM: int = 3
    _SLOT_RIGHT: int = 4
    _SLOT_TOP: int = 5
    _ARRAY_SIZE: int = _SLOT_TOP + 1

    def __init__(self, array: COSArray | None = None) -> None:
        super().__init__(array)
        if array is None:
            self._array.grow_to_size(self._ARRAY_SIZE, COSNull.NULL)
            self._set_type(self.TYPE)

    def get_left(self) -> float | None:
        return self._get_float(self._SLOT_LEFT)

    def set_left(self, left: float | None) -> None:
        self._set_float(self._SLOT_LEFT, left, self._ARRAY_SIZE)

    def get_bottom(self) -> float | None:
        return self._get_float(self._SLOT_BOTTOM)

    def set_bottom(self, bottom: float | None) -> None:
        self._set_float(self._SLOT_BOTTOM, bottom, self._ARRAY_SIZE)

    def get_right(self) -> float | None:
        return self._get_float(self._SLOT_RIGHT)

    def set_right(self, right: float | None) -> None:
        self._set_float(self._SLOT_RIGHT, right, self._ARRAY_SIZE)

    def get_top(self) -> float | None:
        return self._get_float(self._SLOT_TOP)

    def set_top(self, top: float | None) -> None:
        self._set_float(self._SLOT_TOP, top, self._ARRAY_SIZE)

    # ---------- typed accessors ----------

    def get_rect(self) -> tuple[float | None, float | None, float | None, float | None]:
        """Return the four edge coordinates as ``(left, bottom, right, top)``.

        Each tuple slot is the float value or ``None`` when the slot is
        missing/null in the underlying array. Convenience accessor for
        callers that want to read the whole rectangle in one go.
        """
        return (self.get_left(), self.get_bottom(), self.get_right(), self.get_top())

    def set_rect(
        self,
        left: float | None,
        bottom: float | None,
        right: float | None,
        top: float | None,
    ) -> None:
        """Write all four edge coordinates in one call.

        Pass ``None`` for any slot to mark it as ``COSNull`` (i.e.
        *retain the current viewer value for that coordinate*).
        """
        self.set_left(left)
        self.set_bottom(bottom)
        self.set_right(right)
        self.set_top(top)

    # ---------- predicate helpers ----------

    def _is_slot_unset(self, slot: int) -> bool:
        arr = self.get_cos_array()
        if slot >= arr.size():
            return True
        value = arr.get_object(slot)
        return not isinstance(value, (COSInteger, COSFloat))

    def is_left_unset(self) -> bool:
        """``True`` when the ``left`` x-coordinate is missing or null."""
        return self._is_slot_unset(self._SLOT_LEFT)

    def is_bottom_unset(self) -> bool:
        """``True`` when the ``bottom`` y-coordinate is missing or null."""
        return self._is_slot_unset(self._SLOT_BOTTOM)

    def is_right_unset(self) -> bool:
        """``True`` when the ``right`` x-coordinate is missing or null."""
        return self._is_slot_unset(self._SLOT_RIGHT)

    def is_top_unset(self) -> bool:
        """``True`` when the ``top`` y-coordinate is missing or null."""
        return self._is_slot_unset(self._SLOT_TOP)

    def is_complete(self) -> bool:
        """``True`` when all four edge coordinates are explicitly set.

        Convenience predicate for callers that want to know whether
        the destination fully pins the rectangle versus inheriting some
        coordinates from the current view.
        """
        return not (
            self.is_left_unset()
            or self.is_bottom_unset()
            or self.is_right_unset()
            or self.is_top_unset()
        )

    # ---------- clear helpers ----------

    def _clear_slot(self, slot: int) -> None:
        arr = self.get_cos_array()
        arr.grow_to_size(slot + 1, COSNull.NULL)
        arr.set(slot, COSNull.NULL)

    def clear_left(self) -> None:
        """Clear the ``left`` slot to ``COSNull``."""
        self._clear_slot(self._SLOT_LEFT)

    def clear_bottom(self) -> None:
        """Clear the ``bottom`` slot to ``COSNull``."""
        self._clear_slot(self._SLOT_BOTTOM)

    def clear_right(self) -> None:
        """Clear the ``right`` slot to ``COSNull``."""
        self._clear_slot(self._SLOT_RIGHT)

    def clear_top(self) -> None:
        """Clear the ``top`` slot to ``COSNull``."""
        self._clear_slot(self._SLOT_TOP)


__all__ = ["PDPageFitRectangleDestination"]
