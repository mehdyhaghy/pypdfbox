from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDParentTreeValue,
    PDStructureElement,
    PDStructureElementNumberTreeNode,
    PDStructureTreeRoot,
)
from pypdfbox.pdmodel.pd_page import PDPage

# ---------- /ParentTreeNextKey ----------


def test_parent_tree_next_key_default_negative_one() -> None:
    root = PDStructureTreeRoot()
    assert root.get_parent_tree_next_key() == -1


def test_parent_tree_next_key_round_trip() -> None:
    root = PDStructureTreeRoot()
    root.set_parent_tree_next_key(42)
    assert root.get_parent_tree_next_key() == 42
    root.set_parent_tree_next_key(0)
    assert root.get_parent_tree_next_key() == 0


# ---------- /ParentTree typed round-trip ----------


def test_parent_tree_round_trip_via_setter() -> None:
    root = PDStructureTreeRoot()
    assert root.get_parent_tree() is None

    elem = COSDictionary()
    elem.set_name(COSName.TYPE, "StructElem")  # type: ignore[attr-defined]
    parent_tree = PDStructureElementNumberTreeNode()
    parent_tree.set_numbers({1: elem})

    root.set_parent_tree(parent_tree)

    fetched = root.get_parent_tree()
    assert isinstance(fetched, PDStructureElementNumberTreeNode)
    assert fetched.get_value(1) is elem


def test_parent_tree_set_none_removes_entry() -> None:
    root = PDStructureTreeRoot()
    parent_tree = PDStructureElementNumberTreeNode()
    parent_tree.set_numbers({0: COSDictionary()})
    root.set_parent_tree(parent_tree)
    root.set_parent_tree(None)
    assert root.get_parent_tree() is None
    assert root.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("ParentTree")
    ) is None


def test_get_parent_tree_value_dictionary() -> None:
    root = PDStructureTreeRoot()
    elem = COSDictionary()
    elem.set_name(COSName.TYPE, "StructElem")  # type: ignore[attr-defined]
    parent_tree = PDStructureElementNumberTreeNode()
    parent_tree.set_numbers({7: elem})
    root.set_parent_tree(parent_tree)

    value = root.get_parent_tree_value(7)
    assert isinstance(value, PDParentTreeValue)
    assert value.get_cos_object() is elem


def test_get_parent_tree_value_array() -> None:
    root = PDStructureTreeRoot()
    arr = COSArray()
    arr.add(COSDictionary())
    parent_tree = PDStructureElementNumberTreeNode()
    parent_tree.set_numbers({0: arr})
    root.set_parent_tree(parent_tree)

    value = root.get_parent_tree_value(0)
    assert isinstance(value, PDParentTreeValue)
    assert value.get_cos_object() is arr


def test_get_parent_tree_value_returns_none_for_missing_tree() -> None:
    root = PDStructureTreeRoot()
    assert root.get_parent_tree_value(0) is None


def test_get_parent_tree_value_returns_none_for_missing_key() -> None:
    root = PDStructureTreeRoot()
    parent_tree = PDStructureElementNumberTreeNode()
    parent_tree.set_numbers({0: COSDictionary()})
    root.set_parent_tree(parent_tree)
    assert root.get_parent_tree_value(123) is None


# ---------- /K kids ----------


def test_get_kids_empty_when_k_absent() -> None:
    root = PDStructureTreeRoot()
    assert root.get_kids() == []


def test_set_kids_round_trip() -> None:
    root = PDStructureTreeRoot()
    child = COSDictionary()
    child.set_name(COSName.TYPE, "StructElem")  # type: ignore[attr-defined]
    root.set_kids([child])
    kids = root.get_kids()
    assert len(kids) == 1


# ---------- /RoleMap ----------


def test_role_map_round_trip_via_setter() -> None:
    root = PDStructureTreeRoot()
    role_map = {"MyHeader": "H1", "MyParagraph": "P", "MySpan": "Span"}
    root.set_role_map(role_map)
    fetched = root.get_role_map()
    assert fetched == role_map


def test_role_map_set_none_removes_entry() -> None:
    root = PDStructureTreeRoot()
    root.set_role_map({"A": "P"})
    root.set_role_map(None)
    assert root.get_role_map() == {}
    assert root.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("RoleMap")
    ) is None


# ---------- /ClassMap ----------


def test_class_map_round_trip_via_setter() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureClassMap,
    )

    root = PDStructureTreeRoot()
    attr = COSDictionary()
    attr.set_name(COSName.get_pdf_name("O"), "Layout")
    root.set_class_map({"MyClass": attr})
    fetched = root.get_class_map()
    assert isinstance(fetched, PDStructureClassMap)
    defs = fetched.get_class_definitions()
    assert "MyClass" in defs
    assert defs["MyClass"][0].get_cos_object() is attr


def test_class_map_empty_when_absent() -> None:
    root = PDStructureTreeRoot()
    assert root.get_class_map() is None


# ---------- /IDTree convenience lookup ----------


def test_get_struct_element_for_id_returns_none_when_id_tree_absent() -> None:
    root = PDStructureTreeRoot()
    assert root.get_struct_element_for_id("missing") is None


def test_get_struct_element_for_id_returns_none_for_unknown_id() -> None:
    root = PDStructureTreeRoot()
    # Empty IDTree dict still produces a typed wrapper but no values.
    root.get_cos_object().set_item(COSName.get_pdf_name("IDTree"), COSDictionary())
    assert root.get_struct_element_for_id("nope") is None


def test_get_struct_element_for_id_finds_element() -> None:
    root = PDStructureTreeRoot()
    elem = COSDictionary()
    elem.set_name(COSName.TYPE, "StructElem")  # type: ignore[attr-defined]
    elem.set_string(COSName.get_pdf_name("ID"), "elem-1")

    id_tree = COSDictionary()
    names = COSArray()
    from pypdfbox.cos import COSString
    names.add(COSString("elem-1"))
    names.add(elem)
    id_tree.set_item(COSName.get_pdf_name("Names"), names)
    root.get_cos_object().set_item(COSName.get_pdf_name("IDTree"), id_tree)

    fetched = root.get_struct_element_for_id("elem-1")
    assert isinstance(fetched, PDStructureElement)
    assert fetched.get_cos_object() is elem


# ---------- /ParentTree convenience lookup ----------


def test_get_struct_element_for_mcid_returns_none_when_parent_tree_absent() -> None:
    root = PDStructureTreeRoot()
    page = PDPage()
    page.set_struct_parents(0)
    assert root.get_struct_element_for_mcid(page, 0) is None


def test_get_struct_element_for_mcid_returns_none_when_struct_parents_unset() -> None:
    root = PDStructureTreeRoot()
    page = PDPage()
    # default get_struct_parents() returns -1 when /StructParents is absent.
    assert root.get_struct_element_for_mcid(page, 0) is None


def test_get_struct_element_for_mcid_finds_element() -> None:
    root = PDStructureTreeRoot()
    page = PDPage()
    page.set_struct_parents(3)

    elem = COSDictionary()
    elem.set_name(COSName.TYPE, "StructElem")  # type: ignore[attr-defined]

    arr = COSArray()
    arr.add(elem)  # mcid 0
    arr.add(elem)  # mcid 1

    parent_tree = PDStructureElementNumberTreeNode()
    parent_tree.set_numbers({3: arr})
    root.set_parent_tree(parent_tree)

    fetched = root.get_struct_element_for_mcid(page, 1)
    assert isinstance(fetched, PDStructureElement)
    assert fetched.get_cos_object() is elem


def test_get_struct_element_for_mcid_returns_none_for_out_of_range_mcid() -> None:
    root = PDStructureTreeRoot()
    page = PDPage()
    page.set_struct_parents(0)

    elem = COSDictionary()
    arr = COSArray()
    arr.add(elem)

    parent_tree = PDStructureElementNumberTreeNode()
    parent_tree.set_numbers({0: arr})
    root.set_parent_tree(parent_tree)

    assert root.get_struct_element_for_mcid(page, 5) is None
