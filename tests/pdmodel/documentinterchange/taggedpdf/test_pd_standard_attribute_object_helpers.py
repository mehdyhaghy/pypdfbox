"""Public typed-helper coverage for ``PDStandardAttributeObject``.

These tests exercise the public ``get_*`` / ``set_*`` helpers added on the
PDFBox-parity surface (per upstream
``org.apache.pdfbox.pdmodel.documentinterchange.taggedpdf.PDStandardAttributeObject``).
The legacy private ``_get_*`` / ``_set_*`` helpers used by the typed
subclasses are exercised separately in ``test_attribute_objects.py``.
"""

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
    """Trivial concrete subclass; the upstream class is abstract in name only."""


def _make() -> _ConcreteStandard:
    return _ConcreteStandard(COSDictionary())


# ---------- has_attribute / remove_attribute ----------


def test_has_attribute_reports_presence() -> None:
    obj = _make()
    assert not obj.has_attribute("Foo")
    obj.set_string("Foo", "bar")
    assert obj.has_attribute("Foo")


def test_remove_attribute_clears_entry() -> None:
    obj = _make()
    obj.set_string("Foo", "bar")
    assert obj.has_attribute("Foo")
    obj.remove_attribute("Foo")
    assert not obj.has_attribute("Foo")


# ---------- string ----------


def test_get_string_returns_default_when_absent() -> None:
    obj = _make()
    assert obj.get_string("Desc") is None
    assert obj.get_string("Desc", "fallback") == "fallback"


def test_set_string_round_trip_and_default_removes() -> None:
    obj = _make()
    obj.set_string("Desc", "hello", default="off")
    assert obj.get_string("Desc") == "hello"
    # Setting back to the default removes the key.
    obj.set_string("Desc", "off", default="off")
    assert not obj.has_attribute("Desc")


# ---------- name ----------


def test_get_name_default_and_set_name_round_trip() -> None:
    obj = _make()
    assert obj.get_name("Placement", "Inline") == "Inline"
    obj.set_name("Placement", "Block", default="Inline")
    assert obj.get_name("Placement", "Inline") == "Block"
    # default-equal set removes the key.
    obj.set_name("Placement", "Inline", default="Inline")
    assert not obj.has_attribute("Placement")


# ---------- integer / number ----------


def test_get_set_integer_with_default_removes() -> None:
    obj = _make()
    assert obj.get_integer("RowSpan", 1) == 1
    obj.set_integer("RowSpan", 4, default=1)
    assert obj.get_integer("RowSpan", 1) == 4
    obj.set_integer("RowSpan", 1, default=1)
    assert not obj.has_attribute("RowSpan")


def test_get_set_number_round_trip_and_default_removes() -> None:
    obj = _make()
    assert obj.get_number("SpaceBefore", 0.0) == 0.0
    obj.set_number("SpaceBefore", 3.5)
    assert obj.get_number("SpaceBefore", 0.0) == 3.5
    obj.set_number("SpaceBefore", 0.0)
    assert not obj.has_attribute("SpaceBefore")


def test_set_number_with_int_writes_cos_integer() -> None:
    obj = _make()
    obj.set_number("LineHeight", 12)
    raw = obj.get_cos_object().get_dictionary_object("LineHeight")
    assert isinstance(raw, COSInteger)
    assert raw.value == 12


# ---------- arrays ----------


def test_get_set_array_of_string_round_trip() -> None:
    obj = _make()
    assert obj.get_array_of_string("Headers") is None
    obj.set_array_of_string("Headers", ["a", "b", "c"])
    assert obj.get_array_of_string("Headers") == ["a", "b", "c"]
    obj.set_array_of_string("Headers", None)
    assert not obj.has_attribute("Headers")


def test_get_set_array_of_name_round_trip_and_writes_cos_name() -> None:
    obj = _make()
    obj.set_array_of_name("Roles", ["rb", "cb"])
    assert obj.get_array_of_name("Roles") == ["rb", "cb"]
    raw = obj.get_cos_object().get_dictionary_object("Roles")
    assert isinstance(raw, COSArray)
    assert isinstance(raw.get_object(0), COSName)


def test_get_set_array_of_number_round_trip_and_removes() -> None:
    obj = _make()
    assert obj.get_array_of_number("Dashes") is None
    obj.set_array_of_number("Dashes", [1.0, 2.5, 3.0])
    assert obj.get_array_of_number("Dashes") == [1.0, 2.5, 3.0]
    raw = obj.get_cos_object().get_dictionary_object("Dashes")
    assert isinstance(raw, COSArray)
    assert all(isinstance(raw.get_object(i), COSFloat) for i in range(raw.size()))

    obj.set_array_of_number("Dashes", None)
    assert not obj.has_attribute("Dashes")


def test_set_array_of_number_rejects_bool_entries() -> None:
    obj = _make()
    with pytest.raises(TypeError):
        obj.set_array_of_number("Dashes", [1.0, True])


# ---------- color / color-or-four-colours ----------


def test_get_set_color_round_trip() -> None:
    obj = _make()
    assert obj.get_color("BackgroundColor") is None
    obj.set_color("BackgroundColor", (1.0, 0.5, 0.25))
    assert obj.get_color("BackgroundColor") == (1.0, 0.5, 0.25)


def test_get_color_or_four_colors_three_elements_returns_tuple() -> None:
    obj = _make()
    # Use exactly-representable floats so we don't bake COSFloat's 32-bit
    # narrowing into the test expectation.
    obj.set_color("BorderColor", (0.25, 0.5, 0.75))
    out = obj.get_color_or_four_colors("BorderColor")
    assert isinstance(out, tuple)
    assert out == (0.25, 0.5, 0.75)


def test_get_color_or_four_colors_four_elements_returns_pd_four_colours() -> None:
    obj = _make()
    four = PDFourColours()
    four.set_top((1.0, 0.0, 0.0))
    four.set_right((0.0, 1.0, 0.0))
    four.set_bottom((0.0, 0.0, 1.0))
    four.set_left((0.5, 0.5, 0.5))
    obj.get_cos_object().set_item("BorderColor", four.get_cos_array())
    out = obj.get_color_or_four_colors("BorderColor")
    assert isinstance(out, PDFourColours)
    assert out.get_top() == (1.0, 0.0, 0.0)
    assert out.get_left() == (0.5, 0.5, 0.5)


def test_get_color_or_four_colors_absent_returns_none() -> None:
    obj = _make()
    assert obj.get_color_or_four_colors("BorderColor") is None


# ---------- polymorphic combinators ----------


def test_get_name_or_array_of_name_handles_single_name() -> None:
    obj = _make()
    obj.get_cos_object().set_item("Role", COSName.get_pdf_name("rb"))
    assert obj.get_name_or_array_of_name("Role") == "rb"


def test_get_name_or_array_of_name_handles_array() -> None:
    obj = _make()
    array = COSArray()
    array.add(COSName.get_pdf_name("rb"))
    array.add(COSName.get_pdf_name("cb"))
    obj.get_cos_object().set_item("Role", array)
    assert obj.get_name_or_array_of_name("Role") == ["rb", "cb"]


def test_get_name_or_array_of_name_falls_back_to_default() -> None:
    obj = _make()
    assert obj.get_name_or_array_of_name("Role", "fallback") == "fallback"


def test_get_number_or_array_of_number_handles_scalar_and_array() -> None:
    obj = _make()
    obj.get_cos_object().set_item("LineHeight", COSFloat(1.5))
    assert obj.get_number_or_array_of_number("LineHeight") == 1.5

    obj2 = _make()
    array = COSArray()
    array.add(COSFloat(0.5))
    array.add(COSInteger(2))
    obj2.get_cos_object().set_item("Dashes", array)
    assert obj2.get_number_or_array_of_number("Dashes") == [0.5, 2.0]


def test_get_number_or_name_returns_float_or_string() -> None:
    obj = _make()
    obj.get_cos_object().set_item("LineHeight", COSFloat(1.25))
    assert obj.get_number_or_name("LineHeight") == 1.25

    obj2 = _make()
    obj2.get_cos_object().set_item("LineHeight", COSName.get_pdf_name("Auto"))
    assert obj2.get_number_or_name("LineHeight") == "Auto"

    obj3 = _make()
    assert obj3.get_number_or_name("LineHeight", "Normal") == "Normal"


def test_get_string_reads_existing_cos_string() -> None:
    # Sanity: verifies the helper consumes a pre-populated COSString.
    obj = _make()
    obj.get_cos_object().set_item("Note", COSString("hello"))
    assert obj.get_string("Note") == "hello"
