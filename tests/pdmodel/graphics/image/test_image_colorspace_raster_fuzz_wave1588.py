"""Fuzz / parity tests for applying a PDF colour space to a decoded image
raster (wave 1588).

Hammers the ``decode_pdimage_to_pil`` path that maps each image sample
through the image's colour space to produce an sRGB pixel:

- ``Indexed``: sample is a palette index -> the looked-up base-space
  colour -> RGB (with DeviceRGB / DeviceGray / DeviceCMYK bases, so the
  palette byte stride = base component count is exercised).
- ``DeviceGray``: sample -> gray RGB.
- ``DeviceRGB``: 3 samples passthrough.
- ``DeviceCMYK``: 4 samples -> subtractive RGB.
- ``Separation``: 1 sample -> tint transform -> alternate -> RGB.
- ``BitsPerComponent`` (1/2/4/8) affecting the max sample value / index
  packing.
- ``hival`` clamping of out-of-range indices, and a too-short palette.
- a ``/Decode`` array remapping samples *before* the colour lookup (the
  remap is applied to the sample, not to the produced RGB).

Verifies known pixel values against the PDFBox
``SampledImageReader`` / colour-space ``toRGBImage`` semantics.
"""

from __future__ import annotations

import pytest
from PIL import Image  # noqa: F401  (import guard: skip cleanly if Pillow absent)

from pypdfbox.cos import (
    COSArray,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.image import PDImageXObject

# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------


def _farr(values: list[float]) -> COSArray:
    arr = COSArray()
    for v in values:
        arr.add(COSFloat(float(v)))
    return arr


def _build_image(
    raw: bytes,
    width: int,
    height: int,
    bpc: int,
    color_space: object,
    decode: list[float] | None = None,
) -> PDImageXObject:
    stream = COSStream()
    stream.set_raw_data(raw)
    image = PDImageXObject(stream)
    image.set_width(width)
    image.set_height(height)
    image.set_bits_per_component(bpc)
    stream.set_item("ColorSpace", color_space)
    if decode is not None:
        stream.set_item("Decode", _farr(decode))
    return image


def _indexed_cs(base: object, hival: int, palette: bytes) -> COSArray:
    cs = COSArray()
    cs.add(COSName.get_pdf_name("Indexed"))
    cs.add(base)
    cs.add(COSInteger.get(hival))
    cs.add(COSString(palette))
    return cs


def _separation_cs(alternate_name: str, body: bytes, alt_range: list[float]) -> COSArray:
    tint = COSStream()
    tint.set_int("FunctionType", 4)
    tint.set_item("Domain", _farr([0.0, 1.0]))
    tint.set_item("Range", _farr(alt_range))
    tint.set_data(body)
    cs = COSArray()
    cs.add(COSName.get_pdf_name("Separation"))
    cs.add(COSName.get_pdf_name("Spot1"))
    cs.add(COSName.get_pdf_name(alternate_name))
    cs.add(tint)
    return cs


def _row(image: PDImageXObject) -> list[tuple[int, ...]]:
    pil = image.to_pil_image()
    assert pil is not None
    w, h = pil.size
    return [pil.getpixel((x, y)) for y in range(h) for x in range(w)]


# RGB palette: 0=red 1=green 2=blue 3=yellow 4=cyan 5=magenta
_RGB_PALETTE = bytes(
    [255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 0, 0, 255, 255, 255, 0, 255]
)


# --------------------------------------------------------------------------
# DeviceGray
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("samples", "expected"),
    [
        ([0, 255], [(0, 0, 0), (255, 255, 255)]),
        ([128, 64], [(128, 128, 128), (64, 64, 64)]),
        ([1, 254], [(1, 1, 1), (254, 254, 254)]),
    ],
)
def test_device_gray_passthrough(samples: list[int], expected: list[tuple]) -> None:
    img = _build_image(
        bytes(samples), len(samples), 1, 8, COSName.get_pdf_name("DeviceGray")
    )
    assert _row(img) == expected


def test_device_gray_decode_inverts() -> None:
    img = _build_image(
        bytes([0, 255]), 2, 1, 8, COSName.get_pdf_name("DeviceGray"), decode=[1, 0]
    )
    assert _row(img) == [(255, 255, 255), (0, 0, 0)]


def test_device_gray_decode_half_range() -> None:
    # Decode [0 0.5]: sample 255 -> gray 0.5 -> ~128.
    img = _build_image(
        bytes([0, 255]), 2, 1, 8, COSName.get_pdf_name("DeviceGray"), decode=[0, 0.5]
    )
    px = _row(img)
    assert px[0] == (0, 0, 0)
    assert px[1][0] in (127, 128)


@pytest.mark.parametrize("bpc", [1, 2, 4])
def test_device_gray_sub_byte_endpoints(bpc: int) -> None:
    # A single max-value sample fills the high nibble/bit of the first byte.
    img = _build_image(bytes([0xFF]), 1, 1, bpc, COSName.get_pdf_name("DeviceGray"))
    assert _row(img) == [(255, 255, 255)]


# --------------------------------------------------------------------------
# DeviceRGB
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "triple",
    [(10, 20, 30), (0, 0, 0), (255, 255, 255), (200, 1, 99)],
)
def test_device_rgb_passthrough(triple: tuple[int, int, int]) -> None:
    img = _build_image(bytes(triple), 1, 1, 8, COSName.get_pdf_name("DeviceRGB"))
    assert _row(img) == [triple]


def test_device_rgb_decode_swaps_channels() -> None:
    # Decode [1 0 0 1 0 1] inverts only the red channel.
    img = _build_image(
        bytes([0, 100, 200]),
        1,
        1,
        8,
        COSName.get_pdf_name("DeviceRGB"),
        decode=[1, 0, 0, 1, 0, 1],
    )
    assert _row(img) == [(255, 100, 200)]


# --------------------------------------------------------------------------
# DeviceCMYK
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cmyk", "expected"),
    [
        ((255, 0, 0, 0), (0, 255, 255)),  # cyan
        ((0, 255, 0, 0), (255, 0, 255)),  # magenta
        ((0, 0, 255, 0), (255, 255, 0)),  # yellow
        ((0, 0, 0, 255), (0, 0, 0)),  # black
        ((0, 0, 0, 0), (255, 255, 255)),  # white
    ],
)
def test_device_cmyk_subtractive(cmyk: tuple, expected: tuple) -> None:
    img = _build_image(bytes(cmyk), 1, 1, 8, COSName.get_pdf_name("DeviceCMYK"))
    assert _row(img) == [expected]


def test_device_cmyk_half_cyan_under_black() -> None:
    # C=128, K=128: r = (255-128)*(255-128)//255 = 63.
    img = _build_image(
        bytes([128, 0, 0, 128]), 1, 1, 8, COSName.get_pdf_name("DeviceCMYK")
    )
    r, g, b = _row(img)[0]
    assert r == 63
    assert g == 127
    assert b == 127


# --------------------------------------------------------------------------
# Indexed (8-bit)
# --------------------------------------------------------------------------


def test_indexed_rgb_base_8bit() -> None:
    cs = _indexed_cs(COSName.get_pdf_name("DeviceRGB"), 5, _RGB_PALETTE)
    img = _build_image(bytes([0, 1, 2, 3, 4, 5]), 6, 1, 8, cs)
    assert _row(img) == [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (0, 255, 255),
        (255, 0, 255),
    ]


def test_indexed_gray_base_stride_one() -> None:
    # Base DeviceGray -> 1 palette byte per entry.
    cs = _indexed_cs(COSName.get_pdf_name("DeviceGray"), 2, bytes([0, 128, 255]))
    img = _build_image(bytes([0, 1, 2]), 3, 1, 8, cs)
    assert _row(img) == [(0, 0, 0), (128, 128, 128), (255, 255, 255)]


def test_indexed_cmyk_base_stride_four() -> None:
    # Base DeviceCMYK -> 4 palette bytes per entry; wrong stride would mix
    # channels across entries.
    pal = bytes([255, 0, 0, 0, 0, 255, 0, 0])  # cyan, magenta
    cs = _indexed_cs(COSName.get_pdf_name("DeviceCMYK"), 1, pal)
    img = _build_image(bytes([0, 1]), 2, 1, 8, cs)
    assert _row(img) == [(0, 255, 255), (255, 0, 255)]


def test_indexed_hival_clamps_out_of_range_index() -> None:
    # hival=2 -> indices > 2 clamp to entry 2 (blue).
    cs = _indexed_cs(COSName.get_pdf_name("DeviceRGB"), 2, _RGB_PALETTE)
    img = _build_image(bytes([0, 5, 200, 2]), 2, 2, 8, cs)
    assert _row(img) == [(255, 0, 0), (0, 0, 255), (0, 0, 255), (0, 0, 255)]


def test_indexed_short_palette_shrinks_actual_max() -> None:
    # hival claims 5 entries but only 2 entries of bytes are present; the
    # actual max index shrinks to 1 and out-of-range indices clamp there.
    pal = bytes([255, 0, 0, 0, 255, 0])  # only 2 entries
    cs = _indexed_cs(COSName.get_pdf_name("DeviceRGB"), 5, pal)
    img = _build_image(bytes([0, 1, 3]), 3, 1, 8, cs)
    assert _row(img) == [(255, 0, 0), (0, 255, 0), (0, 255, 0)]


# --------------------------------------------------------------------------
# Indexed (sub-byte bpc)
# --------------------------------------------------------------------------


def test_indexed_1bit() -> None:
    # 2 pixels, indices 0 then 1: 0b0100_0000 = 0x40.
    cs = _indexed_cs(COSName.get_pdf_name("DeviceRGB"), 1, _RGB_PALETTE)
    img = _build_image(bytes([0x40]), 2, 1, 1, cs)
    assert _row(img) == [(255, 0, 0), (0, 255, 0)]


def test_indexed_2bit() -> None:
    # 4 pixels, indices 0,1,2,3: 0b00_01_10_11 = 0x1B.
    cs = _indexed_cs(COSName.get_pdf_name("DeviceRGB"), 3, _RGB_PALETTE)
    img = _build_image(bytes([0x1B]), 4, 1, 2, cs)
    assert _row(img) == [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]


def test_indexed_4bit() -> None:
    # 2 pixels, indices 0 and 3: 0x03.
    cs = _indexed_cs(COSName.get_pdf_name("DeviceRGB"), 3, _RGB_PALETTE)
    img = _build_image(bytes([0x03]), 2, 1, 4, cs)
    assert _row(img) == [(255, 0, 0), (255, 255, 0)]


def test_indexed_default_decode_is_index_range_4bit() -> None:
    # Default /Decode for an Indexed 4-bit image is [0 15] (the index
    # range, not [0 1]); a 16-entry grayscale ramp maps sample == index.
    pal = b"".join(bytes([k * 17, k * 17, k * 17]) for k in range(16))
    cs = _indexed_cs(COSName.get_pdf_name("DeviceRGB"), 15, pal)
    img = _build_image(bytes([0x01, 0x23]), 4, 1, 4, cs)
    px = _row(img)
    assert [p[0] for p in px] == [0, 17, 34, 51]


# --------------------------------------------------------------------------
# Indexed /Decode remap (applied BEFORE the palette lookup)
# --------------------------------------------------------------------------


def test_indexed_decode_remaps_sample_to_index_1bit() -> None:
    # 1-bit indices 0,1 with Decode [0 3]: sample 1 -> index 3 (yellow).
    cs = _indexed_cs(COSName.get_pdf_name("DeviceRGB"), 3, _RGB_PALETTE)
    img = _build_image(bytes([0x40]), 2, 1, 1, cs, decode=[0, 3])
    assert _row(img) == [(255, 0, 0), (255, 255, 0)]


def test_indexed_decode_scales_4bit() -> None:
    # 4-bit, Decode [0 7]: index = round(sample * 7/15).
    pal = b"".join(bytes([k * 16, 0, 0]) for k in range(16))
    cs = _indexed_cs(COSName.get_pdf_name("DeviceRGB"), 15, pal)
    img = _build_image(bytes([0x01, 0x23, 0xAB]), 6, 1, 4, cs, decode=[0, 7])
    # samples 0,1,2,3,10,11 -> indices 0,0,1,1,5,5.
    assert [p[0] for p in _row(img)] == [0, 0, 16, 16, 80, 80]


def test_indexed_decode_half_integer_index_rounds_half_up() -> None:
    # Regression: a fractional /Decode that lands the index exactly on N.5
    # must round half-UP (Java ``Math.round``), not banker's (Python
    # ``round``). Decode [0 7.5] on a 4-bit image: samples 1,3,5 -> float
    # indices 0.5,1.5,2.5 -> integer indices 1,2,3 (NOT 0,2,2).
    pal = b"".join(bytes([k * 16, 0, 0]) for k in range(16))
    cs = _indexed_cs(COSName.get_pdf_name("DeviceRGB"), 15, pal)
    # bytes: 0x13, 0x50 -> sub-byte samples 1,3,5,0.
    img = _build_image(bytes([0x13, 0x50]), 4, 1, 4, cs, decode=[0, 7.5])
    indices = [p[0] // 16 for p in _row(img)]
    assert indices == [1, 2, 3, 0]


def test_indexed_decode_reversed_full_range() -> None:
    # Decode [3 0] on a 2-bit image reverses the index ramp: sample s ->
    # index 3 - s.
    cs = _indexed_cs(COSName.get_pdf_name("DeviceRGB"), 3, _RGB_PALETTE)
    img = _build_image(bytes([0x1B]), 4, 1, 2, cs, decode=[3, 0])
    # samples 0,1,2,3 -> indices 3,2,1,0 -> yellow, blue, green, red.
    assert _row(img) == [(255, 255, 0), (0, 0, 255), (0, 255, 0), (255, 0, 0)]


# --------------------------------------------------------------------------
# Separation (tint transform per pixel)
# --------------------------------------------------------------------------


def test_separation_to_gray_alternate() -> None:
    # tint transform g = 1 - t; alternate DeviceGray.
    cs = _separation_cs("DeviceGray", b"{ 1 exch sub }", [0.0, 1.0])
    img = _build_image(bytes([0, 255]), 2, 1, 8, cs)
    assert _row(img) == [(255, 255, 255), (0, 0, 0)]


def test_separation_to_cmyk_magenta_ramp() -> None:
    # tint t -> CMYK (0, t, 0, 0); alternate DeviceCMYK.
    cs = _separation_cs(
        "DeviceCMYK",
        b"{ 0 exch 0 0 }",
        [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
    )
    img = _build_image(bytes([0, 255]), 2, 1, 8, cs)
    px = _row(img)
    assert px[0] == (255, 255, 255)  # tint 0 -> white
    assert px[1] == (255, 0, 255)  # tint 1 -> magenta


def test_separation_per_pixel_distinct_tints() -> None:
    cs = _separation_cs("DeviceGray", b"{ 1 exch sub }", [0.0, 1.0])
    img = _build_image(bytes([0, 64, 128, 255]), 2, 2, 8, cs)
    px = _row(img)
    # gray = 1 - sample/255, *255 truncated.
    assert px[0] == (255, 255, 255)
    assert px[3] == (0, 0, 0)
    assert px[1][0] > px[2][0]  # lower tint -> lighter gray


def test_separation_decode_inverts_tint() -> None:
    cs = _separation_cs("DeviceGray", b"{ 1 exch sub }", [0.0, 1.0])
    # Decode [1 0]: sample 0 -> tint 1 -> gray 0 -> black; sample 255 -> white.
    img = _build_image(bytes([0, 255]), 2, 1, 8, cs, decode=[1, 0])
    assert _row(img) == [(0, 0, 0), (255, 255, 255)]


# --------------------------------------------------------------------------
# bits-per-component affects the max sample value
# --------------------------------------------------------------------------


def test_device_gray_bpc_max_value_scales_to_255() -> None:
    # A 2-bit DeviceGray max sample (3) decodes to 255, intermediate (1,2)
    # to ~85/170. Two pixels in one byte: 0b11_01_0000.
    img = _build_image(bytes([0xD0]), 2, 1, 2, COSName.get_pdf_name("DeviceGray"))
    px = _row(img)
    assert px[0] == (255, 255, 255)
    assert px[1][0] in (85, 84, 86)


def test_indexed_bpc_changes_default_decode_upper() -> None:
    # The same raw byte 0x80 read as 1-bit picks index 1; read as 2-bit
    # picks index 2; the palette lookup must follow the bpc-derived index.
    cs = _indexed_cs(COSName.get_pdf_name("DeviceRGB"), 3, _RGB_PALETTE)
    one_bit = _build_image(bytes([0x80]), 1, 1, 1, cs)
    two_bit = _build_image(bytes([0x80]), 1, 1, 2, cs)
    assert _row(one_bit) == [(0, 255, 0)]  # index 1 -> green
    assert _row(two_bit) == [(0, 0, 255)]  # index 2 -> blue
