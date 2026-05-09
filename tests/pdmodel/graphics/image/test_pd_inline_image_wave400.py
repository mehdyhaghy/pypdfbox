from __future__ import annotations

import zlib

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel.graphics.color import PDDeviceCMYK, PDDeviceRGB, PDIndexed
from pypdfbox.pdmodel.graphics.image import PDInlineImage


def _params(width: int = 1, height: int = 1, bpc: int = 8) -> COSDictionary:
    params = COSDictionary()
    params.set_int("W", width)
    params.set_int("H", height)
    params.set_int("BPC", bpc)
    return params


def _metadata_only_image(params: COSDictionary) -> PDInlineImage:
    image = PDInlineImage.__new__(PDInlineImage)
    image._parameters = params
    image._resources = None
    image._raw_data = b""
    image._decoded_data = b""
    return image


def test_wave400_color_space_long_form_and_cmyk_abbreviation_resolve() -> None:
    params = _params()
    params.set_item("ColorSpace", COSName.get_pdf_name("DeviceRGB"))
    assert PDInlineImage(params, b"\x00\x00\x00", None).get_color_space() is PDDeviceRGB.INSTANCE

    params = _params()
    params.set_item("CS", COSName.get_pdf_name("CMYK"))
    assert (
        PDInlineImage(params, b"\x00\x00\x00\x00", None).get_color_space()
        is PDDeviceCMYK.INSTANCE
    )


def test_wave400_indexed_inline_color_space_expands_short_names() -> None:
    indexed = COSArray()
    indexed.add(COSName.get_pdf_name("I"))
    indexed.add(COSName.get_pdf_name("RGB"))
    indexed.add(COSInteger.ZERO)
    indexed.add(COSString(b"\x01\x02\x03"))
    params = _params()
    params.set_item("CS", indexed)

    color_space = PDInlineImage(params, b"\x00", None).get_color_space()

    assert isinstance(color_space, PDIndexed)
    assert color_space.get_base_color_space() is PDDeviceRGB.INSTANCE


def test_wave400_illegal_inline_color_space_shapes_raise() -> None:
    params = _params()
    params.set_item("CS", COSName.get_pdf_name("UnresolvableCS"))
    with pytest.raises(OSError, match="unsupported inline image color space name"):
        PDInlineImage(params, b"\x00", None).get_color_space()

    params = _params()
    bad_array = COSArray()
    bad_array.add(COSInteger.ONE)
    bad_array.add(COSName.get_pdf_name("DeviceRGB"))
    params.set_item("CS", bad_array)
    with pytest.raises(OSError, match="Illegal type of inline image color space"):
        PDInlineImage(params, b"\x00", None).get_color_space()

    params = _params()
    params.set_item("CS", COSDictionary())
    with pytest.raises(OSError, match="Illegal type of object"):
        PDInlineImage(params, b"\x00", None).get_color_space()


def test_wave400_color_space_set_and_clear_use_short_keys() -> None:
    params = _params()
    params.set_item("ColorSpace", COSName.get_pdf_name("DeviceGray"))
    image = PDInlineImage(params, b"\x00", None)

    image.set_color_space(PDDeviceRGB.INSTANCE)
    assert params.get_name("CS") == "DeviceRGB"
    image.clear_color_space()

    assert image.get_color_space_cos_object() is None
    assert params.get_dictionary_object("CS") is None
    assert params.get_dictionary_object("ColorSpace") is None


def test_wave400_filter_accessors_ignore_non_name_array_items_and_clear() -> None:
    params = _params()
    filters = COSArray()
    filters.add(COSInteger.ONE)
    filters.add(COSName.get_pdf_name("FlateDecode"))
    params.set_item("Filter", filters)
    image = PDInlineImage(params, zlib.compress(b""), None)

    assert image.has_filters() is True
    assert image.get_filters() == ["FlateDecode"]

    image.set_filters(None)
    assert image.has_filters() is False
    assert image.get_filter_cos_object() is None

    image.set_filters(["FlateDecode"])
    assert image.get_filters() == ["FlateDecode"]
    image.clear_filters()
    assert image.get_filters() == []


def test_wave400_filter_array_with_no_names_reports_empty() -> None:
    params = _params()
    filters = COSArray()
    filters.add(COSInteger.ONE)
    params.set_item("F", filters)
    image = PDInlineImage(params, b"", None)

    assert image.has_filters() is False
    assert image.get_filters() == []


def test_wave400_decode_setters_and_invalid_float_helper() -> None:
    image = PDInlineImage(_params(), b"\x00", None)
    image.set_decode([0.0, 1.0])
    assert image.get_decode_as_floats() == [0.0, 1.0]

    custom = COSArray()
    custom.add(COSFloat(1.0))
    custom.add(COSName.get_pdf_name("bad"))
    image.set_decode(custom)
    assert image.get_decode() is custom
    assert image.get_decode_as_floats() is None

    image.set_decode(None)
    assert image.get_decode() is None


def test_wave400_image_mask_alias_sets_stencil_and_forces_bpc_one() -> None:
    image = PDInlineImage(_params(bpc=8), b"\x00", None)

    image.set_image_mask(True)

    assert image.is_image_mask() is True
    assert image.get_bits_per_component() == 1


def test_wave400_color_key_mask_converts_numbers_and_rejects_malformed_items() -> None:
    params = _params()
    mask = COSArray()
    mask.add(COSFloat(1.9))
    mask.add(COSInteger.get(7))
    params.set_item("Mask", mask)
    image = PDInlineImage(params, b"\x00", None)
    assert image.get_color_key_mask() == [1, 7]

    mask.add(COSName.get_pdf_name("bad"))
    assert image.get_color_key_mask() is None


def test_wave400_create_input_stream_accepts_cosname_stop_filters() -> None:
    raw = b"abc"
    params = _params(width=3)
    params.set_item("F", COSName.get_pdf_name("FlateDecode"))
    image = PDInlineImage(params, zlib.compress(raw), None)

    with image.create_input_stream(stop_filters=[COSName.get_pdf_name("FlateDecode")]) as stream:
        assert stream.read() == zlib.compress(raw)
    with image.create_input_stream(stop_filters=["OtherFilter"]) as stream:
        assert stream.read() == raw


def test_wave400_to_pil_image_early_outs_and_rgb_fallback() -> None:
    params = _params(width=0, height=1)
    assert PDInlineImage(params, b"", None).to_pil_image() is None

    params = _params(width=1, height=1, bpc=4)
    params.set_item("CS", COSName.get_pdf_name("RGB"))
    assert PDInlineImage(params, b"\x00\x00\x00", None).to_pil_image() is None

    fallback = PDInlineImage(_params(width=1, height=1), b"\x10\x20\x30", None).to_pil_image()
    assert fallback is not None
    assert fallback.getpixel((0, 0)) == (16, 32, 48)


def test_wave400_to_pil_image_returns_none_for_short_raw_data() -> None:
    params = _params(width=2, height=1)
    params.set_item("CS", COSName.get_pdf_name("RGB"))
    assert PDInlineImage(params, b"\x00\x01", None).to_pil_image() is None

    params = _params(width=2, height=1)
    params.set_item("CS", COSName.get_pdf_name("G"))
    assert PDInlineImage(params, b"\x00", None).to_pil_image() is None


def test_wave400_suffix_and_predicates_on_metadata_only_images() -> None:
    params = _params()
    params.set_item("F", COSName.get_pdf_name("CCITTFaxDecode"))
    image = _metadata_only_image(params)

    assert image.is_ccitt() is True
    assert image.is_jpeg() is False
    assert image.get_suffix() == "tiff"
