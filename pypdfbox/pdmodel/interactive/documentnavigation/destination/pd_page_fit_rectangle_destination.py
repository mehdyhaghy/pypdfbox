from __future__ import annotations

from pypdfbox.cos import COSArray

from .pd_page_destination import PDPageDestination


class PDPageFitRectangleDestination(PDPageDestination):
    """Fit rectangle destination. Mirrors PDFBox ``PDPageFitRectangleDestination``."""

    TYPE = "FitR"

    def __init__(self, array: COSArray | None = None) -> None:
        super().__init__(array)
        if array is None:
            self._set_type(self.TYPE)

    def get_left(self) -> float | None:
        return self._get_float(2)

    def set_left(self, left: float | None) -> None:
        self._set_float(2, left)

    def get_bottom(self) -> float | None:
        return self._get_float(3)

    def set_bottom(self, bottom: float | None) -> None:
        self._set_float(3, bottom)

    def get_right(self) -> float | None:
        return self._get_float(4)

    def set_right(self, right: float | None) -> None:
        self._set_float(4, right)

    def get_top(self) -> float | None:
        return self._get_float(5)

    def set_top(self, top: float | None) -> None:
        self._set_float(5, top)


__all__ = ["PDPageFitRectangleDestination"]
