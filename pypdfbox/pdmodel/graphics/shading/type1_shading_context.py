"""Paint context for Type 1 (function-based) shading.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.Type1ShadingContext``.
"""

from __future__ import annotations

from typing import Any

from .shading_context import ShadingContext


class Type1ShadingContext(ShadingContext):
    """Function-based shading paint context."""

    def __init__(
        self,
        shading: Any,
        color_model: Any,
        xform: Any,
        matrix: Any,
    ) -> None:
        super().__init__(shading, color_model, xform, matrix)
        self._type1_shading_type = shading
        domain = shading.get_domain()
        if domain is not None:
            self._domain: list[float] = list(domain.to_float_array())
        else:
            self._domain = [0.0, 1.0, 0.0, 1.0]

    def dispose(self) -> None:
        super().dispose()
        self._type1_shading_type = None

    def get_domain(self) -> list[float]:
        return list(self._domain)

    def get_raster(self, x: int, y: int, w: int, h: int) -> Any:
        raise NotImplementedError(
            "Type1ShadingContext.get_raster is wired up with the renderer cluster"
        )
