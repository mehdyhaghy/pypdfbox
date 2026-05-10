"""Hand-written tests for :class:`LosslessFactory`.

Covers the per-mode dispatch documented in the class docstring: 1-bit,
8-bit grayscale, 16-bit grayscale, RGB, RGBA, LA, and indexed/palette
(both with and without transparency). Each test generates a small PIL
source image, runs it through ``LosslessFactory.create_from_image``,
and asserts the resulting :class:`PDImageXObject` has the expected
metadata and a flate-encoded body that round-trips.
"""
from __future__ import annotations

import io
import zlib

from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream, COSString
from pypdfbox.filter import CCITTFaxDecode
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


def _is_ccitt_filter(image_x: PDImageXObject) -> bool:
    f = image_x.get_filter()
    return isinstance(f, COSName) and f.name == "CCITTFaxDecode"


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
    # 13 px wide forces row padding (not multiple of 8). 13×4 = 52
    # pixels, well below the CCITT threshold so this stays on flate.
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


def test_create_from_one_bit_large_image_uses_ccitt() -> None:
    """1-bit images at or above the CCITT pixel threshold use Group 4
    instead of flate. The /DecodeParms must declare K=-1 plus the real
    columns/rows, and the body must round-trip through the matching
    /CCITTFaxDecode decoder."""
    document = PDDocument()
    # 128×128 = 16384 px > 4096 threshold.
    src = Image.new("1", (128, 128), color=1)
    # Sparse pattern → highly compressible.
    for x in range(128):
        src.putpixel((x, x), 0)

    image_x = LosslessFactory.create_from_image(document, src)
    assert image_x.get_width() == 128
    assert image_x.get_height() == 128
    assert image_x.get_bits_per_component() == 1
    cs = image_x.get_color_space_cos_object()
    assert isinstance(cs, COSName) and cs.name == "DeviceGray"
    assert _is_ccitt_filter(image_x)

    cos = image_x.get_cos_object()
    assert isinstance(cos, COSStream)
    decode_parms = cos.get_dictionary_object("DecodeParms")
    assert isinstance(decode_parms, COSDictionary)
    assert decode_parms.get_int("K", 0) == -1
    assert decode_parms.get_int("Columns", 0) == 128
    assert decode_parms.get_int("Rows", 0) == 128

    # Round-trip the encoded body through CCITTFaxDecode.decode and
    # confirm we recover the original packed bitstream.
    raw = cos.get_raw_data()
    out = io.BytesIO()
    CCITTFaxDecode().decode(io.BytesIO(raw), out, cos)
    assert out.getvalue() == src.tobytes()


def test_create_from_one_bit_large_image_emits_compact_stream() -> None:
    """G4 emits a compact stream: a 200×200 mostly-white bitmap with a
    diagonal line should compress to a fraction of the raw size. This
    pins the heuristic's payoff without micro-comparing G4 vs flate
    (flate occasionally wins on uniform bitmaps; G4's value is on
    text/line-art content)."""
    document = PDDocument()
    src = Image.new("1", (200, 200), color=1)
    for x in range(200):
        src.putpixel((x, x), 0)

    image_x = LosslessFactory.create_from_image(document, src)
    assert _is_ccitt_filter(image_x)
    cos = image_x.get_cos_object()
    assert isinstance(cos, COSStream)
    raw = src.tobytes()  # 200/8 * 200 = 5000 bytes
    encoded_size = len(cos.get_raw_data())
    # G4 should compress this comfortably under 25% of the raw size.
    assert encoded_size < len(raw) // 4


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


def test_create_from_i16_little_endian_image() -> None:
    document = PDDocument()
    src = Image.new("I;16L", (2, 1), color=0)
    src.putpixel((0, 0), 0x1234)
    src.putpixel((1, 0), 0xABCD)

    image_x = LosslessFactory.create_from_image(document, src)

    assert image_x.get_bits_per_component() == 16
    body = _decoded_body(image_x)
    assert body == b"\x12\x34\xab\xcd"


def test_create_from_i16_big_endian_image_preserves_pdf_order() -> None:
    document = PDDocument()
    src = Image.new("I;16B", (2, 1), color=0)
    src.putpixel((0, 0), 0x1234)
    src.putpixel((1, 0), 0xABCD)

    image_x = LosslessFactory.create_from_image(document, src)

    assert image_x.get_bits_per_component() == 16
    body = _decoded_body(image_x)
    assert body == b"\x12\x34\xab\xcd"


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


# ---------- helper-level entry points (mirror upstream private helpers) ----------


def test_is_gray_image_returns_true_for_l_and_one_bit() -> None:
    """Mirrors upstream ``LosslessFactory.isGrayImage`` (Java line 118):
    8-bit gray and 1-bit gray sources qualify."""
    assert LosslessFactory.is_gray_image(Image.new("L", (2, 2)))
    assert LosslessFactory.is_gray_image(Image.new("1", (2, 2)))


def test_is_gray_image_returns_false_for_color_or_alpha_modes() -> None:
    """Modes carrying chroma or alpha do not qualify."""
    assert not LosslessFactory.is_gray_image(Image.new("RGB", (2, 2)))
    assert not LosslessFactory.is_gray_image(Image.new("RGBA", (2, 2)))
    assert not LosslessFactory.is_gray_image(Image.new("LA", (2, 2)))
    assert not LosslessFactory.is_gray_image(Image.new("P", (2, 2)))
    assert not LosslessFactory.is_gray_image(Image.new("CMYK", (2, 2)))


def test_is_gray_image_returns_false_for_non_pil_input() -> None:
    """Defensive: non-PIL arguments return ``False`` rather than raising,
    mirroring upstream's null-safe guard pattern."""
    assert not LosslessFactory.is_gray_image(b"not an image")  # type: ignore[arg-type]


def test_create_from_gray_image_l_mode() -> None:
    """``create_from_gray_image`` on an 8-bit ``L`` source produces 8 BPC
    DeviceGray with the body matching the raw pixel bytes."""
    document = PDDocument()
    src = Image.new("L", (3, 2), color=0)
    src.putpixel((0, 0), 42)
    src.putpixel((2, 1), 211)

    image_x = LosslessFactory.create_from_gray_image(src, document)
    assert image_x.get_width() == 3
    assert image_x.get_height() == 2
    assert image_x.get_bits_per_component() == 8
    cs = image_x.get_color_space_cos_object()
    assert isinstance(cs, COSName) and cs.name == "DeviceGray"
    body = _decoded_body(image_x)
    assert body[0] == 42
    assert body[-1] == 211


def test_create_from_gray_image_one_bit_mode() -> None:
    """``create_from_gray_image`` on a ``"1"`` source produces 1 BPC
    DeviceGray with row-padded bit packing (matches upstream's
    ``TYPE_BYTE_BINARY`` path)."""
    document = PDDocument()
    src = Image.new("1", (5, 2), color=0)
    src.putpixel((0, 0), 1)

    image_x = LosslessFactory.create_from_gray_image(src, document)
    assert image_x.get_bits_per_component() == 1
    cs = image_x.get_color_space_cos_object()
    assert isinstance(cs, COSName) and cs.name == "DeviceGray"
    body = _decoded_body(image_x)
    # 5 px → 1 byte/row, 2 rows. First bit set, rest zero.
    assert len(body) == 2
    assert body[0] == 0b1000_0000


def test_create_from_gray_image_rejects_non_gray_modes() -> None:
    """Mirrors upstream's "this should only be called for grayscale"
    contract: callers handing in a chroma mode get a ``ValueError``."""
    document = PDDocument()
    try:
        LosslessFactory.create_from_gray_image(Image.new("RGB", (2, 2)), document)
    except ValueError:
        return
    raise AssertionError("create_from_gray_image should reject 'RGB'")


def test_create_from_gray_image_rejects_non_pil_input() -> None:
    document = PDDocument()
    try:
        LosslessFactory.create_from_gray_image(b"nope", document)  # type: ignore[arg-type]
    except TypeError:
        return
    raise AssertionError("create_from_gray_image should reject non-PIL input")


def test_create_from_rgb_image_opaque_rgb() -> None:
    """``create_from_rgb_image`` on opaque RGB → DeviceRGB 8 BPC."""
    document = PDDocument()
    src = Image.new("RGB", (2, 1), color=(0, 0, 0))
    src.putpixel((0, 0), (10, 20, 30))
    src.putpixel((1, 0), (40, 50, 60))

    image_x = LosslessFactory.create_from_rgb_image(src, document)
    cs = image_x.get_color_space_cos_object()
    assert isinstance(cs, COSName) and cs.name == "DeviceRGB"
    assert image_x.get_bits_per_component() == 8
    assert image_x.get_soft_mask() is None
    body = _decoded_body(image_x)
    assert body == bytes([10, 20, 30, 40, 50, 60])


def test_create_from_rgb_image_rgba_attaches_smask() -> None:
    """``create_from_rgb_image`` on RGBA splits alpha into an SMask, the
    same shape upstream's ``TYPE_INT_ARGB`` path produces."""
    document = PDDocument()
    src = Image.new("RGBA", (2, 1), color=(0, 0, 0, 0))
    src.putpixel((0, 0), (10, 20, 30, 90))
    src.putpixel((1, 0), (40, 50, 60, 250))

    image_x = LosslessFactory.create_from_rgb_image(src, document)
    cs = image_x.get_color_space_cos_object()
    assert isinstance(cs, COSName) and cs.name == "DeviceRGB"
    smask = image_x.get_soft_mask()
    assert smask is not None
    assert smask.get_bits_per_component() == 8
    smask_body = _decoded_body(smask)
    assert smask_body == bytes([90, 250])


def test_create_from_rgb_image_converts_unknown_modes() -> None:
    """Unknown source modes (e.g. ``CMYK``) fall through to RGB
    conversion, the same fallback upstream documents."""
    document = PDDocument()
    src = Image.new("CMYK", (2, 1), color=(255, 0, 0, 0))

    image_x = LosslessFactory.create_from_rgb_image(src, document)
    cs = image_x.get_color_space_cos_object()
    assert isinstance(cs, COSName) and cs.name == "DeviceRGB"
    assert image_x.get_bits_per_component() == 8


def test_create_from_rgb_image_rejects_non_pil_input() -> None:
    document = PDDocument()
    try:
        LosslessFactory.create_from_rgb_image(b"nope", document)  # type: ignore[arg-type]
    except TypeError:
        return
    raise AssertionError("create_from_rgb_image should reject non-PIL input")


def test_prepare_image_x_object_with_pd_color_space() -> None:
    """``prepare_image_x_object`` mirrors upstream's package-private
    helper: takes raw bytes, encodes via flate, and stamps the standard
    image-XObject dictionary entries. Accepts a :class:`PDColorSpace`
    just like the Java signature."""
    from pypdfbox.pdmodel.graphics.color import PDDeviceGray

    document = PDDocument()
    raw = bytes(range(12))
    image_x = LosslessFactory.prepare_image_x_object(
        document, raw, 4, 3, 8, PDDeviceGray.INSTANCE
    )
    assert image_x.get_width() == 4
    assert image_x.get_height() == 3
    assert image_x.get_bits_per_component() == 8
    cs = image_x.get_color_space_cos_object()
    assert isinstance(cs, COSName) and cs.name == "DeviceGray"
    body = _decoded_body(image_x)
    assert body == raw


def test_prepare_image_x_object_with_cos_name_color_space() -> None:
    """The Python helper also accepts a raw COSName for callers that
    already hold the encoded color-space form."""
    document = PDDocument()
    raw = bytes(range(6))
    image_x = LosslessFactory.prepare_image_x_object(
        document, raw, 2, 1, 8, COSName.get_pdf_name("DeviceRGB")
    )
    cs = image_x.get_color_space_cos_object()
    assert isinstance(cs, COSName) and cs.name == "DeviceRGB"
    body = _decoded_body(image_x)
    assert body == raw
