"""Fuzz / parity tests for PDImageXObject + SampledImageReader sample decode
(Wave 1575).

Hammers the raster-decode parameter surface against upstream PDFBox 3.0.7
``PDImageXObject`` / ``SampledImageReader`` semantics:

- ``/Decode`` array default per colour space and explicit inverting/remap.
- ``/Decode`` ignored regression: a non-empty ``list[float]`` from
  ``PDImageXObject.get_decode`` must reach ``SampledImageReader`` (wave 1575
  fix to ``_get_decode_array`` — previously the list shape fell through the
  ``COSArray.to_float_array`` ``except`` branch to a bogus ``[0, 1]``).
- ``/ImageMask`` stencil (always 1 bpc, DeviceGray) and ``/Decode [1 0]``
  flipping the masked-sample sense.
- color-key ``/Mask`` array (length == 2 * components) parsing + range eval.
- ``/BitsPerComponent`` 1/2/4/8/16 sample extraction.
- ``get_suffix`` / ``get_color_space`` dispatch.
- ``/Mask`` as a stream (explicit mask) vs array (color key).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
    PDImageXObject,
    _apply_explicit_mask,
    _unpack_16bit_samples,
    _unpack_sub_byte_samples,
)
from pypdfbox.pdmodel.graphics.image.sampled_image_reader import (
    SampledImageReader,
    _get_decode_array,
)

pytest.importorskip("PIL")

_WIDTH = COSName.get_pdf_name("Width")
_HEIGHT = COSName.get_pdf_name("Height")
_BPC = COSName.get_pdf_name("BitsPerComponent")
_CS = COSName.get_pdf_name("ColorSpace")
_DECODE = COSName.get_pdf_name("Decode")
_IMAGE_MASK = COSName.get_pdf_name("ImageMask")
_MASK = COSName.get_pdf_name("Mask")
_FILTER = COSName.get_pdf_name("Filter")


def _make_image(
    width: int,
    height: int,
    bpc: int | None = None,
    color_space: str | None = None,
    data: bytes | None = None,
    decode: list[float] | None = None,
    image_mask: bool = False,
) -> PDImageXObject:
    cs = COSStream()
    cs.set_item(_WIDTH, COSInteger.get(width))
    cs.set_item(_HEIGHT, COSInteger.get(height))
    if bpc is not None:
        cs.set_item(_BPC, COSInteger.get(bpc))
    if color_space is not None:
        cs.set_item(_CS, COSName.get_pdf_name(color_space))
    if image_mask:
        cs.set_boolean(_IMAGE_MASK, True)
    if decode is not None:
        arr = COSArray()
        for v in decode:
            arr.add(COSFloat(float(v)))
        cs.set_item(_DECODE, arr)
    if data is not None:
        with cs.create_output_stream() as o:
            o.write(data)
    return PDImageXObject(cs)


def _pixels(image) -> list:
    return list(image.convert("RGB").get_flattened_data())


# --------------------------------------------------------------------------
# 1. _get_decode_array: default per colour space
# --------------------------------------------------------------------------


def test_decode_default_rgb_is_three_pairs():
    img = _make_image(2, 1, bpc=8, color_space="DeviceRGB")
    assert _get_decode_array(img) == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


def test_decode_default_gray_is_one_pair():
    img = _make_image(2, 1, bpc=8, color_space="DeviceGray")
    assert _get_decode_array(img) == [0.0, 1.0]


def test_decode_default_cmyk_is_four_pairs():
    img = _make_image(2, 1, bpc=8, color_space="DeviceCMYK")
    assert _get_decode_array(img) == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


def test_decode_default_stencil_is_one_pair():
    # ImageMask resolves to DeviceGray (1 component), default [0 1].
    img = _make_image(8, 1, image_mask=True, data=b"\xff")
    assert _get_decode_array(img) == [0.0, 1.0]


# --------------------------------------------------------------------------
# 2. _get_decode_array: explicit decode honoured for the list shape
#    (regression: PDImageXObject.get_decode returns list[float])
# --------------------------------------------------------------------------


def test_explicit_inverting_gray_decode_reaches_reader():
    img = _make_image(2, 1, bpc=8, color_space="DeviceGray", decode=[1.0, 0.0])
    assert _get_decode_array(img) == [1.0, 0.0]


def test_explicit_rgb_decode_reaches_reader():
    img = _make_image(
        2, 1, bpc=8, color_space="DeviceRGB", decode=[1, 0, 1, 0, 1, 0]
    )
    assert _get_decode_array(img) == [1.0, 0.0, 1.0, 0.0, 1.0, 0.0]


def test_partial_decode_remap_reaches_reader():
    img = _make_image(
        2, 1, bpc=8, color_space="DeviceGray", decode=[0.25, 0.75]
    )
    assert _get_decode_array(img) == [0.25, 0.75]


def test_empty_decode_array_falls_back_to_default():
    cs = COSStream()
    cs.set_item(_WIDTH, COSInteger.get(2))
    cs.set_item(_HEIGHT, COSInteger.get(1))
    cs.set_item(_BPC, COSInteger.get(8))
    cs.set_item(_CS, COSName.get_pdf_name("DeviceRGB"))
    cs.set_item(_DECODE, COSArray())  # empty array
    img = PDImageXObject(cs)
    # Empty decode -> per-component default [0 1 0 1 0 1].
    assert _get_decode_array(img) == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


# --------------------------------------------------------------------------
# 3. End-to-end get_rgb_image with /Decode (the bug's observable effect)
# --------------------------------------------------------------------------


def test_gray_inverting_decode_flips_pixels():
    img = _make_image(
        2, 1, bpc=8, color_space="DeviceGray", data=bytes([0, 255]),
        decode=[1.0, 0.0],
    )
    out = SampledImageReader.get_rgb_image(img)
    # raw 0 -> 255 (white), raw 255 -> 0 (black)
    assert _pixels(out) == [(255, 255, 255), (0, 0, 0)]


def test_gray_default_decode_keeps_pixels():
    img = _make_image(
        2, 1, bpc=8, color_space="DeviceGray", data=bytes([0, 255]),
    )
    out = SampledImageReader.get_rgb_image(img)
    assert _pixels(out) == [(0, 0, 0), (255, 255, 255)]


def test_rgb_inverting_decode_flips_each_channel():
    # one pixel: raw (0, 128, 255) with [1 0 1 0 1 0] -> (255, 127, 0)
    img = _make_image(
        1, 1, bpc=8, color_space="DeviceRGB", data=bytes([0, 128, 255]),
        decode=[1, 0, 1, 0, 1, 0],
    )
    out = SampledImageReader.get_rgb_image(img)
    r, g, b = _pixels(out)[0]
    assert r == 255
    assert b == 0
    assert 126 <= g <= 129


# --------------------------------------------------------------------------
# 4. BitsPerComponent 1/2/4/8/16 sample extraction
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bpc", "byte", "expected"),
    [
        (1, 0b10110000, [1, 0, 1, 1, 0, 0, 0, 0]),
        (2, 0b11100100, [3, 2, 1, 0]),
        (4, 0xAB, [0xA, 0xB]),
    ],
    ids=["bpc1", "bpc2", "bpc4"],
)
def test_unpack_sub_byte_samples(bpc, byte, expected):
    width = 8 // bpc
    out = _unpack_sub_byte_samples(bytes([byte]), width, 1, bpc)
    assert list(out) == expected


def test_unpack_sub_byte_row_padding():
    # 3 samples of 4 bpc per row -> 12 bits -> padded to 2 bytes per row.
    data = bytes([0x12, 0x30, 0x45, 0x60])  # row0: 1,2,3  row1: 4,5,6
    out = _unpack_sub_byte_samples(data, 3, 2, 4)
    assert list(out) == [1, 2, 3, 4, 5, 6]


def test_unpack_16bit_big_endian():
    data = bytes([0x12, 0x34, 0xFF, 0xFF, 0x00, 0x00])
    out = _unpack_16bit_samples(data, 3, 1)
    assert out == [0x1234, 0xFFFF, 0x0000]


def test_unpack_16bit_short_buffer_returns_none():
    assert _unpack_16bit_samples(b"\x12", 3, 1) is None


def test_bpc8_gray_roundtrip_via_reader():
    img = _make_image(
        2, 1, bpc=8, color_space="DeviceGray", data=bytes([64, 192]),
    )
    out = SampledImageReader.get_rgb_image(img)
    assert _pixels(out) == [(64, 64, 64), (192, 192, 192)]


def test_bpc1_gray_via_to_pil():
    # one packed byte 0b10000000 -> samples 1,0,0,0,0,0,0,0 over 8 px
    img = _make_image(
        8, 1, bpc=1, color_space="DeviceGray", data=bytes([0b10000000]),
    )
    out = img.to_pil_image()
    px = _pixels(out)
    assert px[0] == (255, 255, 255)
    assert px[1] == (0, 0, 0)


def test_bpc16_gray_via_to_pil():
    # two 16-bit gray samples: 0xFFFF (white) and 0x0000 (black)
    img = _make_image(
        2, 1, bpc=16, color_space="DeviceGray",
        data=bytes([0xFF, 0xFF, 0x00, 0x00]),
    )
    out = img.to_pil_image()
    assert _pixels(out) == [(255, 255, 255), (0, 0, 0)]


# --------------------------------------------------------------------------
# 5. /ImageMask stencil: always 1 bpc, decode flips masked-sample sense
# --------------------------------------------------------------------------


def test_image_mask_forces_one_bpc():
    img = _make_image(8, 1, bpc=8, image_mask=True, data=b"\xff")
    # is_stencil short-circuits get_bits_per_component to 1.
    assert img.get_bits_per_component() == 1
    assert img.is_stencil()


def test_image_mask_default_color_space_is_gray():
    img = _make_image(8, 1, image_mask=True, data=b"\xff")
    cs = img.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceGray"


def test_stencil_default_decode_value_is_one():
    # Default decode [0 1] -> decode[0] < decode[1] -> masked value == 1:
    # a set bit (1) clears the painted pixel.
    img = _make_image(8, 1, image_mask=True, data=bytes([0b11110000]))
    masked = SampledImageReader.get_stencil_image(img, (255, 0, 0, 255))
    # bits 1 -> transparent, bits 0 -> painted red
    alpha = [masked.getpixel((x, 0))[3] for x in range(8)]
    assert alpha == [0, 0, 0, 0, 255, 255, 255, 255]


def test_stencil_inverting_decode_flips_sense():
    # /Decode [1 0] -> decode[0] > decode[1] -> masked value == 0:
    # now a clear bit (0) clears the painted pixel.
    img = _make_image(
        8, 1, image_mask=True, data=bytes([0b11110000]), decode=[1.0, 0.0]
    )
    masked = SampledImageReader.get_stencil_image(img, (255, 0, 0, 255))
    alpha = [masked.getpixel((x, 0))[3] for x in range(8)]
    assert alpha == [255, 255, 255, 255, 0, 0, 0, 0]


def test_explicit_mask_default_stencil_sense():
    base = _make_image(2, 1, bpc=8, color_space="DeviceRGB",
                       data=bytes([10, 20, 30, 40, 50, 60]))
    base_img = base.to_pil_image()
    # mask 1 bpc, 2 px: byte 0b10000000 -> sample 1,0.
    # default decode: sample 1 -> masked (alpha 0), sample 0 -> opaque (255).
    mask = _make_image(2, 1, image_mask=True, data=bytes([0b10000000]))
    out = _apply_explicit_mask(base_img, mask)
    assert out.getpixel((0, 0))[3] == 0
    assert out.getpixel((1, 0))[3] == 255


def test_explicit_mask_inverting_decode_flips_sense():
    base = _make_image(2, 1, bpc=8, color_space="DeviceRGB",
                       data=bytes([10, 20, 30, 40, 50, 60]))
    base_img = base.to_pil_image()
    mask = _make_image(
        2, 1, image_mask=True, data=bytes([0b10000000]), decode=[1.0, 0.0]
    )
    out = _apply_explicit_mask(base_img, mask)
    # sense flipped: sample 1 -> opaque, sample 0 -> masked
    assert out.getpixel((0, 0))[3] == 255
    assert out.getpixel((1, 0))[3] == 0


# --------------------------------------------------------------------------
# 6. color-key /Mask array (length 2*components) parsing + eval
# --------------------------------------------------------------------------


def _set_color_key(img: PDImageXObject, values: list[int]) -> None:
    arr = COSArray()
    for v in values:
        arr.add(COSInteger.get(v))
    img.get_cos_object().set_item(_MASK, arr)


def test_color_key_mask_array_parses_to_int_list():
    img = _make_image(2, 1, bpc=8, color_space="DeviceRGB",
                      data=bytes([0, 0, 0, 255, 255, 255]))
    _set_color_key(img, [0, 0, 0, 0, 0, 0])
    assert img.get_color_key_mask() == [0, 0, 0, 0, 0, 0]
    assert img.has_color_key_mask()
    assert img.get_mask() is None  # array form, not a stream


def test_color_key_mask_masks_in_range_pixel():
    # 2 RGB px: black (0,0,0) and white (255,255,255). Key range hides black.
    img = _make_image(2, 1, bpc=8, color_space="DeviceRGB",
                      data=bytes([0, 0, 0, 255, 255, 255]))
    _set_color_key(img, [0, 10, 0, 10, 0, 10])
    out = img.get_image()
    assert out.mode == "RGBA"
    assert out.getpixel((0, 0))[3] == 0      # black -> masked
    assert out.getpixel((1, 0))[3] == 255    # white -> opaque


def test_color_key_mask_range_length_is_two_per_component():
    img = _make_image(2, 1, bpc=8, color_space="DeviceRGB",
                      data=bytes([0, 0, 0, 255, 255, 255]))
    _set_color_key(img, [0, 0, 0, 0, 0, 0])
    ck = img.get_color_key_mask()
    cs = img.get_color_space()
    assert len(ck) == 2 * cs.get_number_of_components()


def test_color_key_mask_gray_single_pair():
    img = _make_image(2, 1, bpc=8, color_space="DeviceGray",
                      data=bytes([0, 255]))
    _set_color_key(img, [0, 5])
    out = img.get_image()
    assert out.getpixel((0, 0))[3] == 0      # 0 in [0,5] -> masked
    assert out.getpixel((1, 0))[3] == 255    # 255 outside -> opaque


def test_color_key_mask_non_integer_returns_none():
    img = _make_image(2, 1, bpc=8, color_space="DeviceRGB",
                      data=bytes([0, 0, 0, 1, 1, 1]))
    arr = COSArray()
    arr.add(COSName.get_pdf_name("bogus"))
    arr.add(COSInteger.get(0))
    img.get_cos_object().set_item(_MASK, arr)
    assert img.get_color_key_mask() is None


# --------------------------------------------------------------------------
# 7. /Mask as a stream (explicit mask) vs array (color key) dispatch
# --------------------------------------------------------------------------


def test_mask_stream_is_explicit_not_color_key():
    base = _make_image(2, 1, bpc=8, color_space="DeviceRGB",
                       data=bytes([10, 20, 30, 40, 50, 60]))
    mask = _make_image(2, 1, image_mask=True, data=bytes([0b10000000]))
    base.get_cos_object().set_item(_MASK, mask.get_cos_object())
    assert base.get_mask() is not None
    assert base.has_explicit_mask()
    assert base.get_color_key_mask() is None
    assert not base.has_color_key_mask()


def test_mask_array_is_color_key_not_explicit():
    img = _make_image(2, 1, bpc=8, color_space="DeviceRGB",
                      data=bytes([0, 0, 0, 1, 1, 1]))
    _set_color_key(img, [0, 0, 0, 0, 0, 0])
    assert img.get_mask() is None
    assert not img.has_explicit_mask()
    assert img.get_color_key_mask() is not None


def test_has_mask_true_for_both_forms():
    stream_img = _make_image(2, 1, bpc=8, color_space="DeviceRGB",
                             data=bytes([0, 0, 0, 1, 1, 1]))
    mask = _make_image(2, 1, image_mask=True, data=bytes([0x80]))
    stream_img.get_cos_object().set_item(_MASK, mask.get_cos_object())
    assert stream_img.has_mask()

    key_img = _make_image(2, 1, bpc=8, color_space="DeviceRGB",
                          data=bytes([0, 0, 0, 1, 1, 1]))
    _set_color_key(key_img, [0, 0, 0, 0, 0, 0])
    assert key_img.has_mask()


# --------------------------------------------------------------------------
# 8. get_suffix / get_color_space dispatch
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("filter_name", "expected"),
    [
        ("DCTDecode", "jpg"),
        ("JPXDecode", "jpx"),
        ("CCITTFaxDecode", "tiff"),
        ("FlateDecode", "png"),
        ("LZWDecode", "png"),
        ("RunLengthDecode", "png"),
        ("JBIG2Decode", "jb2"),
    ],
    ids=["dct", "jpx", "ccitt", "flate", "lzw", "rle", "jbig2"],
)
def test_get_suffix_filter_dispatch(filter_name, expected):
    img = _make_image(2, 1, bpc=8, color_space="DeviceRGB")
    img.get_cos_object().set_item(_FILTER, COSName.get_pdf_name(filter_name))
    assert img.get_suffix() == expected


def test_get_suffix_no_filter_is_png():
    img = _make_image(2, 1, bpc=8, color_space="DeviceRGB")
    assert img.get_suffix() == "png"


def test_get_color_space_dispatch_by_name():
    for name, comps in (("DeviceGray", 1), ("DeviceRGB", 3), ("DeviceCMYK", 4)):
        img = _make_image(2, 1, bpc=8, color_space=name)
        cs = img.get_color_space()
        assert cs.get_name() == name
        assert cs.get_number_of_components() == comps


def test_get_color_space_missing_returns_none_for_non_stencil():
    img = _make_image(2, 1, bpc=8)
    assert img.get_color_space() is None


def test_get_color_space_short_cs_alias():
    cs = COSStream()
    cs.set_item(_WIDTH, COSInteger.get(2))
    cs.set_item(_HEIGHT, COSInteger.get(1))
    cs.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceRGB"))
    img = PDImageXObject(cs)
    assert img.get_color_space().get_name() == "DeviceRGB"
