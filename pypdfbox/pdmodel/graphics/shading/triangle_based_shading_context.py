"""Common base for shading types 4, 5, 6 and 7.

Mirrors PDFBox
``org.apache.pdfbox.pdmodel.graphics.shading.TriangleBasedShadingContext``.
"""

from __future__ import annotations

from typing import Any

from .line import Line
from .shaded_triangle import ShadedTriangle
from .shading_context import ShadingContext


class TriangleBasedShadingContext(ShadingContext):
    """Intermediate context performing per-triangle raster colour tables."""

    def __init__(
        self,
        shading: Any,
        color_model: Any,
        xform: Any,
        matrix: Any,
    ) -> None:
        super().__init__(shading, color_model, xform, matrix)
        self._pixel_table_array: list[list[int]] | None = None
        self._x_offset: int = 0
        self._y_offset: int = 0

    # ------------------------------------------------------------------
    # Pixel table plumbing
    # ------------------------------------------------------------------
    def create_pixel_table(self, device_bounds: tuple[int, int, int, int]) -> None:
        """Compute the pixel-colour table covering ``device_bounds``.

        ``device_bounds`` is ``(x, y, width, height)`` in device space.
        """
        x, y, width, height = device_bounds
        self._x_offset = -x
        self._y_offset = -y
        self._pixel_table_array = self.calc_pixel_table_array(device_bounds)

    def calc_pixel_table_array(
        self, device_bounds: tuple[int, int, int, int],
    ) -> list[list[int]]:
        """Abstract — concrete subclasses (Gouraud / PatchMeshes)
        materialise their triangle / patch list and populate the pixel
        table. Mirrors upstream
        ``TriangleBasedShadingContext.calcPixelTableArray``."""
        _ = device_bounds
        raise NotImplementedError(
            "TriangleBasedShadingContext.calc_pixel_table_array is abstract"
        )

    def is_data_empty(self) -> bool:
        """Abstract — subclasses report whether their decoded triangle
        / patch list is empty. Mirrors upstream
        ``TriangleBasedShadingContext.isDataEmpty``."""
        _ = self
        raise NotImplementedError(
            "TriangleBasedShadingContext.is_data_empty is abstract"
        )

    # ------------------------------------------------------------------
    # Triangle rasterisation
    # ------------------------------------------------------------------
    def calc_pixel_table(
        self,
        triangle_list: list[ShadedTriangle],
        array: list[list[int]],
        device_bounds: tuple[int, int, int, int],
    ) -> list[list[int]]:
        dx, dy, dw, dh = device_bounds
        for tri in triangle_list:
            degree = tri.get_deg()
            if degree == 2:
                self.add_line_points(tri.get_line(), array)
                continue
            boundary = tri.get_boundary()
            boundary[0] = max(boundary[0], dx)
            boundary[1] = min(boundary[1], dx + dw)
            boundary[2] = max(boundary[2], dy)
            boundary[3] = min(boundary[3], dy + dh)
            for x in range(boundary[0], boundary[1] + 1):
                for y in range(boundary[2], boundary[3] + 1):
                    p = (x, y)
                    if tri.contains(p):
                        self.add_value_to_array(
                            p,
                            self.eval_function_and_convert_to_rgb(tri.calc_color(p)),
                            array,
                        )
            # "fatten" triangle edges with Bresenham.
            p0 = (round(tri.corner[0][0]), round(tri.corner[0][1]))
            p1 = (round(tri.corner[1][0]), round(tri.corner[1][1]))
            p2 = (round(tri.corner[2][0]), round(tri.corner[2][1]))
            self.add_line_points(Line(p0, p1, tri.color[0], tri.color[1]), array)
            self.add_line_points(Line(p1, p2, tri.color[1], tri.color[2]), array)
            self.add_line_points(Line(p2, p0, tri.color[2], tri.color[0]), array)
        return array

    def add_line_points(self, line: Line | None, array: list[list[int]]) -> None:
        if line is None:
            return
        for p in line.line_points:
            self.add_value_to_array(
                p, self.eval_function_and_convert_to_rgb(line.calc_color(p)), array
            )

    def add_value_to_array(
        self, p: tuple[int, int], value: int, array: list[list[int]],
    ) -> None:
        x_index = p[0] + self._x_offset
        y_index = p[1] + self._y_offset
        if x_index < 0 or y_index < 0 or x_index >= len(array) or y_index >= len(array[0]):
            return
        array[x_index][y_index] = value

    def get_value_from_array(self, x: int, y: int) -> int:
        if self._pixel_table_array is None:
            return -1
        x_index = x + self._x_offset
        y_index = y + self._y_offset
        if (
            x_index < 0
            or y_index < 0
            or x_index >= len(self._pixel_table_array)
            or y_index >= len(self._pixel_table_array[0])
        ):
            return -1
        return self._pixel_table_array[x_index][y_index]

    def eval_function_and_convert_to_rgb(self, values: list[float]) -> int:
        shading = self.get_shading()
        if shading.get_function() is not None:
            values = list(shading.eval_function(values))
        return self.convert_to_rgb(values)

    def get_raster(self, x: int, y: int, w: int, h: int) -> Any:
        """Generate a ``PIL.Image`` raster covering ``(x, y, w, h)`` in
        device space using the precomputed pixel table. Mirrors upstream
        ``TriangleBasedShadingContext.getRaster``
        (TriangleBasedShadingContext.java line 199) — writes only where
        ``getValueFromArray`` returns a non-negative RGB; pixels outside
        the table read as transparent."""
        from PIL import Image  # noqa: PLC0415

        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if self.is_data_empty() and self.get_background() is None:
            return out
        pixels = out.load()
        for row in range(h):
            for col in range(w):
                value = self.get_value_from_array(x + col, row + y)
                if value >= 0:
                    r = value & 0xFF
                    g = (value >> 8) & 0xFF
                    b = (value >> 16) & 0xFF
                    pixels[col, row] = (r, g, b, 255)
        return out
