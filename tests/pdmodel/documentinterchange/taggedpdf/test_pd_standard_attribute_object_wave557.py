from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDFourColours,
    PDStandardAttributeObject,
)


class _ConcreteStandard(PDStandardAttributeObject):
    pass


def _make() -> _ConcreteStandard:
    return _ConcreteStandard(COSDictionary())


def test_wave557_legacy_scalar_helpers_round_trip_and_clear() -> None:
    obj = _make()

    assert not obj.is_specified("Label")
    obj._set_string("Label", "caption")
    assert obj._get_string("Label") == "caption"
    assert obj.is_specified("Label")
    obj._set_string("Label", None)
    assert obj._get_string("Label") is None

    assert obj._get_name("Scope", "Row") == "Row"
    obj._set_name("Scope", "Column")
    assert obj._get_name("Scope") == "Column"
    obj._set_name("Scope", None)
    assert obj._get_name("Scope") is None

    assert obj._get_integer("ColSpan", 1) == 1
    obj._set_integer("ColSpan", 3)
    assert obj._get_integer("ColSpan") == 3

    assert obj._get_number("SpaceAfter", 2.5) == 2.5
    obj._set_number("SpaceAfter", 4)
    assert isinstance(obj._get_item("SpaceAfter"), COSInteger)
    obj._set_number("SpaceAfter", 4.5)
    assert obj._get_number("SpaceAfter") == 4.5


def test_wave557_legacy_setters_reject_bool_values() -> None:
    obj = _make()

    with pytest.raises(TypeError, match="ColSpan must be an integer"):
        obj._set_integer("ColSpan", True)
    with pytest.raises(TypeError, match="LineHeight must be a number"):
        obj._set_number("LineHeight", False)


def test_wave557_array_helpers_ignore_wrong_item_types() -> None:
    obj = _make()
    array = COSArray()
    array.add(COSName.get_pdf_name("NameValue"))
    array.add(COSString("StringValue"))
    array.add(COSInteger.get(7))
    obj.get_cos_object().set_item("MixedStrings", array)

    assert obj._get_array("MixedStrings") is array
    assert obj._get_array("Missing") is None
    assert obj.get_array_of_string("MixedStrings") == ["NameValue", "StringValue"]
    assert obj.get_array_of_name("MissingNames") is None

    numbers = COSArray()
    numbers.add(COSInteger.get(1))
    numbers.add(COSName.get_pdf_name("Ignored"))
    numbers.add(COSFloat(2.5))
    obj.get_cos_object().set_item("Numbers", numbers)
    assert obj.get_array_of_number("Numbers") == [1.0, 2.5]


def test_wave557_clear_attribute_and_array_of_name_clear() -> None:
    obj = _make()

    obj.set_string("ActualText", "visible")
    obj.clear_attribute("ActualText")
    assert not obj.has_attribute("ActualText")

    obj.set_array_of_name("Roles", ["rb"])
    assert obj.has_attribute("Roles")
    obj.set_array_of_name("Roles", None)
    assert not obj.has_attribute("Roles")


def test_wave557_color_and_four_colour_helpers_handle_malformed_values() -> None:
    obj = _make()
    malformed = COSArray()
    malformed.add(COSFloat(1.0))
    malformed.add(COSName.get_pdf_name("NotNumeric"))
    obj.get_cos_object().set_item("Color", malformed)
    assert obj.get_color("Color") is None

    obj.set_color("Color", (0.25, 0.5, 0.75))
    assert obj.get_color("Color") == (0.25, 0.5, 0.75)
    obj.set_color("Color", None)
    assert obj.get_color("Color") is None

    four = PDFourColours.single_color((0.1, 0.2, 0.3))
    obj._set_four_colours("BorderColor", four)
    assert obj._get_four_colours("BorderColor") is not None
    obj._set_four_colours("BorderColor", None)
    assert obj._get_four_colours("BorderColor") is None

    incomplete_four = COSArray()
    incomplete_four.add(COSArray())
    incomplete_four.add(COSArray())
    incomplete_four.add(COSArray())
    incomplete_four.add(COSName.get_pdf_name("NotAColor"))
    obj.get_cos_object().set_item("BorderColor", incomplete_four)
    assert obj.get_color_or_four_colors("BorderColor") is None

    five_components = COSArray()
    for value in range(5):
        five_components.add(COSInteger.get(value))
    obj.get_cos_object().set_item("BorderColor", five_components)
    assert obj.get_color_or_four_colors("BorderColor") is None


def test_wave557_gamma_and_raw_item_helpers_round_trip_and_clear() -> None:
    obj = _make()

    assert obj._get_gamma("Gamma") is None
    obj._set_gamma("Gamma", 2.2)
    assert obj._get_gamma("Gamma") == pytest.approx(2.2)
    obj._set_gamma("Gamma", None)
    assert obj._get_gamma("Gamma") is None

    raw = COSString("raw")
    obj._set_item("Raw", raw)
    assert obj._get_item("Raw") is raw
    obj._set_item("Raw", None)
    assert obj._get_item("Raw") is None


def test_wave557_polymorphic_helpers_reject_malformed_arrays() -> None:
    obj = _make()
    names = COSArray()
    names.add(COSName.get_pdf_name("Block"))
    names.add(COSString("not-a-name"))
    obj.get_cos_object().set_item("Placement", names)
    assert obj.get_name_or_array_of_name("Placement") is None

    numbers = COSArray()
    numbers.add(COSFloat(1.0))
    numbers.add(COSName.get_pdf_name("Auto"))
    obj.get_cos_object().set_item("LineHeight", numbers)
    assert obj.get_number_or_array_of_number("LineHeight") is None

    assert obj.get_number_or_array_of_number("Missing") is None
    assert obj.get_number_or_array_of_number("Missing", obj.UNSPECIFIED) is None
    assert obj.get_number_or_array_of_number("Missing", 3.0) == 3.0
