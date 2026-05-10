"""Hand-written tests pinning the upstream-named aliases added to round
out the outlines cluster:

- ``PDOutlineNode.append_child`` — alias for ``add_last`` (Java
  ``appendChild``).
- ``PDOutlineItem.get_text_style`` / ``set_text_style`` — aliases for
  ``get_text_flags`` / ``set_text_flags`` (Java ``getTextStyle`` /
  ``setTextStyle(int)``), reading and writing the ``/F`` flag bits.
"""
from __future__ import annotations

from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
)

# ---------- append_child ----------


def test_append_child_appends_to_empty_outline() -> None:
    parent = PDDocumentOutline()
    child = PDOutlineItem()
    child.set_title("only")

    parent.append_child(child)

    assert parent.has_children() is True
    assert parent.get_first_child().get_cos_object() is child.get_cos_object()
    assert parent.get_last_child().get_cos_object() is child.get_cos_object()
    assert child.get_parent().get_cos_object() is parent.get_cos_object()


def test_append_child_appends_to_existing_chain_at_the_end() -> None:
    parent = PDDocumentOutline()
    a = PDOutlineItem()
    a.set_title("A")
    b = PDOutlineItem()
    b.set_title("B")
    parent.add_last(a)
    parent.add_last(b)

    c = PDOutlineItem()
    c.set_title("C")
    parent.append_child(c)

    titles = [child.get_title() for child in parent.children()]
    assert titles == ["A", "B", "C"]
    assert parent.get_last_child().get_cos_object() is c.get_cos_object()
    assert b.get_next_sibling().get_cos_object() is c.get_cos_object()
    assert c.get_previous_sibling().get_cos_object() is b.get_cos_object()


def test_append_child_rejects_node_with_existing_siblings() -> None:
    parent = PDDocumentOutline()
    a = PDOutlineItem()
    b = PDOutlineItem()
    parent.add_last(a)
    parent.add_last(b)

    # ``a`` already has ``b`` as a next sibling, so it can't be appended
    # somewhere else as a single node.
    other = PDDocumentOutline()
    import pytest  # local import to keep top-level imports tight

    with pytest.raises(ValueError):
        other.append_child(a)


# ---------- get_text_style / set_text_style ----------


def test_get_text_style_default_zero_on_fresh_item() -> None:
    item = PDOutlineItem()
    assert item.get_text_style() == 0


def test_set_text_style_round_trips_through_text_flags() -> None:
    item = PDOutlineItem()
    item.set_text_style(PDOutlineItem.FLAG_BOLD)
    assert item.get_text_style() == PDOutlineItem.FLAG_BOLD
    # The alias and the underlying accessor read the same ``/F`` entry.
    assert item.get_text_flags() == PDOutlineItem.FLAG_BOLD


def test_set_text_style_with_combined_bits_round_trips() -> None:
    item = PDOutlineItem()
    combined = PDOutlineItem.FLAG_ITALIC | PDOutlineItem.FLAG_BOLD
    item.set_text_style(combined)
    assert item.get_text_style() == combined
    assert item.is_bold() is True
    assert item.is_italic() is True


def test_set_text_flags_then_get_text_style_reads_same_value() -> None:
    item = PDOutlineItem()
    item.set_text_flags(PDOutlineItem.FLAG_ITALIC)
    assert item.get_text_style() == PDOutlineItem.FLAG_ITALIC


def test_set_text_style_zero_clears_flags() -> None:
    item = PDOutlineItem()
    item.set_text_style(PDOutlineItem.FLAG_BOLD)
    item.set_text_style(0)
    assert item.get_text_style() == 0
    assert item.is_bold() is False
    assert item.is_italic() is False
