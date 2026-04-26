from __future__ import annotations

from pypdfbox.cos import COSArray

from .pd_page_destination import PDPageDestination


class PDPageFitWidthDestination(PDPageDestination):
    """Fit page width destination. Mirrors PDFBox ``PDPageFitWidthDestination``."""

    TYPE = "FitH"
    TYPE_BOUNDED = "FitBH"

    def __init__(self, array: COSArray | None = None) -> None:
        super().__init__(array)
        if array is None:
            self._set_type(self.TYPE)

    def fit_bounding_box(self) -> bool:
        return self.get_type() == self.TYPE_BOUNDED

    def set_fit_bounding_box(self, fit_bounding_box: bool) -> None:
        self._set_type(self.TYPE_BOUNDED if fit_bounding_box else self.TYPE)

    def get_top(self) -> float | None:
        return self._get_float(2)

    def set_top(self, top: float | None) -> None:
        self._set_float(2, top)


__all__ = ["PDPageFitWidthDestination"]
