"""Hand-written tests for :class:`JPEGFactory`.

Covers the API surface as exercised in pypdfbox: the three factory
methods, the ``/Filter /DCTDecode`` + raw-bytes contract, color-space
dispatch by component count, and the CMYK ``/Decode`` array.
"""
from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel.graphics.image import JPEGFactory, PDImageXObject


def _rgb_jpeg_bytes(size: tuple[int, int] = (32, 32), quality: int = 80) -> bytes:
    """Build an in-memory RGB JPEG via Pillow."""
    img = Image.new("RGB", size, color=(120, 80, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _gray_jpeg_bytes(size: tuple[int, int] = (16, 24)) -> bytes:
    img = Image.new("L", size, color=128)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _cmyk_jpeg_bytes(size: tuple[int, int] = (8, 8)) -> bytes:
    img = Image.new("CMYK", size, color=(10, 20, 30, 40))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# create_from_byte_array
# ---------------------------------------------------------------------------


def test_create_from_byte_array_rgb_metadata():
    """RGB JPEG → /DeviceRGB, /Width=32, /Height=32, BPC=8, /Filter=DCTDecode."""
    data = _rgb_jpeg_bytes((32, 32))
    image = JPEGFactory.create_from_byte_array(None, data)

    assert isinstance(image, PDImageXObject)
    assert image.get_width() == 32
    assert image.get_height() == 32
    assert image.get_bits_per_component() == 8

    cs = image.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceRGB"

    filt = image.get_filter()
    assert isinstance(filt, COSName)
    assert filt.name == "DCTDecode"


def test_create_from_byte_array_round_trips_bytes():
    """The raw JPEG bytes must round-trip verbatim — DCTDecode-encoded
    streams keep the source bytes as the on-disk body."""
    data = _rgb_jpeg_bytes((48, 48))
    image = JPEGFactory.create_from_byte_array(None, data)

    cos = image.get_cos_object()
    assert isinstance(cos, COSStream)
    assert cos.get_raw_data() == data


def test_create_from_byte_array_subtype_image():
    """/Subtype must be /Image so the XObject is recognised as an image."""
    data = _rgb_jpeg_bytes()
    image = JPEGFactory.create_from_byte_array(None, data)
    cos = image.get_cos_object()
    subtype = cos.get_dictionary_object(COSName.SUBTYPE)  # type: ignore[attr-defined]
    assert subtype is not None
    assert isinstance(subtype, COSName)
    assert subtype.name == "Image"


def test_create_from_byte_array_gray():
    """1-component JPEG → /DeviceGray."""
    data = _gray_jpeg_bytes((16, 24))
    image = JPEGFactory.create_from_byte_array(None, data)
    assert image.get_width() == 16
    assert image.get_height() == 24
    cs = image.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceGray"


def test_create_from_byte_array_cmyk_decode_array():
    """4-component JPEG → /DeviceCMYK plus the inverted /Decode array."""
    data = _cmyk_jpeg_bytes((8, 8))
    image = JPEGFactory.create_from_byte_array(None, data)
    cs = image.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceCMYK"

    decode = image.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Decode")
    )
    assert isinstance(decode, COSArray)
    # Upstream emits [1 0 1 0 1 0 1 0] for CMYK JPEGs.
    assert decode.to_float_array() == [1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0]


def test_create_from_byte_array_rejects_non_bytes():
    with pytest.raises(TypeError):
        JPEGFactory.create_from_byte_array(None, "not bytes")  # type: ignore[arg-type]


def test_create_from_byte_array_rejects_non_jpeg():
    """A PNG payload must be rejected — JPEGFactory only consumes JPEG."""
    img = Image.new("RGB", (4, 4), color=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    with pytest.raises(ValueError):
        JPEGFactory.create_from_byte_array(None, buf.getvalue())


# ---------------------------------------------------------------------------
# create_from_stream
# ---------------------------------------------------------------------------


def test_create_from_stream_reads_to_eof():
    """create_from_stream must consume the whole stream, mirroring upstream."""
    data = _rgb_jpeg_bytes((20, 30))
    image = JPEGFactory.create_from_stream(None, io.BytesIO(data))
    assert image.get_width() == 20
    assert image.get_height() == 30
    assert image.get_cos_object().get_raw_data() == data


def test_create_from_stream_accepts_bytes():
    """Bytes-like inputs are tolerated for caller convenience."""
    data = _rgb_jpeg_bytes()
    image = JPEGFactory.create_from_stream(None, data)
    assert image.get_width() == 32
    assert image.get_height() == 32


# ---------------------------------------------------------------------------
# create_from_image
# ---------------------------------------------------------------------------


def test_create_from_image_rgb():
    """Encoding a PIL RGB image yields a /DeviceRGB DCT image."""
    img = Image.new("RGB", (40, 50), color=(255, 0, 0))
    image = JPEGFactory.create_from_image(None, img)
    assert image.get_width() == 40
    assert image.get_height() == 50
    cs = image.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceRGB"
    # The encoded body should start with the JPEG SOI marker.
    raw = image.get_cos_object().get_raw_data()
    assert raw.startswith(b"\xff\xd8\xff")


def test_create_from_image_gray():
    img = Image.new("L", (12, 18), color=64)
    image = JPEGFactory.create_from_image(None, img)
    cs = image.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceGray"
    assert image.get_width() == 12
    assert image.get_height() == 18


def _assert_dct_gray_smask(image, width: int, height: int) -> None:
    smask = image.get_soft_mask()
    assert smask is not None
    assert smask.get_width() == width
    assert smask.get_height() == height
    assert smask.get_bits_per_component() == 8
    cs = smask.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceGray"
    filt = smask.get_filter()
    assert isinstance(filt, COSName)
    assert filt.name == "DCTDecode"


def _rgba_gradient(width: int, height: int) -> Image.Image:
    image = Image.new("RGBA", (width, height), color=(50, 100, 150, 255))
    pixels = image.load()
    assert pixels is not None
    for y in range(height):
        for x in range(width):
            alpha = round(255 * ((y * width) + x) / ((width * height) - 1))
            pixels[x, y] = (50, 100, 150, alpha)
    return image


def _la_gradient(width: int, height: int) -> Image.Image:
    image = Image.new("LA", (width, height), color=(80, 255))
    pixels = image.load()
    assert pixels is not None
    for y in range(height):
        for x in range(width):
            alpha = round(255 * ((y * width) + x) / ((width * height) - 1))
            pixels[x, y] = (80, alpha)
    return image


def _pa_gradient(width: int, height: int) -> Image.Image:
    image = Image.new("PA", (width, height))
    image.putpalette([50, 100, 150, 150, 100, 50] * 128)
    pixels = image.load()
    assert pixels is not None
    for y in range(height):
        for x in range(width):
            alpha = round(255 * ((y * width) + x) / ((width * height) - 1))
            pixels[x, y] = ((x + y) % 2, alpha)
    return image


def _p_transparency_gradient(width: int, height: int) -> Image.Image:
    image = Image.new("P", (width, height))
    palette: list[int] = []
    for i in range(256):
        palette.extend((i, 255 - i, (i * 3) % 256))
    image.putpalette(palette)
    pixels = image.load()
    assert pixels is not None
    for y in range(height):
        for x in range(width):
            pixels[x, y] = ((y * width) + x) % 256
    image.info["transparency"] = bytes(range(256))
    return image


def test_create_from_image_rgba_extracts_alpha_smask():
    """RGBA inputs become RGB JPEGs with a grayscale JPEG /SMask."""
    img = _rgba_gradient(16, 16)
    image = JPEGFactory.create_from_image(None, img)
    cs = image.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceRGB"
    _assert_dct_gray_smask(image, 16, 16)
    smask = image.get_soft_mask()
    assert smask is not None
    mask_image = smask.to_pil_image()
    assert mask_image is not None
    lo, hi = mask_image.convert("L").getextrema()
    assert lo < hi


def test_create_from_image_la_extracts_gray_alpha_smask():
    img = _la_gradient(16, 16)
    image = JPEGFactory.create_from_image(None, img)

    cs = image.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceGray"
    _assert_dct_gray_smask(image, 16, 16)
    smask = image.get_soft_mask()
    assert smask is not None
    mask_image = smask.to_pil_image()
    assert mask_image is not None
    lo, hi = mask_image.convert("L").getextrema()
    assert lo < hi


def test_create_from_image_pa_extracts_palette_alpha_smask():
    img = _pa_gradient(16, 16)
    image = JPEGFactory.create_from_image(None, img)

    cs = image.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceRGB"
    _assert_dct_gray_smask(image, 16, 16)
    smask = image.get_soft_mask()
    assert smask is not None
    mask_image = smask.to_pil_image()
    assert mask_image is not None
    lo, hi = mask_image.convert("L").getextrema()
    assert lo < hi


def test_create_from_image_p_transparency_extracts_alpha_smask():
    img = _p_transparency_gradient(16, 16)
    image = JPEGFactory.create_from_image(None, img)

    cs = image.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceRGB"
    _assert_dct_gray_smask(image, 16, 16)
    smask = image.get_soft_mask()
    assert smask is not None
    mask_image = smask.to_pil_image()
    assert mask_image is not None
    lo, hi = mask_image.convert("L").getextrema()
    assert lo < hi


def test_create_from_image_rgb_has_no_soft_mask():
    img = Image.new("RGB", (8, 8), color=(50, 100, 150))
    image = JPEGFactory.create_from_image(None, img)
    assert image.get_soft_mask() is None


def test_create_from_image_quality_clamped():
    """Quality outside [0, 1] is clamped, not rejected."""
    img = Image.new("RGB", (8, 8), color=(0, 255, 0))
    # Both extremes round-trip without raising.
    JPEGFactory.create_from_image(None, img, quality=-1.0)
    JPEGFactory.create_from_image(None, img, quality=2.0)


def test_create_from_image_rejects_non_image():
    with pytest.raises(TypeError):
        JPEGFactory.create_from_image(None, b"not an image")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# class shape
# ---------------------------------------------------------------------------


def test_jpeg_factory_is_static_only():
    """Upstream JPEGFactory has a private no-arg constructor — instantiation
    is forbidden. The Python port enforces the same by raising in __init__."""
    with pytest.raises(TypeError):
        JPEGFactory()


# ---------------------------------------------------------------------------
# snake_case helpers ported from upstream package-private statics
# ---------------------------------------------------------------------------


def test_retrieve_dimensions_returns_width_height_components():
    """retrieve_dimensions sniffs (w, h, n) from the encoded JPEG header,
    matching upstream JPEGFactory.retrieveDimensions."""
    data = _rgb_jpeg_bytes((40, 25))
    width, height, num_components = JPEGFactory.retrieve_dimensions(data)
    assert (width, height, num_components) == (40, 25, 3)


def test_retrieve_dimensions_accepts_stream():
    """The helper accepts a file-like object as well as raw bytes."""
    data = _gray_jpeg_bytes((12, 10))
    width, height, num_components = JPEGFactory.retrieve_dimensions(io.BytesIO(data))
    assert (width, height, num_components) == (12, 10, 1)


def test_retrieve_dimensions_rejects_non_jpeg():
    img = Image.new("RGB", (4, 4), color=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    with pytest.raises(ValueError):
        JPEGFactory.retrieve_dimensions(buf.getvalue())


def test_get_num_components_from_image_metadata_modes():
    """The helper returns 1/3/4 for L/RGB/CMYK and 0 for unknown modes
    so the caller can fall back, matching upstream contract."""
    assert JPEGFactory.get_num_components_from_image_metadata(Image.new("L", (2, 2))) == 1
    assert JPEGFactory.get_num_components_from_image_metadata(Image.new("RGB", (2, 2))) == 3
    assert JPEGFactory.get_num_components_from_image_metadata(Image.new("CMYK", (2, 2))) == 4
    assert JPEGFactory.get_num_components_from_image_metadata(Image.new("P", (2, 2))) == 0


def test_get_alpha_image_returns_alpha_only_when_present():
    rgba = Image.new("RGBA", (3, 3), color=(10, 20, 30, 200))
    alpha = JPEGFactory.get_alpha_image(rgba)
    assert alpha is not None
    assert alpha.mode == "L"
    assert JPEGFactory.get_alpha_image(Image.new("RGB", (3, 3))) is None


def test_get_color_image_strips_alpha():
    rgba = Image.new("RGBA", (4, 4), color=(50, 60, 70, 128))
    rgb = JPEGFactory.get_color_image(rgba)
    assert rgb.mode == "RGB"
    # Already-RGB images pass through unmodified, mirroring upstream's
    # short-circuit when there's no alpha.
    plain = Image.new("RGB", (4, 4))
    assert JPEGFactory.get_color_image(plain) is plain


def test_get_color_space_from_awt_dispatch():
    """Mode-driven dispatch matches PRD: L → DeviceGray, RGB → DeviceRGB,
    CMYK → DeviceCMYK."""
    from pypdfbox.pdmodel.graphics.color import (
        PDDeviceCMYK,
        PDDeviceGray,
        PDDeviceRGB,
    )

    assert (
        JPEGFactory.get_color_space_from_awt(Image.new("L", (2, 2)))
        is PDDeviceGray.INSTANCE
    )
    assert (
        JPEGFactory.get_color_space_from_awt(Image.new("RGB", (2, 2)))
        is PDDeviceRGB.INSTANCE
    )
    assert (
        JPEGFactory.get_color_space_from_awt(Image.new("CMYK", (2, 2)))
        is PDDeviceCMYK.INSTANCE
    )
    with pytest.raises(NotImplementedError):
        JPEGFactory.get_color_space_from_awt(Image.new("HSV", (2, 2)))


def test_get_jpeg_image_writer_returns_non_none():
    """Upstream's contract is 'never returns null'; we mirror it."""
    assert JPEGFactory.get_jpeg_image_writer() is not None


def test_encode_image_to_jpeg_stream_yields_jpeg_bytes():
    img = Image.new("RGB", (24, 16), color=(100, 50, 200))
    encoded = JPEGFactory.encode_image_to_jpeg_stream(img, 0.8, 96)
    assert encoded.startswith(b"\xff\xd8\xff")
    width, height, num_components = JPEGFactory.retrieve_dimensions(encoded)
    assert (width, height, num_components) == (24, 16, 3)


def test_create_jpeg_threads_through_helpers():
    """create_jpeg is the workhorse that all create_from_image overloads
    chain into; verify it produces a /DCTDecode XObject end-to-end."""
    img = Image.new("RGB", (20, 20), color=(0, 200, 0))
    ximage = JPEGFactory.create_jpeg(None, img, 0.75, 72)
    assert ximage.get_width() == 20
    assert ximage.get_height() == 20
    cs = ximage.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceRGB"
