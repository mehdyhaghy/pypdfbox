"""Ported upstream tests from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/image/PDInlineImageTest.java``.

Translated from JUnit 5 to pytest per CLAUDE.md §"Test Porting Conventions".

Skipped upstream tests (require rendering-cluster work):

- ``testInlineImage`` — relies on ``getStencilImage(Paint)``, ``getImage()``
  (BufferedImage construction via ``SampledImageReader``), ``ImageIO``
  round-trip, ``PDPageContentStream.drawImage`` and ``PDFRenderer``.
  These all depend on the rendering pipeline (Pillow-based renderer)
  which lands in a later cluster.
- ``testShortCCITT1`` / ``testShortCCITT2`` / ``testShortCCITT3`` — exercise
  ``getImage()`` returning a ``BufferedImage.TYPE_BYTE_GRAY`` raster,
  again rendering-cluster work. The CCITTFax filter itself is ported,
  but the inline-image to-raster pipeline is not.

Ported here is the malformed-``/D`` defensive accessor
(``testGetDecodeWithInvalidType``), which is purely metadata behaviour
and exercisable today.
"""
from __future__ import annotations

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
