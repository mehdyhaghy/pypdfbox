"""Tests for the :class:`SoftMask` AWT-paint surface (the inner
``SoftPaintContext`` raster compositor).

Upstream's ``SoftMask`` is a ``java.awt.Paint`` that wraps an inner
paint and multiplies its alpha by the soft-mask luminance pixel by
pixel. The Python port keeps the same public surface but consumes
Pillow ``Image`` objects in place of AWT rasters. These tests pin
the public constructor + ``createContext`` contract, the backdrop
colour luminance derivation (the latent bug fixed in wave 1370 where
``PDColor.to_rgb()`` returns a unit-float tuple but the constructor
treated the return as a packed ARGB int), the transfer-function
short-circuit, and the per-pixel mixing behaviour in
``SoftPaintContext.get_raster``.
"""
from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.rendering.soft_mask import TRANSLUCENT, SoftMask, SoftPaintContext


class _StubPaintContext:
    """Tiny paint-context that returns a solid-colour RGBA raster of the
    requested size, mimicking AWT's ``PaintContext.getRaster``."""

    def __init__(self, color: tuple[int, int, int, int]) -> None:
        self._color = color
        self.disposed = False

    def get_raster(self, x: int, y: int, w: int, h: int) -> Image.Image:  # noqa: ARG002
        return Image.new("RGBA", (w, h), self._color)

    def dispose(self) -> None:
        self.disposed = True


class _StubPaint:
    def __init__(self, color: tuple[int, int, int, int]) -> None:
        self._color = color

    def create_context(self, *_a: Any, **_k: Any) -> _StubPaintContext:
        return _StubPaintContext(self._color)


def test_soft_mask_transparency_is_translucent() -> None:
    """The AWT contract requires ``getTransparency() == TRANSLUCENT`` so
    the AWT renderer treats this paint as having a non-trivial alpha
    channel."""
    sm = SoftMask(paint=None, mask=None, bbox_device=None)
    assert sm.get_transparency() == TRANSLUCENT
    assert TRANSLUCENT == 3


def test_soft_mask_backdrop_white_luminance_is_255() -> None:
    """White backdrop in DeviceRGB → luminance 255 (full backdrop)."""
    color = PDColor([1.0, 1.0, 1.0], PDDeviceRGB.INSTANCE)
    sm = SoftMask(paint=None, mask=None, bbox_device=None, backdrop_color=color)
    # _bc is the per-component luminance in 0..255 space.
    assert sm._bc == 255  # noqa: SLF001


def test_soft_mask_backdrop_black_luminance_is_zero() -> None:
    color = PDColor([0.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    sm = SoftMask(paint=None, mask=None, bbox_device=None, backdrop_color=color)
    assert sm._bc == 0  # noqa: SLF001


def test_soft_mask_backdrop_mid_grey_is_about_127() -> None:
    """50% grey backdrop maps to ~127 (BT.601 of 128,128,128)."""
    color = PDColor([0.5, 0.5, 0.5], PDDeviceRGB.INSTANCE)
    sm = SoftMask(paint=None, mask=None, bbox_device=None, backdrop_color=color)
    # 0.5*255 → 127 (round); BT.601 of (127, 127, 127) is 127.
    assert 120 < sm._bc < 135  # noqa: SLF001


def test_soft_mask_backdrop_pure_green_uses_bt601_weight() -> None:
    """Green is the heaviest BT.601 luma coefficient (0.587). Pure green
    backdrop → luminance ≈ 149."""
    color = PDColor([0.0, 1.0, 0.0], PDDeviceRGB.INSTANCE)
    sm = SoftMask(paint=None, mask=None, bbox_device=None, backdrop_color=color)
    # 587 * 255 / 1000 = 149.685 → 149
    assert 140 <= sm._bc <= 155  # noqa: SLF001


def test_soft_mask_backdrop_default_is_zero_when_none() -> None:
    """When no backdrop_color is supplied the field stays at 0 (matching
    the upstream default)."""
    sm = SoftMask(paint=None, mask=None, bbox_device=None, backdrop_color=None)
    assert sm._bc == 0  # noqa: SLF001


def test_soft_mask_identity_transfer_is_dropped() -> None:
    """Upstream short-circuits identity transfer functions to None so the
    raster loop can skip the table lookup."""

    class _Identity:
        def is_identity(self) -> bool:
            return True

    sm = SoftMask(
        paint=None, mask=None, bbox_device=None, transfer_function=_Identity()
    )
    assert sm._transfer_function is None  # noqa: SLF001


def test_soft_mask_non_identity_transfer_is_kept() -> None:
    class _Fn:
        def is_identity(self) -> bool:
            return False

        def eval(self, _x: list[float]) -> list[float]:
            return [1.0]

    fn = _Fn()
    sm = SoftMask(
        paint=None, mask=None, bbox_device=None, transfer_function=fn
    )
    assert sm._transfer_function is fn  # noqa: SLF001


def test_soft_mask_create_context_returns_soft_paint_context() -> None:
    """``createContext`` wraps the inner paint's context in a
    :class:`SoftPaintContext`. The inner paint's create_context call
    receives the same arguments."""
    paint = _StubPaint((50, 100, 150, 255))
    sm = SoftMask(paint=paint, mask=None, bbox_device=None)
    ctx = sm.create_context(None, None, None, None, None)
    assert isinstance(ctx, SoftPaintContext)


def test_soft_mask_create_context_handles_paint_without_create_context() -> None:
    """A paint that doesn't expose ``create_context`` should yield a
    SoftPaintContext whose inner context is None — defensive against
    null/dummy paints."""
    sm = SoftMask(paint=object(), mask=None, bbox_device=None)
    ctx = sm.create_context(None, None, None, None, None)
    assert isinstance(ctx, SoftPaintContext)
    assert ctx._context is None  # noqa: SLF001


def test_soft_paint_context_color_model_is_argb() -> None:
    sm = SoftMask(paint=None, mask=None, bbox_device=None)
    ctx = sm.create_context(None, None, None, None, None)
    assert ctx.get_color_model() == "ARGB"


def test_soft_paint_context_dispose_propagates() -> None:
    paint = _StubPaint((10, 20, 30, 255))
    sm = SoftMask(paint=paint, mask=None, bbox_device=None)
    ctx = sm.create_context(None, None, None, None, None)
    inner = ctx._context  # noqa: SLF001
    assert isinstance(inner, _StubPaintContext)
    assert inner.disposed is False
    ctx.dispose()
    assert inner.disposed is True


def test_soft_paint_context_get_raster_zero_size_returns_empty() -> None:
    sm = SoftMask(paint=None, mask=None, bbox_device=None)
    ctx = sm.create_context(None, None, None, None, None)
    out = ctx.get_raster(0, 0, 0, 0)
    # Defensive: never None, never zero-sized.
    assert out is not None
    assert out.size == (1, 1)


def test_soft_paint_context_get_raster_full_opaque_mask_keeps_paint() -> None:
    """All-255 mask → resulting alpha equals the inner paint's alpha."""
    paint = _StubPaint((100, 150, 200, 255))
    mask = Image.new("L", (4, 4), 255)
    sm = SoftMask(paint=paint, mask=mask, bbox_device=(0, 0))
    ctx = sm.create_context(None, None, None, None, None)
    out = ctx.get_raster(0, 0, 4, 4)
    assert out is not None
    assert out.size == (4, 4)
    # Alpha channel at (0,0) should be 255 (paint alpha * mask 255/255).
    px = out.getpixel((0, 0))
    assert px[:3] == (100, 150, 200)
    assert px[3] == 255


def test_soft_paint_context_get_raster_zero_mask_makes_transparent() -> None:
    """All-zero mask → resulting alpha is zero everywhere."""
    paint = _StubPaint((100, 150, 200, 255))
    mask = Image.new("L", (4, 4), 0)
    sm = SoftMask(paint=paint, mask=mask, bbox_device=(0, 0))
    ctx = sm.create_context(None, None, None, None, None)
    out = ctx.get_raster(0, 0, 4, 4)
    assert out is not None
    px = out.getpixel((2, 2))
    assert px[3] == 0


def test_soft_paint_context_get_raster_outside_mask_uses_backdrop_luma() -> None:
    """Pixels outside the mask bbox should fall back to the backdrop
    luminance — alpha *= bc / 255."""
    paint = _StubPaint((50, 50, 50, 200))
    mask = Image.new("L", (2, 2), 0)  # Doesn't matter — querying outside.
    # White backdrop → bc = 255 → full alpha pass-through.
    color = PDColor([1.0, 1.0, 1.0], PDDeviceRGB.INSTANCE)
    sm = SoftMask(
        paint=paint, mask=mask, bbox_device=(100, 100), backdrop_color=color
    )
    ctx = sm.create_context(None, None, None, None, None)
    # Sample (0, 0) is far outside the mask bbox (which lives at 100, 100).
    out = ctx.get_raster(0, 0, 2, 2)
    px = out.getpixel((0, 0))
    # White backdrop → alpha unchanged at 200.
    assert 195 <= px[3] <= 205, px
