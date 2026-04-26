from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary
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


def test_jpx_decode_empty_input_returns_no_bytes() -> None:
    out = io.BytesIO()
    result = JPXDecode().decode(io.BytesIO(b""), out)
    assert result.bytes_written == 0
    assert out.getvalue() == b""


def test_jpx_decode_invalid_input_raises_oserror() -> None:
    with pytest.raises(OSError, match="OpenJPEG decode failed"):
        JPXDecode().decode(io.BytesIO(b"not a jp2 stream"), io.BytesIO())


def test_jpx_encode_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="decode-only"):
        JPXDecode().encode(io.BytesIO(b""), io.BytesIO(), COSDictionary())
