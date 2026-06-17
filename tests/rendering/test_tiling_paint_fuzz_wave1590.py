"""Fuzz / parity battery for the tiling-pattern paint helpers (wave 1590 agent E).

Exercises the bug-prone branches of ``pypdfbox.rendering.tiling_paint`` and the
renderer-side ``PDFRenderer._paint_tiling_pattern`` tile-size computation:

* ``TilingPaint.ceiling`` — mirrors upstream
  ``BigDecimal.valueOf(num).setScale(5, RoundingMode.CEILING).intValue()``: it
  rounds up only at the 5th decimal then **truncates toward zero**, so a tiny
  floating-point overshoot does NOT inflate the raster by a pixel (the wave-1590
  fix: was a naive ``math.ceil`` that bumped 40.0000001 → 41, mis-tiling).
* ``get_anchor_rect`` tile-size from ``/XStep``/``/YStep`` with the ``/BBox``
  fallback when a step is 0, the pattern ``/Matrix`` scaling, the MAXEDGE clamp,
  and the bbox-lower-left anchor origin.
* ``_compute_pattern_matrix`` — pattern ``/Matrix`` concatenated with the
  initial (device-scale) matrix when supplied as a ``Matrix``.
* ``_abs_scale_factors`` overloads (Matrix / 6-tuple / None).
* paint type 1 (colored, cell colours) vs paint type 2 (uncolored, supplied
  tint) tile-size invariance.

Compared against Apache PDFBox 3.0.7 ``TilingPaint.getAnchorRect`` /
``getImage`` / ``ceiling`` semantics. No single upstream JUnit source.
"""

from __future__ import annotations

import math
from decimal import ROUND_CEILING, Decimal
from typing import Any

import pytest

from pypdfbox.rendering.tiling_paint import (
    MAXEDGE,
    TilingPaint,
    _abs_scale_factors,
)
from pypdfbox.util.matrix import Matrix

_UNSET = object()


# ---------------------------------------------------------------------------
# Fakes (mirrors the existing coverage-test fakes; cell render is mocked away)
# ---------------------------------------------------------------------------
class _FakeBBox:
    def __init__(
        self,
        width: float = 10.0,
        height: float = 10.0,
        llx: float = 0.0,
        lly: float = 0.0,
    ) -> None:
        self._w = width
        self._h = height
        self._llx = llx
        self._lly = lly

    def get_width(self) -> float:
        return self._w

    def get_height(self) -> float:
        return self._h

    def get_lower_left_x(self) -> float:
        return self._llx

    def get_lower_left_y(self) -> float:
        return self._lly


class _FakePattern:
    def __init__(
        self,
        bbox: Any = _UNSET,
        x_step: float = 10.0,
        y_step: float = 10.0,
        matrix: Matrix | None = None,
        paint_type: int = 1,
    ) -> None:
        self._bbox = _FakeBBox() if bbox is _UNSET else bbox
        self._x_step = x_step
        self._y_step = y_step
        self._matrix = matrix if matrix is not None else Matrix()
        self._paint_type = paint_type

    def get_matrix(self) -> Matrix | None:
        return self._matrix

    def get_b_box(self) -> Any:
        return self._bbox

    def get_x_step(self) -> float:
        return self._x_step

    def get_y_step(self) -> float:
        return self._y_step

    def get_paint_type(self) -> int:
        return self._paint_type


class _Drawer:
    """Stub drawer; ``draw_tiling_pattern`` is a no-op so the cell render is
    mocked (we exercise the size/matrix helpers, not the content stream)."""

    def draw_tiling_pattern(self, pattern: Any, color: Any, color_space: Any) -> None:
        return None


def _make_paint(pattern: _FakePattern, xform: Any = None) -> TilingPaint:
    return TilingPaint(_Drawer(), pattern, None, None, xform)


def _upstream_ceiling(num: float) -> int:
    """Reference port of upstream ``ceiling`` for the oracle assertions."""
    return int(Decimal(repr(float(num))).quantize(Decimal("1.00000"), rounding=ROUND_CEILING))


# ===========================================================================
# ceiling — the core tile-size helper (wave-1590 fix)
# ===========================================================================
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1.0, 1),
        (1.01, 1),  # NOT 2 — truncates after setScale(5)
        (1.001, 1),
        (12.3, 12),  # NOT 13 — intValue truncates toward zero
        (40.0, 40),
        (40.0000001, 40),  # tiny overshoot absorbed, NOT 41
        (40.00001, 40),  # exactly 5dp, no round-up, truncate
        (40.000011, 40),  # rounds up at 5dp to 40.00002 — int part unchanged
        (39.999999, 40),  # rounds up at 5dp → 40.00000 → 40
        (100.0000004, 100),
        (0.0, 0),
        (0.000001, 0),  # below 5dp granularity → 0
        (1.999999, 2),
        (-1.5, -1),  # truncate toward zero
        (-0.5, 0),
        (-5.3, -5),
        (-5.0000001, -5),
    ],
)
def test_ceiling_matches_upstream_bigdecimal(value: float, expected: int) -> None:
    assert TilingPaint.ceiling(value) == expected
    # Cross-check against the BigDecimal-equivalent reference port.
    assert TilingPaint.ceiling(value) == _upstream_ceiling(value)


def test_ceiling_diverges_from_math_ceil() -> None:
    # The whole point of the upstream impl: it is NOT Math.ceil. Pin a value
    # where the two disagree so a regression to math.ceil is caught.
    assert math.ceil(40.0000001) == 41
    assert TilingPaint.ceiling(40.0000001) == 40


@pytest.mark.parametrize(
    "value",
    [3.14159, 7.5, 250.0, 999.99999, 1234.5678, 0.123456, 60.000004, 60.000006],
)
def test_ceiling_random_parity(value: float) -> None:
    assert TilingPaint.ceiling(value) == _upstream_ceiling(value)


# ===========================================================================
# get_anchor_rect — tile size from /XStep /YStep + /Matrix scaling
# ===========================================================================
def test_anchor_rect_uses_steps_not_bbox() -> None:
    # Tile size derives from /XStep, /YStep (NOT /BBox) scaled by the pattern
    # matrix. Here matrix is identity so width=xStep, height=yStep.
    pat = _FakePattern(bbox=_FakeBBox(10, 10), x_step=25.0, y_step=40.0)
    paint = _make_paint(pat)
    x, y, w, h = paint.get_anchor_rect(pat)
    assert (w, h) == (25.0, 40.0)
    assert (x, y) == (0.0, 0.0)


def test_anchor_rect_zero_xstep_falls_back_to_bbox_width() -> None:
    pat = _FakePattern(bbox=_FakeBBox(17, 11), x_step=0.0, y_step=40.0)
    paint = _make_paint(pat)
    _x, _y, w, h = paint.get_anchor_rect(pat)
    assert w == 17.0  # /BBox width
    assert h == 40.0  # /YStep untouched


def test_anchor_rect_zero_ystep_falls_back_to_bbox_height() -> None:
    pat = _FakePattern(bbox=_FakeBBox(17, 11), x_step=25.0, y_step=0.0)
    paint = _make_paint(pat)
    _x, _y, w, h = paint.get_anchor_rect(pat)
    assert w == 25.0
    assert h == 11.0  # /BBox height


def test_anchor_rect_both_steps_zero_uses_full_bbox() -> None:
    pat = _FakePattern(bbox=_FakeBBox(8, 9), x_step=0.0, y_step=0.0)
    paint = _make_paint(pat)
    _x, _y, w, h = paint.get_anchor_rect(pat)
    assert (w, h) == (8.0, 9.0)


def test_anchor_rect_missing_bbox_returns_none() -> None:
    pat = _FakePattern(bbox=None)
    paint = _make_paint(pat)
    assert paint.get_anchor_rect(pat) is None


def test_anchor_rect_none_pattern_returns_none() -> None:
    pat = _FakePattern()
    paint = _make_paint(pat)
    assert paint.get_anchor_rect(None) is None


def test_anchor_origin_from_bbox_lower_left() -> None:
    # Anchor origin = bbox lower-left * matrix scale (upstream getAnchorRect).
    pat = _FakePattern(bbox=_FakeBBox(10, 10, llx=3.0, lly=5.0), x_step=10, y_step=10)
    paint = _make_paint(pat)
    x, y, _w, _h = paint.get_anchor_rect(pat)
    assert (x, y) == (3.0, 5.0)


def test_anchor_rect_matrix_scale_applied_to_steps() -> None:
    # Pattern /Matrix supplied through xform (the initial matrix) scales the
    # steps. patternMatrix = concatenate(initial, pattern_matrix); here pattern
    # matrix is identity so the scale comes entirely from the initial matrix.
    initial = Matrix.get_scale_instance(2.0, 3.0)
    pat = _FakePattern(bbox=_FakeBBox(10, 10), x_step=20.0, y_step=10.0)
    paint = _make_paint(pat, xform=initial)
    _x, _y, w, h = paint.get_anchor_rect(pat)
    assert w == pytest.approx(40.0)  # 20 * 2
    assert h == pytest.approx(30.0)  # 10 * 3


def test_anchor_rect_matrix_scale_applied_to_origin() -> None:
    initial = Matrix.get_scale_instance(2.0, 3.0)
    pat = _FakePattern(bbox=_FakeBBox(10, 10, llx=4.0, lly=5.0), x_step=10, y_step=10)
    paint = _make_paint(pat, xform=initial)
    x, y, _w, _h = paint.get_anchor_rect(pat)
    assert x == pytest.approx(8.0)  # 4 * 2
    assert y == pytest.approx(15.0)  # 5 * 3


@pytest.mark.parametrize(
    ("x_step", "y_step", "sx", "sy"),
    [
        (10.0, 10.0, 1.0, 1.0),
        (15.0, 30.0, 2.0, 2.0),
        (12.5, 7.5, 1.5, 4.0),
        (40.0, 20.0, 0.5, 0.5),
        (3.0, 3.0, 10.0, 0.25),
    ],
)
def test_anchor_rect_step_times_scale(
    x_step: float, y_step: float, sx: float, sy: float
) -> None:
    initial = Matrix.get_scale_instance(sx, sy)
    pat = _FakePattern(bbox=_FakeBBox(5, 5), x_step=x_step, y_step=y_step)
    paint = _make_paint(pat, xform=initial)
    _x, _y, w, h = paint.get_anchor_rect(pat)
    assert w == pytest.approx(x_step * sx)
    assert h == pytest.approx(y_step * sy)


def test_anchor_rect_maxedge_clamp() -> None:
    # PDFBOX-3653: an enormous step*scale gets clamped to MAXEDGE per axis.
    big = MAXEDGE * 10.0
    pat = _FakePattern(bbox=_FakeBBox(10, 10), x_step=big, y_step=big)
    paint = _make_paint(pat)
    _x, _y, w, h = paint.get_anchor_rect(pat)
    assert abs(w) <= MAXEDGE
    assert abs(h) <= MAXEDGE


def test_anchor_rect_below_maxedge_not_clamped() -> None:
    pat = _FakePattern(bbox=_FakeBBox(10, 10), x_step=100.0, y_step=100.0)
    paint = _make_paint(pat)
    _x, _y, w, h = paint.get_anchor_rect(pat)
    assert (w, h) == (100.0, 100.0)


# ===========================================================================
# _compute_pattern_matrix — pattern /Matrix composed with the initial matrix
# ===========================================================================
def test_pattern_matrix_concatenated_with_initial_when_matrix_xform() -> None:
    initial = Matrix.get_scale_instance(2.0, 2.0)
    pat_matrix = Matrix.get_scale_instance(3.0, 3.0)
    pat = _FakePattern(matrix=pat_matrix)
    paint = _make_paint(pat, xform=initial)
    pm = paint.get_pattern_matrix()
    # concatenate(initial, pattern) -> combined scale 6 on both axes.
    assert pm.get_scaling_factor_x() == pytest.approx(6.0)
    assert pm.get_scaling_factor_y() == pytest.approx(6.0)


def test_pattern_matrix_falls_back_to_pattern_matrix_when_xform_not_matrix() -> None:
    pat_matrix = Matrix.get_scale_instance(4.0, 5.0)
    pat = _FakePattern(matrix=pat_matrix)
    # xform a plain tuple (device transform shape) -> not concatenated.
    paint = _make_paint(pat, xform=(1, 0, 0, 1, 0, 0))
    pm = paint.get_pattern_matrix()
    assert pm.get_scaling_factor_x() == pytest.approx(4.0)
    assert pm.get_scaling_factor_y() == pytest.approx(5.0)


def test_pattern_matrix_none_pattern_identity() -> None:
    pat = _FakePattern()
    paint = _make_paint(pat)
    pm = TilingPaint._compute_pattern_matrix(None, None)
    assert pm.get_scaling_factor_x() == pytest.approx(1.0)
    assert paint.get_pattern_matrix() is not None


# ===========================================================================
# _abs_scale_factors — DPI/device scale extraction
# ===========================================================================
def test_abs_scale_factors_none_is_identity() -> None:
    assert _abs_scale_factors(None) == (1.0, 1.0)


def test_abs_scale_factors_matrix() -> None:
    m = Matrix.get_scale_instance(-2.0, 3.0)
    sx, sy = _abs_scale_factors(m)
    assert (sx, sy) == (2.0, 3.0)  # absolute value


@pytest.mark.parametrize(
    ("coeffs", "expected"),
    [
        ((2.0, 0.0, 0.0, 3.0, 0.0, 0.0), (2.0, 3.0)),
        ((-2.0, 0.0, 0.0, -3.0, 0.0, 0.0), (2.0, 3.0)),
        ((3.0, 4.0, 0.0, 5.0, 0.0, 0.0), (5.0, 5.0)),  # sqrt(9+16)=5
    ],
)
def test_abs_scale_factors_tuple(coeffs: tuple[float, ...], expected: tuple[float, float]) -> None:
    sx, sy = _abs_scale_factors(coeffs)
    assert sx == pytest.approx(expected[0])
    assert sy == pytest.approx(expected[1])


def test_abs_scale_factors_unknown_type_identity() -> None:
    assert _abs_scale_factors(object()) == (1.0, 1.0)


# ===========================================================================
# get_image — raster size = ceiling(step * matrix_scale * device_scale)
# ===========================================================================
def test_get_image_raster_size_uses_ceiling() -> None:
    pat = _FakePattern(bbox=_FakeBBox(10, 10), x_step=12.3, y_step=7.5)
    paint = _make_paint(pat)
    img = paint._image
    # raster = max(1, ceiling(width)); width=12.3 -> ceiling=12, height=7.5->7.
    assert img is not None
    assert img.size == (12, 7)


def test_get_image_raster_min_one_pixel() -> None:
    pat = _FakePattern(bbox=_FakeBBox(1, 1), x_step=0.4, y_step=0.4)
    paint = _make_paint(pat)
    img = paint._image
    assert img is not None
    assert img.size == (1, 1)  # ceiling(0.4)=0 -> max(1, 0)=1


def test_get_image_applies_device_scale() -> None:
    pat = _FakePattern(bbox=_FakeBBox(10, 10), x_step=10.0, y_step=10.0)
    # device scale 2x via a 6-tuple xform; matrix path not triggered (not Matrix).
    paint = _make_paint(pat, xform=(2.0, 0.0, 0.0, 2.0, 0.0, 0.0))
    img = paint._image
    assert img is not None
    # anchor width=10 (no matrix concat), * device scale 2 = 20.
    assert img.size == (20, 20)


# ===========================================================================
# paint type 1 (colored) vs paint type 2 (uncolored) — tile size invariant
# ===========================================================================
@pytest.mark.parametrize("paint_type", [1, 2])
def test_tile_size_independent_of_paint_type(paint_type: int) -> None:
    # The anchor rect / tile size is the same for colored and uncolored; the
    # paint type only governs *which colour* the cell paints in, not its size.
    pat = _FakePattern(bbox=_FakeBBox(10, 10), x_step=20.0, y_step=30.0, paint_type=paint_type)
    paint = _make_paint(pat)
    _x, _y, w, h = paint.get_anchor_rect(pat)
    assert (w, h) == (20.0, 30.0)


def test_paint_type_2_passes_color_through_constructor() -> None:
    # An uncolored paint is constructed with a colour + colour space; ensure the
    # constructor stores them (the supplied tint, used by PaintType 2 cells).
    sentinel_cs = object()
    sentinel_color = object()
    pat = _FakePattern(paint_type=2)
    paint = TilingPaint(_Drawer(), pat, sentinel_cs, sentinel_color, None)
    assert paint._color is sentinel_color
    assert paint._color_space is sentinel_cs


# ===========================================================================
# get_transparency parity
# ===========================================================================
def test_get_transparency_translucent() -> None:
    from pypdfbox.rendering.tiling_paint import TRANSLUCENT

    pat = _FakePattern()
    paint = _make_paint(pat)
    assert paint.get_transparency() == TRANSLUCENT
