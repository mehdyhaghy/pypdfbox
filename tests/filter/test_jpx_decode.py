from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSFloat
from pypdfbox.filter import FilterFactory, JPXDecode


def _encode_jp2(image: Image.Image) -> bytes:
    """Encode ``image`` as a JPEG 2000 codestream (JP2 container)."""
    buf = io.BytesIO()
    image.save(buf, format="JPEG2000")
    return buf.getvalue()


def test_jpx_filter_registered_under_long_and_short_names() -> None:
    assert FilterFactory.is_registered("JPXDecode")
    assert FilterFactory.is_registered("JPX")
    assert isinstance(FilterFactory.get("JPXDecode"), JPXDecode)
    assert FilterFactory.get("JPX") is FilterFactory.get("JPXDecode")


def test_jpx_decode_rgb() -> None:
    src = Image.new("RGB", (8, 4), color=(200, 100, 50))
    encoded_bytes = _encode_jp2(src)

    out = io.BytesIO()
    result = JPXDecode().decode(io.BytesIO(encoded_bytes), out)

    assert result.bytes_written == 8 * 4 * 3
    assert out.getvalue() == src.tobytes()
    assert result.parameters.get_int("Width") == 8
    assert result.parameters.get_int("Height") == 4
    assert result.parameters.get_int("BitsPerComponent") == 8
    assert result.parameters.get_int("ColorComponents") == 3


def test_jpx_decode_grayscale() -> None:
    src = Image.new("L", (4, 4), color=128)
    encoded_bytes = _encode_jp2(src)

    out = io.BytesIO()
    result = JPXDecode().decode(io.BytesIO(encoded_bytes), out)

    assert result.bytes_written == 16
    assert result.parameters.get_int("ColorComponents") == 1
    assert result.parameters.get_int("BitsPerComponent") == 8


def test_wave317_jpx_decode_reports_endian_16_bit_grayscale_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Fake16BitJPXImage:
        mode = "I;16B"
        size = (2, 1)

        def __enter__(self) -> Fake16BitJPXImage:
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

        def load(self) -> None:
            return None

        def tobytes(self) -> bytes:
            return b"\x00\x01\xff\xff"

        def getbands(self) -> tuple[str, ...]:
            return ("I",)

    def fake_open(_stream: io.BytesIO) -> Fake16BitJPXImage:
        return Fake16BitJPXImage()

    monkeypatch.setattr("pypdfbox.filter.jpx_decode.Image.open", fake_open)

    out = io.BytesIO()
    result = JPXDecode().decode(io.BytesIO(b"fake-jp2"), out)

    assert out.getvalue() == b"\x00\x01\xff\xff"
    assert result.bytes_written == 4
    assert result.parameters.get_int("Width") == 2
    assert result.parameters.get_int("Height") == 1
    assert result.parameters.get_int("ColorComponents") == 1
    assert result.parameters.get_int("BitsPerComponent") == 16


def test_jpx_decode_empty_input_returns_no_bytes() -> None:
    out = io.BytesIO()
    result = JPXDecode().decode(io.BytesIO(b""), out)
    assert result.bytes_written == 0
    assert out.getvalue() == b""


def test_jpx_decode_invalid_input_raises_oserror() -> None:
    with pytest.raises(OSError, match="OpenJPEG decode failed"):
        JPXDecode().decode(io.BytesIO(b"not a jp2 stream"), io.BytesIO())


def test_jpx_encode_round_trips_rgb_raster() -> None:
    """Pillow's OpenJPEG-backed encoder produces a JP2 stream that the
    sibling :meth:`decode` recovers to the same component count and
    geometry. We do not assert pixel exactness because JPEG 2000 in its
    default Pillow mode is lossy.
    """
    width, height = 8, 4
    src = Image.new("RGB", (width, height), color=(123, 200, 50))
    raw = src.tobytes()

    params = COSDictionary()
    params.set_int("Width", width)
    params.set_int("Height", height)
    params.set_int("BitsPerComponent", 8)
    params.set_int("ColorComponents", 3)

    encoded_buf = io.BytesIO()
    JPXDecode().encode(io.BytesIO(raw), encoded_buf, params)
    encoded_bytes = encoded_buf.getvalue()
    assert len(encoded_bytes) > 0

    out = io.BytesIO()
    result = JPXDecode().decode(io.BytesIO(encoded_bytes), out)
    assert result.parameters.get_int("Width") == width
    assert result.parameters.get_int("Height") == height
    assert result.parameters.get_int("ColorComponents") == 3
    assert result.bytes_written == width * height * 3


def test_jpx_encode_requires_parameters() -> None:
    with pytest.raises(OSError, match="parameters are required"):
        JPXDecode().encode(io.BytesIO(b""), io.BytesIO(), None)


def test_jpx_encode_rejects_unsupported_bpc() -> None:
    params = COSDictionary()
    params.set_int("Width", 4)
    params.set_int("Height", 4)
    params.set_int("BitsPerComponent", 4)
    params.set_int("ColorComponents", 1)
    with pytest.raises(OSError, match="unsupported /BitsPerComponent"):
        JPXDecode().encode(io.BytesIO(b"\x00" * 8), io.BytesIO(), params)


def test_jpx_encode_grayscale_round_trip() -> None:
    width, height = 4, 4
    src = Image.new("L", (width, height), color=200)
    raw = src.tobytes()

    params = COSDictionary()
    params.set_int("Width", width)
    params.set_int("Height", height)
    params.set_int("BitsPerComponent", 8)
    params.set_int("ColorComponents", 1)

    encoded_buf = io.BytesIO()
    JPXDecode().encode(io.BytesIO(raw), encoded_buf, params)

    out = io.BytesIO()
    result = JPXDecode().decode(io.BytesIO(encoded_buf.getvalue()), out)
    assert result.parameters.get_int("Width") == width
    assert result.parameters.get_int("Height") == height
    assert result.parameters.get_int("ColorComponents") == 1


def test_jpx_decode_clears_decode_entry_when_not_image_mask() -> None:
    """Per ISO 32000-1 §8.9.5.1 Note 5 / upstream JPXFilter: the
    ``/Decode`` array is ignored for JPX-encoded images and must be
    stripped from the parameters so downstream colorspace handling
    doesn't double-apply the linear remap."""
    src = Image.new("RGB", (4, 4), color=(10, 20, 30))
    encoded_bytes = _encode_jp2(src)

    params = COSDictionary()

    decode_arr = COSArray()
    for _ in range(3):
        decode_arr.add(COSFloat(0.0))
        decode_arr.add(COSFloat(1.0))
    params.set_item("Decode", decode_arr)

    result = JPXDecode().decode(
        io.BytesIO(encoded_bytes), io.BytesIO(), params
    )

    assert result.parameters is not params
    assert "Decode" in params
    assert "Decode" not in result.parameters


def test_jpx_decode_returns_repaired_parameter_copy_without_mutating_input() -> None:
    src = Image.new("RGB", (4, 3), color=(10, 20, 30))
    encoded_bytes = _encode_jp2(src)

    params = COSDictionary()
    params.set_name("ColorSpace", "DeviceRGB")
    params.set_int("Width", 99)
    decode_arr = COSArray()
    for _ in range(3):
        decode_arr.add(COSFloat(0.0))
        decode_arr.add(COSFloat(1.0))
    params.set_item("Decode", decode_arr)

    result = JPXDecode().decode(io.BytesIO(encoded_bytes), io.BytesIO(), params)

    assert result.parameters is not params
    assert params.get_int("Width") == 99
    assert "Height" not in params
    assert "Decode" in params
    assert result.parameters.get_name("ColorSpace") == "DeviceRGB"
    assert result.parameters.get_int("Width") == 4
    assert result.parameters.get_int("Height") == 3
    assert result.parameters.get_int("BitsPerComponent") == 8
    assert result.parameters.get_int("ColorComponents") == 3
    assert "Decode" not in result.parameters


def test_jpx_decode_preserves_decode_entry_when_image_mask() -> None:
    """When ``/ImageMask`` is true, the ``/Decode`` array is meaningful
    and upstream preserves it."""
    src = Image.new("L", (4, 4), color=255)
    encoded_bytes = _encode_jp2(src)

    params = COSDictionary()

    params.set_boolean("ImageMask", True)
    decode_arr = COSArray()
    decode_arr.add(COSFloat(1.0))
    decode_arr.add(COSFloat(0.0))
    params.set_item("Decode", decode_arr)

    result = JPXDecode().decode(
        io.BytesIO(encoded_bytes), io.BytesIO(), params
    )

    assert result.parameters is not params
    assert "Decode" in params
    assert "Decode" in result.parameters
