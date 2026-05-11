"""Common context for Type 6 / Type 7 patch-mesh shadings.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.PatchMeshesShadingContext``.
"""

from __future__ import annotations

from typing import Any

from .patch import Patch
from .triangle_based_shading_context import TriangleBasedShadingContext


class PatchMeshesShadingContext(TriangleBasedShadingContext):
    """Shared logic for the two patch-mesh shading types."""

    def __init__(
        self,
        shading: Any,
        color_model: Any,
        xform: Any,
        matrix: Any,
        device_bounds: tuple[int, int, int, int] | None,
        control_points: int,
    ) -> None:
        super().__init__(shading, color_model, xform, matrix)
        self._patch_list: list[Patch] = list(
            shading.collect_patches(xform, matrix, control_points)
        )
        if device_bounds is not None:
            self.create_pixel_table(device_bounds)

    def calc_pixel_table_array(
        self, device_bounds: tuple[int, int, int, int],
    ) -> list[list[int]]:
        _x, _y, w, h = device_bounds
        initial = self.get_rgb_background() if self.get_background() is not None else -1
        array: list[list[int]] = [[initial] * (h + 1) for _ in range(w + 1)]
        for patch in self._patch_list:
            self.calc_pixel_table(patch.list_of_triangles, array, device_bounds)
        return array

    def is_data_empty(self) -> bool:
        return not self._patch_list

    def dispose(self) -> None:
        self._patch_list = []
        super().dispose()
