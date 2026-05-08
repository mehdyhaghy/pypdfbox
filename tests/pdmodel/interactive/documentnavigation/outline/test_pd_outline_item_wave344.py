"""Wave 344 robustness coverage for detached sibling insertion."""
from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
)

_PARENT = COSName.PARENT  # type: ignore[attr-defined]


def _item(title: str) -> PDOutlineItem:
    item = PDOutlineItem()
    item.set_title(title)
    return item


def test_wave344_insert_after_detached_anchor_clears_stale_parent() -> None:
    old_parent = PDDocumentOutline()
    stale_child = _item("stale")
    old_parent.add_last(stale_child)
    assert old_parent.get_open_count() == 1

    anchor = _item("anchor")
    anchor.insert_sibling_after(stale_child)

    assert anchor.get_next_sibling() == stale_child
    assert stale_child.get_previous_sibling() == anchor
    assert stale_child.get_parent() is None
    assert stale_child.get_cos_object().get_dictionary_object(_PARENT) is None
    assert old_parent.get_open_count() == 1


def test_wave344_insert_before_detached_anchor_clears_stale_parent() -> None:
    old_parent = PDDocumentOutline()
    stale_child = _item("stale")
    old_parent.add_last(stale_child)
    assert old_parent.get_open_count() == 1

    anchor = _item("anchor")
    anchor.insert_sibling_before(stale_child)

    assert anchor.get_previous_sibling() == stale_child
    assert stale_child.get_next_sibling() == anchor
    assert stale_child.get_parent() is None
    assert stale_child.get_cos_object().get_dictionary_object(_PARENT) is None
    assert old_parent.get_open_count() == 1
