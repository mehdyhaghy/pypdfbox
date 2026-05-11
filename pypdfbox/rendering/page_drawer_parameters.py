"""Parameter bag for ``PageDrawer``.

Mirrors ``org.apache.pdfbox.rendering.PageDrawerParameters``. The class
exists so ``PDFRenderer`` and ``PageDrawer`` can share private
implementation data without breaking the public ``PageDrawer`` ctor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .render_destination import RenderDestination

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_page import PDPage

    from .pdf_renderer import PDFRenderer


class PageDrawerParameters:
    """Immutable bundle of renderer-level options forwarded to ``PageDrawer``."""

    __slots__ = (
        "_renderer",
        "_page",
        "_subsampling_allowed",
        "_destination",
        "_rendering_hints",
        "_image_downscaling_optimization_threshold",
    )

    def __init__(
        self,
        renderer: PDFRenderer,
        page: PDPage,
        subsampling_allowed: bool,
        destination: RenderDestination,
        rendering_hints: Any,
        image_downscaling_optimization_threshold: float,
    ) -> None:
        self._renderer = renderer
        self._page = page
        self._subsampling_allowed = bool(subsampling_allowed)
        self._destination = destination
        self._rendering_hints = rendering_hints
        self._image_downscaling_optimization_threshold = float(
            image_downscaling_optimization_threshold
        )

    def get_page(self) -> PDPage:
        """Return the page being rendered."""
        return self._page

    def get_renderer(self) -> PDFRenderer:
        """Return the parent renderer."""
        return self._renderer

    def is_subsampling_allowed(self) -> bool:
        """Whether image-subsampling shortcuts are permitted."""
        return self._subsampling_allowed

    def get_destination(self) -> RenderDestination:
        """Return the render destination (EXPORT / VIEW / PRINT)."""
        return self._destination

    def get_rendering_hints(self) -> Any:
        """Return the AWT-style rendering hints dict."""
        return self._rendering_hints

    def get_image_downscaling_optimization_threshold(self) -> float:
        """Return the threshold below which raster images get downsampled."""
        return self._image_downscaling_optimization_threshold


__all__ = ["PageDrawerParameters"]
