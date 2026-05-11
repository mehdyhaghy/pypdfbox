"""Paint context for Type 2 (axial) shading.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.AxialShadingContext``.
"""

from __future__ import annotations

import math
from typing import Any

from .shading_context import ShadingContext


class AxialShadingContext(ShadingContext):
    """Generates the colour table along an axial-gradient line."""

    def __init__(
        self,
        shading: Any,
        color_model: Any,
        xform: Any,
        matrix: Any,
        device_bounds: Any,
    ) -> None:
        super().__init__(shading, color_model, xform, matrix)
        self._axial_shading_type = shading
        coords_arr = shading.get_coords()
        if coords_arr is not None:
            self._coords: list[float] = list(coords_arr.to_float_array())
        else:
            self._coords = [0.0] * 4

        domain = shading.get_domain()
        if domain is not None:
            self._domain: list[float] = list(domain.to_float_array())
        else:
            self._domain = [0.0, 1.0]

        extend = shading.get_extend()
        if extend is not None:
            self._extend = [
                bool(extend.get_object(0).get_value()),
                bool(extend.get_object(1).get_value()),
            ]
        else:
            self._extend = [False, False]

        self._x1x0 = self._coords[2] - self._coords[0]
        self._y1y0 = self._coords[3] - self._coords[1]
        self._d1d0 = self._domain[1] - self._domain[0]
        self._denom = self._x1x0 * self._x1x0 + self._y1y0 * self._y1y0

        # Compute step factor from device bounds.
        try:
            min_x, max_x = device_bounds[0], device_bounds[2]
            min_y, max_y = device_bounds[1], device_bounds[3]
            dist = math.hypot(max_x - min_x, max_y - min_y)
        except (TypeError, IndexError):
            dist = 1.0
        self._factor: int = max(0, int(math.ceil(dist)))
        self._color_table: list[int] = self.calc_color_table()

    def calc_color_table(self) -> list[int]:
        factor = self._factor
        table = [0] * (factor + 1)
        if factor == 0 or self._d1d0 == 0:
            values = self._axial_shading_type.eval_function(self._domain[0])
            table[0] = self.convert_to_rgb(list(values))
        else:
            for i in range(factor + 1):
                t = self._domain[0] + self._d1d0 * i / factor
                values = self._axial_shading_type.eval_function(t)
                table[i] = self.convert_to_rgb(list(values))
        return table

    def dispose(self) -> None:
        super().dispose()
        self._axial_shading_type = None

    def get_coords(self) -> list[float]:
        return list(self._coords)

    def get_domain(self) -> list[float]:
        return list(self._domain)

    def get_extend(self) -> list[bool]:
        return list(self._extend)

    def get_function(self) -> Any:
        return self._axial_shading_type.get_function()

    def get_raster(self, x: int, y: int, w: int, h: int) -> Any:
        # Full pixel raster output requires an inverse transform from device space
        # to shading space; pypdfbox renderer is not wired in yet. The render math
        # is exercised by the colour table; pixel emission is deferred.
        raise NotImplementedError(
            "AxialShadingContext.get_raster is wired up with the renderer cluster"
        )
