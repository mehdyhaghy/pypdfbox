from __future__ import annotations

import pytest

from pypdfbox.cos import COSFloat, COSInteger, COSName, COSObject, COSString
from pypdfbox.pdmodel.fdf import FDFField
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
)

_PARENT = COSName.PARENT  # type: ignore[attr-defined]
_V = COSName.get_pdf_name("V")


def _item(title: str) -> PDOutlineItem:
    item = PDOutlineItem()
    item.set_title(title)
    return item


def test_fdf_value_list_accepts_cos_base_and_rejects_other_entries() -> None:
    field = FDFField()

    field.set_value([COSName.get_pdf_name("Yes"), "Other"])

    assert field.get_value() == ["Yes", "Other"]
    with pytest.raises(TypeError, match="value list entries"):
        field.set_value(["ok", object()])


def test_fdf_default_value_accepts_cos_base_and_rejects_other_values() -> None:
    field = FDFField()

    field.set_default_value(COSName.get_pdf_name("DefaultOn"))

    assert field.get_default_value() == "DefaultOn"
    with pytest.raises(TypeError, match="set_default_value expected"):
        field.set_default_value(42)


def test_fdf_options_accept_prebuilt_cos_values() -> None:
    field = FDFField()

    field.set_options([COSName.get_pdf_name("On"), ("export", "display")])

    assert field.get_options() == ["On", ["export", "display"]]


def test_fdf_value_conversion_resolves_cos_object_and_integer() -> None:
    field = FDFField()
    field.get_cos_object().set_item(_V, COSObject(1, resolved=COSString("wrapped")))

    assert field.get_value() == "wrapped"

    field.set_value(COSInteger.get(7))
    assert field.get_value() == 7


def test_fdf_value_conversion_returns_unknown_cos_base_verbatim() -> None:
    field = FDFField()
    value = COSFloat(1.25)

    field.set_value(value)

    assert field.get_value() is value


def test_outline_add_first_before_existing_child_links_chain() -> None:
    parent = PDDocumentOutline()
    second = _item("second")
    first = _item("first")
    parent.add_last(second)

    parent.add_first(first)

    assert list(parent) == [first, second]
    assert parent.get_first_child() == first
    assert parent.get_last_child() == second
    assert first.get_next_sibling() == second
    assert second.get_previous_sibling() == first


def test_outline_count_update_ignores_self_referencing_parent() -> None:
    item = _item("self")
    item.set_open_count(2)
    item.get_cos_object().set_item(_PARENT, item.get_cos_object())

    item._update_parent_open_count(3)  # noqa: SLF001

    assert item.get_open_count() == 2


def test_outline_remove_child_from_closed_parent_reduces_abs_count() -> None:
    parent = _item("parent")
    child = _item("child")
    parent.add_last(child)
    parent.set_open_count(-1)

    assert parent.remove_child(child) is True

    assert parent.get_open_count() == 0
    assert parent.has_children() is False
    assert child.get_parent() is None


def test_outline_iterator_stops_on_next_cycle() -> None:
    parent = PDDocumentOutline()
    child = _item("cycle")
    parent.add_last(child)
    child.set_next_sibling(child)
    iterator = parent.iterator()

    assert next(iterator) == child
    with pytest.raises(StopIteration):
        next(iterator)
    assert iterator.has_next() is False
