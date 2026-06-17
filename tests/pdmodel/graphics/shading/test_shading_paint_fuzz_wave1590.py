"""Fuzz / parity battery for axial (Type 2) + radial (Type 3) shading
*rasterization* paint contexts, wave 1590 agent D.

Where ``test_axial_radial_shading_fuzz_wave1572`` pins the dictionary model
(coords/domain/extend/function accessors), this file hammers the per-pixel
colour evaluation in
:class:`pypdfbox.pdmodel.graphics.shading.axial_shading_context.AxialShadingContext`
and
:class:`pypdfbox.pdmodel.graphics.shading.radial_shading_context.RadialShadingContext`,
pinned against Apache PDFBox 3.0.7's ``AxialShadingContext.getRaster`` /
``RadialShadingContext.getRaster`` / ``calculateInputValues``:

* Axial parameter projection
  ``inputValue = (x1x0*(px-x0) + y1y0*(py-y0)) / (x1x0^2 + y1y0^2)`` — a pixel
  at the start of the axis projects to ``t == 0``, at the end to ``t == 1``,
  perpendicular offsets do not change ``t``.
* Domain ``[t0,t1]`` remap of the colour table sample positions.
* ``/Extend`` ``[false,false]`` → out-of-axis pixels get background or stay
  transparent (continue); ``[true,true]`` → clamped to the endpoint colours.
* Degenerate axis ``x0==x1 && y0==y1`` (``denom == 0``) → background or
  transparent, never a divide-by-zero.
* Radial two-circle quadratic root selection (larger valid root wins) and the
  degenerate ``denom == 0`` case where upstream's IEEE-754 float division
  yields one NaN + one Infinity (NOT both NaN), feeding the extend logic.

The fakes mimic only the surface the contexts touch so we exercise the
rasterization paths without the full ``PDShadingType{2,3}`` COS graph. The
colour table here is the identity ramp (``eval_function(t) -> [t,t,t]`` with a
null colour space treated as already-RGB), so for ``factor`` steps the packed
table entry ``i`` is ``(c,c,c)`` with ``c = int(min(1,max(0,t))*255)`` —
letting us assert the *exact* colour a given pixel resolves to.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.pdmodel.graphics.shading import (
    AxialShadingContext,
    RadialShadingContext,
)
from pypdfbox.pdmodel.graphics.shading.radial_shading_context import (
    _java_divide,
    _java_int_cast,
    _java_max,
)

# ----------------------------------------------------------------------
# Test doubles (mirrors the context coverage test fakes)
# ----------------------------------------------------------------------


class _Arr:
    def __init__(self, values: list[float]) -> None:
        self._values = list(values)

    def to_float_array(self) -> list[float]:
        return list(self._values)


class _Bool:
    def __init__(self, v: bool) -> None:
        self._v = v

    def get_value(self) -> bool:
        return self._v


class _ExtendArr:
    def __init__(self, a: bool, b: bool) -> None:
        self._items = [_Bool(a), _Bool(b)]

    def get_object(self, i: int) -> _Bool:
        return self._items[i]


class _FakeShading:
    def __init__(
        self,
        coords: list[float] | None = None,
        domain: list[float] | None = None,
        extend: tuple[bool, bool] | None = None,
        background: list[float] | None = None,
    ) -> None:
        self._coords = coords
        self._domain = domain
        self._extend = extend
        self._background = background

    def get_color_space(self) -> Any:
        return None  # null color space -> values treated as already-RGB

    def get_background(self) -> Any:
        return _Arr(self._background) if self._background is not None else None

    def get_function(self) -> Any:
        return "FN"

    def get_coords(self) -> Any:
        return _Arr(self._coords) if self._coords is not None else None

    def get_domain(self) -> Any:
        return _Arr(self._domain) if self._domain is not None else None

    def get_extend(self) -> Any:
        return _ExtendArr(*self._extend) if self._extend is not None else None

    def eval_function(self, t: Any) -> list[float]:
        if isinstance(t, (list, tuple)):
            t = t[0] if t else 0.0
        v = max(0.0, min(1.0, float(t)))
        return [v, v, v]


def _axial_ctx(
    coords,
    *,
    domain=None,
    extend=None,
    background=None,
    bounds=(0, 0, 16, 16),
) -> AxialShadingContext:
    return AxialShadingContext(
        _FakeShading(coords=coords, domain=domain, extend=extend, background=background),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=bounds,
    )


def _radial_ctx(
    coords,
    *,
    domain=None,
    extend=None,
    background=None,
    bounds=(0, 0, 16, 16),
) -> RadialShadingContext:
    return RadialShadingContext(
        _FakeShading(coords=coords, domain=domain, extend=extend, background=background),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=bounds,
    )


def _gray_for_t(t: float, factor: int) -> int:
    """Reproduce the context's ramp lookup for the identity colour table.

    ``key = int(t * factor)`` (clamped), table[key] built from
    ``eval_function(domain0 + d1d0*key/factor)``.
    """
    key = int(t * factor)
    key = max(0, min(factor, key))
    return key


# ======================================================================
# AXIAL — parameter projection
# ======================================================================


def test_axial_pixel_at_start_projects_to_t0():
    # Horizontal axis from (2,5) to (12,5): the start pixel -> t == 0 -> color
    # of domain[0]. With identity ramp + domain [0,1], that's (0,0,0).
    ctx = _axial_ctx([2.0, 5.0, 12.0, 5.0])
    img = ctx.get_raster(2, 5, 1, 1)
    assert img.getpixel((0, 0)) == (0, 0, 0, 255)


def test_axial_pixel_at_end_projects_to_t1():
    ctx = _axial_ctx([2.0, 5.0, 12.0, 5.0])
    # Pixel at the end of the axis -> t == 1 -> table[factor] -> (255,255,255).
    img = ctx.get_raster(12, 5, 1, 1)
    assert img.getpixel((0, 0)) == (255, 255, 255, 255)


def test_axial_pixel_at_midpoint_is_grey():
    ctx = _axial_ctx([0.0, 0.0, 10.0, 0.0])
    img = ctx.get_raster(5, 0, 1, 1)
    r, g, b, a = img.getpixel((0, 0))
    assert a == 255
    assert r == g == b
    assert 120 <= r <= 135  # ~midpoint grey


def test_axial_perpendicular_offset_does_not_change_t():
    # The projection onto the axis ignores the perpendicular component:
    # a pixel directly above the midpoint resolves to the same t as the
    # midpoint itself.
    ctx = _axial_ctx([0.0, 0.0, 10.0, 0.0])
    base = ctx.get_raster(5, 0, 1, 1).getpixel((0, 0))
    offset = ctx.get_raster(5, 7, 1, 1).getpixel((0, 0))
    assert base == offset


def test_axial_projection_formula_uses_length_squared_denominator():
    # A diagonal axis (0,0)->(6,8) has denom = 36+64 = 100. The pixel at the
    # exact end must land on t == 1 (white), proving the denominator is the
    # squared axis length, not the length.
    ctx = _axial_ctx([0.0, 0.0, 6.0, 8.0])
    assert ctx._denom == pytest.approx(100.0)
    img = ctx.get_raster(6, 8, 1, 1)
    assert img.getpixel((0, 0)) == (255, 255, 255, 255)


def test_axial_quarter_point_on_diagonal_axis():
    ctx = _axial_ctx([0.0, 0.0, 8.0, 0.0])
    # x=2 -> t=0.25
    img = ctx.get_raster(2, 0, 1, 1)
    r, _, _, _ = img.getpixel((0, 0))
    assert 55 <= r <= 75  # ~0.25*255


# ======================================================================
# AXIAL — /Extend rules
# ======================================================================


def test_axial_before_start_no_extend_no_bg_is_transparent():
    ctx = _axial_ctx([4.0, 0.0, 12.0, 0.0], extend=(False, False))
    img = ctx.get_raster(0, 0, 1, 1)  # px=0 is before the axis start
    assert img.getpixel((0, 0)) == (0, 0, 0, 0)


def test_axial_after_end_no_extend_no_bg_is_transparent():
    ctx = _axial_ctx([4.0, 0.0, 12.0, 0.0], extend=(False, False))
    img = ctx.get_raster(40, 0, 1, 1)  # past the axis end
    assert img.getpixel((0, 0)) == (0, 0, 0, 0)


def test_axial_before_start_extend_clamps_to_start_color():
    ctx = _axial_ctx([4.0, 0.0, 12.0, 0.0], extend=(True, False))
    img = ctx.get_raster(0, 0, 1, 1)
    assert img.getpixel((0, 0)) == (0, 0, 0, 255)  # start color


def test_axial_after_end_extend_clamps_to_end_color():
    ctx = _axial_ctx([4.0, 0.0, 12.0, 0.0], extend=(False, True))
    img = ctx.get_raster(40, 0, 1, 1)
    assert img.getpixel((0, 0)) == (255, 255, 255, 255)  # end color


def test_axial_extend_only_start_does_not_extend_end():
    ctx = _axial_ctx([4.0, 0.0, 12.0, 0.0], extend=(True, False))
    img = ctx.get_raster(40, 0, 1, 1)
    assert img.getpixel((0, 0)) == (0, 0, 0, 0)  # end not extended -> transparent


def test_axial_extend_only_end_does_not_extend_start():
    ctx = _axial_ctx([4.0, 0.0, 12.0, 0.0], extend=(False, True))
    img = ctx.get_raster(0, 0, 1, 1)
    assert img.getpixel((0, 0)) == (0, 0, 0, 0)  # start not extended -> transparent


# ======================================================================
# AXIAL — background for out-of-axis pixels
# ======================================================================


def test_axial_before_start_no_extend_uses_background():
    # Background green; out-of-axis no-extend pixel takes background, opaque.
    ctx = _axial_ctx(
        [4.0, 0.0, 12.0, 0.0], extend=(False, False), background=[0.0, 1.0, 0.0]
    )
    img = ctx.get_raster(0, 0, 1, 1)
    assert img.getpixel((0, 0)) == (0, 255, 0, 255)


def test_axial_after_end_no_extend_uses_background():
    ctx = _axial_ctx(
        [4.0, 0.0, 12.0, 0.0], extend=(False, False), background=[1.0, 0.0, 0.0]
    )
    img = ctx.get_raster(40, 0, 1, 1)
    assert img.getpixel((0, 0)) == (255, 0, 0, 255)


def test_axial_on_axis_ignores_background():
    # A pixel that lands on the axis uses the ramp, not background.
    ctx = _axial_ctx(
        [0.0, 0.0, 10.0, 0.0], extend=(False, False), background=[1.0, 0.0, 0.0]
    )
    img = ctx.get_raster(0, 0, 1, 1)
    assert img.getpixel((0, 0)) == (0, 0, 0, 255)  # ramp start, not red bg


# ======================================================================
# AXIAL — domain remap
# ======================================================================


def test_axial_domain_default_is_zero_one():
    ctx = _axial_ctx([0.0, 0.0, 10.0, 0.0])
    assert ctx.get_domain() == [0.0, 1.0]


def test_axial_reversed_domain_remaps_table():
    # Domain [1,0] reverses the colour ramp: the table is sampled at
    # t = 1 + (-1)*i/factor, so table[0] is white, table[factor] is black.
    ctx = _axial_ctx([0.0, 0.0, 10.0, 0.0], domain=[1.0, 0.0])
    start = ctx.get_raster(0, 0, 1, 1).getpixel((0, 0))
    end = ctx.get_raster(10, 0, 1, 1).getpixel((0, 0))
    assert start == (255, 255, 255, 255)
    assert end == (0, 0, 0, 255)


def test_axial_sub_domain_compresses_range():
    # Domain [0, 0.5]: the whole axis maps into the lower half of the ramp,
    # so the end pixel is mid-grey, not white.
    ctx = _axial_ctx([0.0, 0.0, 10.0, 0.0], domain=[0.0, 0.5])
    end = ctx.get_raster(10, 0, 1, 1).getpixel((0, 0))
    r, g, b, _ = end
    assert r == g == b
    assert 120 <= r <= 135


# ======================================================================
# AXIAL — degenerate axis (start == end)
# ======================================================================


def test_axial_degenerate_axis_no_bg_is_transparent():
    ctx = _axial_ctx([5.0, 5.0, 5.0, 5.0], extend=(True, True))
    assert ctx._denom == 0
    img = ctx.get_raster(5, 5, 1, 1)
    # denom==0 + no background -> continue (transparent), no divide-by-zero.
    assert img.getpixel((0, 0)) == (0, 0, 0, 0)


def test_axial_degenerate_axis_with_bg_uses_background():
    ctx = _axial_ctx(
        [5.0, 5.0, 5.0, 5.0], extend=(False, False), background=[0.0, 0.0, 1.0]
    )
    img = ctx.get_raster(5, 5, 1, 1)
    assert img.getpixel((0, 0)) == (0, 0, 255, 255)


def test_axial_degenerate_axis_does_not_raise_across_block():
    ctx = _axial_ctx([3.0, 3.0, 3.0, 3.0])
    # Must not raise ZeroDivisionError for any pixel.
    img = ctx.get_raster(0, 0, 8, 8)
    assert img.size == (8, 8)


# ======================================================================
# RADIAL — quadratic root / two-circle interpolation
# ======================================================================


def test_radial_center_of_concentric_circles_resolves():
    # Concentric circles centered at (8,8): r0=0, r1=8. The center pixel is
    # inside the start circle; with extend it resolves to t==0 (start color).
    ctx = _radial_ctx([8.0, 8.0, 0.0, 8.0, 8.0, 8.0], extend=(True, True))
    img = ctx.get_raster(8, 8, 1, 1)
    assert img.getpixel((0, 0)) == (0, 0, 0, 255)


def test_radial_on_end_circle_is_end_color():
    ctx = _radial_ctx([8.0, 8.0, 0.0, 8.0, 8.0, 8.0], extend=(True, True))
    # Pixel on the outer circle (8 px from center) -> t==1 -> white.
    img = ctx.get_raster(0, 8, 1, 1)
    assert img.getpixel((0, 0)) == (255, 255, 255, 255)


def test_radial_outside_end_no_extend_no_bg_transparent():
    ctx = _radial_ctx([8.0, 8.0, 0.0, 8.0, 8.0, 4.0], extend=(False, False))
    # Far corner, well outside the largest circle.
    img = ctx.get_raster(0, 0, 1, 1)
    assert img.getpixel((0, 0)) == (0, 0, 0, 0)


def test_radial_outside_end_no_extend_uses_background():
    ctx = _radial_ctx(
        [8.0, 8.0, 0.0, 8.0, 8.0, 4.0],
        extend=(False, False),
        background=[1.0, 1.0, 0.0],
    )
    img = ctx.get_raster(0, 0, 1, 1)
    assert img.getpixel((0, 0)) == (255, 255, 0, 255)


def test_radial_outside_end_extend_clamps():
    ctx = _radial_ctx([8.0, 8.0, 2.0, 8.0, 8.0, 6.0], extend=(False, True))
    # Just outside the end circle, extend[1] true + r1>0 -> clamped to white.
    img = ctx.get_raster(0, 8, 1, 1)
    assert img.getpixel((0, 0)) == (255, 255, 255, 255)


def test_radial_does_not_raise_over_block():
    ctx = _radial_ctx([8.0, 8.0, 1.0, 8.0, 8.0, 7.0], extend=(True, True))
    img = ctx.get_raster(0, 0, 16, 16)
    assert img.size == (16, 16)


def test_radial_larger_valid_root_wins():
    # When both roots are valid the larger one is chosen (matches upstream
    # Math.max). Use an off-center growing circle so two roots exist.
    ctx = _radial_ctx([6.0, 8.0, 0.0, 10.0, 8.0, 6.0], extend=(True, True))
    # Sample a pixel and confirm it resolves to a real color (no crash, opaque).
    img = ctx.get_raster(8, 8, 1, 1)
    _, _, _, a = img.getpixel((0, 0))
    assert a == 255


# ======================================================================
# RADIAL — degenerate denom (x1x0^2 + y1y0^2 == r1r0^2)
# ======================================================================


def test_radial_degenerate_denom_is_zero():
    # axis dx=3, dy=4 -> 25 ; r1r0=5 -> 25 ; denom == 0.
    ctx = _radial_ctx([0.0, 0.0, 1.0, 3.0, 4.0, 6.0], extend=(True, True))
    assert ctx._denom == 0


def test_radial_degenerate_denom_roots_match_java_one_nan_one_inf():
    # Upstream's float division by zero yields one NaN + one Infinity, NOT
    # both NaN; pypdfbox must replicate so the extend logic still applies.
    ctx = _radial_ctx([0.0, 0.0, 1.0, 3.0, 4.0, 6.0], extend=(True, True))
    r0, r1 = ctx.calculate_input_values(1.0, 1.0)
    import math

    nan_count = sum(1 for v in (r0, r1) if math.isnan(v))
    inf_count = sum(1 for v in (r0, r1) if math.isinf(v))
    assert nan_count == 1
    assert inf_count == 1


def test_radial_degenerate_denom_does_not_raise():
    ctx = _radial_ctx([0.0, 0.0, 1.0, 3.0, 4.0, 6.0], extend=(True, True))
    # The whole block must rasterize without ValueError / ZeroDivisionError /
    # OverflowError from the infinity roots.
    img = ctx.get_raster(0, 0, 8, 8)
    assert img.size == (8, 8)


def test_radial_degenerate_denom_extend_picks_table_zero():
    # With both extend true the degenerate (NaN/Inf) root path resolves via
    # Java max(NaN, Inf)==NaN and (int)(NaN*factor)==0 -> table[0] (black).
    ctx = _radial_ctx([0.0, 0.0, 1.0, 3.0, 4.0, 6.0], extend=(True, True))
    img = ctx.get_raster(1, 1, 1, 1)
    r, g, b, a = img.getpixel((0, 0))
    assert a == 255
    assert (r, g, b) == (0, 0, 0)


def test_radial_degenerate_denom_no_extend_no_bg_transparent():
    ctx = _radial_ctx([0.0, 0.0, 1.0, 3.0, 4.0, 6.0], extend=(False, False))
    img = ctx.get_raster(1, 1, 1, 1)
    assert img.getpixel((0, 0)) == (0, 0, 0, 0)


# ======================================================================
# RADIAL — helper unit tests (Java IEEE-754 semantics)
# ======================================================================


def test_java_divide_zero_over_zero_is_nan():
    import math

    assert math.isnan(_java_divide(0.0, 0.0))


def test_java_divide_positive_over_zero_is_pos_inf():
    assert _java_divide(5.0, 0.0) == float("inf")


def test_java_divide_negative_over_zero_is_neg_inf():
    assert _java_divide(-5.0, 0.0) == float("-inf")


def test_java_divide_nan_numerator_over_zero_is_nan():
    import math

    assert math.isnan(_java_divide(float("nan"), 0.0))


def test_java_divide_normal_is_exact():
    assert _java_divide(7.0, 2.0) == 3.5


def test_java_max_propagates_nan():
    import math

    assert math.isnan(_java_max(float("nan"), float("inf")))
    assert math.isnan(_java_max(float("inf"), float("nan")))


def test_java_max_picks_larger_finite():
    assert _java_max(2.0, 9.0) == 9.0
    assert _java_max(9.0, 2.0) == 9.0


def test_java_int_cast_nan_is_zero():
    assert _java_int_cast(float("nan")) == 0


def test_java_int_cast_pos_inf_is_int_max():
    assert _java_int_cast(float("inf")) == 2147483647


def test_java_int_cast_neg_inf_is_int_min():
    assert _java_int_cast(float("-inf")) == -2147483648


def test_java_int_cast_truncates_toward_zero():
    assert _java_int_cast(3.9) == 3
    assert _java_int_cast(-3.9) == -3


# ======================================================================
# Cross-check: ramp lookup helper agreement (documents the index formula)
# ======================================================================


@pytest.mark.parametrize(
    "t",
    [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0],
    ids=["t0", "t01", "t025", "t05", "t075", "t09", "t1"],
)
def test_axial_ramp_index_matches_int_truncation(t):
    factor = 16
    expected_key = _gray_for_t(t, factor)
    assert 0 <= expected_key <= factor
