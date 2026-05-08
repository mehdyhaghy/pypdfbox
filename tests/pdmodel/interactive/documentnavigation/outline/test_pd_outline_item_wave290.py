"""Wave 290 coverage for outline item optional-entry helpers."""
from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import PDOutlineItem

_A = COSName.A  # type: ignore[attr-defined]
_C = COSName.C  # type: ignore[attr-defined]
_DEST = COSName.get_pdf_name("Dest")
_F = COSName.get_pdf_name("F")
_SE = COSName.get_pdf_name("SE")


def test_malformed_destination_array_is_absent_and_clearable() -> None:
    item = PDOutlineItem()
    item.get_cos_object().set_item(_DEST, COSArray([COSInteger.get(0)]))

    assert item.get_destination() is None
    assert item.has_destination() is False

    item.clear_destination()
    assert item.get_cos_object().get_dictionary_object(_DEST) is None


def test_named_destination_reports_present_and_clear_removes_entry() -> None:
    item = PDOutlineItem()
    item.get_cos_object().set_item(_DEST, COSString("Chapter1"))

    assert item.get_destination() is not None
    assert item.has_destination() is True

    item.clear_destination()
    assert item.has_destination() is False


def test_malformed_text_color_array_is_absent_in_typed_helpers() -> None:
    item = PDOutlineItem()
    item.get_cos_object().set_item(
        _C,
        COSArray([COSFloat(0.2), COSString("bad"), COSFloat(0.8)]),
    )

    assert item.get_text_color() is None
    assert item.has_text_color() is False


def test_text_color_helpers_accept_numeric_prefix_and_clear_entry() -> None:
    item = PDOutlineItem()
    item.get_cos_object().set_item(
        _C,
        COSArray(
            [
                COSInteger.get(0),
                COSFloat(0.5),
                COSInteger.get(1),
                COSString("ignored trailing value"),
            ]
        ),
    )

    assert item.get_text_color() == (0.0, 0.5, 1.0)
    assert item.has_text_color() is True

    item.clear_text_color()
    assert item.get_text_color() is None
    assert item.has_text_color() is False


def test_action_structure_and_text_flag_helpers_are_typed_and_clearable() -> None:
    item = PDOutlineItem()
    item.get_cos_object().set_item(_A, COSString("not an action"))
    item.get_cos_object().set_item(_SE, COSString("not a structure element"))
    item.get_cos_object().set_item(_F, COSString("not flags"))

    assert item.has_action() is False
    assert item.has_structure_element() is False
    assert item.has_text_flags() is False

    item.get_cos_object().set_item(_A, COSDictionary())
    item.get_cos_object().set_item(_SE, COSDictionary())
    item.set_text_flags(PDOutlineItem.FLAG_BOLD)

    assert item.has_action() is True
    assert item.has_structure_element() is True
    assert item.has_text_flags() is True

    item.clear_action()
    item.clear_structure_element()
    item.clear_text_flags()

    assert item.has_action() is False
    assert item.has_structure_element() is False
    assert item.has_text_flags() is False
