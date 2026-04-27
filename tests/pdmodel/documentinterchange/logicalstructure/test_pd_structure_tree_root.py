from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDMarkInfo,
    PDStructureElement,
    PDStructureElementNumberTreeNode,
    PDStructureTreeRoot,
)


def test_fresh_struct_tree_root_has_correct_type() -> None:
    root = PDStructureTreeRoot()
    assert root.get_cos_object().get_name(COSName.TYPE) == "StructTreeRoot"  # type: ignore[attr-defined]


def test_struct_tree_root_role_map_round_trip() -> None:
    root = PDStructureTreeRoot()
    role_map = {"MyHeader": "H1", "MyParagraph": "P"}
    root.set_role_map(role_map)
    fetched = root.get_role_map()
    assert fetched == role_map


def test_struct_tree_root_id_tree_returns_typed_node() -> None:
    root = PDStructureTreeRoot()
    assert root.get_id_tree() is None
    root.get_cos_object().set_item(COSName.get_pdf_name("IDTree"), COSDictionary())
    id_tree = root.get_id_tree()
    assert isinstance(id_tree, PDNameTreeNode)


def test_struct_tree_root_parent_tree_returns_typed_number_tree() -> None:
    root = PDStructureTreeRoot()
    assert root.get_parent_tree() is None

    parent_tree = COSDictionary()
    nums = COSArray()
    nums.add(COSInteger.get(0))
    struct_elem = COSDictionary()
    struct_elem.set_name(COSName.TYPE, "StructElem")  # type: ignore[attr-defined]
    nums.add(struct_elem)
    parent_tree.set_item(COSName.get_pdf_name("Nums"), nums)

    root.get_cos_object().set_item(COSName.get_pdf_name("ParentTree"), parent_tree)
    wrapped = root.get_parent_tree()

    assert isinstance(wrapped, PDStructureElementNumberTreeNode)
    assert wrapped.get_value(0) is struct_elem


def test_struct_tree_root_set_parent_tree_accepts_typed_number_tree() -> None:
    root = PDStructureTreeRoot()
    parent_tree = PDStructureElementNumberTreeNode()
    struct_elem = COSDictionary()
    parent_tree.set_numbers({5: struct_elem})

    root.set_parent_tree(parent_tree)

    wrapped = root.get_parent_tree()
    assert isinstance(wrapped, PDStructureElementNumberTreeNode)
    assert wrapped.get_value(5) is struct_elem


def test_struct_tree_root_parent_tree_next_key_round_trip() -> None:
    root = PDStructureTreeRoot()
    assert root.get_parent_tree_next_key() == 0
    root.set_parent_tree_next_key(7)
    assert root.get_parent_tree_next_key() == 7


def test_struct_tree_root_class_map_round_trip() -> None:
    root = PDStructureTreeRoot()
    attr = COSDictionary()
    attr.set_name(COSName.get_pdf_name("O"), "Layout")
    root.set_class_map({"MyClass": attr})
    fetched = root.get_class_map()
    assert "MyClass" in fetched
    assert fetched["MyClass"] is attr


def test_struct_element_constructor_sets_structure_type() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_cos_object().get_name(COSName.TYPE) == "StructElem"  # type: ignore[attr-defined]
    assert elem.get_structure_type() == "P"


def test_struct_element_text_round_trip() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_alternate_description("Heading")
    elem.set_language("en-US")
    elem.set_actual_text("Hello world")
    elem.set_title("My Heading")
    elem.set_expanded_form("ABC")
    elem.set_id("elem-1")
    elem.set_revision_number(2)

    assert elem.get_alternate_description() == "Heading"
    assert elem.get_language() == "en-US"
    assert elem.get_actual_text() == "Hello world"
    assert elem.get_title() == "My Heading"
    assert elem.get_expanded_form() == "ABC"
    assert elem.get_id() == "elem-1"
    assert elem.get_revision_number() == 2


def test_struct_element_append_kid_round_trip() -> None:
    elem = PDStructureElement(structure_type="P")
    child = COSDictionary()
    child.set_name(COSName.get_pdf_name("S"), "Span")
    elem.append_kid(child)

    kids = elem.get_kids()
    assert len(kids) == 1
    assert kids[0] is child

    second = COSDictionary()
    second.set_name(COSName.get_pdf_name("S"), "Span")
    elem.append_kid(second)
    kids = elem.get_kids()
    assert len(kids) == 2
    assert kids[0] is child
    assert kids[1] is second


def test_mark_info_boolean_round_trip() -> None:
    mi = PDMarkInfo()
    assert not mi.is_marked()
    assert not mi.is_user_properties()
    assert not mi.is_suspects()

    mi.set_marked(True)
    mi.set_user_properties(True)
    mi.set_suspects(True)

    assert mi.is_marked()
    assert mi.is_user_properties()
    assert mi.is_suspects()
