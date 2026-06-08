from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.action import PDActionGoTo
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDNamedDestination,
    PDPageFitDestination,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
)


def _item(title: str) -> PDOutlineItem:
    item = PDOutlineItem()
    item.set_title(title)
    return item


def test_public_sibling_setters_wire_previous_and_next_links() -> None:
    first = _item("first")
    second = _item("second")

    first.set_next_sibling(second)
    second.set_previous_sibling(first)

    assert first.get_next_sibling().get_cos_object() is second.get_cos_object()
    assert second.get_previous_sibling().get_cos_object() is first.get_cos_object()


def test_insert_sibling_after_middle_relinks_neighbors() -> None:
    parent = PDDocumentOutline()
    first = _item("first")
    third = _item("third")
    parent.add_last(first)
    parent.add_last(third)
    second = _item("second")

    first.insert_sibling_after(second)

    assert parent.get_first_child().get_cos_object() is first.get_cos_object()
    assert parent.get_last_child().get_cos_object() is third.get_cos_object()
    assert first.get_next_sibling().get_cos_object() is second.get_cos_object()
    assert second.get_previous_sibling().get_cos_object() is first.get_cos_object()
    assert second.get_next_sibling().get_cos_object() is third.get_cos_object()
    assert third.get_previous_sibling().get_cos_object() is second.get_cos_object()


def test_insert_sibling_after_tail_updates_parent_last_child() -> None:
    parent = PDDocumentOutline()
    first = _item("first")
    parent.add_last(first)
    second = _item("second")

    first.insert_sibling_after(second)

    assert parent.get_last_child().get_cos_object() is second.get_cos_object()
    assert second.get_parent().get_cos_object() is parent.get_cos_object()


def test_insert_sibling_before_head_updates_parent_first_child() -> None:
    parent = PDDocumentOutline()
    second = _item("second")
    parent.add_last(second)
    first = _item("first")

    second.insert_sibling_before(first)

    assert parent.get_first_child().get_cos_object() is first.get_cos_object()
    assert first.get_next_sibling().get_cos_object() is second.get_cos_object()
    assert second.get_previous_sibling().get_cos_object() is first.get_cos_object()


def test_text_style_aliases_read_and_write_flags() -> None:
    item = PDOutlineItem()

    item.set_text_style(PDOutlineItem.FLAG_BOLD)

    assert item.get_text_style() == PDOutlineItem.FLAG_BOLD
    assert item.get_text_flags() == PDOutlineItem.FLAG_BOLD


def test_find_destination_page_resolves_named_goto_action_string() -> None:
    with PDDocument() as document:
        document.add_page(PDPage())
        target = PDPage()
        document.add_page(target)

        destination = PDPageFitDestination()
        destination.set_page_number(1)
        legacy_dests = COSDictionary()
        legacy_dests.set_item(COSName.get_pdf_name("chapter"), destination.get_cos_object())
        document.get_document_catalog().get_cos_object().set_item(
            COSName.get_pdf_name("Dests"),
            legacy_dests,
        )

        action = PDActionGoTo()
        action.set_destination("chapter")
        item = PDOutlineItem()
        item.set_action(action)

        assert item.find_destination_page(document) is target.get_cos_object()


def test_find_destination_page_handles_negative_and_raises_for_out_of_range() -> None:
    with PDDocument() as document:
        document.add_page(PDPage())

        unset_page_number = PDPageFitDestination()
        item = PDOutlineItem()
        item.set_destination(unset_page_number)
        assert item.find_destination_page(document) is None

        out_of_range = PDPageFitDestination()
        out_of_range.set_page_number(5)
        item.set_destination(out_of_range)
        with pytest.raises(IndexError):
            item.find_destination_page(document)


def test_find_destination_page_resolves_wrapped_legacy_d_entry() -> None:
    with PDDocument() as document:
        document.add_page(PDPage())
        target = PDPage()
        document.add_page(target)

        destination = PDPageXYZDestination()
        destination.set_page_number(1)
        wrapped = COSDictionary()
        wrapped.set_item(COSName.get_pdf_name("D"), destination.get_cos_object())
        legacy_dests = COSDictionary()
        legacy_dests.set_item(COSName.get_pdf_name("wrapped"), wrapped)
        document.get_document_catalog().get_cos_object().set_item(
            COSName.get_pdf_name("Dests"),
            legacy_dests,
        )

        item = PDOutlineItem()
        item.set_destination(PDNamedDestination("wrapped"))

        assert item.find_destination_page(document) is target.get_cos_object()


def test_resolve_named_destination_rejects_objects_without_string_name() -> None:
    with PDDocument() as document:
        assert PDOutlineItem._resolve_named_destination(document, object()) is None

        class EmptyNamedDestination:
            def get_named_destination(self) -> None:
                return None

        assert (
            PDOutlineItem._resolve_named_destination(document, EmptyNamedDestination())
            is None
        )


def test_resolve_named_destination_unwraps_name_tree_dictionary_entry() -> None:
    destination = PDPageFitDestination()
    destination.set_page_number(3)
    wrapped = COSDictionary()
    wrapped.set_item(COSName.get_pdf_name("D"), destination.get_cos_object())

    class FakeTree:
        def get_value(self, name: str) -> COSDictionary | None:
            return wrapped if name == "chapter" else None

    class FakeNames:
        def get_dests(self) -> FakeTree:
            return FakeTree()

    class FakeCatalog:
        def get_names(self) -> FakeNames:
            return FakeNames()

        def get_dests(self) -> None:
            return None

    class FakeDocument:
        def get_document_catalog(self) -> FakeCatalog:
            return FakeCatalog()

    resolved = PDOutlineItem._resolve_named_destination(
        FakeDocument(), PDNamedDestination("chapter")
    )

    assert isinstance(resolved, PDPageFitDestination)
    assert resolved.get_page_number() == 3


def test_coerce_named_destination_entry_handles_wrapped_invalid_and_typed_values() -> None:
    destination = PDPageXYZDestination()
    destination.set_page_number(2)

    assert PDOutlineItem._coerce_named_destination_entry(destination) is destination
    assert PDOutlineItem._coerce_named_destination_entry(object()) is None

    malformed = COSDictionary()
    malformed.set_item(
        COSName.get_pdf_name("D"),
        COSArray([COSInteger.get(0), COSName.get_pdf_name("UnknownDestType")]),
    )
    assert PDOutlineItem._coerce_named_destination_entry(malformed) is None


def test_find_destination_page_returns_none_for_non_page_destination(
    monkeypatch: Any,
) -> None:
    with PDDocument() as document:
        item = PDOutlineItem()
        monkeypatch.setattr(item, "get_destination", lambda: object())

        assert item.find_destination_page(document) is None
