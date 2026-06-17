"""Tests for the rasterisation paths in ``TilingPaint`` (Wave 1285).

Covers the new ``get_anchor_rect`` / ``get_image`` / ``create_context``
implementations: the TODO stubs previously returned ``None``.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.rendering.tiling_paint import MAXEDGE, TilingPaint


class _StubBBox:
    def __init__(self, x: float, y: float, w: float, h: float) -> None:
        self._x, self._y, self._w, self._h = x, y, w, h

    def get_lower_left_x(self) -> float:
        return self._x

    def get_lower_left_y(self) -> float:
        return self._y

    def get_upper_right_x(self) -> float:
        return self._x + self._w

    def get_upper_right_y(self) -> float:
        return self._y + self._h

    def get_width(self) -> float:
        return self._w

    def get_height(self) -> float:
        return self._h


class _StubPattern:
    def __init__(self, bbox: _StubBBox | None, x_step: float = 10.0, y_step: float = 10.0) -> None:
        self._bbox = bbox
        self._x_step = x_step
        self._y_step = y_step

    def get_b_box(self) -> _StubBBox | None:
        return self._bbox

    def get_x_step(self) -> float:
        return self._x_step

    def get_y_step(self) -> float:
        return self._y_step

    def get_matrix(self) -> Any:
        return None


class _StubDrawer:
    def __init__(self) -> None:
        self.called = False

    def draw_tiling_pattern(self, *_args, **_kwargs) -> None:
        self.called = True


@pytest.fixture
def pattern() -> _StubPattern:
    return _StubPattern(_StubBBox(0.0, 0.0, 8.0, 4.0), x_step=8.0, y_step=4.0)


def test_get_anchor_rect_uses_bbox_and_steps(pattern: _StubPattern) -> None:
    drawer = _StubDrawer()
    paint = TilingPaint(drawer, pattern)
    rect = paint.get_anchor_rect(pattern)
    assert rect == (0.0, 0.0, 8.0, 4.0)


def test_get_anchor_rect_returns_none_when_bbox_missing() -> None:
    drawer = _StubDrawer()
    paint = TilingPaint(drawer, _StubPattern(bbox=None))
    assert paint.get_anchor_rect(_StubPattern(bbox=None)) is None


def test_get_anchor_rect_zero_xstep_falls_back_to_bbox_width() -> None:
    pat = _StubPattern(_StubBBox(0.0, 0.0, 5.0, 5.0), x_step=0.0, y_step=5.0)
    paint = TilingPaint(_StubDrawer(), pat)
    rect = paint.get_anchor_rect(pat)
    assert rect[2] == 5.0  # width from bbox.get_width()


def test_get_image_returns_pillow_image_with_expected_size(pattern: _StubPattern) -> None:
    pytest.importorskip("PIL")
    drawer = _StubDrawer()
    paint = TilingPaint(drawer, pattern)
    rect = paint.get_anchor_rect(pattern)
    image = paint.get_image(drawer, pattern, None, None, rect)
    assert image is not None
    # rasterWidth = ceil(width * x_scale); identity xform → matches bbox
    assert image.size == (8, 4)
    assert image.mode == "RGBA"
    assert drawer.called  # drawer hook fired


def test_create_context_exposes_image_and_anchor(pattern: _StubPattern) -> None:
    pytest.importorskip("PIL")
    drawer = _StubDrawer()
    paint = TilingPaint(drawer, pattern)
    ctx = paint.create_context(None, None, None, None, None)
    assert ctx is not None
    assert ctx.anchor_rect == (0.0, 0.0, 8.0, 4.0)
    assert ctx.image is not None
    assert ctx.get_color_model() == "RGBA"


def test_create_context_dispose_is_safe(pattern: _StubPattern) -> None:
    pytest.importorskip("PIL")
    drawer = _StubDrawer()
    paint = TilingPaint(drawer, pattern)
    ctx = paint.create_context(None, None, None, None, None)
    # Should not raise.
    ctx.dispose()


def test_get_anchor_rect_clamps_huge_dimensions_to_maxedge() -> None:
    huge = MAXEDGE * 2
    pat = _StubPattern(_StubBBox(0.0, 0.0, 1.0, 1.0), x_step=huge, y_step=huge)
    paint = TilingPaint(_StubDrawer(), pat)
    rect = paint.get_anchor_rect(pat)
    assert rect is not None
    _, _, w, h = rect
    assert abs(w) <= MAXEDGE
    assert abs(h) <= MAXEDGE


def test_ceiling_static() -> None:
    # Mirrors upstream BigDecimal.setScale(5, CEILING).intValue(): 1.001 rounds
    # to 1.00100 at 5dp, then intValue truncates toward zero back to 1.
    assert TilingPaint.ceiling(1.0) == 1
    assert TilingPaint.ceiling(1.001) == 1
    assert TilingPaint.ceiling(-0.5) == 0


def test_get_transparency_constant(pattern: _StubPattern) -> None:
    paint = TilingPaint(_StubDrawer(), pattern)
    assert paint.get_transparency() == 3
