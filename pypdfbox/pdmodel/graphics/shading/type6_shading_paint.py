"""Paint adapter for Type 6 (Coons patch mesh) shading.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.Type6ShadingPaint``.
"""

from __future__ import annotations

from typing import Any

from .shading_paint import ShadingPaint


class Type6ShadingPaint(ShadingPaint):
    """Paint for Coons patch (Type 6) shading."""

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
            "Type6ShadingPaint.create_context wires up with the renderer cluster"
        )
