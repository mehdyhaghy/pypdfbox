from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDStandardAttributeObject,
)


class _ConcreteStandard(PDStandardAttributeObject):
    pass


def _make() -> _ConcreteStandard:
    return _ConcreteStandard(COSDictionary())


def test_wave597_public_array_setters_clear_existing_entries() -> None:
    obj = _make()

    obj.set_array_of_string("Headers", ["H1"])
    obj.set_array_of_name("Names", ["Block"])
    obj.set_array_of_number("Dashes", [1.0])

    obj.set_array_of_string("Headers", None)
    obj.set_array_of_name("Names", None)
    obj.set_array_of_number("Dashes", None)

    assert not obj.has_attribute("Headers")
    assert not obj.has_attribute("Names")
    assert not obj.has_attribute("Dashes")


def test_wave597_array_readers_ignore_or_reject_malformed_members() -> None:
    obj = _make()

    strings = COSArray()
    strings.add(COSName.get_pdf_name("NameValue"))
    strings.add(COSInteger.get(7))
    obj.get_cos_object().set_item("Strings", strings)
    assert obj.get_array_of_string("Strings") == ["NameValue"]

    names = COSArray()
    names.add(COSName.get_pdf_name("Before"))
    names.add(COSInteger.get(1))
    obj.get_cos_object().set_item("Names", names)
    assert obj.get_name_or_array_of_name("Names") is None

    numbers = COSArray()
    numbers.add(COSInteger.get(2))
    numbers.add(COSName.get_pdf_name("Bad"))
    obj.get_cos_object().set_item("Numbers", numbers)
    assert obj.get_number_or_array_of_number("Numbers") is None


def test_wave597_color_helpers_clear_and_reject_bad_components() -> None:
    obj = _make()

    obj.set_color("BackgroundColor", (0.0, 0.5, 1.0))
    assert obj.has_attribute("BackgroundColor")

    obj.set_color("BackgroundColor", None)
    assert obj.get_color("BackgroundColor") is None
    assert not obj.has_attribute("BackgroundColor")

    bad_color = COSArray()
    bad_color.add(COSFloat(0.25))
    bad_color.add(COSName.get_pdf_name("Bad"))
    bad_color.add(COSFloat(0.75))
    obj.get_cos_object().set_item("BackgroundColor", bad_color)
    assert obj.get_color("BackgroundColor") is None
    assert obj.get_color_or_four_colors("BackgroundColor") is None


def test_wave597_four_color_shape_requires_all_side_colors() -> None:
    obj = _make()
    malformed_four = COSArray()
    for value in (0.0, 0.25, 0.5):
        side = COSArray()
        side.add(COSFloat(value))
        malformed_four.add(side)
    malformed_four.add(COSName.get_pdf_name("BadSide"))

    obj.get_cos_object().set_item("BorderColor", malformed_four)

    assert obj.get_color_or_four_colors("BorderColor") is None
