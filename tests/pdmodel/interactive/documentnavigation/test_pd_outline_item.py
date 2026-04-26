from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.action import PDActionGoTo, PDActionURI
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitDestination,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
)


def test_outline_item_typed_destination_round_trip() -> None:
    item = PDOutlineItem()
    dest = PDPageFitDestination()
    dest.set_page_number(1)

    item.set_destination(dest)
    resolved = item.get_destination()

    assert isinstance(resolved, PDPageFitDestination)
    assert resolved.get_page_number() == 1


def test_outline_item_typed_action_round_trip() -> None:
    item = PDOutlineItem()
    action = PDActionURI()
    action.set_uri("https://example.test")

    item.set_action(action)
    resolved = item.get_action()

    assert isinstance(resolved, PDActionURI)
    assert resolved.get_uri() == "https://example.test"


def test_document_outline_root_iterates_children_with_destinations_and_actions() -> None:
    outline = PDDocumentOutline()
    destination_item = PDOutlineItem()
    destination_item.set_title("Direct destination")
    destination = PDPageFitDestination()
    destination.set_page_number(0)
    destination_item.set_destination(destination)

    action_item = PDOutlineItem()
    action_item.set_title("GoTo action")
    action_destination = PDPageXYZDestination()
    action_destination.set_page_number(1)
    action_destination.set_zoom(1.25)
    action = PDActionGoTo()
    action.set_destination(action_destination)
    action_item.set_action(action)

    outline.add_last(destination_item)
    outline.add_last(action_item)

    children = list(outline.children())
    assert [child.get_title() for child in children] == [
        "Direct destination",
        "GoTo action",
    ]
    assert outline.get_first_child().get_cos_object() is destination_item.get_cos_object()
    assert outline.get_last_child().get_cos_object() is action_item.get_cos_object()
    assert destination_item.get_parent().get_cos_object() is outline.get_cos_object()
    assert action_item.get_previous_sibling().get_cos_object() is (
        destination_item.get_cos_object()
    )

    resolved_destination = children[0].get_destination()
    assert isinstance(resolved_destination, PDPageFitDestination)
    assert resolved_destination.get_page_number() == 0

    resolved_action = children[1].get_action()
    assert isinstance(resolved_action, PDActionGoTo)
    resolved_action_destination = resolved_action.get_destination()
    assert isinstance(resolved_action_destination, PDPageXYZDestination)
    assert resolved_action_destination.get_page_number() == 1
    assert resolved_action_destination.get_zoom() == 1.25


def test_catalog_document_outline_round_trip_preserves_children() -> None:
    with PDDocument() as document:
        catalog = document.get_document_catalog()
        outline = PDDocumentOutline()
        child = PDOutlineItem()
        child.set_title("Chapter 1")
        destination = PDPageFitDestination()
        destination.set_page_number(0)
        child.set_destination(destination)
        outline.add_last(child)

        catalog.set_document_outline(outline)
        resolved = catalog.get_document_outline()

    assert isinstance(resolved, PDDocumentOutline)
    assert resolved.get_cos_object() is outline.get_cos_object()
    resolved_child = resolved.get_first_child()
    assert resolved_child is not None
    assert resolved_child.get_title() == "Chapter 1"
    resolved_destination = resolved_child.get_destination()
    assert isinstance(resolved_destination, PDPageFitDestination)
    assert resolved_destination.get_page_number() == 0


def test_outline_item_text_color_round_trip() -> None:
    item = PDOutlineItem()
    assert item.get_text_color() is None

    item.set_text_color((1.0, 0.5, 0.0))
    color = item.get_text_color()
    assert color == (1.0, 0.5, 0.0)

    item.set_text_color(None)
    assert item.get_text_color() is None


def test_outline_item_italic_and_bold_flag_round_trip() -> None:
    item = PDOutlineItem()
    assert item.get_text_flags() == 0
    assert not item.is_italic()
    assert not item.is_bold()

    item.set_italic(True)
    item.set_bold(True)
    assert item.is_italic()
    assert item.is_bold()
    assert item.get_text_flags() == PDOutlineItem.FLAG_ITALIC | PDOutlineItem.FLAG_BOLD

    item.set_italic(False)
    assert not item.is_italic()
    assert item.is_bold()
    assert item.get_text_flags() == PDOutlineItem.FLAG_BOLD

    item.set_text_flags(0)
    assert not item.is_italic()
    assert not item.is_bold()


def test_outline_item_structure_element_round_trip_with_raw_dict() -> None:
    item = PDOutlineItem()
    assert item.get_structure_element() is None

    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("StructElem"))
    raw.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("P"))

    item.set_structure_element(raw)
    resolved = item.get_structure_element()
    assert resolved is raw

    item.set_structure_element(None)
    assert item.get_structure_element() is None


def test_outline_item_negative_count_is_collapsed() -> None:
    item = PDOutlineItem()
    assert item.get_count() == 0
    assert not item.is_collapsed()

    item.set_count(-3)
    assert item.get_count() == -3
    assert item.is_collapsed()

    item.set_count(3)
    assert item.get_count() == 3
    assert not item.is_collapsed()


def test_outline_item_find_destination_page_resolves_explicit_page_index() -> None:
    with PDDocument() as document:
        document.add_page(PDPage())
        document.add_page(PDPage())
        assert document.get_number_of_pages() == 2

        item = PDOutlineItem()
        destination = PDPageFitDestination()
        destination.set_page_number(1)
        item.set_destination(destination)

        resolved = item.find_destination_page(document)
        expected = document.get_pages()[1].get_cos_object()
        assert resolved is expected


def test_outline_item_find_destination_page_returns_none_when_no_dest() -> None:
    with PDDocument() as document:
        item = PDOutlineItem()
        assert item.find_destination_page(document) is None
