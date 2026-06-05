"""Behavioural coverage for ``PDImageXObject.get_image()`` mask combinations
(wave 1491), exercising the precedence that ``_apply_image_masks`` mirrors from
upstream ``PDImageXObject.getImage`` / ``applyMask``:

* color-key ``/Mask`` array ALONE                 → keyed pixels transparent
* ``/SMask`` ALONE                                → SMask alpha
* color-key ``/Mask`` array + ``/SMask``          → SMask wins, color-key dropped
* stencil-stream ``/Mask`` + ``/SMask``           → SMask wins, stencil dropped

The combined cases pin the wave-1491 finding: upstream ``applyMask`` overwrites
the ARGB alpha band wholesale with the mask samples (Java line 679), so a
color-key (or stencil) ``/Mask`` has no net effect once an ``/SMask`` is
present. The parity oracle (``oracle/test_color_key_mask_smask_oracle.py``)
proves this against live Java; these tests lock the same behaviour without the
oracle so the contract is guarded on every run.
"""
from __future__ import annotations

from PIL import Image

from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument

_IMG = 32


def _dark_left_image() -> Image.Image:
    """DeviceGray base: left half dark (20), right half bright (220)."""
    base = Image.new("L", (_IMG, _IMG), 220)
    px = base.load()
    for x in range(_IMG // 2):
        for y in range(_IMG):
            px[x, y] = 20
    return base


def _vertical_ramp() -> Image.Image:
    """Top→bottom 255..0 luminance ramp (used as the /SMask alpha)."""
    ramp = Image.new("L", (_IMG, _IMG))
    px = ramp.load()
    for y in range(_IMG):
        val = round((_IMG - 1 - y) * 255 / (_IMG - 1))
        for x in range(_IMG):
            px[x, y] = val
    return ramp


def _alpha_at(img: Image.Image, x: int, y: int) -> int:
    return img.convert("RGBA").getpixel((x, y))[3]


def test_color_key_only_keys_left_half_transparent() -> None:
    """A color-key ``[0 60]`` alone keys out the dark left half (alpha 0) and
    leaves the bright right half opaque (alpha 255)."""
    with PDDocument() as doc:
        image = LosslessFactory.create_from_image(doc, _dark_left_image())
        image.set_color_key_mask([0, 60])
        out = image.get_image()
    assert out is not None
    assert _alpha_at(out, 2, 2) == 0  # left (dark) → keyed transparent
    assert _alpha_at(out, _IMG - 2, 2) == 255  # right (bright) → opaque


def test_smask_only_applies_ramp_alpha() -> None:
    """An ``/SMask`` ramp alone becomes the alpha plane: opaque at the top,
    transparent at the bottom, on both halves."""
    with PDDocument() as doc:
        image = LosslessFactory.create_from_image(doc, _dark_left_image())
        image.set_soft_mask(LosslessFactory.create_from_image(doc, _vertical_ramp()))
        out = image.get_image()
    assert out is not None
    assert _alpha_at(out, 2, 0) > 230  # top → opaque
    assert _alpha_at(out, 2, _IMG - 1) < 25  # bottom → transparent
    # Left and right columns track the same ramp (no color-key involved).
    assert abs(_alpha_at(out, 2, 0) - _alpha_at(out, _IMG - 2, 0)) <= 2


def test_color_key_plus_smask_drops_color_key() -> None:
    """color-key ``/Mask`` array + ``/SMask`` → the SMask alpha wins and the
    color-key is discarded (mirrors Java ``applyMask`` band-3 overwrite). The
    color-keyed dark-left half follows the ramp instead of going transparent."""
    with PDDocument() as doc:
        image = LosslessFactory.create_from_image(doc, _dark_left_image())
        image.set_color_key_mask([0, 60])  # would key the left half on its own
        image.set_soft_mask(LosslessFactory.create_from_image(doc, _vertical_ramp()))
        assert image.has_color_key_mask()
        assert image.has_soft_mask()
        out = image.get_image()
    assert out is not None
    # Top-left is color-keyed in isolation, but the SMask is opaque at the top
    # and OVERWRITES the alpha → opaque, NOT transparent.
    assert _alpha_at(out, 2, 0) > 230, "color-key not discarded under /SMask"
    # Left and right top cells track the same ramp value (color-key has no net
    # effect): both opaque at the top.
    assert abs(_alpha_at(out, 2, 0) - _alpha_at(out, _IMG - 2, 0)) <= 2
    # Bottom follows the ramp → transparent on both halves.
    assert _alpha_at(out, 2, _IMG - 1) < 25


def test_stencil_mask_plus_smask_drops_stencil() -> None:
    """stencil-stream ``/Mask`` + ``/SMask`` → SMask wins, the stencil is
    dropped (the wave-1449 dual-mask rule). The stencil keys the right half,
    but the rendered alpha follows the SMask ramp on both halves."""
    stencil = Image.new("1", (_IMG, _IMG), 0)
    spx = stencil.load()
    for x in range(_IMG // 2, _IMG):  # right half masked out by the stencil
        for y in range(_IMG):
            spx[x, y] = 1
    with PDDocument() as doc:
        image = LosslessFactory.create_from_image(doc, _dark_left_image())
        mask = LosslessFactory.create_from_image(doc, stencil)
        mask.set_image_mask(True)
        image.set_mask(mask)
        image.set_soft_mask(LosslessFactory.create_from_image(doc, _vertical_ramp()))
        assert image.has_explicit_mask()
        assert image.has_soft_mask()
        out = image.get_image()
    assert out is not None
    # Right half is stencil-masked in isolation, but the SMask overwrites the
    # alpha → top-right follows the ramp (opaque), not the stencil (transparent).
    assert _alpha_at(out, _IMG - 2, 0) > 230, "stencil not discarded under /SMask"
    assert abs(_alpha_at(out, 2, 0) - _alpha_at(out, _IMG - 2, 0)) <= 2
    assert _alpha_at(out, 2, _IMG - 1) < 25


def test_apply_image_masks_no_mask_returns_input_unchanged() -> None:
    """Regression: an image with no /SMask, /Mask, or color-key is returned
    untouched (still opaque RGB)."""
    with PDDocument() as doc:
        image = LosslessFactory.create_from_image(doc, _dark_left_image())
        assert not image.has_soft_mask()
        assert not image.has_explicit_mask()
        assert not image.has_color_key_mask()
        out = image.get_image()
    assert out is not None
    assert out.mode in ("L", "RGB")  # no alpha plane added


def test_get_image_renders_isinstance_pd_image_x_object() -> None:
    """Sanity: the helpers above operate on a real PDImageXObject."""
    with PDDocument() as doc:
        image = LosslessFactory.create_from_image(doc, _dark_left_image())
        assert isinstance(image, PDImageXObject)
