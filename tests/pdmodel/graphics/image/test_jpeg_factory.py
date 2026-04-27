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


def test_create_from_image_rgba_flattens_alpha():
    """RGBA must flatten to RGB — JPEG cannot carry alpha. The current
    port drops the alpha channel rather than emitting an /SMask second
    XObject (see CHANGES.md soft-mask follow-up)."""
    img = Image.new("RGBA", (16, 16), color=(50, 100, 150, 200))
    image = JPEGFactory.create_from_image(None, img)
    cs = image.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceRGB"


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
