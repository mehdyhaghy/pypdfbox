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
        """Return a :class:`PatchMeshesShadingContext` for this Coons-patch
        mesh. Mirrors upstream ``Type6ShadingPaint.createContext`` which
        constructs a ``Type6ShadingContext``. pypdfbox uses the shared
        :class:`PatchMeshesShadingContext` (Type 6 / 7) parameterised by
        ``control_points=12`` (Coons)."""
        _ = (user_bounds, hints)
        from .patch_meshes_shading_context import (  # noqa: PLC0415
            PatchMeshesShadingContext,
        )

        bounds = tuple(device_bounds) if device_bounds is not None else None
        return PatchMeshesShadingContext(
            self.shading,
            cm,
            xform,
            self.matrix,
            bounds,
            control_points=12,
        )
