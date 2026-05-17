"""Coverage-boost tests for
:class:`pypdfbox.pdmodel.graphics.shading.type1_shading_context.Type1ShadingContext`.

Targets the uncovered branches of the function-based shading paint
context:

- Domain pulled from the shading object (line 28) vs. default ``[0, 1,
  0, 1]`` (line 30).
- ``dispose`` clearing the shading reference (lines 33-34).
- ``get_raster`` per-pixel branches:
  - background applied when the pixel lies outside the domain (lines 68,
    70).
  - function evaluation exception swallowed and the pixel left
    transparent (lines 74-75).
  - colour-space ``to_rgb`` conversion (lines 77-78).
  - short tint output zero-padded to RGB (line 80).

A test double for :class:`PDShadingType1` is used so we can exercise the
shading-context surface without dragging the full ``PDShading`` graph
through every assertion. The double mirrors the methods the context
touches (``get_color_space``, ``get_background``, ``get_domain``,
``eval_function``).
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.pdmodel.graphics.shading.type1_shading_context import (
    Type1ShadingContext,
)


# ----------------------------------------------------------------------
# Test doubles
# ----------------------------------------------------------------------
class _Arr:
    def __init__(self, values: list[float]) -> None:
        self._values = list(values)

    def to_float_array(self) -> list[float]:
        return list(self._values)


class _BgArr:
    def __init__(self, values: list[float]) -> None:
        self._values = list(values)

    def to_float_array(self) -> list[float]:
        return list(self._values)


class _RgbColorSpace:
    """A colour space exposing ``to_rgb`` — exercises the conversion
    branch of ``get_raster``."""

    def to_rgb(self, value: list[float]) -> list[float]:
        # Identity passthrough — same length as input.
        return list(value)


class _RaisingColorSpace:
    """A colour space whose ``to_rgb`` raises, exercising the
    ``contextlib.suppress`` branch of ``get_raster``."""

    def to_rgb(self, value: list[float]) -> list[float]:
        raise NotImplementedError("force suppression")


class _BareColorSpace:
    """A colour space with no ``to_rgb`` attribute — exercises the
    ``hasattr(cs, 'to_rgb')`` guard."""


class _FakeType1Shading:
    """Configurable fake matching ``PDShadingType1``'s context surface."""

    def __init__(
        self,
        domain: list[float] | None = None,
        background: list[float] | None = None,
        color_space: Any = None,
        eval_result: list[float] | None = None,
        eval_raises: type[BaseException] | None = None,
    ) -> None:
        self._domain = domain
        self._background = background
        self._color_space = color_space
        self._eval_result = eval_result
        self._eval_raises = eval_raises

    def get_color_space(self) -> Any:
        return self._color_space

    def get_background(self) -> Any:
        return _BgArr(self._background) if self._background is not None else None

    def get_domain(self) -> Any:
        return _Arr(self._domain) if self._domain is not None else None

    def eval_function(self, value: list[float]) -> list[float]:
        if self._eval_raises is not None:
            raise self._eval_raises("forced")
        if self._eval_result is not None:
            return list(self._eval_result)
        # Default: mid-grey tied to the input coords so we get
        # non-trivial output.
        return [0.5, 0.5, 0.5]


def _make_context(
    shading: _FakeType1Shading,
) -> Type1ShadingContext:
    return Type1ShadingContext(
        shading=shading,
        color_model=None,
        xform=None,
        matrix=None,
    )


# ----------------------------------------------------------------------
# Constructor — domain handling
# ----------------------------------------------------------------------
def test_domain_pulled_from_shading_when_present() -> None:
    ctx = _make_context(_FakeType1Shading(domain=[0.25, 0.75, -1.0, 1.0]))
    # Hits line 28 (domain is not None branch).
    assert ctx.get_domain() == [0.25, 0.75, -1.0, 1.0]


def test_domain_defaults_when_absent() -> None:
    ctx = _make_context(_FakeType1Shading(domain=None))
    # Hits line 30 (default).
    assert ctx.get_domain() == [0.0, 1.0, 0.0, 1.0]


def test_get_domain_returns_a_copy() -> None:
    ctx = _make_context(_FakeType1Shading(domain=[0.0, 4.0, 0.0, 4.0]))
    a = ctx.get_domain()
    a.append(999.0)
    # Original ctx state unchanged.
    assert ctx.get_domain() == [0.0, 4.0, 0.0, 4.0]


# ----------------------------------------------------------------------
# dispose
# ----------------------------------------------------------------------
def test_dispose_clears_shading_reference() -> None:
    ctx = _make_context(_FakeType1Shading())
    assert ctx._type1_shading_type is not None  # noqa: SLF001
    ctx.dispose()
    # Hits lines 33-34.
    assert ctx._type1_shading_type is None  # noqa: SLF001
    # ``super().dispose`` clears the colour-model too.
    assert ctx.get_color_model() is None


# ----------------------------------------------------------------------
# get_raster — happy path
# ----------------------------------------------------------------------
def test_get_raster_in_domain_uses_function_output() -> None:
    shading = _FakeType1Shading(
        domain=[0.0, 4.0, 0.0, 4.0],
        eval_result=[0.0, 1.0, 0.0],
    )
    ctx = _make_context(shading)
    img = ctx.get_raster(0, 0, 2, 2)
    assert img.mode == "RGBA"
    assert img.size == (2, 2)
    # Pure-green fill, alpha 255.
    assert img.getpixel((0, 0)) == (0, 255, 0, 255)
    assert img.getpixel((1, 1)) == (0, 255, 0, 255)


def test_get_raster_out_of_domain_with_background_uses_bg() -> None:
    # Domain is a single pixel at origin -> the (1, 0), (0, 1), (1, 1)
    # pixels are out of bounds and should fall back to the background.
    shading = _FakeType1Shading(
        domain=[0.0, 0.0, 0.0, 0.0],
        background=[1.0, 0.0, 0.0],
        eval_result=[0.0, 1.0, 0.0],
    )
    ctx = _make_context(shading)
    img = ctx.get_raster(0, 0, 2, 2)
    # Hits lines 68 + 70.
    # (0, 0) is in-domain -> function output (green).
    assert img.getpixel((0, 0)) == (0, 255, 0, 255)
    # (1, 0), (0, 1), (1, 1) are out-of-domain -> red background.
    assert img.getpixel((1, 0)) == (255, 0, 0, 255)
    assert img.getpixel((0, 1)) == (255, 0, 0, 255)
    assert img.getpixel((1, 1)) == (255, 0, 0, 255)


def test_get_raster_out_of_domain_without_background_is_transparent() -> None:
    shading = _FakeType1Shading(
        domain=[0.0, 0.0, 0.0, 0.0],
        background=None,
        eval_result=[0.0, 1.0, 0.0],
    )
    ctx = _make_context(shading)
    img = ctx.get_raster(0, 0, 2, 2)
    # Out-of-domain with bg=None -> ``continue`` -> pixel stays
    # transparent (initial fill).
    assert img.getpixel((1, 0)) == (0, 0, 0, 0)
    assert img.getpixel((0, 1)) == (0, 0, 0, 0)
    assert img.getpixel((1, 1)) == (0, 0, 0, 0)
    # (0, 0) still picks up the function output.
    assert img.getpixel((0, 0)) == (0, 255, 0, 255)


# ----------------------------------------------------------------------
# get_raster — eval exception path
# ----------------------------------------------------------------------
@pytest.mark.parametrize("exc", [OSError, ValueError, ZeroDivisionError])
def test_get_raster_function_eval_exception_leaves_pixel_transparent(
    exc: type[Exception],
) -> None:
    shading = _FakeType1Shading(
        domain=[0.0, 4.0, 0.0, 4.0],
        eval_raises=exc,
    )
    ctx = _make_context(shading)
    img = ctx.get_raster(0, 0, 2, 2)
    # Hits lines 74-75 — every pixel hits the except branch -> continue.
    for j in range(2):
        for i in range(2):
            assert img.getpixel((i, j)) == (0, 0, 0, 0)


# ----------------------------------------------------------------------
# get_raster — colour-space conversion branches
# ----------------------------------------------------------------------
def test_get_raster_color_space_to_rgb_converts_components() -> None:
    shading = _FakeType1Shading(
        domain=[0.0, 4.0, 0.0, 4.0],
        color_space=_RgbColorSpace(),
        eval_result=[0.25, 0.5, 0.75],
    )
    ctx = _make_context(shading)
    img = ctx.get_raster(0, 0, 1, 1)
    # Hits lines 77-78 — identity passthrough so values land at
    # (64, 128, 191) per int(x * 255).
    assert img.getpixel((0, 0)) == (
        int(0.25 * 255),
        int(0.5 * 255),
        int(0.75 * 255),
        255,
    )


def test_get_raster_color_space_to_rgb_suppresses_exception() -> None:
    shading = _FakeType1Shading(
        domain=[0.0, 4.0, 0.0, 4.0],
        color_space=_RaisingColorSpace(),
        eval_result=[0.25, 0.5, 0.75],
    )
    ctx = _make_context(shading)
    img = ctx.get_raster(0, 0, 1, 1)
    # cs.to_rgb raises NotImplementedError -> suppress -> fall back to
    # the raw function output.
    assert img.getpixel((0, 0)) == (
        int(0.25 * 255),
        int(0.5 * 255),
        int(0.75 * 255),
        255,
    )


def test_get_raster_color_space_without_to_rgb_is_skipped() -> None:
    shading = _FakeType1Shading(
        domain=[0.0, 4.0, 0.0, 4.0],
        color_space=_BareColorSpace(),
        eval_result=[0.1, 0.2, 0.3],
    )
    ctx = _make_context(shading)
    img = ctx.get_raster(0, 0, 1, 1)
    # ``hasattr(cs, 'to_rgb')`` is False -> values used directly.
    assert img.getpixel((0, 0)) == (
        int(0.1 * 255),
        int(0.2 * 255),
        int(0.3 * 255),
        255,
    )


# ----------------------------------------------------------------------
# get_raster — short component padding
# ----------------------------------------------------------------------
def test_get_raster_pads_short_function_output_to_rgb() -> None:
    shading = _FakeType1Shading(
        domain=[0.0, 4.0, 0.0, 4.0],
        eval_result=[0.75],  # only one component -> pad to 3
    )
    ctx = _make_context(shading)
    img = ctx.get_raster(0, 0, 1, 1)
    # Hits line 80 — pads to [0.75, 0.0, 0.0].
    assert img.getpixel((0, 0)) == (int(0.75 * 255), 0, 0, 255)


def test_get_raster_pads_two_component_function_output() -> None:
    shading = _FakeType1Shading(
        domain=[0.0, 4.0, 0.0, 4.0],
        eval_result=[0.4, 0.6],  # two components -> pad B channel
    )
    ctx = _make_context(shading)
    img = ctx.get_raster(0, 0, 1, 1)
    assert img.getpixel((0, 0)) == (int(0.4 * 255), int(0.6 * 255), 0, 255)


# ----------------------------------------------------------------------
# get_raster — clamping
# ----------------------------------------------------------------------
def test_get_raster_clamps_out_of_range_values() -> None:
    shading = _FakeType1Shading(
        domain=[0.0, 4.0, 0.0, 4.0],
        eval_result=[-0.5, 2.0, 0.5],  # < 0 and > 1 -> clamped
    )
    ctx = _make_context(shading)
    img = ctx.get_raster(0, 0, 1, 1)
    assert img.getpixel((0, 0)) == (0, 255, int(0.5 * 255), 255)


# ----------------------------------------------------------------------
# get_raster — origin offset
# ----------------------------------------------------------------------
def test_get_raster_uses_origin_offsets_in_domain_check() -> None:
    # Domain rectangle = [5, 6] x [7, 8]. Origin offset (5, 7), size 2x2
    # -> pixel (0, 0) is at device coords (5, 7) (in-domain), pixel
    # (1, 1) is at (6, 8) (in-domain), pixel (1, 0) at (6, 7) in, pixel
    # (0, 1) at (5, 8) in. All four are in-domain -> full coverage.
    shading = _FakeType1Shading(
        domain=[5.0, 6.0, 7.0, 8.0],
        eval_result=[1.0, 1.0, 1.0],
    )
    ctx = _make_context(shading)
    img = ctx.get_raster(5, 7, 2, 2)
    for j in range(2):
        for i in range(2):
            assert img.getpixel((i, j)) == (255, 255, 255, 255)
