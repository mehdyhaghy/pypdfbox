"""Wave 326 robustness coverage for outline child removal."""
from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
)

_NEXT = COSName.get_pdf_name("Next")
_PREV = COSName.PREV  # type: ignore[attr-defined]


def _item(title: str) -> PDOutlineItem:
    item = PDOutlineItem()
    item.set_title(title)
    return item


def test_wave326_remove_first_child_ignores_stale_prev_link() -> None:
    parent = PDDocumentOutline()
    first = _item("first")
    second = _item("second")
    outsider = _item("outsider")
    parent.add_last(first)
    parent.add_last(second)
    first.get_cos_object().set_item(_PREV, outsider.get_cos_object())

    assert parent.remove_child(first) is True

    assert parent.get_first_child() == second
    assert second.get_previous_sibling() is None
    assert outsider.get_next_sibling() is None
    assert first.get_previous_sibling() is None


def test_wave326_remove_last_child_ignores_stale_next_link() -> None:
    parent = PDDocumentOutline()
    first = _item("first")
    second = _item("second")
    outsider = _item("outsider")
    parent.add_last(first)
    parent.add_last(second)
    second.get_cos_object().set_item(_NEXT, outsider.get_cos_object())

    assert parent.remove_child(second) is True

    assert parent.get_last_child() == first
    assert first.get_next_sibling() is None
    assert outsider.get_previous_sibling() is None
    assert second.get_next_sibling() is None
