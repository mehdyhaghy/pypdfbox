"""Rasterised line segment used by triangle-based shadings.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.Line``.

The line keeps two endpoint colours and uses Bresenham's algorithm to
compute the set of integer-coordinate points along the segment. Colours
of intermediate points are computed by linear interpolation along the
dominant axis.
"""

from __future__ import annotations

from collections.abc import Sequence


class Line:
    """A 2D line described by two coloured integer endpoints."""

    __slots__ = ("point0", "point1", "color0", "color1", "line_points")

    def __init__(
        self,
        p0: tuple[int, int],
        p1: tuple[int, int],
        c0: Sequence[float],
        c1: Sequence[float],
    ) -> None:
        self.point0: tuple[int, int] = (int(p0[0]), int(p0[1]))
        self.point1: tuple[int, int] = (int(p1[0]), int(p1[1]))
        self.color0: list[float] = [float(v) for v in c0]
        self.color1: list[float] = [float(v) for v in c1]
        self.line_points: set[tuple[int, int]] = self.calc_line(
            self.point0[0], self.point0[1], self.point1[0], self.point1[1],
        )

    @staticmethod
    def calc_line(x0: int, y0: int, x1: int, y1: int) -> set[tuple[int, int]]:
        """Bresenham's line algorithm yielding the rasterised pixel set."""
        points: set[tuple[int, int]] = set()
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            points.add((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy
        return points

    def calc_color(self, p: tuple[int, int]) -> list[float]:
        """Linearly interpolate this segment's colour at point ``p``."""
        x0, y0 = self.point0
        x1, y1 = self.point1
        if x0 == x1 and y0 == y1:
            return list(self.color0)
        number_of_color_components = len(self.color0)
        pc = [0.0] * number_of_color_components
        if x0 == x1:
            length = float(y1 - y0)
            for i in range(number_of_color_components):
                pc[i] = (
                    self.color0[i] * (y1 - p[1]) / length
                    + self.color1[i] * (p[1] - y0) / length
                )
        else:
            length = float(x1 - x0)
            for i in range(number_of_color_components):
                pc[i] = (
                    self.color0[i] * (x1 - p[0]) / length
                    + self.color1[i] * (p[0] - x0) / length
                )
        return pc
