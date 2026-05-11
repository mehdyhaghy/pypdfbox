"""Paint adapter for Type 7 (tensor patch mesh) shading.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.Type7ShadingPaint``.
"""

from __future__ import annotations

from typing import Any

from .shading_paint import ShadingPaint


class Type7ShadingPaint(ShadingPaint):
    """Paint for tensor-product patch (Type 7) shading."""

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
        raise NotImplementedError(
            "Type7ShadingPaint.create_context wires up with the renderer cluster"
        )
