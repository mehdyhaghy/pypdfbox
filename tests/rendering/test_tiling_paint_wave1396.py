"""Wave 1396 — verify TilingPaint.get_image runs symbolic-graphics cleanup in finally.

Mirrors upstream PDFBOX-5660 (svn r1934553, commit 1e5bee9 on apache/pdfbox
trunk): the inner ``drawer.drawTilingPattern(...)`` call is wrapped in
try/finally so the AWT ``Graphics2D`` is disposed even when the drawer
raises. The Python port's ``ImageDraw.Draw`` analogue holds no OS
resources — disposal is symbolic ``del draw, new_pm`` — but the structural
parity has to hold so future drawer changes that *do* acquire resources
inherit the correct cleanup ordering.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.rendering.tiling_paint import TilingPaint


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


class _RaisingDrawer:
    """Drawer whose ``draw_tiling_pattern`` always raises an expected exception."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.called = False

    def draw_tiling_pattern(self, *_args, **_kwargs) -> None:
        self.called = True
        raise self._exc


class _UnexpectedRaisingDrawer:
    """Drawer that raises an exception not in the handled tuple."""

    def __init__(self) -> None:
        self.called = False

    def draw_tiling_pattern(self, *_args, **_kwargs) -> None:
        self.called = True
        raise RuntimeError("boom")


@pytest.fixture
def pattern() -> _StubPattern:
    return _StubPattern(_StubBBox(0.0, 0.0, 8.0, 4.0), x_step=8.0, y_step=4.0)


@pytest.mark.parametrize(
    "exc",
    [AttributeError("nope"), TypeError("nope"), ValueError("nope")],
    ids=["attribute_error", "type_error", "value_error"],
)
def test_get_image_swallows_handled_drawer_exception(
    pattern: _StubPattern, exc: Exception
) -> None:
    """Handled drawer exceptions must not propagate — try/except still fires."""
    drawer = _RaisingDrawer(exc)
    # Construction triggers ``get_image`` internally; if the finally clause
    # were broken the constructor would itself raise.
    paint = TilingPaint(drawer, pattern)
    assert drawer.called is True
    assert paint._image is not None  # blank cell returned on swallowed exc


def test_get_image_propagates_unexpected_exception(pattern: _StubPattern) -> None:
    """RuntimeError isn't in the handled tuple, but the finally block must still run.

    If the symbolic ``del draw, new_pm`` finally block were missing the
    behaviour would be identical (Python GC reclaims locals on stack
    unwind) — but the assertion ``RuntimeError`` propagates verifies that
    the new structure didn't accidentally swallow non-listed exceptions
    via an over-broad ``except``.
    """
    drawer = _UnexpectedRaisingDrawer()
    with pytest.raises(RuntimeError, match="boom"):
        TilingPaint(drawer, pattern)
    assert drawer.called is True


def test_get_image_happy_path_still_renders(pattern: _StubPattern) -> None:
    """No-exception path: drawer called, image populated, no leak of locals."""

    class _OkDrawer:
        def __init__(self) -> None:
            self.called = False

        def draw_tiling_pattern(self, *_args, **_kwargs) -> None:
            self.called = True

    drawer = _OkDrawer()
    paint = TilingPaint(drawer, pattern)
    assert drawer.called is True
    assert paint._image is not None
    # Anchor rect must still be set after the finally block.
    assert paint._anchor_rect == (0.0, 0.0, 8.0, 4.0)
