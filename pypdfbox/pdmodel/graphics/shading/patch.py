"""Abstract patch base class for Type 6 / 7 mesh shadings.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.Patch``.

A patch carries 4 corner colours and an edge-arranged grid of cubic
Bezier control points. Subclasses provide the surface-equation specific
rules for tessellation; this base class supplies the helpers that turn a
coordinate/colour grid into a list of ``ShadedTriangle`` instances.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .shaded_triangle import ShadedTriangle


class _CoordinateColorPair:
    """Helper mirroring PDFBox ``CoordinateColorPair`` (package-private)."""

    __slots__ = ("coordinate", "color")

    def __init__(self, coordinate: tuple[float, float], color: Sequence[float]) -> None:
        self.coordinate = coordinate
        self.color = list(color)


class Patch:
    """Abstract base for ``CoonsPatch`` / ``TensorPatch``."""

    def __init__(self, color: Sequence[Sequence[float]]) -> None:
        # cornerColor – defensive copy.
        self.corner_color: list[list[float]] = [list(c) for c in color]
        self.control_points: list[list[tuple[float, float]]] = []
        self.level: list[int] = [4, 4]
        self.list_of_triangles: list[ShadedTriangle] = []

    # ------------------------------------------------------------------
    # Abstract API
    # ------------------------------------------------------------------
    def get_flag1_edge(self) -> list[tuple[float, float]]:
        """Abstract — Coons / Tensor subclasses return their implicit
        edge points for flag=1. Mirrors upstream
        ``Patch.getFlag1Edge``."""
        _ = self
        raise NotImplementedError("Patch.get_flag1_edge is abstract")

    def get_flag2_edge(self) -> list[tuple[float, float]]:
        """Abstract — Coons / Tensor subclasses return their implicit
        edge points for flag=2. Mirrors upstream
        ``Patch.getFlag2Edge``."""
        _ = self
        raise NotImplementedError("Patch.get_flag2_edge is abstract")

    def get_flag3_edge(self) -> list[tuple[float, float]]:
        """Abstract — Coons / Tensor subclasses return their implicit
        edge points for flag=3. Mirrors upstream
        ``Patch.getFlag3Edge``."""
        _ = self
        raise NotImplementedError("Patch.get_flag3_edge is abstract")

    # ------------------------------------------------------------------
    # Flag-driven implicit colour helpers
    # ------------------------------------------------------------------
    def get_flag1_color(self) -> list[list[float]]:
        n = len(self.corner_color[0])
        return [
            [self.corner_color[1][i] for i in range(n)],
            [self.corner_color[2][i] for i in range(n)],
        ]

    def get_flag2_color(self) -> list[list[float]]:
        n = len(self.corner_color[0])
        return [
            [self.corner_color[2][i] for i in range(n)],
            [self.corner_color[3][i] for i in range(n)],
        ]

    def get_flag3_color(self) -> list[list[float]]:
        n = len(self.corner_color[0])
        return [
            [self.corner_color[3][i] for i in range(n)],
            [self.corner_color[0][i] for i in range(n)],
        ]

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------
    @staticmethod
    def get_len(ps: tuple[float, float], pe: tuple[float, float]) -> float:
        return math.hypot(pe[0] - ps[0], pe[1] - ps[1])

    def is_edge_a_line(self, ctl: Sequence[tuple[float, float]]) -> bool:
        ctl1 = abs(self.edge_equation_value(ctl[1], ctl[0], ctl[3]))
        ctl2 = abs(self.edge_equation_value(ctl[2], ctl[0], ctl[3]))
        x = abs(ctl[0][0] - ctl[3][0])
        y = abs(ctl[0][1] - ctl[3][1])
        return (ctl1 <= x and ctl2 <= x) or (ctl1 <= y and ctl2 <= y)

    @staticmethod
    def edge_equation_value(
        p: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
    ) -> float:
        return (p2[1] - p1[1]) * (p[0] - p1[0]) - (p2[0] - p1[0]) * (p[1] - p1[1])

    def get_shaded_triangles(
        self, patch_cc: list[list[_CoordinateColorPair]],
    ) -> list[ShadedTriangle]:
        triangles: list[ShadedTriangle] = []
        sz_v = len(patch_cc)
        sz_u = len(patch_cc[0]) if sz_v else 0
        for i in range(1, sz_v):
            for j in range(1, sz_u):
                p0 = patch_cc[i - 1][j - 1].coordinate
                p1 = patch_cc[i - 1][j].coordinate
                p2 = patch_cc[i][j].coordinate
                p3 = patch_cc[i][j - 1].coordinate
                ll = True
                if self.overlaps(p0, p1) or self.overlaps(p0, p3):
                    ll = False
                else:
                    triangles.append(
                        ShadedTriangle(
                            [p0, p1, p3],
                            [
                                patch_cc[i - 1][j - 1].color,
                                patch_cc[i - 1][j].color,
                                patch_cc[i][j - 1].color,
                            ],
                        ),
                    )
                if ll and (self.overlaps(p2, p1) or self.overlaps(p2, p3)):
                    continue
                triangles.append(
                    ShadedTriangle(
                        [p3, p1, p2],
                        [
                            patch_cc[i][j - 1].color,
                            patch_cc[i - 1][j].color,
                            patch_cc[i][j].color,
                        ],
                    ),
                )
        return triangles

    @staticmethod
    def overlaps(p0: tuple[float, float], p1: tuple[float, float]) -> bool:
        return abs(p0[0] - p1[0]) < 0.001 and abs(p0[1] - p1[1]) < 0.001
