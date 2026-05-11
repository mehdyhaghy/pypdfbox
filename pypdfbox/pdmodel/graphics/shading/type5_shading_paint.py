"""Paint adapter for Type 5 (lattice Gouraud) shading.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.Type5ShadingPaint``.
"""

from __future__ import annotations

import contextlib
from typing import Any

from .shading_paint import ShadingPaint


class Type5ShadingPaint(ShadingPaint):
    """Paint for lattice-form Type 5 Gouraud shading."""

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
        lattice-form mesh triangles. Mirrors upstream
        ``Type5ShadingPaint.createContext`` (line 56) which constructs a
        ``Type5ShadingContext`` — shared with Type 4 in pypdfbox via
        :class:`GouraudShadingContext`."""
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
