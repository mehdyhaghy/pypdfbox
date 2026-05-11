"""Per-page printer hook.

Mirrors ``org.apache.pdfbox.printing.PDFPrintable`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/printing/PDFPrintable.java``).

The Java original implements ``java.awt.print.Printable``. We expose the
same set of getters/setters and a ``render`` entry point that returns a
``PIL.Image`` of the page at the requested DPI — this is the natural
Python analogue for sending a page to a Pillow-based printer backend.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image

    from pypdfbox.pdmodel.pd_document import PDDocument


class Scaling(Enum):
    NONE = "NONE"
    SHRINK_TO_FIT = "SHRINK_TO_FIT"
    STRETCH_TO_FIT = "STRETCH_TO_FIT"
    SCALE_TO_FIT = "SCALE_TO_FIT"
    ACTUAL_SIZE = "ACTUAL_SIZE"


class PDFPrintable:
    """One-page printable adapter wrapping :class:`PDFRenderer`."""

    def __init__(
        self,
        document: PDDocument,
        scaling: Scaling | None = None,
        dpi: float = 0.0,
        show_page_border: bool = False,
        center: bool = True,
    ) -> None:
        self._document = document
        self._scaling = scaling if scaling is not None else Scaling.SHRINK_TO_FIT
        self._dpi = dpi
        self._show_page_border = show_page_border
        self._center = center
        self._page_index = 0
        self._subsampling_allowed = False
        self._rendering_hints: dict | None = None

    def get_rendering_hints(self) -> dict | None:
        return self._rendering_hints

    def set_rendering_hints(self, rendering_hints: dict | None) -> None:
        self._rendering_hints = rendering_hints

    def is_subsampling_allowed(self) -> bool:
        return self._subsampling_allowed

    def set_subsampling_allowed(self, subsampling_allowed: bool) -> None:
        self._subsampling_allowed = subsampling_allowed

    def get_scaling(self) -> Scaling:
        return self._scaling

    def set_scaling(self, scaling: Scaling) -> None:
        self._scaling = scaling

    def get_dpi(self) -> float:
        return self._dpi

    def set_dpi(self, dpi: float) -> None:
        self._dpi = dpi

    def render(self, page_index: int | None = None) -> Image:
        """Render the requested page via :class:`PDFRenderer`."""
        from pypdfbox.rendering.pdf_renderer import PDFRenderer

        renderer = PDFRenderer(self._document)
        idx = self._page_index if page_index is None else page_index
        if self._dpi and self._dpi > 0:
            return renderer.render_image_with_dpi(idx, self._dpi)
        return renderer.render_image(idx)

    # --- Upstream parity surface --------------------------------------
    def print(
        self,
        graphics: object | None = None,
        page_format: object | None = None,
        page_index: int | None = None,
    ) -> int:
        """Mirror of ``PDFPrintable.print`` (Java ``Printable.print``).

        Renders ``page_index`` to a Pillow image and stores it on
        ``graphics`` when supplied. Returns ``0`` (``PAGE_EXISTS``) when
        the page rendered, ``1`` (``NO_SUCH_PAGE``) on out-of-range.
        """
        if page_index is None:
            page_index = self._page_index
        try:
            image = self.render(page_index)
        except (IndexError, ValueError):
            return 1
        if graphics is not None and hasattr(graphics, "draw_image"):
            import contextlib

            with contextlib.suppress(AttributeError, TypeError):
                graphics.draw_image(image, 0, 0)
        return 0

    def get_rotated_media_box(self, page: object) -> tuple[float, float, float, float]:
        """Mirror of ``PDFPrintable.getRotatedMediaBox`` (upstream private)."""
        return self._rotated_box(page, "media")

    def get_rotated_crop_box(self, page: object) -> tuple[float, float, float, float]:
        """Mirror of ``PDFPrintable.getRotatedCropBox`` (upstream private)."""
        return self._rotated_box(page, "crop")

    @staticmethod
    def _rotated_box(page: object, which: str) -> tuple[float, float, float, float]:
        if page is None:
            return (0.0, 0.0, 0.0, 0.0)
        getter = "get_media_box" if which == "media" else "get_crop_box"
        box = getattr(page, getter, lambda: None)()
        if box is None:
            return (0.0, 0.0, 0.0, 0.0)
        rotation = 0
        if hasattr(page, "get_rotation"):
            try:
                rotation = int(page.get_rotation() or 0)
            except (TypeError, ValueError):
                rotation = 0
        width = box.get_width() if hasattr(box, "get_width") else 0.0
        height = box.get_height() if hasattr(box, "get_height") else 0.0
        lower_x = box.get_lower_left_x() if hasattr(box, "get_lower_left_x") else 0.0
        lower_y = box.get_lower_left_y() if hasattr(box, "get_lower_left_y") else 0.0
        if rotation % 180 == 90:
            return (lower_x, lower_y, height, width)
        return (lower_x, lower_y, width, height)


__all__ = ["PDFPrintable", "Scaling"]
