"""Ported upstream tests from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/image/PDInlineImageTest.java``.

Translated from JUnit 5 to pytest per CLAUDE.md §"Test Porting Conventions".

Skipped upstream tests (require rendering-cluster work):

- ``testInlineImage`` — the body is split: dictionary/COS metadata is
  ported as :func:`test_inline_image_metadata` and the new
  :func:`test_inline_image_stencil_image_dimensions` /
  :func:`test_inline_image_get_image_dimensions` cover the rendering
  surface. The ``ImageIO`` round-trip, ``PDPageContentStream.drawImage``
  and ``PDFRenderer.renderImage`` parts remain rendering-cluster work.
- ``testShortCCITT1`` / ``testShortCCITT2`` / ``testShortCCITT3`` — exercise
  ``getImage()`` returning a ``BufferedImage.TYPE_BYTE_GRAY`` raster,
  again rendering-cluster work. The CCITTFax filter itself is ported,
  but the inline-image to-raster pipeline is not.

Ported here are the malformed-``/D`` defensive accessor
(``testGetDecodeWithInvalidType``), the metadata half of
``testInlineImage`` and stencil-image / image-dimension parity
assertions exercisable today.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
)
from pypdfbox.pdmodel.graphics.image import PDInlineImage


def test_get_decode_with_invalid_type() -> None:
    # Test 1: /D set to integer (should return None, not raise)
    dict_ = COSDictionary()
    dict_.set_boolean(COSName.get_pdf_name("IM"), True)
    dict_.set_int(COSName.get_pdf_name("W"), 1)
    dict_.set_int(COSName.get_pdf_name("H"), 1)
    dict_.set_int(COSName.get_pdf_name("BPC"), 1)
    dict_.set_int(COSName.get_pdf_name("D"), 123)  # wrong type: integer

    data = b"\x00"
    inline_image = PDInlineImage(dict_, data, None)
    assert inline_image.get_decode() is None, (
        "get_decode() should return None for non-array /D value"
    )

    # Test 2: /D set to valid COSArray (still works)
    dict2 = COSDictionary()
    dict2.set_boolean(COSName.get_pdf_name("IM"), True)
    dict2.set_int(COSName.get_pdf_name("W"), 1)
    dict2.set_int(COSName.get_pdf_name("H"), 1)
    dict2.set_int(COSName.get_pdf_name("BPC"), 1)
    decode_array = COSArray()
    decode_array.add(COSInteger.ONE)
    decode_array.add(COSInteger.ZERO)
    dict2.set_item(COSName.get_pdf_name("D"), decode_array)

    inline_image2 = PDInlineImage(dict2, data, None)
    assert inline_image2.get_decode() is not None, (
        "get_decode() should return array for valid /D value"
    )
    assert inline_image2.get_decode().size() == 2

    # Test 3: /D not set (should return None)
    dict3 = COSDictionary()
    dict3.set_boolean(COSName.get_pdf_name("IM"), True)
    dict3.set_int(COSName.get_pdf_name("W"), 1)
    dict3.set_int(COSName.get_pdf_name("H"), 1)
    dict3.set_int(COSName.get_pdf_name("BPC"), 1)

    inline_image3 = PDInlineImage(dict3, data, None)
    assert inline_image3.get_decode() is None, (
        "get_decode() should return None when /D is not set"
    )


# Inline-image *metadata* parity from the body of upstream's testInlineImage —
# the BufferedImage / Paint / ImageIO assertions are skipped (see module
# docstring), but the dictionary-readback assertions are exercisable now.


def test_inline_image_metadata() -> None:
    dict_ = COSDictionary()
    dict_.set_boolean(COSName.get_pdf_name("IM"), True)
    width = 31
    height = 27
    dict_.set_int(COSName.get_pdf_name("W"), width)
    dict_.set_int(COSName.get_pdf_name("H"), height)
    dict_.set_int(COSName.get_pdf_name("BPC"), 1)

    rowbytes = width // 8
    if rowbytes * 8 < width:
        rowbytes += 1

    datalen = rowbytes * height
    data = bytearray(datalen)
    for i in range(datalen):
        data[i] = 0b10101010 if (i // 4 % 2 == 0) else 0

    inline_image1 = PDInlineImage(dict_, bytes(data), None)
    assert inline_image1.is_stencil()
    assert inline_image1.get_width() == width
    assert inline_image1.get_height() == height
    assert inline_image1.get_bits_per_component() == 1

    dict2 = COSDictionary()
    dict2.add_all(dict_)
    decode_array = COSArray()
    decode_array.add(COSInteger.ONE)
    decode_array.add(COSInteger.ZERO)
    dict2.set_item(COSName.get_pdf_name("Decode"), decode_array)

    inline_image2 = PDInlineImage(dict2, bytes(data), None)
    assert inline_image2.get_decode() is not None
    assert inline_image2.get_decode().size() == 2


def test_inline_image_get_stencil_image_requires_stencil() -> None:
    """Mirrors the upstream contract on ``getStencilImage(Paint)``: when
    the image is not a stencil, the call raises (Java throws
    ``IllegalStateException``; the Pythonic analogue is ``ValueError``)."""
    dict_ = COSDictionary()
    dict_.set_int(COSName.get_pdf_name("W"), 8)
    dict_.set_int(COSName.get_pdf_name("H"), 8)
    dict_.set_int(COSName.get_pdf_name("BPC"), 8)
    dict_.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("G"))
    img = PDInlineImage(dict_, b"\x00" * 64, None)
    with pytest.raises(ValueError, match="not a stencil"):
        img.get_stencil_image(None)


def test_inline_image_get_raw_raster_returns_decoded_bytes() -> None:
    """Mirrors upstream ``PDInlineImage#getRawRaster()`` (Java line 365).
    For inline images the decoded payload is already buffered, so the
    raw-raster surface aliases :meth:`get_data`."""
    payload = bytes(range(16))
    dict_ = COSDictionary()
    dict_.set_int(COSName.get_pdf_name("W"), 4)
    dict_.set_int(COSName.get_pdf_name("H"), 4)
    dict_.set_int(COSName.get_pdf_name("BPC"), 8)
    img = PDInlineImage(dict_, payload, None)
    assert img.get_raw_raster() == payload
    assert img.get_raw_raster() == img.get_data()


def test_inline_image_get_image_returns_none_for_stencil() -> None:
    """Stencil rasters are rendering-cluster work — ``get_image`` returns
    ``None`` rather than raising. Mirrors upstream ``PDInlineImage#getImage()``
    (Java line 353) when ``SampledImageReader`` is unable to produce a
    raster (for our subset that means stencil + 1-bit data)."""
    dict_ = COSDictionary()
    dict_.set_boolean(COSName.get_pdf_name("IM"), True)
    dict_.set_int(COSName.get_pdf_name("W"), 8)
    dict_.set_int(COSName.get_pdf_name("H"), 1)
    dict_.set_int(COSName.get_pdf_name("BPC"), 1)
    img = PDInlineImage(dict_, b"\xff", None)
    # Stencil rasters are rendering-cluster work; pypdfbox's PIL fallback
    # bails out (returns None) rather than producing an unfaithful raster.
    assert img.get_image() is None


def test_inline_image_get_raw_image_returns_none_when_not_decodable() -> None:
    """``get_raw_image`` mirrors :meth:`get_image` for the cases where
    PIL cannot decode the raster (stencil / non-8bpc / unsupported CS).
    Upstream returns the raw-CS image; pypdfbox's library-first path
    returns ``None`` until the rendering cluster lands."""
    dict_ = COSDictionary()
    dict_.set_boolean(COSName.get_pdf_name("IM"), True)
    dict_.set_int(COSName.get_pdf_name("W"), 8)
    dict_.set_int(COSName.get_pdf_name("H"), 1)
    dict_.set_int(COSName.get_pdf_name("BPC"), 1)
    img = PDInlineImage(dict_, b"\xff", None)
    assert img.get_raw_image() is None


def test_inline_image_to_long_name_expands_short_devices() -> None:
    """Mirrors ``PDInlineImage#toLongName`` (Java line 151): ``/G`` →
    ``/DeviceGray``, ``/RGB`` → ``/DeviceRGB``, ``/CMYK`` →
    ``/DeviceCMYK``; everything else passes through identity."""
    img = PDInlineImage(COSDictionary(), b"", None)
    g = COSName.get_pdf_name("G")
    rgb = COSName.get_pdf_name("RGB")
    cmyk = COSName.get_pdf_name("CMYK")
    other = COSName.get_pdf_name("Indexed")
    assert img.to_long_name(g) is COSName.get_pdf_name("DeviceGray")
    assert img.to_long_name(rgb) is COSName.get_pdf_name("DeviceRGB")
    assert img.to_long_name(cmyk) is COSName.get_pdf_name("DeviceCMYK")
    assert img.to_long_name(other) is other


def test_inline_image_create_color_space_resolves_short_name() -> None:
    """Public ``create_color_space`` accepts the raw inline ``/CS`` value
    (a short-form ``COSName`` here) and returns a resolved
    :class:`PDColorSpace`. Mirrors ``PDInlineImage#createColorSpace``
    (Java line 168)."""
    from pypdfbox.pdmodel.graphics.color import PDDeviceRGB

    img = PDInlineImage(COSDictionary(), b"", None)
    cs = img.create_color_space(COSName.get_pdf_name("RGB"))
    assert cs is PDDeviceRGB.INSTANCE
