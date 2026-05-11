"""Paint adapter for Type 2 (axial) shading.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.AxialShadingPaint``.
"""

from __future__ import annotations

from typing import Any

from .axial_shading_context import AxialShadingContext
from .shading_paint import ShadingPaint


class AxialShadingPaint(ShadingPaint):
    """Paint factory yielding :class:`AxialShadingContext`."""

    def __init__(self, shading_type2: Any, matrix: Any) -> None:
        super().__init__(shading_type2, matrix)

    def create_context(
        self,
        cm: Any,
        device_bounds: Any,
        user_bounds: Any,
        xform: Any,
        hints: Any | None = None,
    ) -> AxialShadingContext:
        return AxialShadingContext(self.shading, cm, xform, self.matrix, device_bounds)
