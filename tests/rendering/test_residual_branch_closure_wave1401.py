"""Wave 1401 — close residual partial branches in
``pypdfbox.rendering`` subtree.

Targets:

* ``soft_mask._clamp_unit`` lines 32, 34: under-zero and above-one
  branches (reachable via SoftMask construction with extreme backdrop
  colours).
* ``_pen_bridge`` lines 79->exit, 84->exit: delegate without
  ``move_to`` / ``line_to`` methods — the ``if fn is not None`` False
  branch fires.
* ``tiling_paint`` line 181->197: bbox-is-None branch inside
  ``TilingPaint.get_image``.
"""

from __future__ import annotations

from typing import Any

import pytest

# ========================================================== soft_mask clamp


class _StubBackdropColor:
    """A PDColor-like that returns the configured RGB triple from to_rgb()."""

    def __init__(self, r: float, g: float, b: float) -> None:
        self._rgb = (r, g, b)

    def to_rgb(self) -> tuple[float, float, float]:
        return self._rgb


def test_soft_mask_backdrop_color_with_negative_component_clamps_to_zero() -> None:
    """A backdrop colour component < 0 triggers ``_clamp_unit`` line 32:
    the ``if v < 0.0: return 0.0`` branch fires."""
    from pypdfbox.rendering.soft_mask import SoftMask

    backdrop = _StubBackdropColor(-0.5, 0.5, 0.5)
    soft = SoftMask(
        paint=object(),
        mask=object(),
        bbox_device=None,
        backdrop_color=backdrop,
    )
    assert 0 <= soft._bc <= 255


def test_soft_mask_backdrop_color_with_above_one_component_clamps_to_one() -> None:
    """A backdrop colour component > 1.0 triggers ``_clamp_unit`` line 34:
    the ``if v > 1.0: return 1.0`` branch fires."""
    from pypdfbox.rendering.soft_mask import SoftMask

    backdrop = _StubBackdropColor(0.5, 1.5, 0.5)
    soft = SoftMask(
        paint=object(),
        mask=object(),
        bbox_device=None,
        backdrop_color=backdrop,
    )
    assert 0 <= soft._bc <= 255


def test_soft_mask_backdrop_color_with_mixed_clamp_components() -> None:
    """Both clamp branches in one construction."""
    from pypdfbox.rendering.soft_mask import SoftMask

    backdrop = _StubBackdropColor(1.5, 0.5, -0.2)
    soft = SoftMask(
        paint=object(),
        mask=object(),
        bbox_device=None,
        backdrop_color=backdrop,
    )
    assert 0 <= soft._bc <= 255


def test_soft_mask_clamp_unit_inline_smoke() -> None:
    """Direct exercise of ``_clamp_unit`` — defensive coverage for the
    extreme boundary inputs."""
    from pypdfbox.rendering.soft_mask import _clamp_unit

    assert _clamp_unit(-1.0) == 0.0
    assert _clamp_unit(2.0) == 1.0
    assert _clamp_unit(0.5) == 0.5
    assert _clamp_unit(0.0) == 0.0
    assert _clamp_unit(1.0) == 1.0


# ========================================================== _pen_bridge


def test_pen_bridge_delegate_without_move_to_silently_drops_call() -> None:
    """A delegate missing ``move_to`` triggers the ``if fn is not None``
    False branch at line 79 (and similarly 84 for ``line_to``)."""
    pytest.importorskip("fontTools")
    from pypdfbox.rendering._pen_bridge import make_base_pen_bridge

    class _DelegateNoMethods:
        """Empty delegate — no move_to / line_to / etc."""

    bridge = make_base_pen_bridge(_DelegateNoMethods())
    bridge.moveTo((0.0, 0.0))
    bridge.lineTo((1.0, 1.0))


def test_pen_bridge_delegate_with_partial_methods_drops_only_missing() -> None:
    """A delegate with ``move_to`` but no ``line_to``: 79 True, 84 False."""
    pytest.importorskip("fontTools")
    from pypdfbox.rendering._pen_bridge import make_base_pen_bridge

    calls: list[tuple[str, Any]] = []

    class _DelegateMoveOnly:
        def move_to(self, pt: tuple[float, float]) -> None:
            calls.append(("move_to", pt))

    bridge = make_base_pen_bridge(_DelegateMoveOnly())
    bridge.moveTo((0.0, 0.0))
    bridge.lineTo((1.0, 1.0))  # silent drop on missing method
    assert calls == [("move_to", (0.0, 0.0))]


# ========================================================== tiling_paint


def test_tiling_paint_get_image_with_pattern_lacking_bbox_skips_translate() -> None:
    """``TilingPaint.get_image`` 181->197: when ``pattern.get_b_box()``
    returns ``None`` the ``if bbox is not None`` False branch fires
    (the translate step is skipped, drawer is still called).

    We construct ``TilingPaint`` with a fake pattern that has a bbox
    (satisfies ``__init__``'s ``get_anchor_rect`` call), then drive
    ``get_image`` directly with a *different* stub pattern whose
    ``get_b_box`` returns None — this targets the bbox-None branch
    inside ``get_image`` itself.
    """
    pytest.importorskip("PIL")
    from pypdfbox.rendering.tiling_paint import TilingPaint
    from pypdfbox.util.matrix import Matrix

    class _FakeBBox:
        def get_width(self) -> float:
            return 10.0

        def get_height(self) -> float:
            return 10.0

        def get_lower_left_x(self) -> float:
            return 0.0

        def get_lower_left_y(self) -> float:
            return 0.0

    class _FakePatternWithBBox:
        def get_matrix(self) -> Matrix:
            return Matrix.get_scale_instance(1.0, 1.0)

        def get_b_box(self) -> _FakeBBox:
            return _FakeBBox()

        def get_x_step(self) -> float:
            return 10.0

        def get_y_step(self) -> float:
            return 10.0

    class _StubDrawer:
        def __init__(self) -> None:
            self.calls: list[Any] = []

        def draw_tiling_pattern(
            self, pattern: Any, color: Any, color_space: Any
        ) -> None:
            self.calls.append((pattern, color, color_space))

    drawer = _StubDrawer()
    paint = TilingPaint(drawer=drawer, pattern=_FakePatternWithBBox())

    # Now drive get_image with a STUB pattern that lacks bbox so the 181
    # check falls through to the False branch (no translate).
    class _NoBBoxPattern:
        def get_b_box(self) -> None:
            return None

    img = paint.get_image(
        _StubDrawer(),
        _NoBBoxPattern(),
        None,
        None,
        (0.0, 0.0, 10.0, 10.0),
    )
    assert img is not None
