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

import logging
from typing import TYPE_CHECKING, Any

from .glyf_descript import GlyfDescript
from .point import Point

if TYPE_CHECKING:
    from fontTools.pens.recordingPen import RecordingPen


_LOG = logging.getLogger(__name__)

_ON_CURVE = GlyfDescript.ON_CURVE


class GlyphRenderer:
    """Render a :class:`GlyphDescription` into a recorded path."""

    def __init__(
        self,
        glyph_description: Any,
        hinted_x: list[int] | None = None,
        hinted_y: list[int] | None = None,
    ) -> None:
        """Wrap ``glyph_description``.

        When ``hinted_x`` / ``hinted_y`` are given, the path is built from
        those grid-fitted (hinted) coordinates instead of the glyph's raw
        coordinates. They are in font units (the hinting having been
        applied and scaled back) and must be parallel to the glyph's
        points. Mirrors upstream's two constructors.
        """
        self._glyph_description = glyph_description
        self._hinted_x = hinted_x
        self._hinted_y = hinted_y

    def get_path(self) -> RecordingPen:
        """Build and return the recorded path for the wrapped glyph.

        Mirrors upstream ``getPath()`` (GlyphRenderer.java line 55). The
        returned object is a fontTools ``RecordingPen``; its ``value``
        attribute is a list of ``(operator, args)`` tuples ready to be
        replayed onto any other pen.
        """
        from fontTools.pens.recordingPen import RecordingPen

        gd = self._glyph_description
        n = gd.get_point_count()
        # describe(): the per-point coordinates, on-curve flags and contour ends, as parallel
        # lists rather than Point objects (the hinted path is built once per glyph and size,
        # so this is on the rendering hot path); calculate_path() below is the same walk
        hinted_x = self._hinted_x
        hinted_y = self._hinted_y
        xs = (
            [int(hinted_x[i]) for i in range(n)]
            if hinted_x is not None
            else [int(gd.get_x_coordinate(i)) for i in range(n)]
        )
        ys = (
            [int(hinted_y[i]) for i in range(n)]
            if hinted_y is not None
            else [int(gd.get_y_coordinate(i)) for i in range(n)]
        )
        # a description may carry the per-point on-curve and contour-end flags precomputed
        # (the hinter's does); otherwise derive them through the accessor surface
        on = getattr(gd, "on_curve_flags", None)
        ends = getattr(gd, "contour_end_flags", None)
        if on is None or ends is None or len(on) != n or len(ends) != n:
            on, ends = GlyphRenderer._point_flags(gd, n)

        path = RecordingPen()
        out = path.value
        append = out.append
        start = 0
        for p in range(n):
            if not ends[p]:
                continue
            stop = p + 1
            contour = list(zip(xs[start:stop], ys[start:stop], on[start:stop], strict=True))
            first = contour[0]
            last = contour[-1]
            if first[2]:
                # close by repeating the start
                contour.append(first)
            elif last[2]:
                # off-curve start, on-curve end: prepend the end
                contour.insert(0, last)
            else:
                # both off-curve: synthesise an on-curve midpoint
                pmid = (_mid_int(first[0], last[0]), _mid_int(first[1], last[1]), True)
                contour.insert(0, pmid)
                contour.append(pmid)
            head = contour[0]
            append(("moveTo", ((head[0], head[1]),)))
            j = 1
            clen = len(contour)
            while j < clen:
                px, py, pon = contour[j]
                if pon:
                    append(("lineTo", ((px, py),)))
                elif j + 1 < clen:
                    nx, ny, non = contour[j + 1]
                    if non:
                        append(("qCurveTo", ((px, py), (nx, ny))))
                        j += 1
                    else:
                        append(
                            ("qCurveTo", ((px, py), (_mid_int(px, nx), _mid_int(py, ny))))
                        )
                else:  # pragma: no cover - defensive; the contour always ends on-curve
                    append(("lineTo", ((px, py),)))
                j += 1
            append(("closePath", ()))
            start = p + 1
        return path

    # ---- internals ---------------------------------------------------

    @staticmethod
    def _point_flags(gd: Any, n: int) -> tuple[list[bool], list[bool]]:
        """The on-curve and end-of-contour flag of each point, as :meth:`describe` sets them."""
        get_flags = gd.get_flags
        on = [(get_flags(i) & _ON_CURVE) != 0 for i in range(n)]
        ends = [False] * n
        end_pt_index = 0
        end_pt_of_contour_index = -1
        get_end = gd.get_end_pt_of_contours
        for i in range(n):
            if end_pt_of_contour_index == -1:
                end_pt_of_contour_index = get_end(end_pt_index)
            if end_pt_of_contour_index == i:
                ends[i] = True
                end_pt_index += 1
                end_pt_of_contour_index = -1
        return on, ends

    @staticmethod
    def describe(
        gd: Any,
        hinted_x: list[int] | None = None,
        hinted_y: list[int] | None = None,
    ) -> list[Point]:
        """Snapshot the description's point array.

        Mirrors upstream ``describe(GlyphDescription)`` (line 64). The
        optional hinted coordinate arrays replace the raw ones, as the
        upstream renderer's ``hintedX`` / ``hintedY`` fields do.
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
            x = hinted_x[i] if hinted_x is not None else gd.get_x_coordinate(i)
            y = hinted_y[i] if hinted_y is not None else gd.get_y_coordinate(i)
            points.append(
                Point(
                    int(x),
                    int(y),
                    (gd.get_flags(i) & GlyfDescript.ON_CURVE) != 0,
                    end_pt,
                )
            )
        return points

    def calculate_path(self, points: list[Point]) -> RecordingPen:
        """Walk ``points`` and emit a recorded path.

        Mirrors upstream ``calculatePath(Point[])`` (line 94).
        """
        from fontTools.pens.recordingPen import RecordingPen

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
    return a + (diff // 2 if diff >= 0 else -(-diff // 2))


__all__ = ["GlyphRenderer"]
