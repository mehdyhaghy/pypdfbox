"""Wave 1594 — DCTDecode (JPEG) colour-handling fuzz.

Hammers the JPEG decode + Adobe APP14 transform + CMYK/YCCK colour
paths for behavioural parity with upstream PDFBox ``DCTFilter``:

* component-count -> colour-component mapping (Gray=1 / RGB=3 / CMYK=4),
* the imagecodecs primary path and the Pillow fallback agreeing on CMYK
  *polarity* (the inverted-CMYK trap — both must hand back the JPEG-stored
  Adobe-inverted raster, matching upstream which leaves the correction to
  the ``/Decode`` array),
* the Adobe APP14 marker detection in raw header bytes
  (``get_adobe_transform`` + ``get_adobe_transform_by_brute_force``),
* the YCCK (transform=2) -> CMYK conversion coefficients + K passthrough,
* the ``/Decode [1 0 1 0 1 0 1 0]`` interaction JPEGFactory attaches to
  CMYK JPEGs (applied exactly once, no double-invert on render),
* the colour-space component count matching the JPEG.

These exercise the helpers directly (no Java oracle needed) and assert the
byte-level polarity invariants upstream guarantees.
"""

from __future__ import annotations

import io
from unittest import mock

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import DCTDecode
from pypdfbox.filter.dct_filter import DCTFilter, Raster
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.graphics.image.jpeg_factory import JPEGFactory

# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _jpeg(mode: str, size: tuple[int, int], pixels: bytes) -> bytes:
    image = Image.frombytes(mode, size, pixels)
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=100, subsampling=0)
    return out.getvalue()


def _decode(data: bytes) -> tuple[bytes, COSDictionary]:
    sink = io.BytesIO()
    result = DCTDecode().decode(io.BytesIO(data), sink, COSDictionary())
    return sink.getvalue(), result.parameters


def _app14(transform: int) -> bytes:
    """Canonical APP14 ``Adobe`` segment carrying ``transform``."""
    return (
        b"\xff\xee\x00\x0e"
        + b"Adobe"
        + b"\x00\x65\x00\x00\x00\x00"
        + bytes([transform & 0xFF])
        + b"\x00\x00\x00"
    )


# ----------------------------------------------------------------------
# component-count -> ColorComponents mapping
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "px", "expected_components"),
    [
        ("L", bytes([100] * 4), 1),
        ("L", bytes([0, 255, 128, 64]), 1),
        ("RGB", bytes([10, 20, 30] * 4), 3),
        ("RGB", bytes([255, 0, 0] * 4), 3),
        ("CMYK", bytes([10, 20, 30, 40] * 4), 4),
        ("CMYK", bytes([0, 0, 0, 0] * 4), 4),
    ],
    ids=["gray_flat", "gray_ramp", "rgb_dark", "rgb_red", "cmyk_a", "cmyk_zero"],
)
def test_color_components_match_jpeg(
    mode: str, px: bytes, expected_components: int
) -> None:
    _, params = _decode(_jpeg(mode, (2, 2), px))
    assert params.get_int("ColorComponents") == expected_components
    assert params.get_int("BitsPerComponent") == 8
    assert params.get_int("Width") == 2
    assert params.get_int("Height") == 2


def test_gray_jpeg_is_single_band() -> None:
    samples, params = _decode(_jpeg("L", (3, 3), bytes([77] * 9)))
    assert params.get_int("ColorComponents") == 1
    assert len(samples) == 9


def test_rgb_jpeg_is_three_bands() -> None:
    samples, params = _decode(_jpeg("RGB", (2, 2), bytes([5, 6, 7] * 4)))
    assert params.get_int("ColorComponents") == 3
    assert len(samples) == 2 * 2 * 3


def test_cmyk_jpeg_is_four_bands() -> None:
    samples, params = _decode(_jpeg("CMYK", (2, 2), bytes([1, 2, 3, 4] * 4)))
    assert params.get_int("ColorComponents") == 4
    assert len(samples) == 2 * 2 * 4


# ----------------------------------------------------------------------
# CMYK polarity: imagecodecs primary path vs Pillow fallback must agree
# (the inverted-CMYK trap)
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "px",
    [
        bytes([10, 20, 30, 40] * 4),
        bytes([255, 0, 0, 0] * 4),
        bytes([0, 0, 0, 255] * 4),
        bytes([200, 150, 100, 50] * 4),
    ],
    ids=["mixed", "pure_c", "pure_k", "ramp"],
)
def test_cmyk_primary_and_fallback_polarity_agree(px: bytes) -> None:
    data = _jpeg("CMYK", (2, 2), px)
    primary, _ = _decode(data)
    with mock.patch(
        "pypdfbox.filter.dct_decode.imagecodecs.jpeg8_decode",
        side_effect=Exception("force fallback"),
    ):
        fallback, _ = _decode(data)
    assert primary == fallback


def test_cmyk_decode_preserves_adobe_inverted_polarity() -> None:
    # Adobe-marked CMYK JPEG (Pillow always writes the APP14 marker) is
    # stored inverted (255 = ink-off). Upstream DCTFilter.decode keeps the
    # stored raster; the imagecodecs path returns it inverted. A flat
    # (10,20,30,40) image therefore decodes to (245,235,225,215).
    data = _jpeg("CMYK", (2, 2), bytes([10, 20, 30, 40] * 4))
    samples, _ = _decode(data)
    assert list(samples[:4]) == [245, 235, 225, 215]


def test_cmyk_fallback_inverts_to_match_stored_convention() -> None:
    data = _jpeg("CMYK", (2, 2), bytes([10, 20, 30, 40] * 4))
    with mock.patch(
        "pypdfbox.filter.dct_decode.imagecodecs.jpeg8_decode",
        side_effect=Exception("force fallback"),
    ):
        samples, params = _decode(data)
    assert params.get_int("ColorComponents") == 4
    assert list(samples[:4]) == [245, 235, 225, 215]


def test_rgb_fallback_not_inverted() -> None:
    # The CMYK re-inversion must not touch RGB: a flat colour stays put.
    data = _jpeg("RGB", (2, 2), bytes([10, 20, 30] * 4))
    primary, _ = _decode(data)
    with mock.patch(
        "pypdfbox.filter.dct_decode.imagecodecs.jpeg8_decode",
        side_effect=Exception("force fallback"),
    ):
        fallback, _ = _decode(data)
    assert primary == fallback
    # Lossy at quality=100 but flat colour is near-exact; assert no inversion.
    assert fallback[0] < 128 and fallback[1] < 128


def test_gray_fallback_not_inverted() -> None:
    data = _jpeg("L", (2, 2), bytes([30] * 4))
    with mock.patch(
        "pypdfbox.filter.dct_decode.imagecodecs.jpeg8_decode",
        side_effect=Exception("force fallback"),
    ):
        fallback, _ = _decode(data)
    assert all(b < 128 for b in fallback)


# ----------------------------------------------------------------------
# Adobe APP14 marker / transform detection
# ----------------------------------------------------------------------


@pytest.mark.parametrize("transform", [0, 1, 2])
def test_brute_force_reads_transform_byte(transform: int) -> None:
    assert (
        DCTFilter().get_adobe_transform_by_brute_force(io.BytesIO(_app14(transform)))
        == transform
    )


def test_brute_force_no_adobe_marker_returns_zero() -> None:
    data = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x02\x00\x00\x01\x00\x01\x00\x00"
    assert DCTFilter().get_adobe_transform_by_brute_force(io.BytesIO(data)) == 0


def test_brute_force_wrong_marker_tag_skipped() -> None:
    # "Adobe" present but the 2 bytes before length are not 0xFFEE.
    data = b"\x00\x00\xff\xe0\x00\x0eAdobe\x00\x00\x00\x00\x00\x02"
    assert DCTFilter().get_adobe_transform_by_brute_force(io.BytesIO(data)) == 0


def test_brute_force_finds_marker_with_leading_noise() -> None:
    data = b"\x00" * 13 + _app14(2)
    assert DCTFilter().get_adobe_transform_by_brute_force(io.BytesIO(data)) == 2


def test_brute_force_on_real_cmyk_jpeg_header() -> None:
    # Pillow-written CMYK JPEG carries an Adobe APP14 with transform 0.
    data = _jpeg("CMYK", (2, 2), bytes([10, 20, 30, 40] * 4))
    assert b"Adobe" in data
    assert DCTFilter().get_adobe_transform_by_brute_force(io.BytesIO(data)) == 0


def test_brute_force_partial_adobe_then_full_match() -> None:
    # A partial "Ado" then a full canonical segment: the scanner must reset
    # and still find the real transform.
    data = b"Ado" + b"\x00" + b"\x00" * 9 + _app14(1)
    assert DCTFilter().get_adobe_transform_by_brute_force(io.BytesIO(data)) == 1


@pytest.mark.parametrize("transform", [0, 1, 2])
def test_get_adobe_transform_from_info_dict(transform: int) -> None:
    assert DCTFilter().get_adobe_transform({"adobe_transform": transform}) == transform


def test_get_adobe_transform_absent_returns_zero() -> None:
    assert DCTFilter().get_adobe_transform({}) == 0
    assert DCTFilter().get_adobe_transform(None) == 0


def test_get_adobe_transform_from_loaded_cmyk_image() -> None:
    data = _jpeg("CMYK", (2, 2), bytes([10, 20, 30, 40] * 4))
    image = Image.open(io.BytesIO(data))
    image.load()
    # Pillow surfaces the APP14 transform under info["adobe_transform"].
    assert DCTFilter().get_adobe_transform(image) == 0


# ----------------------------------------------------------------------
# YCCK (transform=2) -> CMYK conversion
# ----------------------------------------------------------------------


def test_ycck_neutral_gray_round_trips_chroma() -> None:
    # Neutral chroma (Cb=Cr=128) -> CMY all equal, K passes through.
    raster = Raster(samples=bytes([128, 128, 128, 77]), width=1, height=1, num_bands=4)
    out = DCTFilter().from_ycc_kto_cmyk(raster)
    c, m, y, k = out.samples
    assert k == 77
    assert abs(c - 127) <= 1 and abs(m - 127) <= 1 and abs(y - 127) <= 1


def test_ycck_k_channel_passthrough() -> None:
    for k in (0, 50, 200, 255):
        raster = Raster(samples=bytes([100, 120, 140, k]), width=1, height=1, num_bands=4)
        assert DCTFilter().from_ycc_kto_cmyk(raster).samples[3] == k


def test_ycck_white_luma_gives_low_cmy() -> None:
    # Y=255 neutral chroma -> RGB near white -> CMY near 0.
    raster = Raster(samples=bytes([255, 128, 128, 0]), width=1, height=1, num_bands=4)
    c, m, y, _ = DCTFilter().from_ycc_kto_cmyk(raster).samples
    assert c == 0 and m == 0 and y == 0


def test_ycck_black_luma_gives_high_cmy() -> None:
    # Y=0 neutral chroma -> RGB near black -> CMY near 255.
    raster = Raster(samples=bytes([0, 128, 128, 0]), width=1, height=1, num_bands=4)
    c, m, y, _ = DCTFilter().from_ycc_kto_cmyk(raster).samples
    assert c >= 254 and m >= 254 and y >= 254


def test_ycck_requires_four_bands() -> None:
    raster = Raster(samples=bytes([1, 2, 3]), width=1, height=1, num_bands=3)
    with pytest.raises(ValueError, match="4-band"):
        DCTFilter().from_ycc_kto_cmyk(raster)


def test_ycck_preserves_geometry() -> None:
    raster = Raster(samples=bytes([100, 128, 128, 10] * 6), width=3, height=2, num_bands=4)
    out = DCTFilter().from_ycc_kto_cmyk(raster)
    assert (out.width, out.height, out.num_bands) == (3, 2, 4)
    assert len(out.samples) == len(raster.samples)


# ----------------------------------------------------------------------
# /Decode interaction on render (JPEGFactory CMYK path)
# ----------------------------------------------------------------------


def test_jpeg_factory_cmyk_attaches_inverting_decode() -> None:
    doc = PDDocument()
    try:
        cmyk = Image.new("CMYK", (2, 2), (10, 20, 30, 40))
        xobj = JPEGFactory.create_from_image(doc, cmyk)
        assert xobj.get_decode() == [1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0]
    finally:
        doc.close()


def test_jpeg_factory_rgb_has_no_decode_inversion() -> None:
    doc = PDDocument()
    try:
        rgb = Image.new("RGB", (2, 2), (10, 20, 30))
        xobj = JPEGFactory.create_from_image(doc, rgb)
        # No inverting /Decode for RGB.
        decode = xobj.get_decode()
        assert decode is None or decode == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
    finally:
        doc.close()


def test_cmyk_render_applies_decode_exactly_once() -> None:
    # Pure-cyan PDF DeviceCMYK (C=1) must render as cyan RGB (0,255,255).
    # A double-invert would give red (255,0,0); a missing invert would also
    # corrupt the colour. Exactly-once is the only correct outcome.
    doc = PDDocument()
    try:
        cmyk = Image.new("CMYK", (2, 2), (255, 0, 0, 0))
        xobj = JPEGFactory.create_from_image(doc, cmyk)
        rgb = xobj.get_image()
        assert rgb.mode == "RGB"
        r, g, b = rgb.getpixel((0, 0))
        assert r < 64 and g > 192 and b > 192
    finally:
        doc.close()


def test_cmyk_render_pure_black_k() -> None:
    doc = PDDocument()
    try:
        cmyk = Image.new("CMYK", (2, 2), (0, 0, 0, 255))
        xobj = JPEGFactory.create_from_image(doc, cmyk)
        r, g, b = xobj.get_image().getpixel((0, 0))
        assert r < 32 and g < 32 and b < 32
    finally:
        doc.close()


def test_gray_render_round_trips_luma() -> None:
    doc = PDDocument()
    try:
        gray = Image.new("L", (2, 2), 30)
        xobj = JPEGFactory.create_from_image(doc, gray)
        r, g, b = xobj.get_image().getpixel((0, 0))
        assert r < 96 and g < 96 and b < 96
    finally:
        doc.close()


def test_rgb_render_round_trips_colour() -> None:
    doc = PDDocument()
    try:
        rgb = Image.new("RGB", (2, 2), (200, 30, 40))
        xobj = JPEGFactory.create_from_image(doc, rgb)
        r, g, b = xobj.get_image().getpixel((0, 0))
        assert r > 160 and g < 96 and b < 96
    finally:
        doc.close()
