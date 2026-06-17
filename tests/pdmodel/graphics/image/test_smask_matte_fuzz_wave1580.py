"""Soft-mask (/SMask) alpha compositing + /Matte un-pre-multiplication fuzz
coverage for ``PDImageXObject`` (wave 1580).

Hammers the soft-mask raster path in
``org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject`` (``getImage`` →
``applyMask``) and ``SampledImageReader``:

* ``get_soft_mask`` returns the soft-mask Image XObject (stream form).
* The grayscale ``/SMask`` becomes the alpha channel with the *spec* sense —
  sample ``0`` → transparent (alpha 0), sample ``255`` → opaque (alpha 255).
  We pin the orientation explicitly so an inverted-alpha regression fails.
* ``/Matte`` un-pre-multiplication: the base colour ``c'`` was stored
  pre-blended against the matte ``m`` and is recovered as
  ``c = m + (c' - m) * 255 / a`` (upstream's ``applyMask`` fixed-point path,
  ``rgb[c] = clampColor(((rgb[c] - matteRGB[c]) * 255 / alphaPixel) +
  matteRGB[c])``). The ``alpha == 0`` edge leaves the pre-blended sample
  untouched (no divide-by-zero).
* ``/SMask`` dimensions differing from the base → resampled to the base size.
* ``/SMask`` carrying its own ``/Decode`` array (``[1 0]`` inverts the alpha).
* No ``/SMask`` → fully opaque raster (mode preserved, no alpha forced).
* ``/Mask`` stencil vs ``/SMask`` precedence — the SMask wins and overwrites
  the alpha band wholesale (Java ``applyMask`` line 679).

Library-first: pixel decode + resize wrap Pillow / the lossless factory; these
tests verify the *alpha merge* + *matte math*, not the raster library.
"""
from __future__ import annotations

import pytest
from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument

_W = COSName.get_pdf_name("Width")
_H = COSName.get_pdf_name("Height")
_BPC = COSName.get_pdf_name("BitsPerComponent")
_IMASK = COSName.get_pdf_name("ImageMask")
_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")


def _alpha(img: Image.Image, x: int, y: int) -> int:
    return img.convert("RGBA").getpixel((x, y))[3]


def _rgb(img: Image.Image, x: int, y: int) -> tuple[int, int, int]:
    return img.convert("RGBA").getpixel((x, y))[:3]


def _matte_unpremultiply(c: int, m: int, a: int) -> int:
    """Reference un-pre-multiply matching upstream ``applyMask`` clampColor."""
    if a == 0:
        return c
    v = m + (c - m) * 255.0 / a
    if v < 0:
        return 0
    if v > 255:
        return 255
    return int(round(v))


# ---------------------------------------------------------------------------
# get_soft_mask accessor — stream form is wrapped, array/absent → None
# ---------------------------------------------------------------------------


def test_get_soft_mask_wraps_stream() -> None:
    with PDDocument() as doc:
        img = LosslessFactory.create_from_image(doc, Image.new("RGB", (4, 4)))
        sm = LosslessFactory.create_from_image(doc, Image.new("L", (4, 4), 128))
        img.set_soft_mask(sm)
        fetched = img.get_soft_mask()
    assert isinstance(fetched, PDImageXObject)
    assert fetched.get_cos_object() is sm.get_cos_object()


def test_get_soft_mask_absent_is_none() -> None:
    img = PDImageXObject(COSStream())
    assert img.get_soft_mask() is None
    assert not img.has_soft_mask()


# ---------------------------------------------------------------------------
# alpha orientation: 0 = transparent, 255 = opaque (NOT inverted)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mask_value", [0, 1, 32, 64, 96, 128, 160, 200, 254, 255])
def test_smask_value_maps_directly_to_alpha(mask_value: int) -> None:
    """SMask sample value passes straight through to the alpha channel —
    0 transparent, 255 opaque (orientation NOT inverted)."""
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (6, 6), (10, 20, 30)))
        base.set_soft_mask(
            LosslessFactory.create_from_image(doc, Image.new("L", (6, 6), mask_value))
        )
        out = base.get_image()
    assert out is not None
    assert out.mode == "RGBA"
    assert _alpha(out, 2, 2) == mask_value


def test_smask_zero_is_fully_transparent_not_opaque() -> None:
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (4, 4), (1, 2, 3)))
        base.set_soft_mask(LosslessFactory.create_from_image(doc, Image.new("L", (4, 4), 0)))
        out = base.get_image()
    assert _alpha(out, 0, 0) == 0  # 0 mask == transparent, never 255


def test_smask_full_is_fully_opaque() -> None:
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (4, 4), (1, 2, 3)))
        base.set_soft_mask(LosslessFactory.create_from_image(doc, Image.new("L", (4, 4), 255)))
        out = base.get_image()
    assert _alpha(out, 0, 0) == 255


def test_smask_gradient_orientation_preserved() -> None:
    """A top→bottom ramp keeps its orientation: top opaque, bottom transparent."""
    n = 16
    ramp = Image.new("L", (n, n))
    px = ramp.load()
    for y in range(n):
        v = round((n - 1 - y) * 255 / (n - 1))
        for x in range(n):
            px[x, y] = v
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (n, n), (9, 9, 9)))
        base.set_soft_mask(LosslessFactory.create_from_image(doc, ramp))
        out = base.get_image()
    assert _alpha(out, 0, 0) > 240  # top opaque
    assert _alpha(out, 0, n - 1) < 15  # bottom transparent


# ---------------------------------------------------------------------------
# no SMask → fully opaque (RGB / mode preserved, no spurious alpha plane)
# ---------------------------------------------------------------------------


def test_no_smask_no_mask_is_opaque() -> None:
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (4, 4), (5, 6, 7)))
        out = base.get_image()
    assert out is not None
    # No mask → opaque raster returned unchanged; if asked as RGBA, all opaque.
    assert _alpha(out, 0, 0) == 255
    assert _rgb(out, 0, 0) == (5, 6, 7)


# ---------------------------------------------------------------------------
# /Matte un-pre-multiplication: c = m + (c' - m) * 255 / a
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pre_blended", "matte", "alpha"),
    [
        (150, 100, 128),
        (200, 0, 64),
        (50, 255, 200),
        (120, 60, 32),
        (180, 90, 250),
        (10, 200, 16),
        (255, 0, 255),
        (100, 100, 8),  # c' == m → recovered colour stays m regardless of alpha
    ],
)
def test_matte_unpremultiply_matches_upstream_formula(
    pre_blended: int, matte: int, alpha: int
) -> None:
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(
            doc, Image.new("RGB", (4, 4), (pre_blended,) * 3)
        )
        sm = LosslessFactory.create_from_image(doc, Image.new("L", (4, 4), alpha))
        sm.set_matte([matte / 255.0] * 3)
        base.set_soft_mask(sm)
        out = base.get_image()
    assert out is not None
    expected = _matte_unpremultiply(pre_blended, matte, alpha)
    r, g, b = _rgb(out, 0, 0)
    # libpng round-trip of the base can wobble +/-1 at the source sample.
    assert abs(r - expected) <= 2
    assert abs(g - expected) <= 2
    assert abs(b - expected) <= 2
    assert _alpha(out, 0, 0) == alpha


def test_matte_alpha_zero_leaves_preblended_sample() -> None:
    """alpha == 0 → no divide-by-zero; pre-blended colour kept, alpha 0."""
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (4, 4), (150, 150, 150)))
        sm = LosslessFactory.create_from_image(doc, Image.new("L", (4, 4), 0))
        sm.set_matte([100 / 255.0] * 3)
        base.set_soft_mask(sm)
        out = base.get_image()
    assert out is not None
    assert _rgb(out, 0, 0) == (150, 150, 150)  # untouched
    assert _alpha(out, 0, 0) == 0


def test_matte_clamps_recovered_color_to_255() -> None:
    """A bright pre-blended sample at low alpha overshoots → clamp to 255."""
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (4, 4), (250, 250, 250)))
        sm = LosslessFactory.create_from_image(doc, Image.new("L", (4, 4), 16))
        sm.set_matte([10 / 255.0] * 3)  # m=10, c'=250, a=16 → way over 255
        base.set_soft_mask(sm)
        out = base.get_image()
    assert _rgb(out, 0, 0) == (255, 255, 255)


def test_matte_absent_no_unpremultiply() -> None:
    """No /Matte → the base colour is passed through unchanged, only alpha set."""
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (4, 4), (123, 45, 67)))
        sm = LosslessFactory.create_from_image(doc, Image.new("L", (4, 4), 128))
        base.set_soft_mask(sm)
        assert sm.get_matte() is None
        out = base.get_image()
    assert _rgb(out, 0, 0) == (123, 45, 67)
    assert _alpha(out, 0, 0) == 128


def test_matte_devicegray_base_expands_to_three_components() -> None:
    """A 1-component gray /Matte on a DeviceGray base is expanded through the
    colour space's to_rgb before un-pre-multiplication (upstream extractMatte)."""
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("L", (4, 4), 150))
        assert base.get_color_space().get_name() == "DeviceGray"
        sm = LosslessFactory.create_from_image(doc, Image.new("L", (4, 4), 128))
        sm.set_matte([100 / 255.0])
        base.set_soft_mask(sm)
        extracted = base.extract_matte(sm)
        out = base.get_image()
    assert extracted is not None and len(extracted) == 3
    expected = _matte_unpremultiply(150, 100, 128)
    r, g, b = _rgb(out, 0, 0)
    assert abs(r - expected) <= 2 and abs(g - expected) <= 2 and abs(b - expected) <= 2


def test_matte_too_short_for_colorspace_skipped() -> None:
    """A /Matte shorter than the colour-space component count is ignored
    (upstream logs and returns null) — no un-pre-multiply applied."""
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (4, 4), (90, 90, 90)))
        sm = LosslessFactory.create_from_image(doc, Image.new("L", (4, 4), 128))
        # RGB base needs 3 matte components; supply only 2.
        sm.set_matte([0.5, 0.5])
        base.set_soft_mask(sm)
        assert base.extract_matte(sm) is None
        out = base.get_image()
    assert _rgb(out, 0, 0) == (90, 90, 90)  # un-touched
    assert _alpha(out, 0, 0) == 128


# ---------------------------------------------------------------------------
# SMask dimensions differing from base → resampled to base size
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("sw", "sh"), [(2, 2), (16, 16), (4, 8), (8, 4), (1, 1)])
def test_smask_resampled_to_base_size(sw: int, sh: int) -> None:
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (8, 8), (1, 2, 3)))
        base.set_soft_mask(LosslessFactory.create_from_image(doc, Image.new("L", (sw, sh), 128)))
        out = base.get_image()
    assert out is not None
    assert out.size == (8, 8)
    assert _alpha(out, 4, 4) == 128


def test_smask_smaller_resample_preserves_corner_orientation() -> None:
    """A 2x2 SMask with distinct corners maps onto the 8x8 base without
    flipping orientation (nearest-neighbour, default /Interpolate false)."""
    sm = Image.new("L", (2, 2))
    sm.putpixel((0, 0), 0)
    sm.putpixel((1, 0), 255)
    sm.putpixel((0, 1), 64)
    sm.putpixel((1, 1), 192)
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (8, 8), (5, 5, 5)))
        base.set_soft_mask(LosslessFactory.create_from_image(doc, sm))
        out = base.get_image()
    assert _alpha(out, 0, 0) == 0  # TL
    assert _alpha(out, 7, 0) == 255  # TR
    assert _alpha(out, 0, 7) == 64  # BL


# ---------------------------------------------------------------------------
# /SMask with /Decode — [1 0] inverts the alpha sense
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mask_value", [0, 50, 100, 128, 200, 255])
def test_smask_decode_one_zero_inverts_alpha(mask_value: int) -> None:
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (4, 4), (7, 8, 9)))
        sm = LosslessFactory.create_from_image(doc, Image.new("L", (4, 4), mask_value))
        sm.set_decode([1.0, 0.0])
        base.set_soft_mask(sm)
        out = base.get_image()
    # /Decode [1 0] maps sample v → 255 - v.
    assert abs(_alpha(out, 0, 0) - (255 - mask_value)) <= 1


def test_smask_decode_zero_one_is_identity() -> None:
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (4, 4), (7, 8, 9)))
        sm = LosslessFactory.create_from_image(doc, Image.new("L", (4, 4), 200))
        sm.set_decode([0.0, 1.0])  # identity
        base.set_soft_mask(sm)
        out = base.get_image()
    assert _alpha(out, 0, 0) == 200


# ---------------------------------------------------------------------------
# /Mask stencil vs /SMask precedence — SMask wins (alpha band overwritten)
# ---------------------------------------------------------------------------


def _stencil(width: int, height: int, all_ones: bool) -> PDImageXObject:
    """Build a 1-bit ImageMask stencil. all_ones → every sample 1
    (transparent); else every sample 0 (opaque)."""
    sten = COSStream()
    sten.set_item(_TYPE, COSName.get_pdf_name("XObject"))
    sten.set_item(_SUBTYPE, COSName.get_pdf_name("Image"))
    sten.set_int(_W, width)
    sten.set_int(_H, height)
    sten.set_int(_BPC, 1)
    sten.set_boolean(_IMASK, True)
    row_bytes = (width + 7) // 8
    fill = 0xFF if all_ones else 0x00
    with sten.create_output_stream() as o:
        o.write(bytes([fill] * row_bytes * height))
    return PDImageXObject(sten)


def test_stencil_mask_alone_sample_one_is_transparent() -> None:
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (8, 8), (5, 6, 7)))
        base.set_mask(_stencil(8, 8, all_ones=True))
        out = base.get_image()
    assert _alpha(out, 0, 0) == 0  # sample 1 → masked out


def test_stencil_mask_alone_sample_zero_is_opaque() -> None:
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (8, 8), (5, 6, 7)))
        base.set_mask(_stencil(8, 8, all_ones=False))
        out = base.get_image()
    assert _alpha(out, 0, 0) == 255  # sample 0 → painted


def test_smask_wins_over_stencil_mask() -> None:
    """Both /SMask and an explicit stencil /Mask present → the SMask alpha
    overwrites the band wholesale; the (all-transparent) stencil is ignored."""
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (8, 8), (5, 6, 7)))
        base.set_mask(_stencil(8, 8, all_ones=True))  # would force transparent
        base.set_soft_mask(LosslessFactory.create_from_image(doc, Image.new("L", (8, 8), 200)))
        assert base.has_soft_mask()
        out = base.get_image()
    assert _alpha(out, 0, 0) == 200  # SMask wins, stencil discarded


def test_smask_wins_over_color_key_mask() -> None:
    """color-key /Mask + /SMask → SMask alpha wins, color-key dropped."""
    dark_left = Image.new("L", (8, 8), 220)
    px = dark_left.load()
    for x in range(4):
        for y in range(8):
            px[x, y] = 20
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, dark_left)
        base.set_color_key_mask([0, 60])  # would key the dark left half out
        base.set_soft_mask(LosslessFactory.create_from_image(doc, Image.new("L", (8, 8), 130)))
        out = base.get_image()
    # Left half is NOT transparent — SMask (130) wins everywhere.
    assert _alpha(out, 1, 1) == 130
    assert _alpha(out, 6, 1) == 130


# ---------------------------------------------------------------------------
# stencil /Mask /Decode [1 0] reverses polarity
# ---------------------------------------------------------------------------


def test_stencil_mask_decode_reverses_polarity() -> None:
    with PDDocument() as doc:
        base = LosslessFactory.create_from_image(doc, Image.new("RGB", (8, 8), (5, 6, 7)))
        sten = _stencil(8, 8, all_ones=True)  # sample 1 everywhere
        sten.set_decode([1.0, 0.0])  # reverses → sample 1 now paints (opaque)
        base.set_mask(sten)
        out = base.get_image()
    assert _alpha(out, 0, 0) == 255  # reversed: sample 1 → opaque
