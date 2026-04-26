from __future__ import annotations

from pypdfbox.cos import COSArray

from .pd_page_destination import PDPageDestination


class PDPageXYZDestination(PDPageDestination):
    """XYZ page destination. Mirrors PDFBox ``PDPageXYZDestination``."""

    TYPE = "XYZ"

    def __init__(self, array: COSArray | None = None) -> None:
        super().__init__(array)
        if array is None:
            self._set_type(self.TYPE)

    def get_left(self) -> float | None:
        return self._get_float(2)

    def set_left(self, left: float | None) -> None:
        self._set_float(2, left)

    def get_top(self) -> float | None:
        return self._get_float(3)

    def set_top(self, top: float | None) -> None:
        self._set_float(3, top)

    def get_zoom(self) -> float | None:
        return self._get_float(4)

    def set_zoom(self, zoom: float | None) -> None:
        self._set_float(4, zoom)


__all__ = ["PDPageXYZDestination"]
