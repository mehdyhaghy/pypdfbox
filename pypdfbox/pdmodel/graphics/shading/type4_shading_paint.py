"""Paint adapter for Type 4 (free Gouraud) shading.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.Type4ShadingPaint``.
"""

from __future__ import annotations

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
        # Concrete Type4ShadingContext is wired in with the renderer cluster.
        raise NotImplementedError(
            "Type4ShadingPaint.create_context wires up with the renderer cluster"
        )
