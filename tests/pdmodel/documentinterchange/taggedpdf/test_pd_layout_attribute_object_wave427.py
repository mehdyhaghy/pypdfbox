from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDLayoutAttributeObject,
)


def test_existing_dictionary_is_aliased_without_overwriting_owner() -> None:
    raw = COSDictionary()
    raw.set_item("O", COSName.get_pdf_name("CustomOwner"))

    obj = PDLayoutAttributeObject(raw)

    assert obj.get_cos_object() is raw
    assert obj.get_owner() == "CustomOwner"


def test_malformed_b_box_values_return_none() -> None:
    obj = PDLayoutAttributeObject()
    obj.get_cos_object().set_item("BBox", COSString("not an array"))
    assert obj.get_b_box() is None

    too_short = COSArray()
    too_short.add(0)
    too_short.add(1)
    obj.get_cos_object().set_item("BBox", too_short)
    assert obj.get_b_box() is None

    wrong_type = COSArray()
    wrong_type.add(0)
    wrong_type.add(1)
    wrong_type.add(COSString("bad"))
    wrong_type.add(3)
    obj.get_cos_object().set_item("BBox", wrong_type)
    assert obj.get_b_box() is None


@pytest.mark.parametrize(
    ("setter_name", "getter_name"),
    [
        ("set_border_thickness", "get_border_thickness"),
        ("set_padding", "get_padding"),
        ("set_column_gap", "get_column_gap"),
        ("set_column_widths", "get_column_widths"),
        ("set_t_padding", "get_t_padding"),
    ],
)
def test_number_or_array_setters_reject_bool(
    setter_name: str, getter_name: str
) -> None:
    obj = PDLayoutAttributeObject()
    setter = getattr(obj, setter_name)

    with pytest.raises(TypeError, match="must be a number or list"):
        setter(True)

    assert obj.get_cos_object().get_dictionary_object(
        getter_name.removeprefix("get_").title().replace("_", "")
    ) is None


@pytest.mark.parametrize(
    ("setter_name", "key", "getter_name", "default"),
    [
        ("set_width", "Width", "get_width", PDLayoutAttributeObject.WIDTH_AUTO),
        ("set_height", "Height", "get_height", PDLayoutAttributeObject.HEIGHT_AUTO),
        (
            "set_line_height",
            "LineHeight",
            "get_line_height",
            PDLayoutAttributeObject.LINE_HEIGHT_NORMAL,
        ),
    ],
)
def test_name_or_number_setters_write_names_and_remove_on_none(
    setter_name: str,
    key: str,
    getter_name: str,
    default: str,
) -> None:
    obj = PDLayoutAttributeObject()
    setter = getattr(obj, setter_name)
    getter = getattr(obj, getter_name)

    setter("CustomName")
    assert getter() == "CustomName"
    assert isinstance(obj.get_cos_object().get_dictionary_object(key), COSName)

    setter(None)
    assert obj.get_cos_object().get_dictionary_object(key) is None
    assert getter() == default


def test_array_alias_none_removes_existing_values() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_all_column_gaps(3)
    obj.set_column_gaps(None)
    assert obj.get_cos_object().get_dictionary_object("ColumnGap") is None

    obj.set_all_column_widths(72)
    obj.set_column_widths(None)
    assert obj.get_cos_object().get_dictionary_object("ColumnWidths") is None

    obj.set_all_t_paddings(2)
    obj.set_t_paddings(None)
    assert obj.get_cos_object().get_dictionary_object("TPadding") is None


def test_repr_reports_owner_and_default_layout_names() -> None:
    obj = PDLayoutAttributeObject()

    assert repr(obj) == (
        "PDLayoutAttributeObject(O=Layout, Placement=Inline, WritingMode=LrTb)"
    )
