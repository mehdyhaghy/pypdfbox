from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDAttributeObject,
    PDStructureClassMap,
    PDStructureElement,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (
    PDStructureElementNameTreeNode,
    PDStructureElementNumberTreeNode,
    PDStructureTreeRoot,
)


def _name(name: str) -> COSName:
    return COSName.get_pdf_name(name)


def _struct_elem_dict(structure_type: str = "P") -> COSDictionary:
    elem = COSDictionary()
    elem.set_name(COSName.TYPE, "StructElem")  # type: ignore[attr-defined]
    elem.set_name(_name("S"), structure_type)
    return elem


def test_wave530_raw_k_setter_round_trips_and_none_removes_entry() -> None:
    root = PDStructureTreeRoot()
    child = _struct_elem_dict("H1")

    root.set_k(child)

    assert root.get_k() is child
    kids = root.get_kids()
    assert len(kids) == 1
    assert isinstance(kids[0], PDStructureElement)

    root.set_k(None)

    assert root.get_k() is None
    assert root.get_kids() == []


def test_wave530_role_map_reads_string_values_and_depth_cap_stops_chain() -> None:
    root = PDStructureTreeRoot()
    role_map = COSDictionary()
    role_map.set_item("Ignored", COSString("P"))
    for index in range(17):
        role_map.set_name(f"Custom{index}", f"Custom{index + 1}")
    role_map.set_name("Custom17", "P")
    root.get_cos_object().set_item(_name("RoleMap"), role_map)

    assert root.get_role_map()["Ignored"] == "P"
    assert root.resolve_role_map("Custom0") == "Custom16"
    assert root.resolve_role_map(None) is None


def test_wave530_set_class_map_accepts_wrappers_lists_and_empty_removal() -> None:
    root = PDStructureTreeRoot()
    first = PDAttributeObject()
    first.set_owner("Layout")
    second = PDAttributeObject()
    second.set_owner("Layout")

    root.set_class_map({"Pair": [first, second]})

    class_map = root.get_class_map()
    assert class_map is not None
    definitions = class_map.get_class_definitions()
    assert len(definitions["Pair"]) == 2

    empty_map = PDStructureClassMap()
    root.set_class_map(empty_map)

    assert root.get_class_map() is None
    assert root.has_class_map() is False


def test_wave530_id_tree_setter_accepts_wrapper_and_raw_dictionary() -> None:
    root = PDStructureTreeRoot()
    elem = PDStructureElement(structure_type="P")
    id_tree = PDStructureElementNameTreeNode()
    id_tree.set_names({"para-1": elem})

    root.set_id_tree(id_tree)

    fetched = root.get_struct_element_for_id("para-1")
    assert isinstance(fetched, PDStructureElement)
    assert fetched.get_cos_object() is elem.get_cos_object()

    raw_tree = COSDictionary()
    root.set_id_tree(raw_tree)

    assert root.get_cos_object().get_dictionary_object(_name("IDTree")) is raw_tree
    assert root.get_struct_element_for_id("para-1") is None

    root.set_id_tree(None)
    assert root.get_id_tree() is None


def test_wave530_parent_tree_lookup_rejects_non_container_values() -> None:
    root = PDStructureTreeRoot()
    parent_tree = PDStructureElementNumberTreeNode()
    parent_tree.set_numbers({2: COSInteger.get(7)})
    root.set_parent_tree(parent_tree)

    assert root.get_parent_tree_value(2) is None
    assert root.get_struct_element_for_mcid(None, 0) is None


def test_wave530_mcid_lookup_rejects_non_dictionary_array_entries() -> None:
    class PageLike:
        def get_struct_parents(self) -> int:
            return 3

    root = PDStructureTreeRoot()
    values = COSArray()
    values.add(COSString("not-a-struct-element"))
    parent_tree = PDStructureElementNumberTreeNode()
    parent_tree.set_numbers({3: values})
    root.set_parent_tree(parent_tree)

    assert root.get_struct_element_for_mcid(PageLike(), 0) is None


def test_wave530_build_parent_tree_reuses_existing_numbers_and_handles_empty_pages() -> None:
    class PageLike:
        def __init__(self, struct_parents: int | None) -> None:
            self._struct_parents = struct_parents

        def get_struct_parents(self) -> int | None:
            return self._struct_parents

    root = PDStructureTreeRoot()
    existing_array = COSArray()
    existing = PDStructureElementNumberTreeNode()
    existing.set_numbers({4: existing_array})
    root.set_parent_tree(existing)

    tree = root.build_parent_tree([PageLike(None), PageLike(-1), PageLike(4), PageLike(6)])

    nums = tree.get_numbers()
    assert nums is not None
    assert nums[4] is existing_array
    assert isinstance(nums[6], COSArray)
    assert root.get_parent_tree_next_key() == 7

    empty_root = PDStructureTreeRoot()
    empty_tree = empty_root.build_parent_tree(None)
    assert empty_tree.get_numbers() == {}
    assert empty_root.get_parent_tree_next_key() == 0
