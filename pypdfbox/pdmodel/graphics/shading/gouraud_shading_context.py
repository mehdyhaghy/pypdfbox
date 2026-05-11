"""Common context for Type 4 / Type 5 Gouraud-triangle shadings.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.GouraudShadingContext``.
"""

from __future__ import annotations

from typing import Any

from .shaded_triangle import ShadedTriangle
from .triangle_based_shading_context import TriangleBasedShadingContext


class GouraudShadingContext(TriangleBasedShadingContext):
    """Shared logic for the two Gouraud shading types."""

    def __init__(
        self,
        shading: Any,
        color_model: Any,
        xform: Any,
        matrix: Any,
    ) -> None:
        super().__init__(shading, color_model, xform, matrix)
        self._triangle_list: list[ShadedTriangle] = []

    def set_triangle_list(self, triangle_list: list[ShadedTriangle]) -> None:
        self._triangle_list = list(triangle_list)

    def calc_pixel_table_array(
        self, device_bounds: tuple[int, int, int, int],
    ) -> list[list[int]]:
        _x, _y, w, h = device_bounds
        initial = self.get_rgb_background() if self.get_background() is not None else -1
        array: list[list[int]] = [[initial] * (h + 1) for _ in range(w + 1)]
        self.calc_pixel_table(self._triangle_list, array, device_bounds)
        return array

    def is_data_empty(self) -> bool:
        return not self._triangle_list

    def dispose(self) -> None:
        self._triangle_list = []
        super().dispose()
