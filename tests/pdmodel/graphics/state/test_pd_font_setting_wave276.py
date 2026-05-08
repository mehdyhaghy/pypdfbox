from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.graphics.state import PDFontSetting


def _type1_font_dict(base_font: str = "Helvetica") -> COSDictionary:
    font_dict = COSDictionary()
    font_dict.set_name("Type", "Font")
    font_dict.set_name("Subtype", "Type1")
    font_dict.set_name("BaseFont", base_font)
    return font_dict


def test_default_cos_array_round_trips_and_defaults_are_lenient() -> None:
    setting = PDFontSetting()

    arr = setting.get_cos_object()
    assert arr.size() == 2
    assert arr.get_object(0) is None
    assert isinstance(arr.get(0), COSNull)
    assert isinstance(arr.get_object(1), COSFloat)
    assert setting.get_font() is None
    assert setting.get_font_size() == 1.0


def test_wrapped_array_is_live_cos_array_round_trip() -> None:
    font_dict = _type1_font_dict("Times-Roman")
    arr = COSArray([font_dict, COSFloat(10.25)])

    setting = PDFontSetting(arr)
    assert setting.get_cos_object() is arr

    font = setting.get_font()
    assert isinstance(font, PDType1Font)
    assert font.get_cos_object() is font_dict
    assert setting.get_font_size() == 10.25

    arr.set(1, COSInteger.get(12))
    assert setting.get_font_size() == 12.0


def test_font_and_size_setters_write_slots_and_can_clear_font() -> None:
    setting = PDFontSetting(COSArray())
    raw_font = _type1_font_dict("Courier")

    setting.set_font(raw_font)
    setting.set_font_size(8)

    arr = setting.get_cos_object()
    assert arr.size() == 2
    assert arr.get_object(0) is raw_font
    assert setting.get_font_size() == 8.0
    assert isinstance(setting.get_font(), PDType1Font)

    setting.set_font(None)
    assert arr.get(0) is COSNull.NULL
    assert arr.get_object(0) is None
    assert setting.get_font() is None
    assert setting.get_font_size() == 8.0


def test_typed_font_setter_stores_underlying_cos_dictionary() -> None:
    font_dict = _type1_font_dict("Helvetica-Bold")
    font = PDType1Font(font_dict)
    setting = PDFontSetting()

    setting.set_font(font)

    assert setting.get_cos_object().get_object(0) is font_dict
    got = setting.get_font()
    assert got is not None
    assert got.get_cos_object() is font_dict


@pytest.mark.parametrize(
    ("arr", "font_size"),
    [
        (COSArray(), 0.0),
        (COSArray([COSName.get_pdf_name("F1")]), 0.0),
        (COSArray([COSNull.NULL, COSString("large")]), 0.0),
        (COSArray([COSString("not a font"), COSFloat(6.5)]), 6.5),
    ],
)
def test_malformed_shapes_are_lenient(arr: COSArray, font_size: float) -> None:
    setting = PDFontSetting(arr)

    assert setting.get_font() is None
    assert setting.get_font_size() == font_size


def test_constructor_rejects_non_array_cos_objects() -> None:
    with pytest.raises(TypeError, match="expects COSArray or None"):
        PDFontSetting(COSName.get_pdf_name("Font"))


def test_equality_and_hash_follow_backing_array_identity() -> None:
    arr = COSArray([COSNull.NULL, COSFloat(5)])
    same = PDFontSetting(arr)
    also_same = PDFontSetting(arr)
    distinct = PDFontSetting(COSArray([COSNull.NULL, COSFloat(5)]))

    assert same == also_same
    assert hash(same) == hash(also_same)
    assert same != distinct
    assert same != object()


def test_repr_and_str_include_class_and_current_size() -> None:
    setting = PDFontSetting()
    setting.set_font_size(7.5)

    text = repr(setting)
    assert text == str(setting)
    assert "PDFontSetting" in text
    assert "font=" in text
    assert "size=7.5" in text
