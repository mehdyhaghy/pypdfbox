"""Hand-written tests for :class:`LosslessFactory`.

Covers the per-mode dispatch documented in the class docstring: 1-bit,
8-bit grayscale, 16-bit grayscale, RGB, RGBA, LA, and indexed/palette
(both with and without transparency). Each test generates a small PIL
source image, runs it through ``LosslessFactory.create_from_image``,
and asserts the resulting :class:`PDImageXObject` has the expected
metadata and a flate-encoded body that round-trips.
"""
from __future__ import annotations

import zlib

from PIL import Image

from pypdfbox.cos import COSArray, COSName, COSStream, COSString
from pypdfbox.pdmodel.graphics.image import LosslessFactory, PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument


# ---------- helpers ----------


def _decoded_body(image_x: PDImageXObject) -> bytes:
    """Inflate the raw ``/FlateDecode`` body and return the decoded bytes."""
    cos = image_x.get_cos_object()
    assert isinstance(cos, COSStream)
    return zlib.decompress(cos.get_raw_data())


def _is_flate_filter(image_x: PDImageXObject) -> bool:
    f = image_x.get_filter()
    return isinstance(f, COSName) and f.name == "FlateDecode"


# ---------- public-API guards ----------


def test_static_factory_cannot_be_instantiated() -> None:
    try:
        LosslessFactory()
    except TypeError:
        return
    raise AssertionError("LosslessFactory() should raise TypeError")


# ---------- 1-bit ----------


def test_create_from_one_bit_image() -> None:
    document = PDDocument()
    # 13 px wide forces row padding (not multiple of 8).
    src = Image.new("1", (13, 4), color=0)
    # Set a couple pixels white.
    src.putpixel((0, 0), 1)
    src.putpixel((12, 3), 1)

    image_x = LosslessFactory.create_from_image(document, src)
    assert image_x.get_width() == 13
    assert image_x.get_height() == 4
    assert image_x.get_bits_per_component() == 1
    cs = image_x.get_color_space_cos_object()
    assert isinstance(cs, COSName)
    assert cs.name == "DeviceGray"
    assert _is_flate_filter(image_x)
    assert image_x.get_soft_mask() is None

    body = _decoded_body(image_x)
    # Each row is ceil(13/8)=2 bytes → 8 bytes total.
    assert len(body) == 2 * 4
    # First bit of row 0 set, last bit of row 3 set.
    assert body[0] == 0b1000_0000
    assert body[7] == 0b0000_1000  # bit 12: byte 1, position 12 % 8 = 4 → 0x08


# ---------- 8-bit grayscale ----------


def test_create_from_l_image() -> None:
    document = PDDocument()
    src = Image.new("L", (4, 3), color=0)
    src.putpixel((0, 0), 17)
    src.putpixel((3, 2), 200)

    image_x = LosslessFactory.create_from_image(document, src)
    assert image_x.get_width() == 4
    assert image_x.get_height() == 3
    assert image_x.get_bits_per_component() == 8
    cs = image_x.get_color_space_cos_object()
    assert isinstance(cs, COSName) and cs.name == "DeviceGray"
    assert _is_flate_filter(image_x)
    assert image_x.get_soft_mask() is None

    body = _decoded_body(image_x)
    assert len(body) == 4 * 3
    assert body[0] == 17
    assert body[-1] == 200


# ---------- 16-bit grayscale ----------


def test_create_from_i16_image() -> None:
    document = PDDocument()
    src = Image.new("I;16", (2, 2), color=0)
    src.putpixel((0, 0), 0x1234)
    src.putpixel((1, 1), 0xABCD)

    image_x = LosslessFactory.create_from_image(document, src)
    assert image_x.get_bits_per_component() == 16
    body = _decoded_body(image_x)
    # 2x2 px, 2 bytes/sample = 8 bytes, big-endian.
    assert len(body) == 8
    assert body[0:2] == b"\x12\x34"
    assert body[6:8] == b"\xab\xcd"


# ---------- LA (gray+alpha) ----------


def test_create_from_la_image_attaches_smask() -> None:
    document = PDDocument()
    src = Image.new("LA", (3, 2), color=(0, 0))
    src.putpixel((0, 0), (100, 200))
    src.putpixel((2, 1), (40, 80))

    image_x = LosslessFactory.create_from_image(document, src)
    cs = image_x.get_color_space_cos_object()
    assert isinstance(cs, COSName) and cs.name == "DeviceGray"
    assert image_x.get_bits_per_component() == 8

    smask = image_x.get_soft_mask()
    assert smask is not None
    assert smask.get_width() == 3
    assert smask.get_height() == 2
    assert smask.get_bits_per_component() == 8
    smask_cs = smask.get_color_space_cos_object()
    assert isinstance(smask_cs, COSName) and smask_cs.name == "DeviceGray"

    body = _decoded_body(image_x)
    smask_body = _decoded_body(smask)
    assert body[0] == 100
    assert smask_body[0] == 200
    assert body[-1] == 40
    assert smask_body[-1] == 80


# ---------- RGB ----------


def test_create_from_rgb_image() -> None:
    document = PDDocument()
    src = Image.new("RGB", (2, 2), color=(0, 0, 0))
    src.putpixel((0, 0), (10, 20, 30))
    src.putpixel((1, 1), (200, 100, 50))

    image_x = LosslessFactory.create_from_image(document, src)
    cs = image_x.get_color_space_cos_object()
    assert isinstance(cs, COSName) and cs.name == "DeviceRGB"
    assert image_x.get_bits_per_component() == 8
    assert image_x.get_soft_mask() is None

    body = _decoded_body(image_x)
    assert len(body) == 2 * 2 * 3
    assert body[0:3] == b"\x0a\x14\x1e"
    assert body[-3:] == b"\xc8\x64\x32"


# ---------- RGBA ----------


def test_create_from_rgba_image_splits_alpha_into_smask() -> None:
    document = PDDocument()
    src = Image.new("RGBA", (2, 2), color=(0, 0, 0, 0))
    src.putpixel((0, 0), (10, 20, 30, 90))
    src.putpixel((1, 1), (50, 60, 70, 250))

    image_x = LosslessFactory.create_from_image(document, src)
    cs = image_x.get_color_space_cos_object()
    assert isinstance(cs, COSName) and cs.name == "DeviceRGB"
    assert image_x.get_bits_per_component() == 8

    smask = image_x.get_soft_mask()
    assert smask is not None
    assert smask.get_width() == 2
    assert smask.get_height() == 2
    assert smask.get_bits_per_component() == 8

    body = _decoded_body(image_x)
    smask_body = _decoded_body(smask)
    # body has no alpha → 4 px * 3 bytes
    assert len(body) == 12
    assert body[0:3] == b"\x0a\x14\x1e"
    assert body[-3:] == b"\x32\x3c\x46"
    # alpha lives in smask
    assert len(smask_body) == 4
    assert smask_body[0] == 90
    assert smask_body[-1] == 250


# ---------- indexed ----------


def test_create_from_p_image_indexed_colorspace() -> None:
    document = PDDocument()
    # Build a tiny palette image with three colors.
    src = Image.new("P", (3, 1), color=0)
    palette = [10, 20, 30, 40, 50, 60, 70, 80, 90] + [0] * (256 * 3 - 9)
    src.putpalette(palette)
    src.putpixel((0, 0), 0)
    src.putpixel((1, 0), 1)
    src.putpixel((2, 0), 2)

    image_x = LosslessFactory.create_from_image(document, src)
    cs = image_x.get_color_space_cos_object()
    assert isinstance(cs, COSArray)
    assert len(cs) == 4
    name0 = cs.get_object(0)
    name1 = cs.get_object(1)
    hival = cs.get_int(2, -1)
    lookup = cs.get_object(3)
    assert isinstance(name0, COSName) and name0.name == "Indexed"
    assert isinstance(name1, COSName) and name1.name == "DeviceRGB"
    assert hival == 2  # max index used
    assert isinstance(lookup, COSString)
    assert lookup.get_bytes() == bytes([10, 20, 30, 40, 50, 60, 70, 80, 90])
    assert image_x.get_bits_per_component() == 8

    body = _decoded_body(image_x)
    assert body == b"\x00\x01\x02"


def test_create_from_p_image_with_single_index_transparency() -> None:
    document = PDDocument()
    src = Image.new("P", (3, 1), color=0)
    src.putpalette([10, 20, 30, 40, 50, 60] + [0] * (256 * 3 - 6))
    src.putpixel((0, 0), 0)
    src.putpixel((1, 0), 1)
    src.putpixel((2, 0), 0)
    src.info["transparency"] = 0

    image_x = LosslessFactory.create_from_image(document, src)
    smask = image_x.get_soft_mask()
    assert smask is not None
    assert smask.get_bits_per_component() == 1
    assert smask.get_width() == 3
    assert smask.get_height() == 1
    smask_body = _decoded_body(smask)
    # 3 px → 1 byte. Pixel 0=transparent, 1=opaque, 2=transparent.
    # Mask: bit i set when opaque; only bit 1 (mid pixel) is set → 0b0100_0000.
    assert smask_body == bytes([0b0100_0000])


# ---------- fallback / convert ----------


def test_create_from_cmyk_image_converts_to_rgb() -> None:
    document = PDDocument()
    src = Image.new("CMYK", (2, 1), color=(255, 0, 0, 0))

    image_x = LosslessFactory.create_from_image(document, src)
    cs = image_x.get_color_space_cos_object()
    # Falls into the "convert to RGB" path.
    assert isinstance(cs, COSName) and cs.name == "DeviceRGB"
    assert image_x.get_bits_per_component() == 8
    body = _decoded_body(image_x)
    assert len(body) == 2 * 1 * 3
