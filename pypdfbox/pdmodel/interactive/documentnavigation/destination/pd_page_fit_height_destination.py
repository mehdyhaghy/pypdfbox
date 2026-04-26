from __future__ import annotations

from pypdfbox.cos import COSArray

from .pd_page_destination import PDPageDestination


class PDPageFitHeightDestination(PDPageDestination):
    """Fit page height destination. Mirrors PDFBox ``PDPageFitHeightDestination``."""

    TYPE = "FitV"
    TYPE_BOUNDED = "FitBV"

    def __init__(self, array: COSArray | None = None) -> None:
        super().__init__(array)
        if array is None:
            self._set_type(self.TYPE)

    def fit_bounding_box(self) -> bool:
        return self.get_type() == self.TYPE_BOUNDED

    def set_fit_bounding_box(self, fit_bounding_box: bool) -> None:
        self._set_type(self.TYPE_BOUNDED if fit_bounding_box else self.TYPE)

    def get_left(self) -> float | None:
        return self._get_float(2)

    def set_left(self, left: float | None) -> None:
        self._set_float(2, left)


__all__ = ["PDPageFitHeightDestination"]
