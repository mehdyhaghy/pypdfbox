from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSNull

from .pd_page_destination import PDPageDestination


class PDPageFitHeightDestination(PDPageDestination):
    """Fit page height destination. Mirrors PDFBox ``PDPageFitHeightDestination``.

    Per PDF 32000-1 §12.3.2.2 (Table 151), the array is
    ``[page /FitV left]`` (or ``[page /FitBV left]`` for the bounding-box
    variant). The ``left`` slot may be ``null`` (or upstream sentinel
    ``-1``) meaning *retain the current x-coordinate*.
    """

    TYPE = "FitV"
    TYPE_BOUNDED = "FitBV"

    #: Slot index for the ``left`` x-coordinate.
    _SLOT_LEFT: int = 2

    def __init__(self, array: COSArray | None = None) -> None:
        super().__init__(array)
        if array is None:
            self._array.grow_to_size(self._SLOT_LEFT + 1, COSNull.NULL)
            self._set_type(self.TYPE)

    def fit_bounding_box(self) -> bool:
        return self.get_type() == self.TYPE_BOUNDED

    def set_fit_bounding_box(self, fit_bounding_box: bool) -> None:
        self._set_type(self.TYPE_BOUNDED if fit_bounding_box else self.TYPE)

    def get_left(self) -> float | None:
        return self._get_float(self._SLOT_LEFT)

    def set_left(self, left: float | None) -> None:
        self._set_float(self._SLOT_LEFT, left)

    # ---------- predicate helpers ----------

    def is_bounded(self) -> bool:
        """``True`` when this destination is the ``/FitBV`` variant."""
        return self.fit_bounding_box()

    def is_left_unset(self) -> bool:
        """``True`` when the ``left`` x-coordinate is missing or null.

        Equivalent to ``get_left() is None`` but spelled as a predicate
        so callers don't have to bind the value into a temporary just
        to ask the question. Mirrors upstream's ``-1`` sentinel
        semantics for the ``left`` slot.
        """
        arr = self.get_cos_array()
        if arr.size() <= self._SLOT_LEFT:
            return True
        value = arr.get_object(self._SLOT_LEFT)
        return not isinstance(value, (COSInteger, COSFloat))

    def clear_left(self) -> None:
        """Clear the ``left`` slot to ``COSNull``.

        Convenience helper that's equivalent to ``set_left(None)`` but
        spelled as a verb for callers who think in terms of "unsetting"
        the slot rather than passing a sentinel value.
        """
        arr = self.get_cos_array()
        arr.grow_to_size(self._SLOT_LEFT + 1, COSNull.NULL)
        arr.set(self._SLOT_LEFT, COSNull.NULL)


__all__ = ["PDPageFitHeightDestination"]
