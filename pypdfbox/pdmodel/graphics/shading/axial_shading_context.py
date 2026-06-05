"""Paint context for Type 2 (axial) shading.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.AxialShadingContext``.
"""

from __future__ import annotations

import math
from typing import Any

from .shading_context import ShadingContext


def _read_extend(extend: Any) -> list[bool]:
    """Normalise a shading's ``/Extend`` to ``[start, end]`` booleans.

    Upstream ``AxialShadingContext`` reads a raw ``COSArray`` of two
    ``COSBoolean`` entries (``((COSBoolean) extend.getObject(i)).getValue()``).
    pypdfbox's ``PDShadingType2.get_extend`` / ``PDShadingType3.get_extend``
    return a plain ``(start, end)`` tuple of booleans instead, so accept both
    shapes (plus ``None`` → spec default ``[false false]``)."""
    if extend is None:
        return [False, False]
    if hasattr(extend, "get_object"):
        return [
            bool(extend.get_object(0).get_value()),
            bool(extend.get_object(1).get_value()),
        ]
    return [bool(extend[0]), bool(extend[1])]


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

        self._extend = _read_extend(shading.get_extend())

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
        """Generate a ``PIL.Image`` raster covering ``(x, y, w, h)`` in
        device space. Mirrors upstream
        ``AxialShadingContext.getRaster`` (AxialShadingContext.java
        line 167) — solves the linear-axis input value, applies extend /
        background rules, and looks up the colour table.

        pypdfbox returns an RGBA Pillow image; the upstream Java surface
        is a ``WritableRaster``. Transparent (alpha=0) pixels are emitted
        for the "continue" branches where no background colour is set."""
        from PIL import Image  # noqa: PLC0415

        bg = self.get_background()
        rgb_bg = self.get_rgb_background()
        coords = self._coords
        domain = self._domain
        extend = self._extend
        denom = self._denom
        factor = self._factor
        table = self._color_table

        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        pixels = out.load()
        for j in range(h):
            for i in range(w):
                use_background = False
                px = float(x + i)
                py = float(y + j)
                input_value = (
                    self._x1x0 * (px - coords[0]) + self._y1y0 * (py - coords[1])
                )
                if denom == 0:
                    if bg is None:
                        continue
                    use_background = True
                else:
                    input_value /= denom
                if input_value < 0:
                    if extend[0]:
                        input_value = domain[0]
                    elif bg is None:
                        continue
                    else:
                        use_background = True
                elif input_value > 1:
                    if extend[1]:
                        input_value = domain[1]
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
