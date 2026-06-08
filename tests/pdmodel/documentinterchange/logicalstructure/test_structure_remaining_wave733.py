from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSObject
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDAttributeObject,
    PDMarkedContentReference,
    PDObjectReference,
    PDStructureClassMap,
    PDStructureElement,
    PDStructureNode,
    PDStructureTreeRoot,
    Revisions,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (
    PDStructureElementNameTreeNode,
    PDStructureElementNumberTreeNode,
)

_A = COSName.get_pdf_name("A")
_C = COSName.get_pdf_name("C")
_K = COSName.get_pdf_name("K")
_O = COSName.get_pdf_name("O")
_P = COSName.get_pdf_name("P")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")
_TYPE = COSName.TYPE  # type: ignore[attr-defined]


def _attr(owner: str = "Layout") -> PDAttributeObject:
    dictionary = COSDictionary()
    dictionary.set_name(_O, owner)
    return PDAttributeObject(dictionary)


def _struct_dict(structure_type: str = "P") -> COSDictionary:
    dictionary = COSDictionary()
    dictionary.set_name(_TYPE, "StructElem")
    dictionary.set_name("S", structure_type)
    return dictionary


def test_node_create_object_dereferences_cos_object_and_rejects_unknown() -> None:
    node = PDStructureNode("StructElem")
    elem_dict = _struct_dict("H1")
    mcr_dict = COSDictionary()
    mcr_dict.set_name(_TYPE, "MCR")
    objr_dict = COSDictionary()
    objr_dict.set_name(_TYPE, "OBJR")
    unknown = COSDictionary()
    unknown.set_name(_TYPE, "Mystery")

    elem = node.create_object(COSObject(10, resolved=elem_dict))
    mcr = node.create_object(COSObject(11, resolved=mcr_dict))
    objr = node.create_object(COSObject(12, resolved=objr_dict))

    assert isinstance(elem, PDStructureElement)
    assert elem.get_cos_object() is elem_dict
    assert isinstance(mcr, PDMarkedContentReference)
    assert mcr.get_cos_object() is mcr_dict
    assert isinstance(objr, PDObjectReference)
    assert objr.get_cos_object() is objr_dict
    assert node.create_object(COSObject(13, resolved=unknown)) is None
    assert node.create_object(COSInteger.get(42)) == 42
    assert node.create_object(COSName.get_pdf_name("NotAKid")) is None


def test_node_objectable_and_insert_null_edges_preserve_kids() -> None:
    node = PDStructureNode("StructElem")
    first = COSDictionary()
    second = COSDictionary()
    node.set_kids([first, second])

    assert node.remove_objectable_kid(first) is True
    assert node.insert_before(COSDictionary(), None) is False
    assert node.insert_before(None, second) is False
    kids = node.get_kids()
    assert len(kids) == 1
    assert kids[0].get_cos_object() is second


def test_node_count_and_contains_handle_single_array_and_int_edges() -> None:
    node = PDStructureNode("StructElem")
    assert node.is_kids_empty() is True
    assert node.get_kids_count() == 0
    assert node.contains_kid(None) is False

    node.append_kid(7)
    assert node.has_kids() is True
    assert node.is_kids_empty() is False
    assert node.get_kids_count() == 1
    assert node.contains_kid(COSInteger.get(7)) is True

    raw_k = node.get_cos_object().get_dictionary_object(_K)
    assert raw_k == COSInteger.get(7)

    node.append_kid(8)
    assert node.get_kids_count() == 2
    assert node.remove_kid(COSInteger.get(7)) is True
    assert node.get_kids() == [8]


def test_class_map_appends_to_existing_array_and_handles_indirect_or_bad_entries() -> None:
    raw = COSDictionary()
    array = COSArray()
    first = _attr("Layout")
    array.add(first.get_cos_object())
    raw.set_item("Existing", array)
    indirect_attr = _attr("List")
    raw.set_item("Indirect", COSObject(20, resolved=indirect_attr.get_cos_object()))
    raw.set_item("Bad", COSName.get_pdf_name("NotAttributes"))

    class_map = PDStructureClassMap(raw)
    class_map.add_class("Existing", [_attr("Table"), _attr("PrintField")])

    assert [attr.get_owner() for attr in class_map.get_class("Existing")] == [
        "Layout",
        "Table",
        "PrintField",
    ]
    assert class_map.get_class("Indirect")[0].get_owner() == "List"
    assert class_map.get_class("Bad") == []
    assert "Bad" not in class_map.get_class_definitions()
    assert repr(class_map) == "PDStructureClassMap(size=3)"


def test_tree_root_presence_predicates_class_map_removal_and_parent_lookup_edges() -> None:
    root = PDStructureTreeRoot()
    assert root.has_id_tree() is False
    assert root.has_parent_tree() is False
    assert root.has_role_map() is False
    assert root.has_class_map() is False
    assert root.has_kids() is False
    assert root.count_kids() == 0

    root.get_cos_object().set_item("IDTree", COSDictionary())
    root.get_cos_object().set_item("ParentTree", COSDictionary())
    root.get_cos_object().set_item(_ROLE_MAP, COSDictionary())
    root.set_class_map({"Tmp": _attr()})
    root.set_class_map({})

    assert root.has_id_tree() is True
    assert root.has_parent_tree() is True
    assert root.has_role_map() is True
    assert root.has_class_map() is False

    class Page:
        def get_struct_parents(self) -> int:
            return 3

    values = COSArray()
    values.add(_struct_dict("P"))
    parent_tree = PDStructureElementNumberTreeNode()
    parent_tree.set_numbers({3: values})
    root.set_parent_tree(parent_tree)

    assert root.get_struct_element_for_mcid(Page(), -1) is None
    assert root.get_struct_element_for_mcid(Page(), 1) is None
    found = root.get_struct_element_for_mcid(Page(), 0)
    assert isinstance(found, PDStructureElement)
    assert found.get_structure_type() == "P"


def test_tree_root_descendants_find_by_role_and_number_tree_helpers() -> None:
    root = PDStructureTreeRoot()
    root.set_role_map({"Fancy": "P"})
    parent = PDStructureElement(structure_type="Sect")
    child = PDStructureElement(structure_type="Fancy")
    leaf = PDStructureElement(structure_type="Span")

    root.append_kid(parent)
    parent.append_kid(child)
    child.append_kid(leaf)

    assert [item.get_structure_type() for item in root.iter_descendants()] == [
        "Sect",
        "Fancy",
        "Span",
    ]
    assert root.find_first_by_role("P").get_cos_object() is child.get_cos_object()
    assert list(root.find_by_role("Missing")) == []
    assert root.resolve_role_map("AlreadyMissing") == "AlreadyMissing"

    names = PDStructureElementNameTreeNode()
    assert names.convert_value_to_cos(parent) is parent.get_cos_object()
    numbers = PDStructureElementNumberTreeNode()
    assert numbers.convert_cos_to_value(values := COSArray()) is values
    assert numbers.convert_value_to_cos(parent) is parent.get_cos_object()


def test_element_parent_resolution_depth_cap_cycle_and_type_predicates() -> None:
    leaf = PDStructureElement(structure_type="Custom0")
    node = leaf.get_cos_object()
    for _ in range(16):
        parent = COSDictionary()
        parent.set_name(_TYPE, "StructElem")
        node.set_item(_P, parent)
        node = parent

    assert leaf.get_role_map() == {}
    assert leaf.get_structure_tree_root() is None

    role_root = COSDictionary()
    role_root.set_name(_TYPE, "StructTreeRoot")
    role_map = COSDictionary()
    for index in range(17):
        role_map.set_name(f"Custom{index}", f"Custom{index + 1}")
    role_root.set_item(_ROLE_MAP, role_map)
    role_leaf = PDStructureElement(structure_type="Custom0")
    role_leaf.set_parent(role_root)

    # Single-hop resolution (matches upstream getStandardStructureType):
    # Custom0 -> Custom1 and stops; the deep chain is never chased.
    assert role_leaf.get_standard_structure_type() == "Custom1"
    assert PDStructureElement.is_standard_structure_type(None) is False
    assert PDStructureElement.is_standard_structure_type("P") is True


def test_element_presence_aliases_clear_kids_and_class_revision_edges() -> None:
    elem = PDStructureElement(structure_type="Figure")
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
    assert elem.is_illustration_level() is True

    elem.set_alt_text("diagram")
    assert elem.get_alt_text() == "diagram"

    elem.append_kid(PDStructureElement(structure_type="Span"))
    assert elem.count_kids() == 1
    elem.clear_kids()
    assert elem.get_kids() == []

    revs: Revisions[object] = Revisions()
    revs.add_object("LooseClass", 0)
    elem.set_class_names(revs)  # type: ignore[arg-type]
    assert elem.get_class_names_as_strings() == ["LooseClass"]

    elem.add_class_name(None)
    elem.remove_class_name(None)
    elem.class_name_changed(None)
    elem.remove_class_name("Missing")
    elem.class_name_changed("Missing")
    assert elem.get_class_names_as_strings() == ["LooseClass"]


def test_element_typed_kid_filters_and_marked_content_object_edges() -> None:
    elem = PDStructureElement(structure_type="P")
    child = PDStructureElement(structure_type="Span")
    mcr = PDMarkedContentReference()
    objr = PDObjectReference()

    elem.append_kid_element(child)
    elem.append_kid_marked_content(mcr)
    elem.append_kid_object_reference(objr)
    elem.append_kid_mcid(9)
    elem.append_kid_marked_content(None)
    elem.append_kid_object_reference(None)

    assert list(elem.iter_kid_elements())[0].get_cos_object() is child.get_cos_object()
    assert list(elem.iter_object_references())[0].get_cos_object() is objr.get_cos_object()
    marked_refs = elem.get_marked_content_references()
    assert isinstance(marked_refs[0], PDMarkedContentReference)
    assert marked_refs[0].get_cos_object() is mcr.get_cos_object()
    assert marked_refs[1] == 9

    class MarkedContent:
        def __init__(self, mcid: int) -> None:
            self._mcid = mcid

        def get_mcid(self) -> int:
            return self._mcid

    elem.append_kid_marked_content_object(MarkedContent(10))
    assert elem.get_marked_content_references()[-1] == 10

    with pytest.raises(ValueError, match="MCID is negative"):
        elem.append_kid_mcid(-1)
    with pytest.raises(ValueError, match="MCID is negative or doesn't exist"):
        elem.append_kid_marked_content_object(MarkedContent(-1))


def test_element_attribute_and_class_change_rewrite_bare_entries() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.remove_attribute(None)
    elem.attribute_changed(None)
    elem.remove_attribute(_attr("Missing"))

    attr = _attr("Layout")
    elem.get_cos_object().set_item(_A, attr.get_cos_object())
    elem.set_revision_number(6)
    elem.attribute_changed(attr)

    assert isinstance(elem.get_cos_object().get_dictionary_object(_A), COSArray)
    assert elem.get_attributes().get_revision_number(attr) == 6

    elem.get_cos_object().set_item(_C, COSName.get_pdf_name("Emphasis"))
    elem.set_revision_number(8)
    elem.class_name_changed("Emphasis")

    assert isinstance(elem.get_cos_object().get_dictionary_object(_C), COSArray)
    assert elem.get_class_names().get_revision_number(COSName.get_pdf_name("Emphasis")) == 8
