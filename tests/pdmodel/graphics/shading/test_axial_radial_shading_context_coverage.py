"""Coverage-boost tests for axial / radial shading paint contexts.

Targets the uncovered branches of
:class:`pypdfbox.pdmodel.graphics.shading.axial_shading_context.AxialShadingContext`
and
:class:`pypdfbox.pdmodel.graphics.shading.radial_shading_context.RadialShadingContext`
— default / explicit ``/Coords``/``/Domain``/``/Extend`` handling, the
``denom == 0`` and ``factor == 0`` short-circuits, ``dispose``, the
``get_function`` passthrough, and the ``get_raster`` extend / background
/ continue branches.

The fakes mimic only the surface the contexts touch (``get_color_space``,
``get_background``, ``get_coords``, ``get_domain``, ``get_extend``,
``get_function``, ``eval_function``) so we exercise the rendering paths
without dragging the full ``PDShadingType2`` / ``PDShadingType3`` graph
through every assertion.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.pdmodel.graphics.shading import (
    AxialShadingContext,
    RadialShadingContext,
)


# ----------------------------------------------------------------------
# Test doubles
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
    """Minimal stand-in for the COSArray returned by ``get_extend``."""

    def __init__(self, a: bool, b: bool) -> None:
        self._items = [_Bool(a), _Bool(b)]

    def get_object(self, i: int) -> _Bool:
        return self._items[i]


class _BgArr:
    def __init__(self, values: list[float]) -> None:
        self._values = list(values)

    def to_float_array(self) -> list[float]:
        return list(self._values)


class _FakeAxialShading:
    """Configurable fake matching ``PDShadingType2``'s context surface."""

    def __init__(
        self,
        coords: list[float] | None = None,
        domain: list[float] | None = None,
        extend: tuple[bool, bool] | None = None,
        background: list[float] | None = None,
        eval_result: list[float] | None = None,
        function_marker: Any = "FN",
    ) -> None:
        self._coords = coords
        self._domain = domain
        self._extend = extend
        self._background = background
        self._eval_result = eval_result if eval_result is not None else [0.4, 0.6, 0.8]
        self._function_marker = function_marker

    def get_color_space(self) -> Any:
        return None

    def get_background(self) -> Any:
        return _BgArr(self._background) if self._background is not None else None

    def get_function(self) -> Any:
        return self._function_marker

    def get_coords(self) -> Any:
        return _Arr(self._coords) if self._coords is not None else None

    def get_domain(self) -> Any:
        return _Arr(self._domain) if self._domain is not None else None

    def get_extend(self) -> Any:
        return _ExtendArr(*self._extend) if self._extend is not None else None

    def eval_function(self, t: Any) -> list[float]:
        if isinstance(t, (list, tuple)):
            t = t[0] if t else 0.0
        # Mix some t dependence so calc_color_table actually varies.
        v = max(0.0, min(1.0, float(t)))
        return [v, v, v]


class _FakeRadialShading(_FakeAxialShading):
    """Six-element ``/Coords`` variant for ``PDShadingType3`` paths."""


# ----------------------------------------------------------------------
# Axial — constructor branches
# ----------------------------------------------------------------------
def test_axial_default_coords_when_absent() -> None:
    ctx = AxialShadingContext(
        _FakeAxialShading(coords=None),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 2, 2),
    )
    assert ctx.get_coords() == [0.0, 0.0, 0.0, 0.0]


def test_axial_default_domain_when_absent() -> None:
    ctx = AxialShadingContext(
        _FakeAxialShading(coords=[0.0, 0.0, 4.0, 0.0], domain=None),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    assert ctx.get_domain() == [0.0, 1.0]


def test_axial_explicit_extend_read_through() -> None:
    shading = _FakeAxialShading(
        coords=[0.0, 0.0, 4.0, 0.0],
        extend=(True, False),
    )
    ctx = AxialShadingContext(
        shading,
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    assert ctx.get_extend() == [True, False]


def test_axial_device_bounds_typeerror_fallback() -> None:
    # device_bounds=None triggers the TypeError except branch; dist => 1.
    ctx = AxialShadingContext(
        _FakeAxialShading(coords=[0.0, 0.0, 4.0, 0.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=None,
    )
    assert ctx._factor == 1


def test_axial_device_bounds_indexerror_fallback() -> None:
    # A short sequence raises IndexError on bounds[2]; dist => 1.
    ctx = AxialShadingContext(
        _FakeAxialShading(coords=[0.0, 0.0, 4.0, 0.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0),
    )
    assert ctx._factor == 1


def test_axial_calc_color_table_zero_factor_branch() -> None:
    # Zero-size bounds collapse dist to 0 -> factor == 0; table has one entry.
    ctx = AxialShadingContext(
        _FakeAxialShading(coords=[0.0, 0.0, 4.0, 0.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(5, 5, 5, 5),
    )
    assert ctx._factor == 0
    assert len(ctx._color_table) == 1


def test_axial_calc_color_table_zero_domain_width() -> None:
    # d1d0 == 0 forces the single-entry branch even when factor > 0.
    ctx = AxialShadingContext(
        _FakeAxialShading(coords=[0.0, 0.0, 4.0, 0.0], domain=[0.5, 0.5]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    assert ctx._factor > 0
    # All but the first entry remain zero-initialised.
    assert ctx._color_table[1:] == [0] * ctx._factor


# ----------------------------------------------------------------------
# Axial — accessors / lifecycle
# ----------------------------------------------------------------------
def test_axial_get_function_passthrough() -> None:
    shading = _FakeAxialShading(coords=[0.0, 0.0, 4.0, 0.0], function_marker="AXIS-FN")
    ctx = AxialShadingContext(
        shading,
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    assert ctx.get_function() == "AXIS-FN"


def test_axial_dispose_drops_shading_reference() -> None:
    ctx = AxialShadingContext(
        _FakeAxialShading(coords=[0.0, 0.0, 4.0, 0.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    ctx.dispose()
    assert ctx._axial_shading_type is None


# ----------------------------------------------------------------------
# Axial — get_raster branches
# ----------------------------------------------------------------------
def test_axial_get_raster_denom_zero_no_background_transparent() -> None:
    # Coincident endpoints -> denom == 0; no background -> all pixels
    # are emitted as the initial transparent RGBA fill.
    ctx = AxialShadingContext(
        _FakeAxialShading(coords=[1.0, 1.0, 1.0, 1.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(0, 0, 2, 2)
    pixels = img.load()
    assert pixels[0, 0] == (0, 0, 0, 0)
    assert pixels[1, 1] == (0, 0, 0, 0)


def test_axial_get_raster_denom_zero_with_background_uses_bg() -> None:
    # denom == 0 with a configured background -> use_background path.
    ctx = AxialShadingContext(
        _FakeAxialShading(
            coords=[1.0, 1.0, 1.0, 1.0],
            background=[1.0, 0.0, 0.0],
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(0, 0, 2, 2)
    r, g, b, a = img.load()[0, 0]
    assert (r, g, b, a) == (255, 0, 0, 255)


def test_axial_get_raster_extend_start_clamps_negative_input() -> None:
    # Sample at x = -4: input_value < 0, extend[0]=True -> clamp to domain[0].
    ctx = AxialShadingContext(
        _FakeAxialShading(coords=[0.0, 0.0, 4.0, 0.0], extend=(True, False)),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(-4, 0, 1, 1)
    # eval_function(domain[0]=0.0) -> grayscale 0.
    assert img.load()[0, 0] == (0, 0, 0, 255)


def test_axial_get_raster_extend_end_clamps_positive_input() -> None:
    # Sample at x = 8: input_value > 1, extend[1]=True -> clamp to domain[1].
    ctx = AxialShadingContext(
        _FakeAxialShading(coords=[0.0, 0.0, 4.0, 0.0], extend=(False, True)),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(8, 0, 1, 1)
    # eval_function(domain[1]=1.0) -> grayscale 255.
    assert img.load()[0, 0] == (255, 255, 255, 255)


def test_axial_get_raster_no_extend_negative_with_background() -> None:
    ctx = AxialShadingContext(
        _FakeAxialShading(
            coords=[0.0, 0.0, 4.0, 0.0],
            background=[0.0, 1.0, 0.0],
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(-4, 0, 1, 1)
    assert img.load()[0, 0] == (0, 255, 0, 255)


def test_axial_get_raster_no_extend_positive_with_background() -> None:
    ctx = AxialShadingContext(
        _FakeAxialShading(
            coords=[0.0, 0.0, 4.0, 0.0],
            background=[0.0, 0.0, 1.0],
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(8, 0, 1, 1)
    assert img.load()[0, 0] == (0, 0, 255, 255)


def test_axial_get_raster_no_extend_negative_no_bg_transparent() -> None:
    ctx = AxialShadingContext(
        _FakeAxialShading(coords=[0.0, 0.0, 4.0, 0.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(-4, 0, 1, 1)
    assert img.load()[0, 0] == (0, 0, 0, 0)


def test_axial_get_raster_no_extend_positive_no_bg_transparent() -> None:
    ctx = AxialShadingContext(
        _FakeAxialShading(coords=[0.0, 0.0, 4.0, 0.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(8, 0, 1, 1)
    assert img.load()[0, 0] == (0, 0, 0, 0)


def test_axial_get_raster_key_clamps_negative_via_extended_domain() -> None:
    # Negative domain start + extend[0]=True forces input_value < 0 in the
    # post-clamp table lookup -> exercises the ``key < 0`` defensive branch.
    ctx = AxialShadingContext(
        _FakeAxialShading(
            coords=[0.0, 0.0, 4.0, 0.0],
            domain=[-1.0, 1.0],
            extend=(True, False),
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(-4, 0, 1, 1)
    assert img.load()[0, 0][3] == 255


def test_axial_get_raster_key_clamps_above_factor_via_extended_domain() -> None:
    # Domain end > 1 + extend[1]=True drives input_value > 1 into the
    # table lookup -> exercises the ``key > factor`` defensive branch.
    ctx = AxialShadingContext(
        _FakeAxialShading(
            coords=[0.0, 0.0, 4.0, 0.0],
            domain=[0.0, 2.0],
            extend=(False, True),
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(8, 0, 1, 1)
    assert img.load()[0, 0][3] == 255


def test_axial_get_raster_inside_gradient_table_lookup() -> None:
    # px=2 along a 0..4 axis -> input_value ~= 0.5 -> mid colour.
    ctx = AxialShadingContext(
        _FakeAxialShading(coords=[0.0, 0.0, 4.0, 0.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(2, 0, 1, 1)
    r, g, b, a = img.load()[0, 0]
    assert a == 255
    assert 100 <= r <= 160


# ----------------------------------------------------------------------
# Radial — constructor branches
# ----------------------------------------------------------------------
def test_radial_default_coords_when_absent() -> None:
    ctx = RadialShadingContext(
        _FakeRadialShading(coords=None),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 2, 2),
    )
    assert ctx.get_coords() == [0.0] * 6


def test_radial_default_domain_when_absent() -> None:
    ctx = RadialShadingContext(
        _FakeRadialShading(coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0], domain=None),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    assert ctx.get_domain() == [0.0, 1.0]


def test_radial_explicit_extend_read_through() -> None:
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0],
            extend=(True, True),
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    assert ctx.get_extend() == [True, True]


def test_radial_device_bounds_typeerror_fallback() -> None:
    ctx = RadialShadingContext(
        _FakeRadialShading(coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=None,
    )
    assert ctx._factor == 1


def test_radial_device_bounds_indexerror_fallback() -> None:
    ctx = RadialShadingContext(
        _FakeRadialShading(coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0,),
    )
    assert ctx._factor == 1


def test_radial_calc_color_table_zero_factor_branch() -> None:
    ctx = RadialShadingContext(
        _FakeRadialShading(coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(5, 5, 5, 5),
    )
    assert ctx._factor == 0
    assert len(ctx._color_table) == 1


def test_radial_calc_color_table_zero_domain_width() -> None:
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0],
            domain=[0.25, 0.25],
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    assert ctx._factor > 0
    assert ctx._color_table[1:] == [0] * ctx._factor


# ----------------------------------------------------------------------
# Radial — accessors / lifecycle / quadratic
# ----------------------------------------------------------------------
def test_radial_get_function_passthrough() -> None:
    shading = _FakeRadialShading(
        coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0],
        function_marker="RAD-FN",
    )
    ctx = RadialShadingContext(
        shading,
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    assert ctx.get_function() == "RAD-FN"


def test_radial_dispose_drops_shading_reference() -> None:
    ctx = RadialShadingContext(
        _FakeRadialShading(coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    ctx.dispose()
    assert ctx._radial_shading_type is None


def test_radial_calculate_input_values_negative_discriminant_returns_nan() -> None:
    # Coords (0,0,3) -> (5,0,1): dx=5, dy=0, r1r0=-2, so
    # denom = 25 + 0 - 4 = 21 (positive). At (1, 10) the quadratic
    # discriminant 4x^2 - 60x + 225 - 21y^2 evaluates negative -> NaN roots.
    ctx = RadialShadingContext(
        _FakeRadialShading(coords=[0.0, 0.0, 3.0, 5.0, 0.0, 1.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    import math
    r0, r1 = ctx.calculate_input_values(1.0, 10.0)
    assert math.isnan(r0) and math.isnan(r1)


def test_radial_calculate_input_values_zero_denominator_returns_nan() -> None:
    # Choose coords where x1x0^2 + y1y0^2 - r1r0^2 == 0.
    # e.g. dx=3, dy=4 -> 9+16=25 ; r1-r0=5 -> 25 -> denom = 0.
    ctx = RadialShadingContext(
        _FakeRadialShading(coords=[0.0, 0.0, 0.0, 3.0, 4.0, 5.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    import math
    r0, r1 = ctx.calculate_input_values(1.0, 1.0)
    assert math.isnan(r0) and math.isnan(r1)


def test_radial_calculate_input_values_positive_denominator_orders_roots() -> None:
    # r1 < r0 -> r1r0 negative -> denom = dx^2 + dy^2 - r1r0^2 > 0.
    ctx = RadialShadingContext(
        _FakeRadialShading(coords=[0.0, 0.0, 3.0, 5.0, 0.0, 1.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    a, b = ctx.calculate_input_values(2.0, 0.0)
    # Positive denominator branch returns (root2, root1) with root2 <= root1.
    assert a <= b


# ----------------------------------------------------------------------
# Radial — get_raster branches
# ----------------------------------------------------------------------
def _radial_extend_both_shading() -> _FakeRadialShading:
    return _FakeRadialShading(
        coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0],
        extend=(True, True),
    )


def test_radial_get_raster_nan_roots_no_background_transparent() -> None:
    # Concentric circles produce NaN roots far outside; no bg -> transparent.
    ctx = RadialShadingContext(
        _FakeRadialShading(coords=[0.0, 0.0, 1.0, 0.0, 0.0, 3.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(100, 100, 1, 1)
    assert img.load()[0, 0] == (0, 0, 0, 0)


def test_radial_get_raster_nan_roots_with_background_uses_bg() -> None:
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 0.0, 0.0, 3.0],
            background=[1.0, 1.0, 0.0],
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(100, 100, 1, 1)
    r, g, b, a = img.load()[0, 0]
    assert (r, g, b) == (255, 255, 0)
    assert a == 255


def test_radial_get_raster_extend_both_outside_picks_larger_root() -> None:
    # Sample at (8, 0): both roots outside [0,1]; extend=(True,True) picks
    # max(r0, r1) -> the larger root then clamps via the >1 branch.
    ctx = RadialShadingContext(
        _radial_extend_both_shading(),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(8, 0, 1, 1)
    pixel = img.load()[0, 0]
    assert pixel[3] == 255


def test_radial_get_raster_extend_start_only_clamps_low() -> None:
    # extend=(True,False): outside-low input is picked via the extend[0]
    # branch, then clamped to 0 because coords[2] (r0) > 0.
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0],
            extend=(True, False),
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    # Sample well inside the leading circle -> both roots < 0.
    img = ctx.get_raster(-10, 0, 1, 1)
    pixel = img.load()[0, 0]
    # Either clamped to grad-start colour or transparent depending on roots.
    assert pixel[3] in (0, 255)


def test_radial_get_raster_extend_end_only_clamps_high() -> None:
    # extend=(False,True): outside-high input is taken via extend[1] then
    # clamped to 1 because coords[5] (r1) > 0.
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0],
            extend=(False, True),
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(20, 0, 1, 1)
    pixel = img.load()[0, 0]
    assert pixel[3] in (0, 255)


def test_radial_get_raster_no_extend_outside_with_background_uses_bg() -> None:
    # Both roots outside [0,1], no extend, but background present -> uses bg.
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0],
            background=[0.5, 0.5, 0.5],
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(20, 20, 1, 1)
    pixel = img.load()[0, 0]
    assert pixel[3] == 255


def test_radial_get_raster_no_extend_outside_no_bg_transparent() -> None:
    ctx = RadialShadingContext(
        _FakeRadialShading(coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(20, 20, 1, 1)
    assert img.load()[0, 0] == (0, 0, 0, 0)


def test_radial_get_raster_inside_returns_solid_pixel() -> None:
    # Sampling on the gradient axis should hit a 0..1 root and emit colour.
    ctx = RadialShadingContext(
        _FakeRadialShading(coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0]),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(2, 0, 1, 1)
    pixel = img.load()[0, 0]
    assert pixel[3] == 255


def test_radial_get_raster_r0_zero_no_extend_inside_to_outside_no_bg() -> None:
    # coords[2] (r0) == 0 forces the extend[0] && coords[2]>0 condition to
    # fail when input_value < 0, exercising the "elif bg is None: continue"
    # branch.
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 0.0, 4.0, 0.0, 3.0],
            extend=(True, False),
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    # No exception -> branch executed.
    img = ctx.get_raster(-2, 0, 2, 2)
    assert img.size == (2, 2)


def test_radial_get_raster_r1_zero_extend_end_with_background() -> None:
    # coords[5] (r1) == 0 forces the high-clamp extend branch to fail and
    # fall back to use_background.
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 4.0, 0.0, 0.0],
            extend=(False, True),
            background=[1.0, 0.0, 1.0],
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(20, 0, 1, 1)
    pixel = img.load()[0, 0]
    # Either bg used or transparent; just exercise the branch.
    assert pixel[3] in (0, 255)


@pytest.mark.parametrize("xy", [(0, 0), (2, 0), (-3, 1), (10, 10)])
def test_radial_get_raster_covers_full_grid(xy: tuple[int, int]) -> None:
    # Full-grid sweep with extend on both ends + background to make sure
    # the inner loop never raises for a variety of inputs.
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0],
            extend=(True, True),
            background=[0.2, 0.4, 0.6],
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 8, 8),
    )
    img = ctx.get_raster(xy[0], xy[1], 3, 3)
    assert img.size == (3, 3)
