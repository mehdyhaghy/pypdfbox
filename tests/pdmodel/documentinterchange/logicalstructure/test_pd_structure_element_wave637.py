from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (
    PDStructureTreeRoot,
)
from pypdfbox.pdmodel.documentinterchange.markedcontent.pd_marked_content import (
    PDMarkedContent,
)
from pypdfbox.pdmodel.pd_page import PDPage


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_wave637_presence_predicates_track_empty_values_and_raw_slots() -> None:
    elem = PDStructureElement(structure_type="P")

    assert elem.has_structure_type() is True
    assert elem.has_id() is False
    assert elem.has_title() is False
    assert elem.has_language() is False
    assert elem.has_alternate_description() is False
    assert elem.has_expanded_form() is False
    assert elem.has_actual_text() is False
    assert elem.has_page() is False
    assert elem.has_parent() is False

    elem.set_element_identifier("id-1")
    elem.set_title("Title")
    elem.set_language("en-US")
    elem.set_alternate_description("Alt")
    elem.set_expanded_form("Expanded")
    elem.set_actual_text("Actual")
    elem.set_page(PDPage())
    elem.set_parent(COSDictionary())

    assert elem.has_id() is True
    assert elem.has_title() is True
    assert elem.has_language() is True
    assert elem.has_alternate_description() is True
    assert elem.has_expanded_form() is True
    assert elem.has_actual_text() is True
    assert elem.has_page() is True
    assert elem.has_parent() is True

    elem.set_id("")
    elem.set_title("")
    elem.set_language("")
    elem.set_alternate_description("")
    elem.set_expanded_form("")
    elem.set_actual_text("")

    assert elem.has_id() is False
    assert elem.has_title() is False
    assert elem.has_language() is False
    assert elem.has_alternate_description() is False
    assert elem.has_expanded_form() is False
    assert elem.has_actual_text() is False


def test_wave637_parent_node_and_root_helpers_dispatch_and_stop_on_cycles() -> None:
    root = PDStructureTreeRoot()
    parent = PDStructureElement(structure_type="Sect")
    child = PDStructureElement(structure_type="P")
    parent.set_parent(root)
    child.set_parent(parent)

    parent_node = child.get_parent_node()
    assert isinstance(parent_node, PDStructureElement)
    assert parent_node.get_cos_object() is parent.get_cos_object()
    assert child.is_root_attached() is True
    assert child.get_structure_tree_root().get_cos_object() is root.get_cos_object()

    root_node = parent.get_parent_node()
    assert isinstance(root_node, PDStructureTreeRoot)
    assert root_node.get_cos_object() is root.get_cos_object()

    child.set_parent(None)
    assert child.get_parent_node() is None
    assert child.is_root_attached() is False

    child.set_parent(child)
    assert child.get_structure_tree_root() is None
    assert child.get_role_map() == {}


def test_wave637_insert_before_typed_overloads_preserve_kid_order() -> None:
    elem = PDStructureElement(structure_type="P")
    first = PDStructureElement(structure_type="Span")
    second = PDStructureElement(structure_type="Figure")
    inserted = PDStructureElement(structure_type="Link")
    elem.append_kid_element(first)
    elem.append_kid_element(second)

    assert elem.insert_before_element(inserted, second) is True
    assert elem.insert_before_mcid(7, second) is True
    missing_before = PDStructureElement(structure_type="Table")
    missing_insert = PDStructureElement(structure_type="Span")
    assert elem.insert_before_element(missing_insert, missing_before) is False
    assert elem.insert_before_element(None, second) is False  # type: ignore[arg-type]
    assert elem.insert_before_mcid(9, None) is False

    kids = elem.get_kids()
    assert [kid.get_structure_type() for kid in kids if isinstance(kid, PDStructureElement)] == [
        "Span",
        "Link",
        "Figure",
    ]
    assert kids[2] == 7


def test_wave637_marked_content_object_appends_mcid_and_rejects_missing_mcid() -> None:
    props = COSDictionary()
    props.set_int(_name("MCID"), 12)
    marked_content = PDMarkedContent(_name("Span"), props)
    elem = PDStructureElement(structure_type="P")

    elem.append_kid_marked_content_object(None)
    elem.append_kid_marked_content_object(marked_content)

    assert elem.get_kids() == [12]

    missing_mcid = PDMarkedContent(_name("Span"), None)
    with pytest.raises(ValueError, match="MCID is negative"):
        elem.append_kid_marked_content_object(missing_mcid)
