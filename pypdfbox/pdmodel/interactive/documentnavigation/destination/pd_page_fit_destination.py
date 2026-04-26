from __future__ import annotations

from pypdfbox.cos import COSArray

from .pd_page_destination import PDPageDestination


class PDPageFitDestination(PDPageDestination):
    """Fit whole page destination. Mirrors PDFBox ``PDPageFitDestination``."""

    TYPE = "Fit"
    TYPE_BOUNDED = "FitB"

    def __init__(self, array: COSArray | None = None) -> None:
        super().__init__(array)
        if array is None:
            self._set_type(self.TYPE)

    def fit_bounding_box(self) -> bool:
        return self.get_type() == self.TYPE_BOUNDED

    def set_fit_bounding_box(self, fit_bounding_box: bool) -> None:
        self._set_type(self.TYPE_BOUNDED if fit_bounding_box else self.TYPE)


__all__ = ["PDPageFitDestination"]
