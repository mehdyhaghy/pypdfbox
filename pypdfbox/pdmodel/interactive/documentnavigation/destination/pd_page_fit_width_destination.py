from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSNull

from .pd_page_destination import PDPageDestination


class PDPageFitWidthDestination(PDPageDestination):
    """Fit page width destination. Mirrors PDFBox ``PDPageFitWidthDestination``.

    Per PDF 32000-1 §12.3.2.2 (Table 151), the array is
    ``[page /FitH top]`` (or ``[page /FitBH top]`` for the bounding-box
    variant). The ``top`` slot may be ``null`` (or upstream sentinel
    ``-1``) meaning *retain the current y-coordinate*.
    """

    TYPE = "FitH"
    TYPE_BOUNDED = "FitBH"

    #: Slot index for the ``top`` y-coordinate.
    _SLOT_TOP: int = 2

    def __init__(self, array: COSArray | None = None) -> None:
        super().__init__(array)
        if array is None:
            self._set_type(self.TYPE)

    def fit_bounding_box(self) -> bool:
        return self.get_type() == self.TYPE_BOUNDED

    def set_fit_bounding_box(self, fit_bounding_box: bool) -> None:
        self._set_type(self.TYPE_BOUNDED if fit_bounding_box else self.TYPE)

    def get_top(self) -> float | None:
        return self._get_float(self._SLOT_TOP)

    def set_top(self, top: float | None) -> None:
        self._set_float(self._SLOT_TOP, top)

    # ---------- predicate helpers ----------

    def is_bounded(self) -> bool:
        """``True`` when this destination is the ``/FitBH`` variant."""
        return self.fit_bounding_box()

    def is_top_unset(self) -> bool:
        """``True`` when the ``top`` y-coordinate is missing or null.

        Equivalent to ``get_top() is None`` but spelled as a predicate
        so callers don't have to bind the value into a temporary just
        to ask the question. Mirrors upstream's ``-1`` sentinel
        semantics for the ``top`` slot.
        """
        arr = self.get_cos_array()
        if self._SLOT_TOP >= arr.size():
            return True
        value = arr.get_object(self._SLOT_TOP)
        return not isinstance(value, (COSInteger, COSFloat))

    def clear_top(self) -> None:
        """Clear the ``top`` slot to ``COSNull``.

        Convenience helper that's equivalent to ``set_top(None)`` but
        spelled as a verb for callers who think in terms of "unsetting"
        the slot rather than passing a sentinel value.
        """
        arr = self.get_cos_array()
        arr.grow_to_size(self._SLOT_TOP + 1, COSNull.NULL)
        arr.set(self._SLOT_TOP, COSNull.NULL)


__all__ = ["PDPageFitWidthDestination"]
