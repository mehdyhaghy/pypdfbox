"""Paint adapter for Type 5 (lattice Gouraud) shading.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.Type5ShadingPaint``.
"""

from __future__ import annotations

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
        raise NotImplementedError(
            "Type5ShadingPaint.create_context wires up with the renderer cluster"
        )
