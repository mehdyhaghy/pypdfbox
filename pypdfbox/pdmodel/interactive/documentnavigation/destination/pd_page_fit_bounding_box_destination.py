from __future__ import annotations

from pypdfbox.cos import COSArray

from .pd_page_destination import PDPageDestination


class PDPageFitBoundingBoxDestination(PDPageDestination):
    """Fit-bounding-box page destination (``/FitB``).

    Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitBoundingBoxDestination``.
    Display the page with its bounding box magnified just enough to fit
    the entire bounding box within the window in both horizontal and
    vertical directions.
    """

    TYPE = "FitB"

    def __init__(self, array: COSArray | None = None) -> None:
        super().__init__(array)
        if array is None:
            self._set_type(self.TYPE)


__all__ = ["PDPageFitBoundingBoxDestination"]
