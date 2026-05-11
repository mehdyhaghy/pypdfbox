"""Sampled cubic Bezier curve used by Type 6 / 7 patch tessellation.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.CubicBezierCurve``.
"""

from __future__ import annotations

from collections.abc import Sequence


class CubicBezierCurve:
    """A cubic Bezier curve sampled at ``2**level + 1`` points."""

    __slots__ = ("_control_points", "_level", "_curve")

    def __init__(self, ctrl_pnts: Sequence[tuple[float, float]], level: int) -> None:
        self._control_points: list[tuple[float, float]] = [
            (float(p[0]), float(p[1])) for p in ctrl_pnts
        ]
        self._level = int(level)
        self._curve = self.get_points(self._level)

    def get_level(self) -> int:
        return self._level

    def get_points(self, level: int) -> list[tuple[float, float]]:
        if level < 0:
            level = 0
        sz = (1 << level) + 1
        res: list[tuple[float, float]] = []
        step = 1.0 / (sz - 1) if sz > 1 else 0.0
        t = -step
        p0, p1, p2, p3 = self._control_points
        for _ in range(sz):
            t += step
            one_minus_t = 1.0 - t
            tmp_x = (
                one_minus_t * one_minus_t * one_minus_t * p0[0]
                + 3 * t * one_minus_t * one_minus_t * p1[0]
                + 3 * t * t * one_minus_t * p2[0]
                + t * t * t * p3[0]
            )
            tmp_y = (
                one_minus_t * one_minus_t * one_minus_t * p0[1]
                + 3 * t * one_minus_t * one_minus_t * p1[1]
                + 3 * t * t * one_minus_t * p2[1]
                + t * t * t * p3[1]
            )
            res.append((tmp_x, tmp_y))
        return res

    def get_cubic_bezier_curve(self) -> list[tuple[float, float]]:
        """Return the sampled curve points."""
        return list(self._curve)

    def to_string(self) -> str:
        joined = " ".join(
            f"Point2D.Double[{p[0]}, {p[1]}]" for p in self._control_points
        )
        return f"Cubic Bezier curve{{control points p0, p1, p2, p3: {joined}}}"

    def __repr__(self) -> str:
        return self.to_string()
