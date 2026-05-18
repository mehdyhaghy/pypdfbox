"""Glyph-to-path conversion ported from upstream ``GlyphRenderer``.

Mirrors ``org.apache.fontbox.ttf.GlyphRenderer`` (GlyphRenderer.java
lines 40-222). Upstream walks a :class:`GlyphDescription`'s point
arrays and emits ``moveTo`` / ``lineTo`` / ``quadTo`` / ``closePath``
calls on a Java ``GeneralPath``. The Python port preserves the same
algorithm — split into contours, handle off-curve start / end with
implicit midpoints, then walk each contour emitting curve / line
segments — but its :meth:`get_path` returns a fontTools ``RecordingPen``
so callers can replay onto any concrete back end.

The renderer can be driven by any object exposing the upstream
``GlyphDescription`` accessor surface — both :class:`GlyfDescript`
subclasses and the existing :class:`GlyphDescription` adapter in
:mod:`pypdfbox.fontbox.ttf.glyph_data` qualify.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .glyf_descript import GlyfDescript
from .point import Point

if TYPE_CHECKING:
    from fontTools.pens.recordingPen import RecordingPen


_LOG = logging.getLogger(__name__)


class GlyphRenderer:
    """Render a :class:`GlyphDescription` into a recorded path."""

    def __init__(self, glyph_description: Any) -> None:
        self._glyph_description = glyph_description

    def get_path(self) -> RecordingPen:
        """Build and return the recorded path for the wrapped glyph.

        Mirrors upstream ``getPath()`` (GlyphRenderer.java line 55). The
        returned object is a fontTools ``RecordingPen``; its ``value``
        attribute is a list of ``(operator, args)`` tuples ready to be
        replayed onto any other pen.
        """
        points = self.describe(self._glyph_description)
        return self.calculate_path(points)

    # ---- internals ---------------------------------------------------

    @staticmethod
    def describe(gd: Any) -> list[Point]:
        """Snapshot the description's point array.

        Mirrors upstream ``describe(GlyphDescription)`` (line 64).
        """
        end_pt_index = 0
        end_pt_of_contour_index = -1
        point_count = gd.get_point_count()
        points: list[Point] = []
        for i in range(point_count):
            if end_pt_of_contour_index == -1:
                end_pt_of_contour_index = gd.get_end_pt_of_contours(end_pt_index)
            end_pt = end_pt_of_contour_index == i
            if end_pt:
                end_pt_index += 1
                end_pt_of_contour_index = -1
            points.append(
                Point(
                    int(gd.get_x_coordinate(i)),
                    int(gd.get_y_coordinate(i)),
                    (gd.get_flags(i) & GlyfDescript.ON_CURVE) != 0,
                    end_pt,
                )
            )
        return points

    def calculate_path(self, points: list[Point]) -> RecordingPen:
        """Walk ``points`` and emit a recorded path.

        Mirrors upstream ``calculatePath(Point[])`` (line 94).
        """
        from fontTools.pens.recordingPen import RecordingPen  # noqa: PLC0415

        path = RecordingPen()
        start = 0
        p = 0
        length = len(points)
        while p < length:
            if points[p].end_of_contour:
                first_point = points[start]
                last_point = points[p]
                contour: list[Point] = [points[q] for q in range(start, p + 1)]
                if points[start].on_curve:
                    # close by repeating the start (line 110-112).
                    contour.append(first_point)
                elif points[p].on_curve:
                    # off-curve start, on-curve end: prepend the end
                    # (line 116-118).
                    contour.insert(0, last_point)
                else:
                    # both off-curve: synthesise an on-curve midpoint
                    # (line 121-125).
                    pmid = self.mid_value(first_point, last_point)
                    contour.insert(0, pmid)
                    contour.append(pmid)
                self.move_to(path, contour[0])
                j = 1
                clen = len(contour)
                while j < clen:
                    pnow = contour[j]
                    if pnow.on_curve:
                        self.line_to(path, pnow)
                    elif j + 1 < clen and contour[j + 1].on_curve:
                        self.quad_to(path, pnow, contour[j + 1])
                        j += 1
                    elif j + 1 < clen:
                        self.quad_to(path, pnow, self.mid_value(pnow, contour[j + 1]))
                    else:  # pragma: no cover - defensive; contour[-1] is always on-curve
                        # Defensive: a stray trailing off-curve should
                        # not happen on a well-formed contour, but
                        # emit it as a line rather than crashing.
                        self.line_to(path, pnow)
                    j += 1
                path.closePath()
                start = p + 1
            p += 1
        return path

    @staticmethod
    def mid_value(a: Point, b: Point) -> Point:
        """Construct the on-curve midpoint between ``a`` and ``b``.

        Mirrors the package-private ``midValue(Point, Point)`` helper in
        upstream's renderer (line 185).
        """
        return Point(_mid_int(a.x, b.x), _mid_int(a.y, b.y), on_curve=True)

    @staticmethod
    def move_to(path: RecordingPen, point: Point) -> None:
        path.moveTo((point.x, point.y))

    @staticmethod
    def line_to(path: RecordingPen, point: Point) -> None:
        path.lineTo((point.x, point.y))

    @staticmethod
    def quad_to(path: RecordingPen, ctrl: Point, point: Point) -> None:
        path.qCurveTo((ctrl.x, ctrl.y), (point.x, point.y))


# ---- helpers (module-level so they're easy to unit test) -------------


def _mid_int(a: int, b: int) -> int:
    """Integer midpoint matching upstream's ``a + (b - a) / 2`` (line 179).

    Java integer division truncates toward zero, so we mirror that
    instead of using Python's floor-division.
    """
    diff = b - a
    # Truncate toward zero.
    truncated = int(diff / 2) if diff != 0 else 0
    return a + truncated


__all__ = ["GlyphRenderer"]
