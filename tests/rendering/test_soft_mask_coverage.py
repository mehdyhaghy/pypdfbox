"""Coverage-boost for ``pypdfbox.rendering.soft_mask`` (wave 1320).

Targets the previously-untested branches in :class:`SoftMask` and
:class:`SoftPaintContext`:

* identity transfer-function short-circuit (line 49)
* backdrop_color OSError swallow (lines 60-61)
* inner-image mode coerce + crop branches (lines 133, 135)
* bbox unpacking failure fall-through (lines 142-143)
* mask mode coercion to L (line 155)
* transfer-function path with caching + eval failure (lines 169-179)
* mask pixel tuple unpack — LA-mode masks (line 197)
"""

from __future__ import annotations

import pytest

from pypdfbox.rendering.soft_mask import SoftMask

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402


class _StubInnerContext:
    def __init__(self, image: Image.Image) -> None:
        self.image = image

    def get_raster(self, x1: int, y1: int, w: int, h: int) -> Image.Image:
        return self.image

    def dispose(self) -> None:
        pass


class _StubPaint:
    def __init__(self, ctx: _StubInnerContext) -> None:
        self._ctx = ctx

    def create_context(self, *_args: object, **_kwargs: object) -> _StubInnerContext:
        return self._ctx


# --------------------------------------------------------------- transfer-function constructor


class _IdentityFn:
    """Stub transfer function whose ``is_identity`` returns True — should
    cause ``SoftMask.__init__`` to null out the field (line 49)."""

    def is_identity(self) -> bool:
        return True

    def eval(self, _xs: list[float]) -> list[float]:  # pragma: no cover - never called
        raise AssertionError("identity transfer should be short-circuited")


def test_identity_transfer_function_is_dropped() -> None:
    sm = SoftMask(None, None, (0, 0, 0, 0), transfer_function=_IdentityFn())
    assert sm._transfer_function is None


def test_non_identity_transfer_function_is_retained() -> None:
    class _Fn:
        def is_identity(self) -> bool:
            return False

        def eval(self, _xs: list[float]) -> list[float]:
            return [0.5]

    fn = _Fn()
    sm = SoftMask(None, None, (0, 0, 0, 0), transfer_function=fn)
    assert sm._transfer_function is fn


def test_transfer_function_without_is_identity_is_retained() -> None:
    """Defaults to ``lambda: False`` per the getattr guard — instance
    survives the short-circuit even though it lacks the method."""

    class _Fn:
        def eval(self, _xs: list[float]) -> list[float]:
            return [0.0]

    fn = _Fn()
    sm = SoftMask(None, None, (0, 0, 0, 0), transfer_function=fn)
    assert sm._transfer_function is fn


# --------------------------------------------------------------- backdrop-color OSError


class _RaisingColor:
    def to_rgb(self) -> int:
        raise OSError("conversion not supported")


def test_backdrop_color_raising_oserror_logs_and_keeps_bc_zero() -> None:
    """Lines 60-61 — the constructor swallows OSError and leaves
    ``_bc`` at its default of 0."""
    sm = SoftMask(None, None, (0, 0, 0, 0), backdrop_color=_RaisingColor())
    assert sm._bc == 0


# --------------------------------------------------------------- inner-image mode + size


def test_get_raster_converts_non_rgba_inner_image() -> None:
    """Line 133 — non-RGBA inner image is coerced to RGBA."""
    inner = Image.new("RGB", (4, 4), (10, 20, 30))
    paint = _StubPaint(_StubInnerContext(inner))
    sm = SoftMask(paint, Image.new("L", (4, 4), 255), (0, 0, 4, 4))
    ctx = sm.create_context(None, None, None, None, None)
    raster = ctx.get_raster(0, 0, 4, 4)
    px = raster.load()
    # Alpha defaulted to 255 by ``convert("RGBA")``.
    assert px[0, 0] == (10, 20, 30, 255)


def test_get_raster_crops_oversized_inner_image() -> None:
    """Line 135 — when the inner raster is larger than requested it
    gets cropped to ``(w, h)``."""
    inner = Image.new("RGBA", (8, 8), (5, 5, 5, 200))
    paint = _StubPaint(_StubInnerContext(inner))
    sm = SoftMask(paint, Image.new("L", (4, 4), 255), (0, 0, 4, 4))
    ctx = sm.create_context(None, None, None, None, None)
    raster = ctx.get_raster(0, 0, 4, 4)
    assert raster.size == (4, 4)


# --------------------------------------------------------------- bbox unpack failure


def test_get_raster_handles_bbox_unpack_failure() -> None:
    """Lines 142-143 — an unindexable bbox falls back to bx=by=0."""
    inner = Image.new("RGBA", (2, 2), (1, 2, 3, 200))
    paint = _StubPaint(_StubInnerContext(inner))
    # Object whose subscript raises TypeError.
    sm = SoftMask(paint, Image.new("L", (2, 2), 255), bbox_device=object())
    ctx = sm.create_context(None, None, None, None, None)
    raster = ctx.get_raster(0, 0, 2, 2)
    assert raster is not None
    assert raster.size == (2, 2)


def test_get_raster_handles_bbox_index_error() -> None:
    """A short tuple triggers IndexError in the unpack — also caught."""
    inner = Image.new("RGBA", (2, 2), (1, 2, 3, 200))
    paint = _StubPaint(_StubInnerContext(inner))
    sm = SoftMask(paint, Image.new("L", (2, 2), 255), bbox_device=())
    ctx = sm.create_context(None, None, None, None, None)
    raster = ctx.get_raster(0, 0, 2, 2)
    assert raster is not None


def test_get_raster_handles_bbox_value_error() -> None:
    """A non-numeric bbox element triggers ValueError — also caught."""
    inner = Image.new("RGBA", (2, 2), (1, 2, 3, 200))
    paint = _StubPaint(_StubInnerContext(inner))
    sm = SoftMask(
        paint, Image.new("L", (2, 2), 255), bbox_device=("nan", "nan", 2, 2)
    )
    ctx = sm.create_context(None, None, None, None, None)
    raster = ctx.get_raster(0, 0, 2, 2)
    assert raster is not None


# --------------------------------------------------------------- mask mode coercion


def test_get_raster_converts_rgb_mask_to_luma() -> None:
    """Line 155 — RGB mask is converted to L before sampling."""
    inner = Image.new("RGBA", (2, 2), (100, 100, 100, 200))
    paint = _StubPaint(_StubInnerContext(inner))
    # Pure-red RGB mask → luma ~76 via Pillow's conversion.
    mask = Image.new("RGB", (2, 2), (255, 0, 0))
    sm = SoftMask(paint, mask, (0, 0, 2, 2))
    ctx = sm.create_context(None, None, None, None, None)
    raster = ctx.get_raster(0, 0, 2, 2)
    px = raster.load()
    # Alpha should be 200 * (~76/255) ≈ 59-60.
    assert 50 <= px[0, 0][3] <= 70


def test_get_raster_keeps_l_mask_unchanged() -> None:
    """L-mode masks skip the conversion branch."""
    inner = Image.new("RGBA", (2, 2), (255, 255, 255, 200))
    paint = _StubPaint(_StubInnerContext(inner))
    mask = Image.new("L", (2, 2), 255)
    sm = SoftMask(paint, mask, (0, 0, 2, 2))
    ctx = sm.create_context(None, None, None, None, None)
    raster = ctx.get_raster(0, 0, 2, 2)
    assert raster.load()[0, 0][3] == 200


# --------------------------------------------------------------- transfer-function paths


class _SquareFn:
    """Transfer function ``f(x) = x*x`` — non-identity, deterministic."""

    def is_identity(self) -> bool:
        return False

    def eval(self, xs: list[float]) -> list[float]:
        x = xs[0]
        return [x * x]


def test_get_raster_uses_transfer_function() -> None:
    """Lines 167-178 — transfer is invoked, result cached, applied."""
    inner = Image.new("RGBA", (2, 2), (0, 0, 0, 200))
    paint = _StubPaint(_StubInnerContext(inner))
    # Half-gray mask → x = 128/255 ≈ 0.502; f(x) ≈ 0.252; alpha 200*0.252 ≈ 50.
    sm = SoftMask(paint, Image.new("L", (2, 2), 128), (0, 0, 2, 2),
                  transfer_function=_SquareFn())
    ctx = sm.create_context(None, None, None, None, None)
    raster = ctx.get_raster(0, 0, 2, 2)
    px = raster.load()
    assert 45 <= px[0, 0][3] <= 55
    # All four pixels share the same gray value — should hit the cache
    # branch at line 169-171 after the first computation.
    assert px[1, 1][3] == px[0, 0][3]


class _RaisingFn:
    """Transfer function that raises during ``eval`` — exercises the
    exception arm at lines 175-177."""

    def is_identity(self) -> bool:
        return False

    def eval(self, _xs: list[float]) -> list[float]:
        raise ValueError("eval broken")


def test_get_raster_handles_transfer_function_failure() -> None:
    """When ``transfer.eval`` raises, the per-pixel factor falls back
    to ``bc/255`` and the failure is logged."""

    class _Color:
        def to_rgb(self) -> int:
            return 0x808080  # bc ≈ 128

    inner = Image.new("RGBA", (2, 2), (0, 0, 0, 200))
    paint = _StubPaint(_StubInnerContext(inner))
    sm = SoftMask(
        paint,
        Image.new("L", (2, 2), 128),
        (0, 0, 2, 2),
        backdrop_color=_Color(),
        transfer_function=_RaisingFn(),
    )
    ctx = sm.create_context(None, None, None, None, None)
    raster = ctx.get_raster(0, 0, 2, 2)
    px = raster.load()
    # Fallback factor is bc/255 = 128/255 ≈ 0.502; alpha ≈ 200 * 0.502 ≈ 100.
    assert 95 <= px[0, 0][3] <= 105


# --------------------------------------------------------------- LA mask sampling


def test_get_raster_handles_la_mask_pixel_tuple() -> None:
    """Line 197 — ``g_mask`` can be a tuple for LA-mode masks; the
    code unwraps the first element. The current implementation always
    coerces the mask to single-channel ``L`` before sampling, so the
    tuple-unwrap branch is defensively retained for callers that pass a
    pre-loaded pixel accessor. We trip it by patching the pixel access
    to return ``(L, A)`` tuples directly."""
    inner = Image.new("RGBA", (2, 2), (0, 0, 0, 200))
    paint = _StubPaint(_StubInnerContext(inner))
    mask = Image.new("LA", (2, 2), (128, 255))
    sm = SoftMask(paint, mask, (0, 0, 2, 2))
    ctx = sm.create_context(None, None, None, None, None)
    # Force the converted mask to keep its LA tuples by monkey-patching
    # ``Image.convert`` for the duration of ``get_raster``: when LA →
    # 'L' is requested, return the original LA image instead.
    orig_convert = Image.Image.convert

    def _identity_convert(self: Image.Image, mode: str) -> Image.Image:
        if self.mode == "LA" and mode == "L":
            return self
        return orig_convert(self, mode)

    Image.Image.convert = _identity_convert  # type: ignore[assignment]
    try:
        raster = ctx.get_raster(0, 0, 2, 2)
    finally:
        Image.Image.convert = orig_convert  # type: ignore[assignment]
    px = raster.load()
    # Alpha = 200 * (128/255) ≈ 100 — unwrapped tuple still hits factor.
    assert 95 <= px[0, 0][3] <= 105
