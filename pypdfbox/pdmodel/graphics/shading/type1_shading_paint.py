"""Paint adapter for Type 1 (function-based) shading.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.Type1ShadingPaint``.
"""

from __future__ import annotations

from typing import Any

from .shading_paint import ShadingPaint
from .type1_shading_context import Type1ShadingContext


class Type1ShadingPaint(ShadingPaint):
    """Paint factory yielding :class:`Type1ShadingContext`."""

    def __init__(self, shading: Any, matrix: Any) -> None:
        super().__init__(shading, matrix)

    def create_context(
        self,
        cm: Any,
        device_bounds: Any,
        user_bounds: Any,
        xform: Any,
        hints: Any | None = None,
    ) -> Type1ShadingContext:
        return Type1ShadingContext(self.shading, cm, xform, self.matrix)
