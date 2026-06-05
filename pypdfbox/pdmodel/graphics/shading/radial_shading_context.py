"""Paint context for Type 3 (radial) shading.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.RadialShadingContext``.
"""

from __future__ import annotations

import math
from typing import Any

from .axial_shading_context import _read_extend
from .shading_context import ShadingContext


class RadialShadingContext(ShadingContext):
    """Generates the colour table along a radial-gradient axis."""

    def __init__(
        self,
        shading: Any,
        color_model: Any,
        xform: Any,
        matrix: Any,
        device_bounds: Any,
    ) -> None:
        super().__init__(shading, color_model, xform, matrix)
        self._radial_shading_type = shading
        coords_arr = shading.get_coords()
        if coords_arr is not None:
            self._coords: list[float] = list(coords_arr.to_float_array())
        else:
            self._coords = [0.0] * 6
        domain = shading.get_domain()
        if domain is not None:
            self._domain: list[float] = list(domain.to_float_array())
        else:
            self._domain = [0.0, 1.0]
        self._extend = _read_extend(shading.get_extend())

        self._x1x0 = self._coords[3] - self._coords[0]
        self._y1y0 = self._coords[4] - self._coords[1]
        self._r1r0 = self._coords[5] - self._coords[2]
        self._r0pow2 = self._coords[2] * self._coords[2]
        self._denom = (
            self._x1x0 * self._x1x0 + self._y1y0 * self._y1y0 - self._r1r0 * self._r1r0
        )
        self._d1d0 = self._domain[1] - self._domain[0]

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
            values = self._radial_shading_type.eval_function(self._domain[0])
            table[0] = self.convert_to_rgb(list(values))
        else:
            for i in range(factor + 1):
                t = self._domain[0] + self._d1d0 * i / factor
                values = self._radial_shading_type.eval_function(t)
                table[i] = self.convert_to_rgb(list(values))
        return table

    def dispose(self) -> None:
        super().dispose()
        self._radial_shading_type = None

    def get_coords(self) -> list[float]:
        return list(self._coords)

    def get_domain(self) -> list[float]:
        return list(self._domain)

    def get_extend(self) -> list[bool]:
        return list(self._extend)

    def get_function(self) -> Any:
        return self._radial_shading_type.get_function()

    def calculate_input_values(self, x: float, y: float) -> tuple[float, float]:
        """Solve the quadratic constraint per Adobe Technical Note #5600."""
        coords = self._coords
        p = (
            -(x - coords[0]) * self._x1x0
            - (y - coords[1]) * self._y1y0
            - coords[2] * self._r1r0
        )
        q = (x - coords[0]) ** 2 + (y - coords[1]) ** 2 - self._r0pow2
        discriminant = p * p - self._denom * q
        if discriminant < 0:
            return (float("nan"), float("nan"))
        root = math.sqrt(discriminant)
        if self._denom == 0:
            return (float("nan"), float("nan"))
        root1 = (-p + root) / self._denom
        root2 = (-p - root) / self._denom
        if self._denom < 0:
            return (root1, root2)
        return (root2, root1)

    def get_raster(self, x: int, y: int, w: int, h: int) -> Any:
        """Generate a ``PIL.Image`` raster covering ``(x, y, w, h)`` in
        device space. Mirrors upstream
        ``RadialShadingContext.getRaster`` (RadialShadingContext.java
        line 170) — solves the quadratic input value, applies extend /
        background rules, picks the larger valid root, and looks up the
        colour table."""
        from PIL import Image  # noqa: PLC0415

        bg = self.get_background()
        rgb_bg = self.get_rgb_background()
        coords = self._coords
        extend = self._extend
        factor = self._factor
        table = self._color_table

        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        pixels = out.load()
        for j in range(h):
            for i in range(w):
                use_background = False
                px = float(x + i)
                py = float(y + j)
                roots = self.calculate_input_values(px, py)
                input_value = -1.0
                r0 = roots[0]
                r1 = roots[1]
                if math.isnan(r0) and math.isnan(r1):
                    if bg is None:
                        continue
                    use_background = True
                else:
                    if 0 <= r0 <= 1:
                        input_value = max(r0, r1) if 0 <= r1 <= 1 else r0
                    elif 0 <= r1 <= 1:
                        input_value = r1
                    elif extend[0] and extend[1]:
                        input_value = max(r0, r1)
                    elif extend[0]:
                        input_value = r0
                    elif extend[1]:
                        input_value = r1
                    elif bg is not None:
                        use_background = True
                    else:
                        continue
                    if not use_background:
                        if input_value > 1:
                            if extend[1] and coords[5] > 0:
                                input_value = 1.0
                            elif bg is None:
                                continue
                            else:
                                use_background = True
                        elif input_value < 0:
                            if extend[0] and coords[2] > 0:
                                input_value = 0.0
                            elif bg is None:
                                continue
                            else:
                                use_background = True
                if use_background:
                    value = rgb_bg
                else:
                    key = int(input_value * factor)
                    if key < 0:
                        key = 0
                    elif key > factor:
                        key = factor
                    value = table[key]
                r = value & 0xFF
                g = (value >> 8) & 0xFF
                b = (value >> 16) & 0xFF
                pixels[i, j] = (r, g, b, 255)
        return out
