"""Paint adapter for Type 4 (free Gouraud) shading.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.Type4ShadingPaint``.
"""

from __future__ import annotations

import contextlib
from typing import Any

from .shading_paint import ShadingPaint


class Type4ShadingPaint(ShadingPaint):
    """Paint for Gouraud-triangle (free-form) Type 4 shading."""

    def __init__(self, shading: Any, matrix: Any) -> None:
        super().__init__(shading, matrix)

    def create_context(
        self,
        cm: Any,
        device_bounds: Any,
        user_bounds: Any,
        xform: Any,
        hints: Any | None = None,
    ) -> Any:
        """Return a :class:`GouraudShadingContext` populated with the
        free-form mesh triangles. Mirrors upstream
        ``Type4ShadingPaint.createContext`` (line 56) which constructs a
        ``Type4ShadingContext`` — pypdfbox's renderer is Pillow-based and
        the shared :class:`GouraudShadingContext` covers the Type 4 and 5
        triangle-mesh cases."""
        _ = (user_bounds, hints)
        from .gouraud_shading_context import GouraudShadingContext  # noqa: PLC0415

        ctx = GouraudShadingContext(self.shading, cm, xform, self.matrix)
        try:
            triangles = list(self.shading.collect_triangles(xform, self.matrix))
        except (NotImplementedError, AttributeError, OSError):
            triangles = []
        ctx.set_triangle_list(triangles)
        if device_bounds is not None:
            with contextlib.suppress(TypeError, ValueError):
                ctx.create_pixel_table(tuple(device_bounds))
        return ctx
