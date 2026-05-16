"""Coverage-boost tests for ``pypdfbox.pdmodel.graphics.state.pd_graphics_state``.

Covers the long tail of getters/setters (line cap/join, miter limit,
overprint flags, alpha source, smoothness, flatness, transfer, soft
mask, line dash, rendering intent, text matrices, colour spaces),
``intersect_clipping_path`` cloning, ``_path_bounds`` branches (None,
non-iterable, PDRectangle-like, empty), the ``get_current_clipping_path``
"first path has no bounds" fallback, and the clone branches for
text-matrix / text-line-matrix / matrices without ``clone``.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.pdmodel.graphics.state.pd_graphics_state import (
    CAP_BUTT,
    JOIN_MITER,
    PDGraphicsState,
)
from pypdfbox.pdmodel.graphics.state.rendering_intent import RenderingIntent


# ---------- Defaults ------------------------------------------------------


def test_constants_match_basic_stroke_defaults() -> None:
    assert CAP_BUTT == 0
    assert JOIN_MITER == 0


def test_defaults_pass_through_construction() -> None:
    gs = PDGraphicsState()
    assert gs.get_line_cap() == CAP_BUTT
    assert gs.get_line_join() == JOIN_MITER
    assert gs.is_stroke_adjustment() is False
    assert gs.get_rendering_intent() is None
    assert gs.is_alpha_source() is False
    assert gs.get_soft_mask() is None
    assert gs.is_non_stroking_overprint() is False
    assert gs.get_overprint_mode() == 0
    assert gs.get_flatness() == 1.0
    assert gs.get_smoothness() == 0.0
    assert gs.get_transfer() is None
    assert gs.get_text_matrix() is None
    assert gs.get_text_line_matrix() is None
    assert gs.get_line_dash_pattern() is not None
    assert gs.get_non_stroke_alpha_constant() == 1.0


# ---------- Setters -------------------------------------------------------


def test_setters_cover_all_simple_state_fields() -> None:
    gs = PDGraphicsState()
    gs.set_line_width(2.5)
    gs.set_line_cap(1)
    gs.set_line_join(2)
    gs.set_miter_limit(4.0)
    gs.set_stroke_adjustment(True)
    gs.set_alpha_constant(0.5)
    gs.set_non_stroke_alpha_constant(0.25)
    gs.set_alpha_source(True)
    gs.set_overprint(True)
    gs.set_non_stroking_overprint(True)
    gs.set_overprint_mode(1)
    gs.set_flatness(3.0)
    gs.set_smoothness(0.5)
    gs.set_rendering_intent(RenderingIntent.PERCEPTUAL)
    gs.set_blend_mode(BlendMode.MULTIPLY)

    assert gs.get_line_width() == 2.5
    assert gs.get_line_cap() == 1
    assert gs.get_line_join() == 2
    assert gs.get_miter_limit() == 4.0
    assert gs.is_stroke_adjustment() is True
    assert gs.get_alpha_constant() == 0.5
    assert gs.get_non_stroke_alpha_constant() == 0.25
    assert gs.is_alpha_source() is True
    assert gs.is_overprint() is True
    assert gs.is_non_stroking_overprint() is True
    assert gs.get_overprint_mode() == 1
    assert gs.get_flatness() == 3.0
    assert gs.get_smoothness() == 0.5
    assert gs.get_rendering_intent() is RenderingIntent.PERCEPTUAL
    assert gs.get_blend_mode() is BlendMode.MULTIPLY


def test_setters_for_complex_fields() -> None:
    gs = PDGraphicsState()
    transfer_sentinel = object()
    soft_mask_sentinel = object()
    dash_sentinel = object()
    text_matrix_sentinel = object()
    text_line_matrix_sentinel = object()
    ctm_sentinel = object()
    text_state_sentinel = object()
    stroke_cs_sentinel = object()
    non_stroke_cs_sentinel = object()
    stroke_color_sentinel = object()
    non_stroke_color_sentinel = object()

    gs.set_transfer(transfer_sentinel)
    gs.set_soft_mask(soft_mask_sentinel)
    gs.set_line_dash_pattern(dash_sentinel)
    gs.set_text_matrix(text_matrix_sentinel)
    gs.set_text_line_matrix(text_line_matrix_sentinel)
    gs.set_current_transformation_matrix(ctm_sentinel)
    gs.set_text_state(text_state_sentinel)
    gs.set_stroking_color_space(stroke_cs_sentinel)
    gs.set_non_stroking_color_space(non_stroke_cs_sentinel)
    gs.set_stroking_color(stroke_color_sentinel)
    gs.set_non_stroking_color(non_stroke_color_sentinel)

    assert gs.get_transfer() is transfer_sentinel
    assert gs.get_soft_mask() is soft_mask_sentinel
    assert gs.get_line_dash_pattern() is dash_sentinel
    assert gs.get_text_matrix() is text_matrix_sentinel
    assert gs.get_text_line_matrix() is text_line_matrix_sentinel
    assert gs.get_current_transformation_matrix() is ctm_sentinel
    assert gs.get_text_state() is text_state_sentinel
    assert gs.get_stroking_color_space() is stroke_cs_sentinel
    assert gs.get_non_stroking_color_space() is non_stroke_cs_sentinel
    assert gs.get_stroking_color() is stroke_color_sentinel
    assert gs.get_non_stroking_color() is non_stroke_color_sentinel


def test_blend_mode_rejects_none() -> None:
    gs = PDGraphicsState()
    with pytest.raises(ValueError, match="blendMode"):
        gs.set_blend_mode(None)


# ---------- Page-rect construction ---------------------------------------


def test_construction_with_page_rect_seeds_clipping_path() -> None:
    """When the constructor is given an object with ``to_general_path``,
    the result is appended to the initial clipping-paths list (line 48).
    """

    class _StubPage:
        def to_general_path(self) -> list[tuple[float, float]]:
            return [(0.0, 0.0), (100.0, 0.0), (100.0, 200.0), (0.0, 200.0)]

    gs = PDGraphicsState(page=_StubPage())
    paths = gs.get_current_clipping_paths()
    assert len(paths) == 1
    assert paths[0] == [(0.0, 0.0), (100.0, 0.0), (100.0, 200.0), (0.0, 200.0)]


# ---------- intersect_clipping_path / get_current_clipping_path ---------


def test_intersect_clipping_path_starts_with_empty_list() -> None:
    gs = PDGraphicsState()
    assert gs.get_current_clipping_path() is None


def test_get_current_clipping_path_with_pd_rectangle_like() -> None:
    """``_path_bounds`` happily accepts any object that exposes the
    PDRectangle accessor surface (lines 304-310).
    """

    class _Rect:
        def __init__(self, llx: float, lly: float, urx: float, ury: float) -> None:
            self._llx, self._lly, self._urx, self._ury = llx, lly, urx, ury

            def _wrap(value: float) -> "_Rect._Acc":
                return _Rect._Acc(value)

            self._w = _wrap

        class _Acc:
            def __init__(self, value: float) -> None:
                self._v = value

            def __call__(self) -> float:
                return self._v

        def get_lower_left_x(self) -> float:
            return self._llx

        def get_lower_left_y(self) -> float:
            return self._lly

        def get_upper_right_x(self) -> float:
            return self._urx

        def get_upper_right_y(self) -> float:
            return self._ury

    gs = PDGraphicsState()
    gs.intersect_clipping_path(_Rect(0, 0, 100, 100))
    gs.intersect_clipping_path(_Rect(50, 50, 200, 200))
    intersected = gs.get_current_clipping_path()
    assert intersected == [(50.0, 50.0), (100.0, 50.0), (100.0, 100.0), (50.0, 100.0)]


def test_get_current_clipping_path_with_non_iterable_first_path_returns_last() -> None:
    """When ``_path_bounds`` returns ``None`` for the seed path
    (non-iterable, non-rectangle), fall back to returning the last path
    (line 270).
    """
    gs = PDGraphicsState()
    gs.intersect_clipping_path(42)  # int -> not iterable, no bounds
    gs.intersect_clipping_path([(0, 0), (10, 0), (10, 10), (0, 10)])
    assert gs.get_current_clipping_path() == [(0, 0), (10, 0), (10, 10), (0, 10)]


def test_get_current_clipping_path_skips_path_without_bounds() -> None:
    """When one of the later paths has no bounds, it's skipped (line 275)
    and the remaining paths' bbox is used.
    """
    gs = PDGraphicsState()
    gs.intersect_clipping_path([(0, 0), (100, 0), (100, 100), (0, 100)])
    gs.intersect_clipping_path(42)  # skipped
    gs.intersect_clipping_path([(25, 25), (75, 25), (75, 75), (25, 75)])
    result = gs.get_current_clipping_path()
    assert result == [(25.0, 25.0), (75.0, 25.0), (75.0, 75.0), (25.0, 75.0)]


def test_path_bounds_returns_none_for_none() -> None:
    assert PDGraphicsState._path_bounds(None) is None


def test_path_bounds_returns_none_for_empty_iterable() -> None:
    assert PDGraphicsState._path_bounds([]) is None


def test_path_bounds_returns_none_for_iterable_of_scalars() -> None:
    # Non-2D iterable elements -> no xs/ys collected -> None.
    assert PDGraphicsState._path_bounds([1, 2, 3]) is None


def test_path_bounds_handles_pdrectangle_like() -> None:
    class _Rect:
        def get_lower_left_x(self) -> float:
            return 1.0

        def get_lower_left_y(self) -> float:
            return 2.0

        def get_upper_right_x(self) -> float:
            return 3.0

        def get_upper_right_y(self) -> float:
            return 4.0

    assert PDGraphicsState._path_bounds(_Rect()) == (1.0, 2.0, 3.0, 4.0)


# ---------- Clone branches ----------------------------------------------


class _Cloneable:
    def __init__(self, value: int = 0) -> None:
        self.value = value
        self.cloned = False

    def clone(self) -> "_Cloneable":
        c = _Cloneable(self.value)
        c.cloned = True
        return c


def test_clone_invokes_clone_on_text_matrix_and_line_matrix() -> None:
    gs = PDGraphicsState()
    tm = _Cloneable(1)
    tlm = _Cloneable(2)
    gs.set_text_matrix(tm)
    gs.set_text_line_matrix(tlm)
    clone = gs.clone()
    assert clone.get_text_matrix() is not tm
    assert clone.get_text_matrix().cloned is True
    assert clone.get_text_line_matrix() is not tlm
    assert clone.get_text_line_matrix().cloned is True


def test_clone_ctm_uses_copy_when_no_clone_method() -> None:
    """CTM without a ``clone`` attribute falls back to ``copy.copy``
    (line 372).
    """
    gs = PDGraphicsState()
    plain_ctm = ["a", "b", "c"]  # has no .clone method
    gs.set_current_transformation_matrix(plain_ctm)
    clone = gs.clone()
    assert clone.get_current_transformation_matrix() == plain_ctm
    assert clone.get_current_transformation_matrix() is not plain_ctm


def test_clone_resets_clipping_path_dirty_flag() -> None:
    gs = PDGraphicsState()
    gs.intersect_clipping_path("path")
    assert gs._is_clipping_path_dirty is True
    clone = gs.clone()
    assert clone._is_clipping_path_dirty is False


# ---------- non-stroking composite --------------------------------------


def test_non_stroking_java_composite_uses_non_stroking_alpha() -> None:
    gs = PDGraphicsState()
    gs.set_non_stroke_alpha_constant(0.3)
    comp = gs.get_non_stroking_java_composite()
    assert isinstance(comp, tuple)
    assert comp[1] == pytest.approx(0.3)
