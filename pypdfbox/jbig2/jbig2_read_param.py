"""Port of ``org.apache.pdfbox.jbig2.JBIG2ReadParam``.

Upstream ``JBIG2ReadParam`` extends ``javax.imageio.ImageReadParam`` and carries
the region-of-interest, subsampling and render-size knobs the JBIG2 reader hands
to ``Bitmaps.asBufferedImage`` / ``asRaster``. Python's stdlib has no
``ImageReadParam``, so the subset of that base class actually used by the JBIG2
plugin (``sourceRegion``, ``sourceXSubsampling`` / ``sourceYSubsampling``,
``subsamplingXOffset`` / ``subsamplingYOffset``, ``sourceRenderSize``) is
inlined here. Field accessors keep the upstream ``ImageReadParam`` names
(snake_cased).

``java.awt.Rectangle`` maps to a plain ``(x, y, width, height)`` integer tuple
(the same convention :class:`~pypdfbox.jbig2.bitmap.Bitmap` already uses for
``get_bounds``); ``java.awt.Dimension`` maps to a ``(width, height)`` tuple.
"""

from __future__ import annotations


class JBIG2ReadParam:
    """Region-of-interest and scale/subsampling parameters for the reader."""

    def __init__(
        self,
        source_x_subsampling: int = 1,
        source_y_subsampling: int = 1,
        subsampling_x_offset: int = 0,
        subsampling_y_offset: int = 0,
        source_region: tuple[int, int, int, int] | None = None,
        source_render_size: tuple[int, int] | None = None,
    ) -> None:
        # Upstream's no-arg constructor delegates to (1, 1, 0, 0, null, null).
        self.can_set_source_render_size = True
        self.source_region = source_region
        self.source_render_size = source_render_size

        if source_x_subsampling < 1 or source_y_subsampling < 1:
            raise ValueError(
                "Illegal subsampling factor: shall be 1 or greater; but was "
                f" sourceXSubsampling={source_x_subsampling}, "
                f"sourceYSubsampling={source_y_subsampling}"
            )

        self.set_source_subsampling(
            source_x_subsampling,
            source_y_subsampling,
            subsampling_x_offset,
            subsampling_y_offset,
        )

    # --- javax.imageio.ImageReadParam subset --------------------------------

    def set_source_subsampling(
        self,
        source_x_subsampling: int,
        source_y_subsampling: int,
        subsampling_x_offset: int,
        subsampling_y_offset: int,
    ) -> None:
        """Mirror ``IIOParam.setSourceSubsampling``."""
        if source_x_subsampling <= 0 or source_y_subsampling <= 0:
            raise ValueError("subsampling factors must be positive")
        if subsampling_x_offset < 0 or subsampling_x_offset >= source_x_subsampling:
            raise ValueError("subsamplingXOffset out of range")
        if subsampling_y_offset < 0 or subsampling_y_offset >= source_y_subsampling:
            raise ValueError("subsamplingYOffset out of range")
        self.source_x_subsampling = source_x_subsampling
        self.source_y_subsampling = source_y_subsampling
        self.subsampling_x_offset = subsampling_x_offset
        self.subsampling_y_offset = subsampling_y_offset

    def set_source_region(
        self, source_region: tuple[int, int, int, int] | None
    ) -> None:
        """Mirror ``IIOParam.setSourceRegion``."""
        if source_region is not None:
            _x, _y, w, h = source_region
            if w <= 0 or h <= 0:
                raise ValueError("sourceRegion width/height must be positive")
        self.source_region = source_region

    def get_source_region(self) -> tuple[int, int, int, int] | None:
        return self.source_region

    def get_source_x_subsampling(self) -> int:
        return self.source_x_subsampling

    def get_source_y_subsampling(self) -> int:
        return self.source_y_subsampling

    def get_subsampling_x_offset(self) -> int:
        return self.subsampling_x_offset

    def get_subsampling_y_offset(self) -> int:
        return self.subsampling_y_offset

    def set_source_render_size(
        self, source_render_size: tuple[int, int] | None
    ) -> None:
        """Mirror ``ImageReadParam.setSourceRenderSize``."""
        if not self.can_set_source_render_size:
            raise ValueError("cannot set source render size")
        if source_render_size is not None:
            w, h = source_render_size
            if w <= 0 or h <= 0:
                raise ValueError("sourceRenderSize width/height must be positive")
        self.source_render_size = source_render_size

    def get_source_render_size(self) -> tuple[int, int] | None:
        return self.source_render_size

    def can_set_source_render_size_(self) -> bool:
        """Mirror ``ImageReadParam.canSetSourceRenderSize``."""
        return self.can_set_source_render_size
