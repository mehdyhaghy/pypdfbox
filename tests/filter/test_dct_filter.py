"""
Hand-written tests for the upstream-named :class:`DCTFilter` alias.

The full codec is exercised by ``test_dct_decode.py``; this module
verifies wiring and cross-instance interoperability.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.filter import DCTDecode, DCTFilter, FilterFactory
from pypdfbox.filter.dct_filter import DCTFilter as DirectDCTFilter


def _jpeg_bytes(mode: str, size: tuple[int, int], pixels: bytes) -> bytes:
    image = Image.frombytes(mode, size, pixels)
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=100, subsampling=0)
    return out.getvalue()


def test_dct_filter_is_dct_decode_subclass() -> None:
    assert issubclass(DCTFilter, DCTDecode)


def test_dct_filter_imports_from_package() -> None:
    assert DCTFilter is DirectDCTFilter


def test_factory_resolves_dct_filter_long_name() -> None:
    inst = FilterFactory.get("DCTFilter")
    assert isinstance(inst, DCTFilter)


def test_factory_resolves_dct_filter_via_cosname() -> None:
    inst = FilterFactory.get(COSName.get_pdf_name("DCTFilter"))
    assert isinstance(inst, DCTFilter)


def test_factory_dct_decode_unchanged() -> None:
    long_filter = FilterFactory.get("DCTDecode")
    short_filter = FilterFactory.get("DCT")
    assert isinstance(long_filter, DCTDecode)
    assert long_filter is short_filter


def test_factory_is_registered_dct_filter() -> None:
    assert FilterFactory.is_registered("DCTFilter")


def test_dct_filter_decode_surfaces_image_parameters() -> None:
    encoded = _jpeg_bytes("RGB", (1, 1), b"\x00\x00\x00")
    decoded = io.BytesIO()

    result = DCTFilter().decode(io.BytesIO(encoded), decoded, COSDictionary())

    assert decoded.getvalue() == b"\x00\x00\x00"
    assert result.bytes_written == 3
    assert result.parameters.get_int("Width") == 1
    assert result.parameters.get_int("Height") == 1
    assert result.parameters.get_int("BitsPerComponent") == 8
    assert result.parameters.get_int("ColorComponents") == 3


def test_dct_filter_encode_is_decode_only() -> None:
    with pytest.raises(NotImplementedError):
        DCTFilter().encode(io.BytesIO(b"raw"), io.BytesIO())
