from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDStandardAttributeObject,
)


class _ConcreteStandard(PDStandardAttributeObject):
    pass


def _make() -> _ConcreteStandard:
    return _ConcreteStandard(COSDictionary())


def test_wave577_public_scalar_setters_remove_default_values() -> None:
    obj = _make()

    obj.set_string("Summary", "custom", default="default")
    obj.set_name("Placement", "Block", default="Inline")
    obj.set_integer("RowSpan", 3, default=1)
    obj.set_number("SpaceBefore", 2.5, default=0.0)

    assert obj.has_attribute("Summary")
    assert obj.has_attribute("Placement")
    assert obj.has_attribute("RowSpan")
    assert obj.has_attribute("SpaceBefore")

    obj.set_string("Summary", "default", default="default")
    obj.set_name("Placement", "Inline", default="Inline")
    obj.set_integer("RowSpan", 1, default=1)
    obj.set_number("SpaceBefore", 0, default=0.0)

    assert not obj.has_attribute("Summary")
    assert not obj.has_attribute("Placement")
    assert not obj.has_attribute("RowSpan")
    assert not obj.has_attribute("SpaceBefore")


def test_wave577_public_numeric_setters_reject_bool_values() -> None:
    obj = _make()

    with pytest.raises(TypeError, match="ColSpan must be an integer"):
        obj.set_integer("ColSpan", True)

    with pytest.raises(TypeError, match="LineHeight must be a number"):
        obj.set_number("LineHeight", False)


def test_wave577_array_name_reader_collects_only_names() -> None:
    obj = _make()
    values = COSArray()
    values.add(COSName.get_pdf_name("Before"))
    values.add(COSInteger.get(7))
    values.add(COSName.get_pdf_name("After"))
    obj.get_cos_object().set_item("Headers", values)

    assert obj.get_array_of_name("Headers") == ["Before", "After"]

    obj.get_cos_object().set_item("Headers", COSName.get_pdf_name("NotArray"))
    assert obj.get_array_of_name("Headers") is None


def test_wave577_number_or_array_default_and_malformed_scalar() -> None:
    obj = _make()

    assert obj.get_number_or_array_of_number("Missing", 4.5) == 4.5
    assert obj.get_number_or_array_of_number("Missing", obj.UNSPECIFIED) is None

    obj.get_cos_object().set_item("LineHeight", COSName.get_pdf_name("Auto"))
    assert obj.get_number_or_array_of_number("LineHeight", 4.5) == 4.5


def test_wave577_number_or_name_falls_back_for_unexpected_values() -> None:
    obj = _make()
    obj.get_cos_object().set_item("LineHeight", COSArray())

    assert obj.get_number_or_name("LineHeight", "Normal") == "Normal"

    obj.get_cos_object().set_item("LineHeight", COSInteger.get(12))
    assert obj.get_number_or_name("LineHeight") == 12.0

    obj.get_cos_object().set_item("LineHeight", COSFloat(1.25))
    assert obj.get_number_or_name("LineHeight") == 1.25
