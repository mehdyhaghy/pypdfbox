from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import DCTDecode, FilterFactory


def _jpeg_bytes(mode: str, size: tuple[int, int], pixels: bytes) -> bytes:
    image = Image.frombytes(mode, size, pixels)
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=100, subsampling=0)
    return out.getvalue()


def test_dct_decode_rgb_jpeg_surfaces_image_parameters() -> None:
    encoded = _jpeg_bytes("RGB", (1, 1), b"\x00\x00\x00")
    decoded = io.BytesIO()

    result = DCTDecode().decode(io.BytesIO(encoded), decoded)

    assert decoded.getvalue() == b"\x00\x00\x00"
    assert result.bytes_written == 3
    assert result.parameters.get_int("Width") == 1
    assert result.parameters.get_int("Height") == 1
    assert result.parameters.get_int("BitsPerComponent") == 8
    assert result.parameters.get_int("ColorComponents") == 3


def test_dct_decode_reuses_supplied_parameters() -> None:
    encoded = _jpeg_bytes("L", (1, 1), b"\x80")
    params = COSDictionary()

    result = DCTDecode().decode(io.BytesIO(encoded), io.BytesIO(), params)

    assert result.parameters is params
    assert params.get_int("Width") == 1
    assert params.get_int("Height") == 1
    assert params.get_int("BitsPerComponent") == 8
    assert params.get_int("ColorComponents") == 1


def test_filter_factory_resolves_dct_short_name_to_registered_filter() -> None:
    assert isinstance(FilterFactory.get_filter("DCTDecode"), DCTDecode)
    assert FilterFactory.get_filter_by_short_name("DCT") is FilterFactory.get_filter(
        "DCTDecode"
    )


def test_dct_encode_is_decode_only_with_jpegfactory_guidance() -> None:
    with pytest.raises(
        NotImplementedError,
        match="DCTFilter encoding not implemented, use the JPEGFactory methods instead",
    ):
        DCTDecode().encode(io.BytesIO(b"raw"), io.BytesIO())
