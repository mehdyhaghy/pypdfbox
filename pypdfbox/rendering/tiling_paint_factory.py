"""Factory that caches ``TilingPaint`` instances per pattern/colour/transform.

Mirrors ``org.apache.pdfbox.rendering.TilingPaintFactory`` plus its
package-private inner ``TilingPaintParameter`` key.
"""

from __future__ import annotations

import logging
import weakref
from typing import TYPE_CHECKING, Any

from .tiling_paint import TilingPaint

if TYPE_CHECKING:
    from pypdfbox.cos import COSDictionary
    from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
    from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
    from pypdfbox.pdmodel.graphics.pattern.pd_tiling_pattern import PDTilingPattern
    from pypdfbox.util.matrix import Matrix

    from .page_drawer import PageDrawer

_LOG = logging.getLogger(__name__)


class TilingPaintFactory:
    """Cache of ``TilingPaint`` instances keyed by their parameters."""

    def __init__(self, drawer: PageDrawer) -> None:
        self._drawer = drawer
        # Mirror upstream's WeakHashMap with weakref values.
        self._weak_cache: dict[TilingPaintParameter, weakref.ReferenceType[Any]] = {}

    def create(
        self,
        pattern: PDTilingPattern,
        color_space: PDColorSpace | None,
        color: PDColor | None,
        xform: Any,
    ) -> Any:
        """Return a cached or newly built ``TilingPaint`` for the inputs."""
        initial_matrix = (
            self._drawer.get_initial_matrix()
            if hasattr(self._drawer, "get_initial_matrix")
            else None
        )
        pattern_dict = pattern.get_cos_object() if hasattr(pattern, "get_cos_object") else None
        key = TilingPaintParameter(initial_matrix, pattern_dict, color_space, color, xform)
        weak_ref = self._weak_cache.get(key)
        paint = weak_ref() if weak_ref is not None else None
        if paint is None:
            paint = TilingPaint(self._drawer, pattern, color_space, color, xform)
            try:
                self._weak_cache[key] = weakref.ref(paint)
            except TypeError:
                # Non-weakly-referenceable objects: fall back to strong ref.
                self._weak_cache[key] = lambda paint=paint: paint
        return paint


class TilingPaintParameter:
    """Hashable cache key for :class:`TilingPaintFactory`.

    Mirrors the upstream private inner class. Intentionally does **not**
    keep a back-reference to the produced :class:`TilingPaint` so the
    weak cache can collect entries.
    """

    __slots__ = ("matrix", "pattern_dict", "color_space", "color", "xform")

    def __init__(
        self,
        matrix: Matrix | None,
        pattern_dict: COSDictionary | None,
        color_space: PDColorSpace | None,
        color: PDColor | None,
        xform: Any,
    ) -> None:
        self.matrix = matrix.clone() if matrix is not None and hasattr(matrix, "clone") else matrix
        self.pattern_dict = pattern_dict
        self.color_space = color_space
        self.color = color
        self.xform = xform

    def equals(self, other: object) -> bool:
        """Mirror upstream ``equals(Object)``."""
        if self is other:
            return True
        if not isinstance(other, TilingPaintParameter):
            return False
        if self.matrix != other.matrix:
            return False
        if (
            self.pattern_dict is not other.pattern_dict
            and self.pattern_dict != other.pattern_dict
        ):
            # Upstream uses Objects.equals; we keep identity for COS dicts.
            return False
        if self.color_space is not other.color_space and self.color_space != other.color_space:
            return False
        if (self.color is None) != (other.color is None):
            return False
        if self.color is not None and other.color is not None:
            if self.color.get_color_space() is not other.color.get_color_space():
                return False
            try:
                if self.color is not other.color and self.color.to_rgb() != other.color.to_rgb():
                    return False
            except OSError as exc:
                _LOG.debug("Couldn't convert color to RGB: %s", exc)
                return False
        return self.xform == other.xform

    def hash_code(self) -> int:
        """Mirror upstream ``hashCode()``."""
        h = 7
        for v in (self.matrix, self.pattern_dict, self.color_space, self.color, self.xform):
            h = 23 * h + (hash(v) if v is not None else 0)
        return h

    def to_string(self) -> str:
        return (
            f"TilingPaintParameter{{matrix={self.matrix}, pattern={self.pattern_dict}, "
            f"colorSpace={self.color_space}, color={self.color}, xform={self.xform}}}"
        )

    def __eq__(self, other: object) -> bool:
        return self.equals(other)

    def __hash__(self) -> int:
        return self.hash_code()

    def __repr__(self) -> str:
        return self.to_string()


__all__ = ["TilingPaintFactory", "TilingPaintParameter"]
