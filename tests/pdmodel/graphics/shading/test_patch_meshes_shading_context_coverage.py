"""Coverage tests for
:mod:`pypdfbox.pdmodel.graphics.shading.patch_meshes_shading_context`.

Exercises ``__init__`` (with and without background / device bounds),
``calc_pixel_table_array`` patch iteration, ``is_data_empty`` both
states, and ``dispose``.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.pdmodel.graphics.shading.patch import Patch
from pypdfbox.pdmodel.graphics.shading.patch_meshes_shading_context import (
    PatchMeshesShadingContext,
)
from pypdfbox.pdmodel.graphics.shading.shaded_triangle import ShadedTriangle


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _Bg:
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def to_float_array(self) -> list[float]:
        return list(self._values)


class _CS:
    def to_rgb(self, values: list[float]) -> list[float]:
        first = values[0] if values else 0.0
        return [first, first, first]


class _StubPatch(Patch):
    def __init__(self, triangles: list[ShadedTriangle]) -> None:
        super().__init__([[0.0], [0.5], [0.25], [0.75]])
        self.list_of_triangles = triangles

    def get_flag1_edge(self) -> list[tuple[float, float]]:
        return []

    def get_flag2_edge(self) -> list[tuple[float, float]]:
        return []

    def get_flag3_edge(self) -> list[tuple[float, float]]:
        return []


class _Shading:
    def __init__(
        self,
        patches: list[_StubPatch],
        background: _Bg | None = None,
    ) -> None:
        self._patches = patches
        self._background = background

    def get_color_space(self) -> _CS:
        return _CS()

    def get_background(self) -> _Bg | None:
        return self._background

    def get_function(self) -> Any:
        return None

    def collect_patches(
        self, xform: Any, matrix: Any, control_points: int,
    ) -> list[_StubPatch]:
        return list(self._patches)


def _triangle() -> ShadedTriangle:
    return ShadedTriangle(
        [(0.0, 0.0), (2.0, 0.0), (1.0, 2.0)],
        [[0.0], [0.5], [1.0]],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_init_collects_patches_and_creates_pixel_table_when_device_bounds_given() -> None:
    shading = _Shading([_StubPatch([_triangle()])])
    ctx = PatchMeshesShadingContext(shading, None, None, None, (0, 0, 4, 4), 12)
    # Pixel table allocated → get_value_from_array no longer returns -1 for
    # every pixel: triangle path filled at least one entry.
    has_filled = any(
        ctx.get_value_from_array(x, y) >= 0 for x in range(5) for y in range(5)
    )
    assert has_filled is True


def test_init_skips_pixel_table_when_device_bounds_is_none() -> None:
    shading = _Shading([_StubPatch([])])
    ctx = PatchMeshesShadingContext(shading, None, None, None, None, 12)
    # No bounds → pixel table never built → defaults to -1 sentinel.
    assert ctx.get_value_from_array(0, 0) == -1


def test_calc_pixel_table_array_uses_background_when_present() -> None:
    bg = _Bg([0.5])
    shading = _Shading([_StubPatch([])], background=bg)
    ctx = PatchMeshesShadingContext(shading, None, None, None, (0, 0, 2, 2), 12)
    arr = ctx.calc_pixel_table_array((0, 0, 2, 2))
    assert len(arr) == 3
    assert len(arr[0]) == 3
    # Every cell initialised to the RGB background (not -1) when no
    # triangle overrides it.
    rgb = ctx.get_rgb_background()
    assert arr[0][0] == rgb


def test_calc_pixel_table_array_uses_sentinel_when_no_background() -> None:
    shading = _Shading([_StubPatch([])])
    ctx = PatchMeshesShadingContext(shading, None, None, None, (0, 0, 2, 2), 12)
    arr = ctx.calc_pixel_table_array((0, 0, 2, 2))
    assert arr[0][0] == -1


def test_is_data_empty_true_when_no_patches() -> None:
    shading = _Shading([])
    ctx = PatchMeshesShadingContext(shading, None, None, None, None, 12)
    assert ctx.is_data_empty() is True


def test_is_data_empty_false_when_patches_collected() -> None:
    shading = _Shading([_StubPatch([_triangle()])])
    ctx = PatchMeshesShadingContext(shading, None, None, None, None, 12)
    assert ctx.is_data_empty() is False


def test_dispose_clears_patch_list_and_propagates_to_super() -> None:
    shading = _Shading([_StubPatch([_triangle()])])
    ctx = PatchMeshesShadingContext(shading, None, None, None, None, 12)
    assert ctx.is_data_empty() is False
    ctx.dispose()
    assert ctx.is_data_empty() is True
    # Super dispose nulls out the shading colour space too.
    assert ctx.get_shading_color_space() is None
