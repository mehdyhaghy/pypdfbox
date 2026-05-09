from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
    PDAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (
    PDStructureElementNameTreeNode,
    PDStructureElementNumberTreeNode,
    PDStructureTreeRoot,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.revisions import Revisions

_A = COSName.get_pdf_name("A")
_C = COSName.get_pdf_name("C")
_O = COSName.get_pdf_name("O")
_P = COSName.get_pdf_name("P")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")
_TYPE = COSName.TYPE  # type: ignore[attr-defined]


def _root_with_role_map(entries: dict[str, str]) -> COSDictionary:
    root = COSDictionary()
    root.set_name(_TYPE, "StructTreeRoot")
    role_map = COSDictionary()
    for key, value in entries.items():
        role_map.set_name(key, value)
    root.set_item(_ROLE_MAP, role_map)
    return root


def test_role_map_and_parent_walk_depth_caps_return_current_state() -> None:
    role_map = {f"Custom{i}": f"Custom{i + 1}" for i in range(20)}
    elem = PDStructureElement(structure_type="Custom0")
    elem.set_parent(_root_with_role_map(role_map))

    assert elem.get_standard_structure_type() == "Custom16"

    leaf = PDStructureElement(structure_type="P")
    node = leaf.get_cos_object()
    for _ in range(17):
        parent = COSDictionary()
        parent.set_name(_TYPE, "StructElem")
        node.set_item(_P, parent)
        node = parent

    assert leaf.get_role_map() == {}
    assert leaf.get_structure_tree_root() is None


def test_single_non_name_class_revision_is_written_as_name() -> None:
    elem = PDStructureElement(structure_type="P")
    revs: Revisions[object] = Revisions()
    revs.add_object("CustomClass", 0)

    elem.set_class_names(revs)  # type: ignore[arg-type]

    assert elem.get_cos_object().get_dictionary_object(_C) == COSName.get_pdf_name(
        "CustomClass"
    )


def test_class_names_as_strings_keeps_raw_string_entries() -> None:
    elem = PDStructureElement(structure_type="P")
    raw = COSArray()
    raw.add(COSName.get_pdf_name("NameClass"))
    raw.add("StringClass")  # type: ignore[arg-type]
    elem.get_cos_object().set_item(_C, raw)

    assert elem.get_class_names_as_strings() == ["NameClass", "StringClass"]


def test_typed_append_null_guards_are_noops() -> None:
    elem = PDStructureElement(structure_type="P")

    elem.append_kid_marked_content(None)
    elem.append_kid_object_reference(None)

    assert elem.get_kids() == []


def test_attribute_null_guards_and_bare_attribute_revision_rewrite() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.remove_attribute(None)
    elem.attribute_changed(None)

    attr_dict = COSDictionary()
    attr_dict.set_name(_O, "Layout")
    attr = PDAttributeObject(attr_dict)
    elem.get_cos_object().set_item(_A, attr_dict)
    elem.set_revision_number(5)

    elem.attribute_changed(attr)

    rewritten = elem.get_cos_object().get_dictionary_object(_A)
    assert isinstance(rewritten, COSArray)
    assert elem.get_attributes().get_revision_number(attr) == 5


def test_single_class_name_changed_rewrites_to_revision_array() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.get_cos_object().set_item(_C, COSName.get_pdf_name("Important"))
    elem.set_revision_number(7)

    elem.class_name_changed("Important")

    rewritten = elem.get_cos_object().get_dictionary_object(_C)
    assert isinstance(rewritten, COSArray)
    assert elem.get_class_names().get_revision_number(COSName.get_pdf_name("Important")) == 7


def test_structure_tree_root_empty_class_map_and_none_kid_clear_branches() -> None:
    root = PDStructureTreeRoot()
    root.set_class_map({"Transient": PDAttributeObject()})

    root.set_class_map({})
    root.append_kid(None)

    assert root.get_class_map() is None
    assert root.get_kids() == []


def test_structure_tree_root_lookup_rejects_null_id_and_non_array_mcid_entry() -> None:
    class PageLike:
        def get_struct_parents(self) -> int:
            return 9

    root = PDStructureTreeRoot()
    parent_tree = PDStructureElementNumberTreeNode()
    parent_tree.set_numbers({9: COSInteger.get(1)})
    root.set_parent_tree(parent_tree)

    assert root.get_struct_element_for_id(None) is None  # type: ignore[arg-type]
    assert root.get_struct_element_for_mcid(PageLike(), 0) is None


def test_structure_tree_root_resolve_role_map_stops_when_mapping_missing() -> None:
    root = PDStructureTreeRoot()
    root.set_role_map({"Custom": "StillCustom"})

    assert root.resolve_role_map("StillCustom") == "StillCustom"


def test_structure_tree_node_helpers_validate_and_create_child_nodes() -> None:
    names = PDStructureElementNameTreeNode()

    with pytest.raises(TypeError, match="IDTree value must be COSDictionary"):
        names.convert_cos_to_value(COSName.get_pdf_name("NotADictionary"))

    assert isinstance(
        names.create_child_node(COSDictionary()), PDStructureElementNameTreeNode
    )
    assert isinstance(
        PDStructureElementNumberTreeNode().create_child_node(COSDictionary()),
        PDStructureElementNumberTreeNode,
    )
