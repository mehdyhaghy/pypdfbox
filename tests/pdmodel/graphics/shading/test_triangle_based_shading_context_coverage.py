"""Coverage tests for
:mod:`pypdfbox.pdmodel.graphics.shading.triangle_based_shading_context`.

Exercises ``create_pixel_table`` (which sets the offsets), the abstract
``calc_pixel_table_array`` / ``is_data_empty`` raises, the
degree-2 line branch inside ``calc_pixel_table``, ``add_line_points``
None-guard, the out-of-bounds branches of ``add_value_to_array`` /
``get_value_from_array``, the function-driven ``eval_function_and_convert_to_rgb``
branch, and ``get_raster`` with empty / populated data.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.pdmodel.graphics.shading.line import Line
from pypdfbox.pdmodel.graphics.shading.shaded_triangle import ShadedTriangle
from pypdfbox.pdmodel.graphics.shading.triangle_based_shading_context import (
    TriangleBasedShadingContext,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _CS:
    def to_rgb(self, values: list[float]) -> list[float]:
        first = values[0] if values else 0.0
        return [first, first, first]


class _Bg:
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def to_float_array(self) -> list[float]:
        return list(self._values)


class _Shading:
    def __init__(
        self,
        background: _Bg | None = None,
        function: Any = None,
    ) -> None:
        self._background = background
        self._function = function

    def get_color_space(self) -> _CS:
        return _CS()

    def get_background(self) -> _Bg | None:
        return self._background

    def get_function(self) -> Any:
        return self._function

    def eval_function(self, values: list[float]) -> list[float]:
        # Demonstrate the function-applied branch — squelches input.
        return [v * 0.5 for v in values]


class _ConcreteTBC(TriangleBasedShadingContext):
    """Concrete subclass exposing data and overriding the abstract abstract
    contract so ``get_raster`` can iterate."""

    def __init__(
        self,
        shading: _Shading,
        triangles: list[ShadedTriangle],
        device_bounds: tuple[int, int, int, int] | None = None,
    ) -> None:
        super().__init__(shading, None, None, None)
        self._triangles = triangles
        if device_bounds is not None:
            self.create_pixel_table(device_bounds)

    def calc_pixel_table_array(
        self, device_bounds: tuple[int, int, int, int],
    ) -> list[list[int]]:
        _x, _y, w, h = device_bounds
        initial = self.get_rgb_background() if self.get_background() is not None else -1
        array: list[list[int]] = [[initial] * (h + 1) for _ in range(w + 1)]
        self.calc_pixel_table(self._triangles, array, device_bounds)
        return array

    def is_data_empty(self) -> bool:
        return not self._triangles


# ---------------------------------------------------------------------------
# Abstract guards
# ---------------------------------------------------------------------------
def test_calc_pixel_table_array_raises_on_base_class() -> None:
    ctx = TriangleBasedShadingContext(_Shading(), None, None, None)
    with pytest.raises(NotImplementedError, match="calc_pixel_table_array"):
        ctx.calc_pixel_table_array((0, 0, 1, 1))


def test_is_data_empty_raises_on_base_class() -> None:
    ctx = TriangleBasedShadingContext(_Shading(), None, None, None)
    with pytest.raises(NotImplementedError, match="is_data_empty"):
        ctx.is_data_empty()


# ---------------------------------------------------------------------------
# Pixel-table machinery
# ---------------------------------------------------------------------------
def test_create_pixel_table_sets_offsets_and_writes_array() -> None:
    tri = ShadedTriangle(
        [(0.0, 0.0), (4.0, 0.0), (0.0, 4.0)],
        [[1.0], [1.0], [1.0]],
    )
    ctx = _ConcreteTBC(_Shading(), [tri], device_bounds=(0, 0, 4, 4))
    # Interior of the triangle has the colour filled.
    assert ctx.get_value_from_array(1, 1) >= 0


def test_get_value_from_array_returns_negative_one_before_creation() -> None:
    ctx = _ConcreteTBC(_Shading(), [])
    assert ctx.get_value_from_array(0, 0) == -1


def test_get_value_from_array_returns_negative_one_for_out_of_bounds() -> None:
    tri = ShadedTriangle(
        [(0.0, 0.0), (2.0, 0.0), (0.0, 2.0)],
        [[1.0], [1.0], [1.0]],
    )
    ctx = _ConcreteTBC(_Shading(), [tri], device_bounds=(0, 0, 2, 2))
    assert ctx.get_value_from_array(99, 99) == -1
    assert ctx.get_value_from_array(-99, -99) == -1


def test_add_value_to_array_silently_drops_out_of_bounds_writes() -> None:
    ctx = _ConcreteTBC(_Shading(), [], device_bounds=(0, 0, 2, 2))
    array: list[list[int]] = [[-1] * 3 for _ in range(3)]
    # Out-of-bounds writes do nothing.
    ctx.add_value_to_array((99, 99), 0xFF00FF, array)
    ctx.add_value_to_array((-99, -99), 0xFF00FF, array)
    assert all(cell == -1 for row in array for cell in row)
    # In-bounds write lands in the array.
    ctx.add_value_to_array((1, 1), 0x123456, array)
    assert array[1][1] == 0x123456


# ---------------------------------------------------------------------------
# calc_pixel_table branches
# ---------------------------------------------------------------------------
def test_calc_pixel_table_handles_degree_two_triangle_via_line() -> None:
    """Triangle with two coincident corners reduces to a line; the loop
    should take the ``degree == 2`` shortcut and call
    ``add_line_points`` exactly once.
    """
    tri = ShadedTriangle(
        [(0.0, 0.0), (4.0, 4.0), (4.0, 4.0)],
        [[1.0], [1.0], [1.0]],
    )
    ctx = _ConcreteTBC(_Shading(), [tri], device_bounds=(0, 0, 4, 4))
    # Points on the diagonal should be filled.
    assert ctx.get_value_from_array(2, 2) >= 0


def test_add_line_points_is_a_noop_for_none() -> None:
    ctx = _ConcreteTBC(_Shading(), [], device_bounds=(0, 0, 2, 2))
    array: list[list[int]] = [[-1] * 3 for _ in range(3)]
    # None line is silently ignored.
    ctx.add_line_points(None, array)
    assert all(cell == -1 for row in array for cell in row)


def test_add_line_points_writes_into_array_for_real_line() -> None:
    ctx = _ConcreteTBC(_Shading(), [], device_bounds=(0, 0, 4, 4))
    array: list[list[int]] = [[-1] * 5 for _ in range(5)]
    line = Line((0, 0), (3, 0), [1.0], [1.0])
    ctx.add_line_points(line, array)
    assert array[0][0] >= 0


# ---------------------------------------------------------------------------
# eval_function_and_convert_to_rgb
# ---------------------------------------------------------------------------
def test_eval_function_path_invoked_when_shading_function_present() -> None:
    """When the shading exposes a function, ``eval_function`` is called
    before colour-space conversion.
    """
    ctx = _ConcreteTBC(_Shading(function=object()), [])
    # Input 0.8 → eval_function squashes to 0.4 → grey channel = 102.
    value = ctx.eval_function_and_convert_to_rgb([0.8])
    r = value & 0xFF
    g = (value >> 8) & 0xFF
    b = (value >> 16) & 0xFF
    assert r == g == b == 102


def test_eval_function_skipped_when_shading_function_absent() -> None:
    ctx = _ConcreteTBC(_Shading(function=None), [])
    value = ctx.eval_function_and_convert_to_rgb([0.8])
    r = value & 0xFF
    # 0.8 * 255 = 204 (truncation via int()).
    assert r == 204


# ---------------------------------------------------------------------------
# get_raster
# ---------------------------------------------------------------------------
def test_get_raster_returns_empty_image_when_data_and_background_empty() -> None:
    ctx = _ConcreteTBC(_Shading(), [], device_bounds=(0, 0, 4, 4))
    img = ctx.get_raster(0, 0, 2, 2)
    assert img.size == (2, 2)
    # Every pixel is transparent.
    for x in range(2):
        for y in range(2):
            assert img.getpixel((x, y)) == (0, 0, 0, 0)


def test_get_raster_paints_pixels_when_table_populated() -> None:
    tri = ShadedTriangle(
        [(0.0, 0.0), (4.0, 0.0), (0.0, 4.0)],
        [[1.0], [1.0], [1.0]],
    )
    ctx = _ConcreteTBC(_Shading(), [tri], device_bounds=(0, 0, 4, 4))
    img = ctx.get_raster(0, 0, 4, 4)
    # At least one pixel inside the triangle is opaque white-ish.
    found_painted = False
    for x in range(4):
        for y in range(4):
            r, g, b, a = img.getpixel((x, y))
            if a == 255:
                found_painted = True
                assert r == 255
                assert g == 255
                assert b == 255
    assert found_painted is True


def test_get_raster_renders_when_background_set_even_if_data_empty() -> None:
    """If background is non-None we skip the early-return and the raster
    reflects pixel-table values (which default to -1 → transparent in
    this minimal subclass that doesn't pre-fill).
    """
    bg = _Bg([1.0])
    ctx = _ConcreteTBC(_Shading(background=bg), [], device_bounds=(0, 0, 2, 2))
    img = ctx.get_raster(0, 0, 2, 2)
    assert img.size == (2, 2)
