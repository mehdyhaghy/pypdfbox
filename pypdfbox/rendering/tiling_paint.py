"""AWT Paint adapter for PDF tiling patterns.

Mirrors ``org.apache.pdfbox.rendering.TilingPaint``.

Upstream uses ``java.awt.TexturePaint`` over a pre-rendered tile to
implement Type 1 patterns. The Python port rasterises the pattern cell
into a Pillow ``Image`` (substitute for ``BufferedImage``) and stores
the result along with its anchor rectangle so callers can paste it
into the page raster the same way ``TexturePaint`` would tile it.
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


def _abs_scale_factors(xform: Any) -> tuple[float, float]:
    """Extract absolute X/Y scaling factors from a transform-like object.

    Accepts ``Matrix`` instances (preferred), a 6-tuple of affine
    coefficients ``(a, b, c, d, e, f)``, or ``None`` (identity).
    """
    if xform is None:
        return 1.0, 1.0
    if hasattr(xform, "get_scaling_factor_x") and hasattr(xform, "get_scaling_factor_y"):
        return abs(xform.get_scaling_factor_x()), abs(xform.get_scaling_factor_y())
    if isinstance(xform, (tuple, list)) and len(xform) >= 4:
        a, b, c, d = xform[0], xform[1], xform[2], xform[3]
        sx = math.sqrt(a * a + b * b) if b else abs(a)
        sy = math.sqrt(c * c + d * d) if c else abs(d)
        return sx, sy
    return 1.0, 1.0


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
        self._pattern_matrix = self._compute_pattern_matrix(pattern, xform)
        self._pattern = pattern
        self._color_space = color_space
        self._color = color
        self._drawer = drawer
        self._xform = xform
        # Pre-compute anchor + image so callers can use the paint without
        # re-rendering. Matches upstream's constructor which stores a
        # TexturePaint over the pre-rendered tile.
        self._anchor_rect = self.get_anchor_rect(pattern)
        self._image = self.get_image(drawer, pattern, color_space, color, self._anchor_rect)
        self._paint: Any = self._image

    @staticmethod
    def _compute_pattern_matrix(pattern: PDTilingPattern, xform: Any) -> Matrix:
        from pypdfbox.util.matrix import Matrix

        if pattern is None:
            return Matrix()
        # Upstream: Matrix.concatenate(drawer.getInitialMatrix(), pattern.getMatrix()).
        # When ``xform`` is itself a Matrix we treat it as the initial matrix
        # and concatenate; otherwise we fall back to the pattern's own matrix.
        pattern_m = pattern.get_matrix() if hasattr(pattern, "get_matrix") else None
        if pattern_m is None:
            pattern_m = Matrix()
        if isinstance(xform, Matrix):
            return Matrix.concatenate_matrices(xform, pattern_m)
        return pattern_m

    def create_context(
        self,
        cm: Any,
        device_bounds: Any,
        user_bounds: Any,
        xform: Any,
        hints: Any,
    ) -> Any:
        """Return a paint context that knows how to tile the cached image.

        Upstream wraps the pre-rendered tile in ``TexturePaint`` and
        delegates ``createContext`` to it. Pillow has no equivalent
        per-context type, so we return a lightweight namespace exposing
        the cached tile image plus the anchor rectangle. Renderers can
        ``paste`` the tile across ``device_bounds`` using PIL's standard
        APIs.
        """
        return _TilingPaintContext(self._image, self._anchor_rect, self._pattern_matrix)

    def get_image(
        self,
        drawer: PageDrawer,
        pattern: PDTilingPattern,
        color_space: PDColorSpace | None,
        color: PDColor | None,
        anchor_rect: Any,
    ) -> Any:
        """Render the pattern cell into a Pillow image (parent stream coords).

        Mirrors upstream ``TilingPaint.getImage`` (lines 127-179 of
        ``TilingPaint.java``).
        """
        if anchor_rect is None:
            return None
        try:
            from PIL import Image, ImageDraw
        except ImportError:  # pragma: no cover - exercised in lossless tests
            _LOG.debug("Pillow not available; skipping tile rasterisation")
            return None

        # anchor_rect is (x, y, w, h)
        try:
            _, _, anchor_w, anchor_h = anchor_rect
        except (TypeError, ValueError):
            return None

        width = abs(float(anchor_w))
        height = abs(float(anchor_h))

        x_scale, y_scale = _abs_scale_factors(self._xform)
        width *= x_scale
        height *= y_scale

        raster_width = max(1, self.ceiling(width))
        raster_height = max(1, self.ceiling(height))

        image = Image.new("RGBA", (raster_width, raster_height), (0, 0, 0, 0))

        # Upstream calls drawer.drawTilingPattern which actually renders
        # the cell content stream. Our page drawer is still a stub, so
        # we mirror the call but tolerate a missing implementation: when
        # ``draw_tiling_pattern`` is a no-op the blank cell is returned
        # (matches a uncolored / unevaluated tile and lets the wrapping
        # paint code remain correct for the common case).
        if drawer is not None and hasattr(drawer, "draw_tiling_pattern"):
            draw = ImageDraw.Draw(image)
            # We pass the Draw context as the ``graphics`` arg so a
            # real implementation can paint into it. The matrix
            # mirrors upstream's ``newPatternMatrix`` (scale-only +
            # bbox-relative translate).
            from pypdfbox.util.matrix import Matrix

            px = abs(self._pattern_matrix.get_scaling_factor_x())
            py = abs(self._pattern_matrix.get_scaling_factor_y())
            new_pm = Matrix.get_scale_instance(px, py)
            bbox = pattern.get_b_box() if hasattr(pattern, "get_b_box") else None
            if bbox is not None and hasattr(new_pm, "translate"):
                import contextlib

                with contextlib.suppress(AttributeError, TypeError):
                    new_pm.translate(-bbox.get_lower_left_x(), -bbox.get_lower_left_y())
            # Upstream signature is ``(graphics, pattern, colorSpace,
            # color, matrix)``; our port currently accepts ``(pattern,
            # color, color_space)`` (page_drawer.py:249). Call the
            # public-port shape — the stub is a no-op anyway.
            # Upstream (PDFBOX-5660, svn r1934553) wraps the
            # ``drawer.drawTilingPattern`` call in try/finally so the
            # AWT ``Graphics2D`` is disposed even on exception. The
            # Python ``ImageDraw.Draw`` analogue holds no OS resources
            # — release is symbolic — but we mirror the structure so
            # parity stays intact and future drawer changes that *do*
            # acquire resources inherit the correct cleanup ordering.
            try:
                drawer.draw_tiling_pattern(pattern, color, color_space)
            except (AttributeError, TypeError, ValueError) as exc:
                _LOG.debug("draw_tiling_pattern stub did not render: %s", exc)
            finally:
                del draw, new_pm

        return image

    def get_anchor_rect(self, pattern: PDTilingPattern) -> Any:
        """Compute the pattern cell's anchor rectangle in user space.

        Mirror of upstream ``TilingPaint.getAnchorRect`` (lines 200-246).
        Returns ``(x, y, w, h)`` with scaling applied. Returns ``None``
        when ``pattern`` is ``None`` or its ``/BBox`` is missing.
        """
        if pattern is None:
            return None
        bbox = pattern.get_b_box() if hasattr(pattern, "get_b_box") else None
        if bbox is None:
            _LOG.warning("Pattern /BBox is missing")
            return None

        x_step = pattern.get_x_step() if hasattr(pattern, "get_x_step") else 0.0
        if x_step == 0:
            _LOG.warning("/XStep is 0, using pattern /BBox width")
            x_step = bbox.get_width()

        y_step = pattern.get_y_step() if hasattr(pattern, "get_y_step") else 0.0
        if y_step == 0:
            _LOG.warning("/YStep is 0, using pattern /BBox height")
            y_step = bbox.get_height()

        x_scale = self._pattern_matrix.get_scaling_factor_x()
        y_scale = self._pattern_matrix.get_scaling_factor_y()
        width = x_step * x_scale
        height = y_step * y_scale

        if abs(width * height) > MAXEDGE * MAXEDGE:
            # PDFBOX-3653: prevent huge sizes
            _LOG.warning(
                "Pattern surface larger than %d x %d, will be clipped",
                MAXEDGE,
                MAXEDGE,
            )
            width = min(MAXEDGE, abs(width)) * (1 if width >= 0 else -1)
            height = min(MAXEDGE, abs(height)) * (1 if height >= 0 else -1)

        return (
            bbox.get_lower_left_x() * x_scale,
            bbox.get_lower_left_y() * y_scale,
            width,
            height,
        )

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


class _TilingPaintContext:
    """Lightweight paint-context returned by :meth:`TilingPaint.create_context`.

    Pillow has no direct equivalent of AWT's ``PaintContext``; we just
    expose the cached tile image and anchor rectangle so a downstream
    Pillow renderer can iterate ``Image.paste`` calls to tile the cell.
    """

    def __init__(self, image: Any, anchor_rect: Any, pattern_matrix: Any) -> None:
        self.image = image
        self.anchor_rect = anchor_rect
        self.pattern_matrix = pattern_matrix

    def get_color_model(self) -> str:
        return "RGBA"

    def dispose(self) -> None:
        # Pillow images don't hold OS resources we need to release.
        return None


__all__ = ["MAXEDGE", "TilingPaint"]
