"""AWT Paint adapter for PDF tiling patterns.

Mirrors ``org.apache.pdfbox.rendering.TilingPaint``.

Upstream uses ``java.awt.TexturePaint`` over a pre-rendered tile to
implement Type 1 patterns. The Python port keeps the constructor and
``create_context`` surface so the renderer can plug a ``TilingPaint``
into the same dispatch slot, but the actual tile rasterisation TODO is
deferred.
"""

from __future__ import annotations

import logging
import math
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
    from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
    from pypdfbox.pdmodel.graphics.pattern.pd_tiling_pattern import PDTilingPattern
    from pypdfbox.util.matrix import Matrix

    from .page_drawer import PageDrawer

_LOG = logging.getLogger(__name__)

TRANSLUCENT = 3

# Mirror upstream's pdfbox.rendering.tilingpaint.maxedge system property.
_DEFAULT_MAXEDGE = 3000


def _resolve_maxedge() -> int:
    raw = os.environ.get("PDFBOX_RENDERING_TILINGPAINT_MAXEDGE", str(_DEFAULT_MAXEDGE))
    try:
        return int(raw)
    except ValueError:
        _LOG.error("Default will be used")
        return _DEFAULT_MAXEDGE


MAXEDGE = _resolve_maxedge()


class TilingPaint:
    """Adapter exposing the AWT ``Paint`` API for a PDF tiling pattern."""

    def __init__(
        self,
        drawer: PageDrawer,
        pattern: PDTilingPattern,
        color_space: PDColorSpace | None = None,
        color: PDColor | None = None,
        xform: Any = None,
    ) -> None:
        self._paint: Any = None
        self._pattern_matrix = self._compute_pattern_matrix(pattern, xform)
        self._pattern = pattern
        self._color_space = color_space
        self._color = color
        self._drawer = drawer

    @staticmethod
    def _compute_pattern_matrix(pattern: PDTilingPattern, xform: Any) -> Matrix:
        from pypdfbox.util.matrix import Matrix

        if pattern is None:
            return Matrix()
        if hasattr(pattern, "get_matrix"):
            return pattern.get_matrix() or Matrix()
        return Matrix()

    def create_context(
        self,
        cm: Any,
        device_bounds: Any,
        user_bounds: Any,
        xform: Any,
        hints: Any,
    ) -> Any:
        """Return a paint context for AWT.

        TODO: full implementation requires rasterising the pattern cell
        into a Pillow ``Image`` and wrapping it in a TexturePaint-style
        context.
        """
        return None

    def get_image(
        self,
        drawer: PageDrawer,
        pattern: PDTilingPattern,
        color_space: PDColorSpace | None,
        color: PDColor | None,
        anchor_rect: Any,
    ) -> Any:
        """Render the pattern cell into a small bitmap.

        TODO: full implementation.
        """
        return None

    def get_anchor_rect(self, pattern: PDTilingPattern) -> Any:
        """Compute the pattern cell's anchor rectangle in user space."""
        if pattern is None:
            return None
        if hasattr(pattern, "get_b_box"):
            return pattern.get_b_box()
        return None

    @staticmethod
    def ceiling(num: float) -> int:
        """Mirror upstream ``ceiling(double)`` (rounded toward +Inf)."""
        return int(math.ceil(num))

    def get_transparency(self) -> int:
        """Mirror upstream ``Paint.getTransparency()`` -> ``TRANSLUCENT``."""
        return TRANSLUCENT

    def get_pattern_matrix(self) -> Matrix:
        """Return the cached pattern-space matrix."""
        return self._pattern_matrix


__all__ = ["MAXEDGE", "TilingPaint"]
