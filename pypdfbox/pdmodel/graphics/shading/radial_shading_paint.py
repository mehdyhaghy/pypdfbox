"""Paint adapter for Type 3 (radial) shading.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.RadialShadingPaint``.
"""

from __future__ import annotations

from typing import Any

from .radial_shading_context import RadialShadingContext
from .shading_paint import ShadingPaint


class RadialShadingPaint(ShadingPaint):
    """Paint factory yielding :class:`RadialShadingContext`."""

    def __init__(self, shading: Any, matrix: Any) -> None:
        super().__init__(shading, matrix)

    def create_context(
        self,
        cm: Any,
        device_bounds: Any,
        user_bounds: Any,
        xform: Any,
        hints: Any | None = None,
    ) -> RadialShadingContext:
        return RadialShadingContext(self.shading, cm, xform, self.matrix, device_bounds)
