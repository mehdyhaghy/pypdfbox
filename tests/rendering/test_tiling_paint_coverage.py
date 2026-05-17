"""Coverage tests for :mod:`pypdfbox.rendering.tiling_paint`.

Drives the constructor, ``get_anchor_rect``, ``get_image`` (with both the
``draw_tiling_pattern`` stub branch and the missing-bbox branches),
``_compute_pattern_matrix`` Matrix concatenation path,
``_abs_scale_factors`` overloads, and the ``_TilingPaintContext``
adapter.
"""

from __future__ import annotations

import logging
from importlib import reload
from typing import Any

from pypdfbox.rendering import tiling_paint as tp_mod
from pypdfbox.rendering.tiling_paint import (
    MAXEDGE,
    TRANSLUCENT,
    TilingPaint,
    _abs_scale_factors,
    _resolve_maxedge,
    _TilingPaintContext,
)
from pypdfbox.util.matrix import Matrix


# ---------------------------------------------------------------------------
# Fakes
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


_UNSET = object()


class _FakePattern:
    def __init__(
        self,
        bbox: _FakeBBox | None = _UNSET,  # type: ignore[assignment]
        x_step: float = 10.0,
        y_step: float = 10.0,
        matrix: Matrix | None = None,
    ) -> None:
        self._bbox = _FakeBBox() if bbox is _UNSET else bbox
        self._x_step = x_step
        self._y_step = y_step
        self._matrix = matrix if matrix is not None else Matrix.get_scale_instance(2.0, 3.0)

    def get_matrix(self) -> Matrix | None:
        return self._matrix

    def get_b_box(self) -> _FakeBBox | None:
        return self._bbox

    def get_x_step(self) -> float:
        return self._x_step

    def get_y_step(self) -> float:
        return self._y_step


class _Drawer:
    """Stub drawer whose ``draw_tiling_pattern`` method is a no-op."""

    def __init__(self) -> None:
        self.called_with: tuple[Any, ...] | None = None

    def draw_tiling_pattern(self, pattern: Any, color: Any, color_space: Any) -> None:
        self.called_with = (pattern, color, color_space)


class _RaisingDrawer:
    """Drawer whose ``draw_tiling_pattern`` raises — covers the except."""

    def draw_tiling_pattern(self, pattern: Any, color: Any, color_space: Any) -> None:
        raise TypeError("simulated rendering error")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------
def test_module_constants_have_expected_defaults() -> None:
    assert TRANSLUCENT == 3
    assert MAXEDGE == 3000


def test_resolve_maxedge_returns_default_on_bad_env(
    monkeypatch: Any, caplog: Any,
) -> None:
    monkeypatch.setenv("PDFBOX_RENDERING_TILINGPAINT_MAXEDGE", "not-a-number")
    with caplog.at_level(logging.ERROR, logger="pypdfbox.rendering.tiling_paint"):
        value = _resolve_maxedge()
    assert value == 3000
    assert any("Default will be used" in r.message for r in caplog.records)


def test_resolve_maxedge_reads_int_override(monkeypatch: Any) -> None:
    monkeypatch.setenv("PDFBOX_RENDERING_TILINGPAINT_MAXEDGE", "777")
    assert _resolve_maxedge() == 777


def test_module_reload_with_env_picks_up_override(monkeypatch: Any) -> None:
    """Reload the module so the module-level MAXEDGE constant reflects env."""
    monkeypatch.setenv("PDFBOX_RENDERING_TILINGPAINT_MAXEDGE", "12")
    reloaded = reload(tp_mod)
    try:
        assert reloaded.MAXEDGE == 12
    finally:
        monkeypatch.delenv("PDFBOX_RENDERING_TILINGPAINT_MAXEDGE", raising=False)
        reload(tp_mod)


def test_abs_scale_factors_handles_none_returns_identity() -> None:
    assert _abs_scale_factors(None) == (1.0, 1.0)


def test_abs_scale_factors_uses_matrix_accessors() -> None:
    m = Matrix.get_scale_instance(2.5, -4.0)
    sx, sy = _abs_scale_factors(m)
    assert sx == 2.5
    assert sy == 4.0


def test_abs_scale_factors_handles_pure_scale_tuple() -> None:
    # b == 0 / c == 0 path uses abs(a) / abs(d) shortcut.
    assert _abs_scale_factors((2.0, 0.0, 0.0, -3.0, 0.0, 0.0)) == (2.0, 3.0)


def test_abs_scale_factors_handles_sheared_tuple() -> None:
    # b != 0 / c != 0 triggers the sqrt branch.
    sx, sy = _abs_scale_factors((1.0, 1.0, 1.0, 1.0, 0.0, 0.0))
    assert round(sx, 4) == round(sy, 4) == round((2.0) ** 0.5, 4)


def test_abs_scale_factors_handles_short_or_non_iterable_returns_identity() -> None:
    assert _abs_scale_factors((1.0,)) == (1.0, 1.0)
    assert _abs_scale_factors("not-a-tuple") == (1.0, 1.0)


# ---------------------------------------------------------------------------
# TilingPaint construction & accessors
# ---------------------------------------------------------------------------
def test_constructor_renders_anchor_and_image_with_drawer_invocation() -> None:
    drawer = _Drawer()
    pattern = _FakePattern()
    paint = TilingPaint(drawer=drawer, pattern=pattern)
    # anchor = (llx*sx, lly*sy, xstep*sx, ystep*sy) = (0, 0, 20, 30)
    assert paint._anchor_rect == (0.0, 0.0, 20.0, 30.0)
    # image size = (ceil(width*1), ceil(height*1)) because xform=None
    assert paint._image.size == (20, 30)
    assert paint.get_transparency() == TRANSLUCENT
    assert paint.get_pattern_matrix() is paint._pattern_matrix
    assert drawer.called_with == (pattern, None, None)


def test_constructor_swallows_drawer_typeerror() -> None:
    paint = TilingPaint(drawer=_RaisingDrawer(), pattern=_FakePattern())
    assert paint._image is not None


def test_create_context_returns_tiling_paint_context_with_cached_state() -> None:
    paint = TilingPaint(drawer=_Drawer(), pattern=_FakePattern())
    ctx = paint.create_context(None, None, None, None, None)
    # Use duck-typed check — module reload in another test can swap class id.
    assert type(ctx).__name__ == "_TilingPaintContext"
    assert ctx.image is paint._image
    assert ctx.anchor_rect == paint._anchor_rect
    assert ctx.pattern_matrix is paint._pattern_matrix


def test_tiling_paint_context_accessors_and_dispose() -> None:
    ctx = _TilingPaintContext(image="img", anchor_rect=(0, 0, 1, 1), pattern_matrix="m")
    assert ctx.get_color_model() == "RGBA"
    assert ctx.dispose() is None


# ---------------------------------------------------------------------------
# _compute_pattern_matrix
# ---------------------------------------------------------------------------
def test_compute_pattern_matrix_returns_identity_for_none_pattern() -> None:
    m = TilingPaint._compute_pattern_matrix(None, None)
    assert isinstance(m, Matrix)


def test_compute_pattern_matrix_returns_pattern_matrix_when_xform_not_matrix() -> None:
    pattern = _FakePattern(matrix=Matrix.get_scale_instance(4.0, 5.0))
    m = TilingPaint._compute_pattern_matrix(pattern, xform=None)
    assert m.get_scaling_factor_x() == 4.0
    assert m.get_scaling_factor_y() == 5.0


def test_compute_pattern_matrix_concatenates_xform_when_matrix() -> None:
    pattern = _FakePattern(matrix=Matrix.get_scale_instance(2.0, 2.0))
    xform = Matrix.get_scale_instance(3.0, 3.0)
    m = TilingPaint._compute_pattern_matrix(pattern, xform=xform)
    # Concatenated scaling 2*3 = 6 along both axes.
    assert m.get_scaling_factor_x() == 6.0
    assert m.get_scaling_factor_y() == 6.0


def test_compute_pattern_matrix_falls_back_to_identity_when_pattern_returns_none() -> None:
    class _PatternNoMatrix:
        def get_matrix(self) -> None:
            return None

        def get_b_box(self) -> _FakeBBox:
            return _FakeBBox()

        def get_x_step(self) -> float:
            return 1.0

        def get_y_step(self) -> float:
            return 1.0

    m = TilingPaint._compute_pattern_matrix(_PatternNoMatrix(), xform=None)
    assert isinstance(m, Matrix)
    # Identity scaling.
    assert m.get_scaling_factor_x() == 1.0
    assert m.get_scaling_factor_y() == 1.0


# ---------------------------------------------------------------------------
# get_anchor_rect edge cases
# ---------------------------------------------------------------------------
def test_get_anchor_rect_returns_none_for_none_pattern() -> None:
    paint = TilingPaint(drawer=None, pattern=_FakePattern())
    assert paint.get_anchor_rect(None) is None


def test_get_anchor_rect_warns_and_returns_none_for_missing_bbox(caplog: Any) -> None:
    paint = TilingPaint(drawer=None, pattern=_FakePattern())
    pattern_no_bbox = _FakePattern(bbox=None)
    with caplog.at_level(logging.WARNING, logger="pypdfbox.rendering.tiling_paint"):
        result = paint.get_anchor_rect(pattern_no_bbox)
    assert result is None
    assert any("/BBox is missing" in r.message for r in caplog.records)


def test_get_anchor_rect_falls_back_to_bbox_dims_when_steps_zero(caplog: Any) -> None:
    pattern_zero_steps = _FakePattern(x_step=0, y_step=0)
    paint = TilingPaint(drawer=None, pattern=pattern_zero_steps)
    with caplog.at_level(logging.WARNING, logger="pypdfbox.rendering.tiling_paint"):
        rect = paint.get_anchor_rect(pattern_zero_steps)
    # bbox is 10x10, scale 2x3 → 20 x 30
    assert rect == (0.0, 0.0, 20.0, 30.0)
    assert any("XStep" in r.message for r in caplog.records)
    assert any("YStep" in r.message for r in caplog.records)


def test_get_anchor_rect_clamps_huge_surfaces_to_maxedge(caplog: Any) -> None:
    huge_pattern = _FakePattern(x_step=10000.0, y_step=10000.0)
    paint = TilingPaint(drawer=None, pattern=huge_pattern)
    with caplog.at_level(logging.WARNING, logger="pypdfbox.rendering.tiling_paint"):
        rect = paint.get_anchor_rect(huge_pattern)
    assert rect is not None
    _, _, w, h = rect
    assert abs(w) <= MAXEDGE
    assert abs(h) <= MAXEDGE
    assert any("larger than" in r.message for r in caplog.records)


def test_get_anchor_rect_preserves_negative_step_sign() -> None:
    """When width clamps but the step is negative, signedness survives."""
    neg_pattern = _FakePattern(x_step=-10000.0, y_step=-10000.0)
    paint = TilingPaint(drawer=None, pattern=neg_pattern)
    rect = paint.get_anchor_rect(neg_pattern)
    assert rect is not None
    _, _, w, h = rect
    assert w < 0
    assert h < 0


# ---------------------------------------------------------------------------
# get_image edge cases
# ---------------------------------------------------------------------------
def test_get_image_returns_none_for_none_anchor() -> None:
    paint = TilingPaint(drawer=None, pattern=_FakePattern())
    assert paint.get_image(None, _FakePattern(), None, None, None) is None


def test_get_image_returns_none_for_malformed_anchor() -> None:
    paint = TilingPaint(drawer=None, pattern=_FakePattern())
    # A 2-tuple cannot unpack into 4 → ValueError caught.
    assert paint.get_image(None, _FakePattern(), None, None, (1, 2)) is None
    # Non-iterable triggers TypeError caught.
    assert paint.get_image(None, _FakePattern(), None, None, 123) is None


def test_get_image_renders_blank_cell_without_drawer() -> None:
    paint = TilingPaint(drawer=None, pattern=_FakePattern())
    img = paint.get_image(None, _FakePattern(), None, None, (0.0, 0.0, 4.0, 5.0))
    assert img is not None
    assert img.size == (4, 5)


def test_get_image_scales_dimensions_by_xform_tuple() -> None:
    """xform with 2x/4x scale doubles + quadruples dimensions."""
    xform = (2.0, 0.0, 0.0, 4.0, 0.0, 0.0)
    paint = TilingPaint(drawer=None, pattern=_FakePattern(), xform=xform)
    img = paint.get_image(None, _FakePattern(), None, None, (0.0, 0.0, 3.0, 5.0))
    assert img is not None
    assert img.size == (6, 20)


def test_ceiling_is_strict_round_up() -> None:
    assert TilingPaint.ceiling(1.0) == 1
    assert TilingPaint.ceiling(1.01) == 2
    assert TilingPaint.ceiling(-1.5) == -1
