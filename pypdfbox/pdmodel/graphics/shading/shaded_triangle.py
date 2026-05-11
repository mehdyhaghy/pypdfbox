"""Triangle (possibly degenerate) carrying per-vertex colour.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.ShadedTriangle``.
"""

from __future__ import annotations

from collections.abc import Sequence

from .line import Line


class ShadedTriangle:
    """A triangle described by 3 corner points and 3 corner colours."""

    def __init__(
        self,
        p: Sequence[tuple[float, float]],
        c: Sequence[Sequence[float]],
    ) -> None:
        self.corner: list[tuple[float, float]] = [
            (float(pt[0]), float(pt[1])) for pt in p
        ]
        self.color: list[list[float]] = [list(comp) for comp in c]
        self._area: float = self.get_area(self.corner[0], self.corner[1], self.corner[2])
        self._degree: int = self.calc_deg(self.corner)

        if self._degree == 2:
            corner0, corner1, corner2 = self.corner[0], self.corner[1], self.corner[2]
            if self.overlaps(corner1, corner2) and not self.overlaps(corner0, corner2):
                p0 = (round(corner0[0]), round(corner0[1]))
                p1 = (round(corner2[0]), round(corner2[1]))
                self._line: Line | None = Line(p0, p1, self.color[0], self.color[2])
            else:
                p0 = (round(corner1[0]), round(corner1[1]))
                p1 = (round(corner2[0]), round(corner2[1]))
                self._line = Line(p0, p1, self.color[1], self.color[2])
        else:
            self._line = None

        self._v0: float = self.edge_equation_value(self.corner[0], self.corner[1], self.corner[2])
        self._v1: float = self.edge_equation_value(self.corner[1], self.corner[2], self.corner[0])
        self._v2: float = self.edge_equation_value(self.corner[2], self.corner[0], self.corner[1])

    @staticmethod
    def calc_deg(p: Sequence[tuple[float, float]]) -> int:
        unique: set[tuple[int, int]] = set()
        for pt in p:
            unique.add((round(pt[0] * 1000), round(pt[1] * 1000)))
        return len(unique)

    def get_deg(self) -> int:
        return self._degree

    def get_boundary(self) -> list[int]:
        """Return ``[xmin, xmax, ymin, ymax]`` rounded to ints."""
        xs = [round(c[0]) for c in self.corner]
        ys = [round(c[1]) for c in self.corner]
        return [min(xs), max(xs), min(ys), max(ys)]

    def get_line(self) -> Line | None:
        return self._line

    def contains(self, p: tuple[float, float]) -> bool:
        if self._degree == 1:
            return (
                self.overlaps(self.corner[0], p)
                or self.overlaps(self.corner[1], p)
                or self.overlaps(self.corner[2], p)
            )
        if self._degree == 2 and self._line is not None:
            tp = (round(p[0]), round(p[1]))
            return tp in self._line.line_points

        pv0 = self.edge_equation_value(p, self.corner[1], self.corner[2])
        if pv0 * self._v0 < 0:
            return False
        pv1 = self.edge_equation_value(p, self.corner[2], self.corner[0])
        if pv1 * self._v1 < 0:
            return False
        pv2 = self.edge_equation_value(p, self.corner[0], self.corner[1])
        return pv2 * self._v2 >= 0

    @staticmethod
    def overlaps(p0: tuple[float, float], p1: tuple[float, float]) -> bool:
        return abs(p0[0] - p1[0]) < 0.001 and abs(p0[1] - p1[1]) < 0.001

    @staticmethod
    def edge_equation_value(
        p: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
    ) -> float:
        return (p2[1] - p1[1]) * (p[0] - p1[0]) - (p2[0] - p1[0]) * (p[1] - p1[1])

    @staticmethod
    def get_area(
        a: tuple[float, float], b: tuple[float, float], c: tuple[float, float],
    ) -> float:
        return abs(
            (c[0] - b[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (c[1] - b[1])
        ) / 2.0

    def calc_color(self, p: tuple[float, float]) -> list[float]:
        number_of_color_components = len(self.color[0])
        if self._degree == 1:
            return [
                (self.color[0][i] + self.color[1][i] + self.color[2][i]) / 3.0
                for i in range(number_of_color_components)
            ]
        if self._degree == 2 and self._line is not None:
            tp = (round(p[0]), round(p[1]))
            return self._line.calc_color(tp)
        if self._area == 0:
            return list(self.color[0])
        aw = self.get_area(p, self.corner[1], self.corner[2]) / self._area
        bw = self.get_area(p, self.corner[2], self.corner[0]) / self._area
        cw = self.get_area(p, self.corner[0], self.corner[1]) / self._area
        return [
            self.color[0][i] * aw + self.color[1][i] * bw + self.color[2][i] * cw
            for i in range(number_of_color_components)
        ]

    def to_string(self) -> str:
        return " ".join(f"Point2D.Double[{c[0]}, {c[1]}]" for c in self.corner)

    def __repr__(self) -> str:
        return self.to_string()
