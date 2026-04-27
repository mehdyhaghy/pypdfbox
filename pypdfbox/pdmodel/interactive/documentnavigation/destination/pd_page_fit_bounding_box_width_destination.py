from __future__ import annotations

from pypdfbox.cos import COSArray

from .pd_page_destination import PDPageDestination


class PDPageFitBoundingBoxWidthDestination(PDPageDestination):
    """Fit-bounding-box width page destination (``/FitBH``).

    Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitBoundingBoxWidthDestination``.
    Display the page with the horizontal coordinate ``top`` positioned at
    the top edge of the window and the contents of the page magnified
    just enough to fit the entire width of the bounding box within the
    window.
    """

    TYPE = "FitBH"

    def __init__(self, array: COSArray | None = None) -> None:
        super().__init__(array)
        if array is None:
            self._set_type(self.TYPE)

    def get_top(self) -> float | None:
        return self._get_float(2)

    def set_top(self, top: float | None) -> None:
        self._set_float(2, top)


__all__ = ["PDPageFitBoundingBoxWidthDestination"]
