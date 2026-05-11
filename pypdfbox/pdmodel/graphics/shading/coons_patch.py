"""Coons surface patch for Type 6 shading.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.CoonsPatch``.
"""

from __future__ import annotations

from collections.abc import Sequence

from .cubic_bezier_curve import CubicBezierCurve
from .patch import Patch, _CoordinateColorPair
from .shaded_triangle import ShadedTriangle


class CoonsPatch(Patch):
    """A 12-control-point Coons patch."""

    def __init__(
        self,
        points: Sequence[tuple[float, float]],
        color: Sequence[Sequence[float]],
    ) -> None:
        super().__init__(color)
        self.control_points = self.reshape_control_points(points)
        self.level = self.calc_level()
        self.list_of_triangles = self.get_triangles()

    @staticmethod
    def reshape_control_points(
        points: Sequence[tuple[float, float]],
    ) -> list[list[tuple[float, float]]]:
        four_rows: list[list[tuple[float, float]]] = [[(0.0, 0.0)] * 4 for _ in range(4)]
        # d1 / c2 / d2 / c1 mirror upstream ordering.
        four_rows[2] = [points[0], points[1], points[2], points[3]]
        four_rows[1] = [points[3], points[4], points[5], points[6]]
        four_rows[3] = [points[9], points[8], points[7], points[6]]
        four_rows[0] = [points[0], points[11], points[10], points[9]]
        return four_rows

    def calc_level(self) -> list[int]:
        level = [4, 4]
        if self.is_edge_a_line(self.control_points[0]) and self.is_edge_a_line(
            self.control_points[1]
        ):
            lc1 = self.get_len(self.control_points[0][0], self.control_points[0][3])
            lc2 = self.get_len(self.control_points[1][0], self.control_points[1][3])
            if lc1 > 800 or lc2 > 800:
                pass
            elif lc1 > 400 or lc2 > 400:
                level[0] = 3
            elif lc1 > 200 or lc2 > 200:
                level[0] = 2
            else:
                level[0] = 1
        if self.is_edge_a_line(self.control_points[2]) and self.is_edge_a_line(
            self.control_points[3]
        ):
            ld1 = self.get_len(self.control_points[2][0], self.control_points[2][3])
            ld2 = self.get_len(self.control_points[3][0], self.control_points[3][3])
            if ld1 > 800 or ld2 > 800:
                pass
            elif ld1 > 400 or ld2 > 400:
                level[1] = 3
            elif ld1 > 200 or ld2 > 200:
                level[1] = 2
            else:
                level[1] = 1
        return level

    def get_triangles(self) -> list[ShadedTriangle]:
        e_c1 = CubicBezierCurve(self.control_points[0], self.level[0])
        e_c2 = CubicBezierCurve(self.control_points[1], self.level[0])
        e_d1 = CubicBezierCurve(self.control_points[2], self.level[1])
        e_d2 = CubicBezierCurve(self.control_points[3], self.level[1])
        patch_cc = self.get_patch_coordinates_color(e_c1, e_c2, e_d1, e_d2)
        return self.get_shaded_triangles(patch_cc)

    def get_flag1_edge(self) -> list[tuple[float, float]]:
        return list(self.control_points[1])

    def get_flag2_edge(self) -> list[tuple[float, float]]:
        row = self.control_points[3]
        return [row[3], row[2], row[1], row[0]]

    def get_flag3_edge(self) -> list[tuple[float, float]]:
        row = self.control_points[0]
        return [row[3], row[2], row[1], row[0]]

    def get_patch_coordinates_color(
        self,
        c1: CubicBezierCurve,
        c2: CubicBezierCurve,
        d1: CubicBezierCurve,
        d2: CubicBezierCurve,
    ) -> list[list[_CoordinateColorPair]]:
        curve_c1 = c1.get_cubic_bezier_curve()
        curve_c2 = c2.get_cubic_bezier_curve()
        curve_d1 = d1.get_cubic_bezier_curve()
        curve_d2 = d2.get_cubic_bezier_curve()

        n_color_components = len(self.corner_color[0])
        sz_v = len(curve_d1)
        sz_u = len(curve_c1)

        patch_cc: list[list[_CoordinateColorPair]] = [
            [_CoordinateColorPair((0.0, 0.0), [0.0] * n_color_components) for _ in range(sz_u)]
            for _ in range(sz_v)
        ]

        step_v = 1.0 / (sz_v - 1) if sz_v > 1 else 0.0
        step_u = 1.0 / (sz_u - 1) if sz_u > 1 else 0.0

        v = -step_v
        for i in range(sz_v):
            v += step_v
            u = -step_u
            for j in range(sz_u):
                u += step_u
                scx = (1 - v) * curve_c1[j][0] + v * curve_c2[j][0]
                scy = (1 - v) * curve_c1[j][1] + v * curve_c2[j][1]
                sdx = (1 - u) * curve_d1[i][0] + u * curve_d2[i][0]
                sdy = (1 - u) * curve_d1[i][1] + u * curve_d2[i][1]
                sbx = (1 - v) * (
                    (1 - u) * self.control_points[0][0][0]
                    + u * self.control_points[0][3][0]
                ) + v * (
                    (1 - u) * self.control_points[1][0][0]
                    + u * self.control_points[1][3][0]
                )
                sby = (1 - v) * (
                    (1 - u) * self.control_points[0][0][1]
                    + u * self.control_points[0][3][1]
                ) + v * (
                    (1 - u) * self.control_points[1][0][1]
                    + u * self.control_points[1][3][1]
                )

                sx = scx + sdx - sbx
                sy = scy + sdy - sby

                color = [
                    (1 - v)
                    * ((1 - u) * self.corner_color[0][ci] + u * self.corner_color[3][ci])
                    + v
                    * ((1 - u) * self.corner_color[1][ci] + u * self.corner_color[2][ci])
                    for ci in range(n_color_components)
                ]
                patch_cc[i][j] = _CoordinateColorPair((sx, sy), color)
        return patch_cc
