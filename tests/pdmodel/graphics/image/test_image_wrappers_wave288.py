from __future__ import annotations

import zlib

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.image import PDImageXObject, PDInlineImage


def _make_image_xobject() -> PDImageXObject:
    return PDImageXObject(COSStream())


def _basic_inline_dict() -> COSDictionary:
    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("W"), 1)
    params.set_int(COSName.get_pdf_name("H"), 1)
    params.set_int(COSName.get_pdf_name("BPC"), 8)
    return params


def test_image_xobject_decode_rejects_malformed_numeric_array() -> None:
    image = _make_image_xobject()
    decode = COSArray()
    decode.add(COSFloat(0.0))
    decode.add(COSString(b"not-a-number"))
    image.get_cos_object().set_item(COSName.get_pdf_name("Decode"), decode)

    assert image.get_decode_array() is decode
    assert image.get_decode() is None
    assert image.has_decode() is False


def test_image_xobject_matte_rejects_malformed_numeric_array() -> None:
    image = _make_image_xobject()
    matte = COSArray()
    matte.add(COSInteger.get(1))
    matte.add(COSString(b"not-a-number"))
    image.get_cos_object().set_item(COSName.get_pdf_name("Matte"), matte)

    assert image.get_matte_array() is matte
    assert image.get_matte() is None
    assert image.has_matte() is False


def test_image_xobject_clear_helpers_remove_optional_entries() -> None:
    image = _make_image_xobject()
    image.get_cos_object().set_item(
        COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceRGB")
    )
    image.set_color_key_mask([0, 255])
    image.set_soft_mask(_make_image_xobject())
    image.set_decode([0.0, 1.0])
    image.set_matte([0.0, 0.5, 1.0])

    image.clear_color_space()
    image.clear_mask()
    image.clear_soft_mask()
    image.clear_decode()
    image.clear_matte()

    assert image.has_color_space() is False
    assert image.has_mask() is False
    assert image.has_soft_mask() is False
    assert image.has_decode() is False
    assert image.has_matte() is False


def test_inline_image_clear_filters_removes_short_and_long_entries() -> None:
    params = _basic_inline_dict()
    params.set_item(COSName.get_pdf_name("Filter"), COSName.get_pdf_name("FlateDecode"))
    image = PDInlineImage(params, zlib.compress(b""), None)

    assert image.has_filters() is True
    image.clear_filters()

    assert image.get_filter_cos_object() is None
    assert image.get_filters() == []
    assert image.has_filters() is False


def test_inline_image_clear_decode_removes_short_and_long_entries() -> None:
    params = _basic_inline_dict()
    decode = COSArray()
    decode.add(COSInteger.get(0))
    decode.add(COSInteger.get(1))
    params.set_item(COSName.get_pdf_name("Decode"), decode)
    image = PDInlineImage(params, b"\x00", None)

    assert image.get_decode() is decode
    image.set_decode(None)

    assert image.get_decode() is None
    assert params.get_dictionary_object(COSName.get_pdf_name("D")) is None
    assert params.get_dictionary_object(COSName.get_pdf_name("Decode")) is None


def test_inline_image_decode_floats_rejects_malformed_numeric_array() -> None:
    params = _basic_inline_dict()
    decode = COSArray()
    decode.add(COSInteger.get(0))
    decode.add(COSString(b"not-a-number"))
    params.set_item(COSName.get_pdf_name("D"), decode)
    image = PDInlineImage(params, b"\x00", None)

    assert image.get_decode() is decode
    assert image.get_decode_as_floats() is None


def test_inline_image_clear_color_space_removes_short_and_long_entries() -> None:
    params = _basic_inline_dict()
    params.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    image = PDInlineImage(params, b"\x00\x00\x00", None)

    assert image.get_color_space_cos_object() is not None
    image.set_color_space(None)

    assert image.get_color_space_cos_object() is None
    assert params.get_dictionary_object(COSName.get_pdf_name("CS")) is None
    assert params.get_dictionary_object(COSName.get_pdf_name("ColorSpace")) is None
