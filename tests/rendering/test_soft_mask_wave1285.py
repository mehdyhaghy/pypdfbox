"""Tests for the soft-mask raster compositing path (Wave 1285).

Covers ``SoftPaintContext.get_raster`` which previously returned ``None``.
"""

from __future__ import annotations

import pytest

from pypdfbox.rendering.soft_mask import SoftMask, SoftPaintContext

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402


class _StubInnerContext:
    def __init__(self, image) -> None:
        self.image = image
        self.disposed = False

    def get_raster(self, x1, y1, w, h):
        return self.image.crop((x1, y1, x1 + w, y1 + h))

    def get_color_model(self):
        return "RGBA"

    def dispose(self) -> None:
        self.disposed = True


class _StubPaint:
    def __init__(self, ctx) -> None:
        self._ctx = ctx

    def create_context(self, *_args, **_kwargs):
        return self._ctx


def test_get_raster_multiplies_alpha_by_mask_luma() -> None:
    inner = Image.new("RGBA", (4, 4), (255, 0, 0, 200))
    mask = Image.new("L", (4, 4), 128)
    paint = _StubPaint(_StubInnerContext(inner))
    sm = SoftMask(paint, mask, bbox_device=(0, 0, 4, 4))
    ctx = sm.create_context(None, None, None, None, None)
    raster = ctx.get_raster(0, 0, 4, 4)
    assert raster is not None
    # Expected alpha = round(200 * 128/255) = 100
    px = raster.load()
    assert px[0, 0][3] == 100
    assert px[3, 3][3] == 100


def test_get_raster_outside_mask_uses_backdrop_color() -> None:
    inner = Image.new("RGBA", (4, 4), (0, 0, 255, 200))
    mask = Image.new("L", (2, 2), 255)

    class _Color:
        def to_rgb(self):
            return 0x808080  # bc = (299*128 + 587*128 + 114*128)/1000 = 128

    paint = _StubPaint(_StubInnerContext(inner))
    sm = SoftMask(paint, mask, bbox_device=(0, 0, 2, 2), backdrop_color=_Color())
    ctx = sm.create_context(None, None, None, None, None)
    # Request 4x4: pixels outside the 2x2 mask should use bc/255 factor.
    raster = ctx.get_raster(0, 0, 4, 4)
    px = raster.load()
    # Inside mask (0,0)
    assert px[0, 0][3] == round(200 * (255 / 255))
    # Outside (3,3) — uses bc=128
    assert px[3, 3][3] == round(200 * (128 / 255))


def test_get_raster_no_inner_context_returns_transparent() -> None:
    mask = Image.new("L", (4, 4), 255)
    sm = SoftMask(paint=None, mask=mask, bbox_device=(0, 0, 4, 4))
    ctx = SoftPaintContext(sm, None)
    raster = ctx.get_raster(0, 0, 4, 4)
    assert raster is not None
    px = raster.load()
    assert px[0, 0][3] == 0  # inner-paint alpha was 0


def test_dispose_propagates_to_inner_context() -> None:
    inner = Image.new("RGBA", (2, 2), (0, 0, 0, 255))
    inner_ctx = _StubInnerContext(inner)
    sm = SoftMask(_StubPaint(inner_ctx), Image.new("L", (2, 2), 255), (0, 0, 2, 2))
    ctx = sm.create_context(None, None, None, None, None)
    ctx.dispose()
    assert inner_ctx.disposed


def test_color_model_is_argb() -> None:
    ctx = SoftPaintContext(SoftMask(None, None, (0, 0, 0, 0)), None)
    assert ctx.get_color_model() == "ARGB"


def test_get_transparency_constant() -> None:
    sm = SoftMask(None, None, (0, 0, 0, 0))
    assert sm.get_transparency() == 3


def test_get_raster_handles_zero_dimensions() -> None:
    sm = SoftMask(None, Image.new("L", (1, 1), 255), (0, 0, 0, 0))
    ctx = sm.create_context(None, None, None, None, None)
    # Should not raise; returns a 1x1 image as a safety net.
    raster = ctx.get_raster(0, 0, 0, 0)
    assert raster is not None
