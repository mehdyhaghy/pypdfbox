from __future__ import annotations

from pypdfbox.cos import COSArray

from .pd_page_destination import PDPageDestination


class PDPageFitBoundingBoxHeightDestination(PDPageDestination):
    """Fit-bounding-box height page destination (``/FitBV``).

    Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitBoundingBoxHeightDestination``.
    Display the page with the vertical coordinate ``left`` positioned at
    the left edge of the window and the contents of the page magnified
    just enough to fit the entire height of the bounding box within the
    window.
    """

    TYPE = "FitBV"
    _SLOT_LEFT: int = 2

    def __init__(self, array: COSArray | None = None) -> None:
        super().__init__(array)
        if array is None:
            self._set_type(self.TYPE)

    def get_left(self) -> float | None:
        return self._get_float(self._SLOT_LEFT)

    def set_left(self, left: float | None) -> None:
        self._set_float(self._SLOT_LEFT, left)

    def is_left_unset(self) -> bool:
        """``True`` when the ``left`` x-coordinate is missing or null."""
        return self.get_left() is None

    def clear_left(self) -> None:
        """Clear the ``left`` slot to ``COSNull``."""
        self.set_left(None)


__all__ = ["PDPageFitBoundingBoxHeightDestination"]
