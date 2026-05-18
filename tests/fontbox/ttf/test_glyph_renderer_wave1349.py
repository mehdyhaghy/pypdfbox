"""Wave 1349 coverage-boost tests for :class:`GlyphRenderer`.

Targets the third elif branch of :meth:`calculate_path` (lines 118-119):
two consecutive off-curve points in the middle of a contour, where
``contour[j+1]`` is also off-curve and ``j+1 < clen``. Upstream
synthesises an implicit on-curve midpoint between them and emits a
``qCurveTo``.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.glyf_descript import GlyfDescript
from pypdfbox.fontbox.ttf.glyf_simple_descript import GlyfSimpleDescript
from pypdfbox.fontbox.ttf.glyph_renderer import GlyphRenderer


def test_render_two_consecutive_off_curve_mid_contour_emits_implicit_midpoint() -> None:
    """Build a one-contour glyph whose middle two interior points are
    both off-curve. After the standard ``points + first_point`` close,
    the walk hits ``contour[j]`` off-curve with ``contour[j+1]`` also
    off-curve and ``j+1 < clen`` → ``mid_value`` + ``qCurveTo`` (lines
    118-119)."""
    d = GlyfSimpleDescript()
    d._contour_count = 1  # noqa: SLF001
    d._end_pts_of_contours = [3]  # noqa: SLF001
    # Point sequence: on-curve, off-curve, off-curve, on-curve (end).
    d._flags = [  # noqa: SLF001
        GlyfDescript.ON_CURVE,
        0,
        0,
        GlyfDescript.ON_CURVE,
    ]
    d._x_coordinates = [0, 10, 20, 30]  # noqa: SLF001
    d._y_coordinates = [0, 10, 10, 0]  # noqa: SLF001
    d._point_count = 4  # noqa: SLF001

    pen = GlyphRenderer(d).get_path()
    ops = [op for (op, _args) in pen.value]

    assert ops[0] == "moveTo"
    assert ops[-1] == "closePath"
    # At least one qCurveTo emitted by the implicit-midpoint branch.
    assert "qCurveTo" in ops
    # The midpoint of (10,10) and (20,10) is (15,10) — that on-curve
    # midpoint must appear as the second arg of one of the qCurveTo
    # operations.
    qcurves = [args for (op, args) in pen.value if op == "qCurveTo"]
    # Expect at least one qCurveTo whose final on-curve target is the
    # synthesised midpoint (15, 10).
    assert any(args[-1] == (15, 10) for args in qcurves)
