"""Tensor-product patch for Type 7 shading.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.TensorPatch``.
"""

from __future__ import annotations

from collections.abc import Sequence

from .patch import Patch, _CoordinateColorPair
from .shaded_triangle import ShadedTriangle


class TensorPatch(Patch):
    """A 16-control-point tensor-product Bezier patch."""

    def __init__(
        self,
        tcp: Sequence[tuple[float, float]],
        color: Sequence[Sequence[float]],
    ) -> None:
        super().__init__(color)
        self.control_points = self.reshape_control_points(tcp)
        self.level = self.calc_level()
        self.list_of_triangles = self.get_triangles()

    @staticmethod
    def reshape_control_points(
        tcp: Sequence[tuple[float, float]],
    ) -> list[list[tuple[float, float]]]:
        square: list[list[tuple[float, float]]] = [[(0.0, 0.0)] * 4 for _ in range(4)]
        for i in range(4):
            square[0][i] = tcp[i]
            square[3][i] = tcp[9 - i]
        for i in range(1, 3):
            square[i][0] = tcp[12 - i]
            square[i][2] = tcp[12 + i]
            square[i][3] = tcp[3 + i]
        square[1][1] = tcp[12]
        square[2][1] = tcp[15]
        return square

    def calc_level(self) -> list[int]:
        level = [4, 4]
        ctl_c1 = [self.control_points[j][0] for j in range(4)]
        ctl_c2 = [self.control_points[j][3] for j in range(4)]
        if self.is_edge_a_line(ctl_c1) and self.is_edge_a_line(ctl_c2):
            if (
                self.is_on_same_side_cc(self.control_points[1][1])
                or self.is_on_same_side_cc(self.control_points[1][2])
                or self.is_on_same_side_cc(self.control_points[2][1])
                or self.is_on_same_side_cc(self.control_points[2][2])
            ):
                pass
            else:
                lc1 = self.get_len(ctl_c1[0], ctl_c1[3])
                lc2 = self.get_len(ctl_c2[0], ctl_c2[3])
                if lc1 > 800 or lc2 > 800:
                    pass
                elif lc1 > 400 or lc2 > 400:
                    level[0] = 3
                elif lc1 > 200 or lc2 > 200:
                    level[0] = 2
                else:
                    level[0] = 1

        if self.is_edge_a_line(self.control_points[0]) and self.is_edge_a_line(
            self.control_points[3]
        ):
            if (
                self.is_on_same_side_dd(self.control_points[1][1])
                or self.is_on_same_side_dd(self.control_points[1][2])
                or self.is_on_same_side_dd(self.control_points[2][1])
                or self.is_on_same_side_dd(self.control_points[2][2])
            ):
                pass
            else:
                ld1 = self.get_len(self.control_points[0][0], self.control_points[0][3])
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

    def is_on_same_side_cc(self, p: tuple[float, float]) -> bool:
        cc = self.edge_equation_value(
            p, self.control_points[0][0], self.control_points[3][0]
        ) * self.edge_equation_value(
            p, self.control_points[0][3], self.control_points[3][3]
        )
        return cc > 0

    def is_on_same_side_dd(self, p: tuple[float, float]) -> bool:
        dd = self.edge_equation_value(
            p, self.control_points[0][0], self.control_points[0][3]
        ) * self.edge_equation_value(
            p, self.control_points[3][0], self.control_points[3][3]
        )
        return dd > 0

    def get_triangles(self) -> list[ShadedTriangle]:
        patch_cc = self.get_patch_coordinates_color()
        return self.get_shaded_triangles(patch_cc)

    def get_flag1_edge(self) -> list[tuple[float, float]]:
        return [self.control_points[i][3] for i in range(4)]

    def get_flag2_edge(self) -> list[tuple[float, float]]:
        return [self.control_points[3][3 - i] for i in range(4)]

    def get_flag3_edge(self) -> list[tuple[float, float]]:
        return [self.control_points[3 - i][0] for i in range(4)]

    def get_patch_coordinates_color(self) -> list[list[_CoordinateColorPair]]:
        n_color_components = len(self.corner_color[0])
        bernstein_u = self.get_bernstein_polynomials(self.level[0])
        sz_u = len(bernstein_u[0])
        bernstein_v = self.get_bernstein_polynomials(self.level[1])
        sz_v = len(bernstein_v[0])
        patch_cc: list[list[_CoordinateColorPair]] = [
            [_CoordinateColorPair((0.0, 0.0), [0.0] * n_color_components) for _ in range(sz_u)]
            for _ in range(sz_v)
        ]

        step_u = 1.0 / (sz_u - 1) if sz_u > 1 else 0.0
        step_v = 1.0 / (sz_v - 1) if sz_v > 1 else 0.0
        v = -step_v
        for k in range(sz_v):
            v += step_v
            u = -step_u
            for ll in range(sz_u):
                tmp_x = 0.0
                tmp_y = 0.0
                for i in range(4):
                    for j in range(4):
                        tmp_x += (
                            self.control_points[i][j][0]
                            * bernstein_u[i][ll]
                            * bernstein_v[j][k]
                        )
                        tmp_y += (
                            self.control_points[i][j][1]
                            * bernstein_u[i][ll]
                            * bernstein_v[j][k]
                        )
                u += step_u
                color = [
                    (1 - v)
                    * ((1 - u) * self.corner_color[0][ci] + u * self.corner_color[3][ci])
                    + v
                    * ((1 - u) * self.corner_color[1][ci] + u * self.corner_color[2][ci])
                    for ci in range(n_color_components)
                ]
                patch_cc[k][ll] = _CoordinateColorPair((tmp_x, tmp_y), color)
        return patch_cc

    @staticmethod
    def get_bernstein_polynomials(lvl: int) -> list[list[float]]:
        sz = (1 << lvl) + 1
        poly: list[list[float]] = [[0.0] * sz for _ in range(4)]
        step = 1.0 / (sz - 1) if sz > 1 else 0.0
        t = -step
        for i in range(sz):
            t += step
            one_minus_t = 1.0 - t
            poly[0][i] = one_minus_t * one_minus_t * one_minus_t
            poly[1][i] = 3 * t * one_minus_t * one_minus_t
            poly[2][i] = 3 * t * t * one_minus_t
            poly[3][i] = t * t * t
        return poly
