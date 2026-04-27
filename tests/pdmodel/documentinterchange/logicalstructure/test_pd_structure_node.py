from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
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

_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_K = COSName.get_pdf_name("K")


# ---------- PDStructureNode ----------


def test_structure_node_fresh_has_no_type() -> None:
    node = PDStructureNode()
    assert node.get_cos_object().get_name(_TYPE) is None
    assert node.get_kids() == []


def test_structure_node_with_type_string_sets_type() -> None:
    node = PDStructureNode("StructElem")
    assert node.get_type() == "StructElem"


def test_structure_node_wraps_existing_dictionary() -> None:
    dic = COSDictionary()
    dic.set_name(_TYPE, "StructTreeRoot")
    node = PDStructureNode(dic)
    assert node.get_cos_object() is dic
    assert node.get_type() == "StructTreeRoot"


def test_structure_node_append_kid_then_get_kids_round_trip() -> None:
    node = PDStructureNode("StructElem")
    child = COSDictionary()
    node.append_kid(child)
    kids = node.get_kids()
    assert kids == [child]


def test_structure_node_append_two_kids_promotes_to_array() -> None:
    node = PDStructureNode("StructElem")
    child_a = COSDictionary()
    child_b = COSDictionary()
    node.append_kid(child_a)
    node.append_kid(child_b)
    kids = node.get_kids()
    assert kids == [child_a, child_b]


def test_structure_node_remove_kid_removes() -> None:
    node = PDStructureNode("StructElem")
    child_a = COSDictionary()
    child_b = COSDictionary()
    node.append_kid(child_a)
    node.append_kid(child_b)
    assert node.remove_kid(child_a) is True
    assert node.get_kids() == [child_b]


def test_structure_node_remove_only_kid_clears_k() -> None:
    node = PDStructureNode("StructElem")
    child = COSDictionary()
    node.append_kid(child)
    assert node.remove_kid(child) is True
    assert node.get_cos_object().get_dictionary_object(_K) is None


def test_structure_node_remove_unknown_kid_returns_false() -> None:
    node = PDStructureNode("StructElem")
    node.append_kid(COSDictionary())
    assert node.remove_kid(COSDictionary()) is False


def test_structure_node_set_kids_clears_when_empty() -> None:
    node = PDStructureNode("StructElem")
    node.append_kid(COSDictionary())
    node.set_kids([])
    assert node.get_kids() == []


def test_structure_node_get_kids_dispatches_mixed_k_array() -> None:
    node = PDStructureNode("StructElem")
    elem = COSDictionary()
    elem.set_name(_TYPE, "StructElem")
    mcr = COSDictionary()
    mcr.set_name(_TYPE, "MCR")
    objr = COSDictionary()
    objr.set_name(_TYPE, "OBJR")
    unknown = COSDictionary()
    unknown.set_name(_TYPE, "SomethingElse")
    arr = COSArray([elem, mcr, objr, COSInteger.get(12), unknown])
    node.get_cos_object().set_item(_K, arr)

    kids = node.get_kids()

    assert isinstance(kids[0], PDStructureElement)
    assert kids[0].get_cos_object() is elem
    assert isinstance(kids[1], PDMarkedContentReference)
    assert kids[1].get_cos_object() is mcr
    assert isinstance(kids[2], PDObjectReference)
    assert kids[2].get_cos_object() is objr
    assert kids[3] == 12
    assert kids[4] is unknown


def test_structure_node_append_and_remove_typed_kids() -> None:
    node = PDStructureNode("StructElem")
    elem = PDStructureElement(structure_type="P")
    mcr = PDMarkedContentReference()
    objr = PDObjectReference()

    node.append_kid(elem)
    node.append_kid(mcr)
    node.append_kid(objr)
    node.append_kid(4)

    raw_k = node.get_cos_object().get_dictionary_object(_K)
    assert isinstance(raw_k, COSArray)
    assert raw_k.get_object(0) is elem.get_cos_object()
    assert raw_k.get_object(1) is mcr.get_cos_object()
    assert raw_k.get_object(2) is objr.get_cos_object()
    assert raw_k.get_object(3) == COSInteger.get(4)
    assert [type(kid) for kid in node.get_kids()] == [
        PDStructureElement,
        PDMarkedContentReference,
        PDObjectReference,
        int,
    ]

    assert node.remove_kid(mcr) is True
    assert node.remove_kid(4) is True
    kids = node.get_kids()
    assert len(kids) == 2
    assert isinstance(kids[0], PDStructureElement)
    assert isinstance(kids[1], PDObjectReference)


# ---------- PDStructureNode.insert_before ----------


def test_structure_node_insert_before_into_array() -> None:
    node = PDStructureNode("StructElem")
    a, b, c = COSDictionary(), COSDictionary(), COSDictionary()
    node.set_kids([a, c])
    new_kid = COSDictionary()
    assert node.insert_before(new_kid, c) is True
    kids = node.get_kids()
    assert kids == [a, new_kid, c]
    # The 'b' wasn't used — keep this branch readable.
    assert b is not new_kid


def test_structure_node_insert_before_promotes_single_kid_to_array() -> None:
    node = PDStructureNode("StructElem")
    only = COSDictionary()
    node.append_kid(only)
    # /K is currently a single dict (not an array).
    assert isinstance(node.get_cos_object().get_dictionary_object(_K), COSDictionary)

    new_kid = COSDictionary()
    assert node.insert_before(new_kid, only) is True
    raw_k = node.get_cos_object().get_dictionary_object(_K)
    assert isinstance(raw_k, COSArray)
    assert raw_k.get_object(0) is new_kid
    assert raw_k.get_object(1) is only


def test_structure_node_insert_before_unknown_returns_false() -> None:
    node = PDStructureNode("StructElem")
    node.append_kid(COSDictionary())
    assert node.insert_before(COSDictionary(), COSDictionary()) is False


def test_structure_node_insert_before_empty_returns_false() -> None:
    node = PDStructureNode("StructElem")
    assert node.insert_before(COSDictionary(), COSDictionary()) is False


def test_structure_node_insert_before_typed_kids() -> None:
    node = PDStructureNode("StructElem")
    head = PDStructureElement(structure_type="P")
    tail = PDStructureElement(structure_type="P")
    middle = PDStructureElement(structure_type="P")
    node.set_kids([head, tail])

    assert node.insert_before(middle, tail) is True
    raw_k = node.get_cos_object().get_dictionary_object(_K)
    assert isinstance(raw_k, COSArray)
    assert raw_k.get_object(0) is head.get_cos_object()
    assert raw_k.get_object(1) is middle.get_cos_object()
    assert raw_k.get_object(2) is tail.get_cos_object()


def test_structure_node_insert_before_int_mcid_anchor() -> None:
    node = PDStructureNode("StructElem")
    node.set_kids([1, 2, 3])
    assert node.insert_before(99, 2) is True
    assert node.get_kids() == [1, 99, 2, 3]


# ---------- PDStructureNode.create dispatch ----------


def test_structure_node_create_dispatches_struct_tree_root() -> None:
    dic = COSDictionary()
    dic.set_name(_TYPE, "StructTreeRoot")
    result = PDStructureNode.create(dic)
    assert isinstance(result, PDStructureTreeRoot)


def test_structure_node_create_dispatches_struct_elem() -> None:
    dic = COSDictionary()
    dic.set_name(_TYPE, "StructElem")
    result = PDStructureNode.create(dic)
    assert isinstance(result, PDStructureElement)


def test_structure_node_create_dispatches_no_type_to_struct_elem() -> None:
    dic = COSDictionary()
    result = PDStructureNode.create(dic)
    assert isinstance(result, PDStructureElement)


# ---------- PDAttributeObject ----------


def test_attribute_object_owner_round_trip() -> None:
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    assert attr.get_owner() == "Layout"


def test_attribute_object_create_returns_generic_for_unknown_owner() -> None:
    dic = COSDictionary()
    dic.set_name(COSName.get_pdf_name("O"), "ZZUnknownOwnerZZ")
    result = PDAttributeObject.create(dic)
    assert isinstance(result, PDAttributeObject)
    assert result.get_owner() == "ZZUnknownOwnerZZ"


def test_attribute_object_is_empty_only_owner() -> None:
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    assert attr.is_empty() is True


# ---------- Revisions ----------


def test_revisions_add_object_size_and_indexed_access() -> None:
    revs: Revisions[str] = Revisions()
    revs.add_object("a", 0)
    revs.add_object("b", 1)
    assert revs.size() == 2
    assert revs.get_object_at(1) is not None
    # The COS-side string is a COSString — check the integer revision
    assert revs.get_revision_number_at(1) == 1
    assert revs.get_revision_number_at(0) == 0


def test_revisions_round_trip_through_cos_array() -> None:
    revs: Revisions[str] = Revisions()
    revs.add_object("x", 3)
    arr = revs.to_cos_array()
    rebuilt: Revisions[str] = Revisions(arr)
    assert rebuilt.size() == 1
    assert rebuilt.get_revision_number_at(0) == 3
