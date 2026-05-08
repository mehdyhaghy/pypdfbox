from __future__ import annotations

from pypdfbox.cos import COSArray, COSNull

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
    _SLOT_TOP: int = 2

    def __init__(self, array: COSArray | None = None) -> None:
        super().__init__(array)
        if array is None:
            self._array.grow_to_size(self._SLOT_TOP + 1, COSNull.NULL)
            self._set_type(self.TYPE)

    def get_top(self) -> float | None:
        return self._get_float(self._SLOT_TOP)

    def set_top(self, top: float | None) -> None:
        self._set_float(self._SLOT_TOP, top)

    def is_top_unset(self) -> bool:
        """``True`` when the ``top`` y-coordinate is missing or null."""
        return self.get_top() is None

    def clear_top(self) -> None:
        """Clear the ``top`` slot to ``COSNull``."""
        self.set_top(None)


__all__ = ["PDPageFitBoundingBoxWidthDestination"]
