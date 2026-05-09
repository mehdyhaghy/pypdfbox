from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSObject
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
    PDAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_marked_content_reference import (
    PDMarkedContentReference,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_object_reference import (
    PDObjectReference,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_node import (
    PDStructureNode,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (
    PDStructureTreeRoot,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.revisions import Revisions
from pypdfbox.pdmodel.documentinterchange.markedcontent.pd_marked_content import (
    PDMarkedContent,
)
from pypdfbox.pdmodel.pd_page import PDPage

_A = COSName.get_pdf_name("A")
_C = COSName.get_pdf_name("C")
_K = COSName.get_pdf_name("K")
_MCID = COSName.get_pdf_name("MCID")
_O = COSName.get_pdf_name("O")
_P = COSName.get_pdf_name("P")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")
_S = COSName.get_pdf_name("S")
_TYPE = COSName.TYPE  # type: ignore[attr-defined]


def test_structure_node_create_rejects_non_dictionary_and_unknown_type() -> None:
    with pytest.raises(TypeError, match="expects COSDictionary"):
        PDStructureNode.create(COSInteger.get(1))  # type: ignore[arg-type]

    raw = COSDictionary()
    raw.set_name(_TYPE, "NotStruct")
    with pytest.raises(ValueError, match="neither StructTreeRoot nor StructElem"):
        PDStructureNode.create(raw)


def test_structure_node_create_object_dereferences_indirect_dictionary() -> None:
    raw = COSDictionary()
    raw.set_name(_TYPE, "OBJR")
    wrapped = PDStructureNode("StructElem").create_object(
        COSObject(499, 0, resolved=raw)
    )

    assert isinstance(wrapped, PDObjectReference)
    assert wrapped.get_cos_object() is raw


def test_structure_node_append_none_and_remove_none_are_noops() -> None:
    node = PDStructureNode("StructElem")

    node.append_kid(None)

    assert node.get_cos_object().get_dictionary_object(_K) is None
    assert node.remove_kid(None) is False


def test_structure_node_removes_equivalent_mcid_from_array_and_compacts() -> None:
    node = PDStructureNode("StructElem")
    node.set_kids([1, 2])

    assert node.remove_kid(COSInteger.get(1)) is True

    assert node.get_kids() == [2]
    assert node.get_cos_object().get_dictionary_object(_K) == COSInteger.get(2)


def test_structure_node_append_and_remove_element_updates_parent_pointer() -> None:
    parent = PDStructureNode("StructElem")
    child = PDStructureElement(structure_type="P")

    parent.append_kid(child)
    assert child.get_parent() is parent.get_cos_object()

    assert parent.remove_kid(child) is True
    assert child.get_parent() is None


def test_structure_element_parent_node_dispatches_root_and_element() -> None:
    root_raw = COSDictionary()
    root_raw.set_name(_TYPE, "StructTreeRoot")
    child = PDStructureElement(structure_type="P")
    child.set_parent(root_raw)

    parent = child.get_parent_node()
    assert isinstance(parent, PDStructureTreeRoot)
    assert parent.get_cos_object() is root_raw

    parent_raw = COSDictionary()
    parent_raw.set_name(_TYPE, "StructElem")
    child.set_parent(parent_raw)
    parent = child.get_parent_node()
    assert isinstance(parent, PDStructureElement)
    assert parent.get_cos_object() is parent_raw


def test_structure_element_parent_node_none_for_missing_or_non_dictionary() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_parent_node() is None

    elem.get_cos_object().set_name(_P, "BadParent")
    assert elem.get_parent_node() is None


def test_structure_element_root_walk_and_attachment_predicate() -> None:
    root_raw = COSDictionary()
    root_raw.set_name(_TYPE, "StructTreeRoot")
    parent = PDStructureElement(structure_type="Div")
    parent.set_parent(root_raw)
    child = PDStructureElement(structure_type="P")
    child.set_parent(parent)

    root = child.get_structure_tree_root()
    assert isinstance(root, PDStructureTreeRoot)
    assert root.get_cos_object() is root_raw
    assert child.is_root_attached() is True


def test_structure_element_root_walk_stops_on_parent_cycle() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_parent(elem)

    assert elem.get_structure_tree_root() is None
    assert elem.is_root_attached() is False
    assert elem.get_role_map() == {}


def test_structure_element_field_presence_predicates_require_non_empty_values() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_id("")
    elem.set_title("")
    elem.set_language("")
    elem.set_alternate_description("")
    elem.set_expanded_form("")
    elem.set_actual_text("")

    assert elem.has_structure_type() is True
    assert elem.has_id() is False
    assert elem.has_title() is False
    assert elem.has_language() is False
    assert elem.has_alternate_description() is False
    assert elem.has_expanded_form() is False
    assert elem.has_actual_text() is False

    elem.set_element_identifier("id-1")
    elem.set_title("Title")
    elem.set_language("en-US")
    elem.set_alternate_description("Alt")
    elem.set_expanded_form("Expanded")
    elem.set_actual_text("Actual")
    elem.set_page(PDPage())

    assert elem.get_id() == "id-1"
    assert elem.get_element_identifier() == "id-1"
    assert elem.has_id() is True
    assert elem.has_title() is True
    assert elem.has_language() is True
    assert elem.has_alternate_description() is True
    assert elem.has_expanded_form() is True
    assert elem.has_actual_text() is True
    assert elem.has_page() is True


def test_structure_element_revision_increment_and_negative_rejected() -> None:
    elem = PDStructureElement(structure_type="P")

    elem.increment_revision_number()
    elem.increment_revision_number()

    assert elem.get_revision_number() == 2
    with pytest.raises(ValueError, match="revision number"):
        elem.set_revision_number(-1)


def test_structure_element_attribute_object_helpers_dispatch_and_filter_owner() -> None:
    elem = PDStructureElement(structure_type="P")
    layout = COSDictionary()
    layout.set_name(_O, "Layout")
    export = COSDictionary()
    export.set_name(_O, "HTML-4.01")
    ignored = COSInteger.get(7)
    elem.get_cos_object().set_item(_A, COSArray([layout, ignored, export]))

    attrs = elem.get_attribute_objects()

    assert [attr.get_owner() for attr in attrs] == ["Layout", "HTML-4.01"]
    assert elem.has_attribute_owner("HTML-4.01") is True
    assert elem.has_attribute_owner("List") is False
    assert elem.has_attribute_owner(None) is False  # type: ignore[arg-type]


def test_structure_element_set_attributes_none_removes_entry() -> None:
    elem = PDStructureElement(structure_type="P")
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    revs: Revisions[PDAttributeObject] = Revisions()
    revs.add_object(attr, 0)
    elem.set_attributes(revs)

    elem.set_attributes(None)

    assert elem.get_cos_object().get_dictionary_object(_A) is None


def test_structure_element_class_helpers_handle_single_name_and_clear() -> None:
    elem = PDStructureElement(structure_type="P")
    revs: Revisions[COSName] = Revisions()
    revs.add_object(COSName.get_pdf_name("Emphasis"), 0)

    elem.set_class_names(revs)

    assert elem.get_cos_object().get_dictionary_object(_C) == COSName.get_pdf_name(
        "Emphasis"
    )
    assert elem.get_class_names_as_strings() == ["Emphasis"]
    assert elem.has_class("Emphasis") is True
    assert elem.has_class(None) is False

    elem.set_class_names(None)
    assert elem.get_cos_object().get_dictionary_object(_C) is None


def test_structure_element_standard_type_and_level_predicates() -> None:
    root = COSDictionary()
    root.set_name(_TYPE, "StructTreeRoot")
    role_map = COSDictionary()
    role_map.set_name("CustomFigure", "Figure")
    root.set_item(_ROLE_MAP, role_map)
    elem = PDStructureElement(structure_type="CustomFigure")
    elem.set_parent(root)

    assert PDStructureElement.is_standard_structure_type("Figure") is True
    assert PDStructureElement.is_standard_structure_type(None) is False
    assert PDStructureElement.is_standard_structure_type("CustomFigure") is False
    assert elem.is_resolved_structure_type_standard() is True
    assert elem.is_illustration_level() is True
    assert elem.is_grouping_level() is False
    assert PDStructureElement(structure_type="P").is_block_level() is True
    assert PDStructureElement(structure_type="Span").is_inline_level() is True


def test_structure_element_typed_insert_and_remove_overloads() -> None:
    elem = PDStructureElement(structure_type="Div")
    head = PDStructureElement(structure_type="P")
    tail = PDStructureElement(structure_type="P")
    middle = PDStructureElement(structure_type="P")
    elem.set_kids([head, tail, 5])

    assert elem.insert_before_element(middle, tail) is True
    assert elem.insert_before_element(None, tail) is False  # type: ignore[arg-type]
    assert elem.insert_before_mcid(3, 5) is True
    assert elem.insert_before_mcid(9, None) is False

    assert elem.remove_kid_element(middle) is True
    assert middle.get_parent() is None
    assert elem.remove_kid_element(None) is False  # type: ignore[arg-type]
    assert elem.remove_kid_mcid(3) is True


def test_structure_element_marked_content_object_append_uses_mcid() -> None:
    props = COSDictionary()
    props.set_int(_MCID, 12)
    marked_content = PDMarkedContent(COSName.get_pdf_name("Span"), props)
    elem = PDStructureElement(structure_type="P")

    elem.append_kid_marked_content_object(marked_content)

    assert elem.get_kids() == [12]
    elem.append_kid_marked_content_object(None)
    assert elem.get_kids() == [12]


def test_structure_element_marked_content_object_rejects_missing_mcid() -> None:
    elem = PDStructureElement(structure_type="P")
    marked_content = PDMarkedContent(COSName.get_pdf_name("Span"), None)

    with pytest.raises(ValueError, match="MCID"):
        elem.append_kid_marked_content_object(marked_content)


def test_structure_element_typed_remove_overloads_for_mcr_and_objr() -> None:
    elem = PDStructureElement(structure_type="P")
    mcr = PDMarkedContentReference()
    objr = PDObjectReference()
    elem.append_kid_marked_content(mcr)
    elem.append_kid_object_reference(objr)

    assert elem.remove_kid_marked_content(mcr) is True
    assert elem.remove_kid_marked_content(None) is False
    assert elem.remove_kid_object_reference(objr) is True
    assert elem.remove_kid_object_reference(None) is False


def test_structure_element_direct_kid_filters_and_clear_kids() -> None:
    elem = PDStructureElement(structure_type="P")
    child = PDStructureElement(structure_type="Span")
    mcr = PDMarkedContentReference()
    mcr.set_mcid(4)
    objr = PDObjectReference()
    elem.set_kids([child, mcr, objr, 9, True])

    assert [kid.get_cos_object() for kid in elem.iter_kid_elements()] == [
        child.get_cos_object()
    ]
    assert [kid.get_cos_object() for kid in elem.iter_object_references()] == [
        objr.get_cos_object()
    ]
    marked_content_refs = elem.get_marked_content_references()
    assert len(marked_content_refs) == 2
    assert isinstance(marked_content_refs[0], PDMarkedContentReference)
    assert marked_content_refs[0].get_cos_object() is mcr.get_cos_object()
    assert marked_content_refs[0].get_mcid() == 4
    assert marked_content_refs[1] == 9
    assert elem.count_kids() == 5

    elem.clear_kids()
    assert elem.get_kids() == []
