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
    assert len(kids) == 1
    assert isinstance(kids[0], PDStructureElement)
    assert kids[0].get_cos_object() is child


def test_structure_node_append_two_kids_promotes_to_array() -> None:
    node = PDStructureNode("StructElem")
    child_a = COSDictionary()
    child_b = COSDictionary()
    node.append_kid(child_a)
    node.append_kid(child_b)
    kids = node.get_kids()
    assert [kid.get_cos_object() for kid in kids] == [child_a, child_b]


def test_structure_node_remove_kid_removes() -> None:
    node = PDStructureNode("StructElem")
    child_a = COSDictionary()
    child_b = COSDictionary()
    node.append_kid(child_a)
    node.append_kid(child_b)
    assert node.remove_kid(child_a) is True
    kids = node.get_kids()
    assert len(kids) == 1
    assert kids[0].get_cos_object() is child_b


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
    assert len(kids) == 4


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


# ---------- PDStructureNode protected objectable kid helpers ----------


def test_structure_nodeappend_objectable_kid_unwraps_cos_object() -> None:
    node = PDStructureNode("StructElem")
    elem = PDStructureElement(structure_type="P")
    node.append_objectable_kid(elem)
    raw_k = node.get_cos_object().get_dictionary_object(_K)
    assert raw_k is elem.get_cos_object()


def test_structure_nodeappend_objectable_kid_none_is_noop() -> None:
    node = PDStructureNode("StructElem")
    node.append_objectable_kid(None)
    assert node.get_cos_object().get_dictionary_object(_K) is None


def test_structure_nodeappend_objectable_kid_accepts_cos_dictionary() -> None:
    node = PDStructureNode("StructElem")
    raw = COSDictionary()
    node.append_objectable_kid(raw)
    assert node.get_cos_object().get_dictionary_object(_K) is raw


def test_structure_noderemove_objectable_kid_returns_true_on_success() -> None:
    node = PDStructureNode("StructElem")
    elem = PDStructureElement(structure_type="P")
    node.append_objectable_kid(elem)
    assert node.remove_objectable_kid(elem) is True
    assert node.get_kids() == []


def test_structure_noderemove_objectable_kid_none_returns_false() -> None:
    node = PDStructureNode("StructElem")
    assert node.remove_objectable_kid(None) is False


def test_structure_noderemove_objectable_kid_unknown_returns_false() -> None:
    node = PDStructureNode("StructElem")
    node.append_kid(COSDictionary())
    other = PDStructureElement(structure_type="P")
    assert node.remove_objectable_kid(other) is False


# ---------- PDStructureNode.insert_before ----------


def test_structure_node_insert_before_into_array() -> None:
    node = PDStructureNode("StructElem")
    a, b, c = COSDictionary(), COSDictionary(), COSDictionary()
    node.set_kids([a, c])
    new_kid = COSDictionary()
    assert node.insert_before(new_kid, c) is True
    kids = node.get_kids()
    assert [kid.get_cos_object() for kid in kids] == [a, new_kid, c]
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


# ---------- PDStructureNode.create_object ----------


def test_structure_node_create_object_struct_elem() -> None:
    node = PDStructureNode("StructElem")
    kid = COSDictionary()
    kid.set_name(_TYPE, "StructElem")
    result = node.create_object(kid)
    assert isinstance(result, PDStructureElement)
    assert result.get_cos_object() is kid


def test_structure_node_create_object_no_type_is_struct_elem() -> None:
    node = PDStructureNode("StructElem")
    kid = COSDictionary()  # No /Type → treated as StructElem
    result = node.create_object(kid)
    assert isinstance(result, PDStructureElement)
    assert result.get_cos_object() is kid


def test_structure_node_create_object_mcr() -> None:
    node = PDStructureNode("StructElem")
    kid = COSDictionary()
    kid.set_name(_TYPE, "MCR")
    result = node.create_object(kid)
    assert isinstance(result, PDMarkedContentReference)
    assert result.get_cos_object() is kid


def test_structure_node_create_object_objr() -> None:
    node = PDStructureNode("StructElem")
    kid = COSDictionary()
    kid.set_name(_TYPE, "OBJR")
    result = node.create_object(kid)
    assert isinstance(result, PDObjectReference)
    assert result.get_cos_object() is kid


def test_structure_node_create_object_int_returns_mcid() -> None:
    node = PDStructureNode("StructElem")
    assert node.create_object(COSInteger.get(7)) == 7


def test_structure_node_create_object_unknown_dict_type_returns_none() -> None:
    node = PDStructureNode("StructElem")
    kid = COSDictionary()
    kid.set_name(_TYPE, "ZZUnknownTypeZZ")
    # wrap_kid preserves unknown dicts; create_object strictly returns None
    # to match upstream's createObject contract.
    assert node.create_object(kid) is None


def test_structure_node_create_object_none_returns_none() -> None:
    node = PDStructureNode("StructElem")
    assert node.create_object(None) is None


# ---------- PDStructureNode.insert_objectable_before ----------


def test_structure_nodeinsert_objectable_before_unwraps_cos_object() -> None:
    node = PDStructureNode("StructElem")
    head = PDStructureElement(structure_type="P")
    tail = PDStructureElement(structure_type="P")
    middle = PDStructureElement(structure_type="P")
    node.set_kids([head, tail])

    assert node.insert_objectable_before(middle, tail) is True
    raw_k = node.get_cos_object().get_dictionary_object(_K)
    assert isinstance(raw_k, COSArray)
    assert raw_k.get_object(0) is head.get_cos_object()
    assert raw_k.get_object(1) is middle.get_cos_object()
    assert raw_k.get_object(2) is tail.get_cos_object()


def test_structure_nodeinsert_objectable_before_none_is_noop() -> None:
    node = PDStructureNode("StructElem")
    only = COSDictionary()
    node.append_kid(only)
    assert node.insert_objectable_before(None, only) is False
    # /K untouched
    assert node.get_cos_object().get_dictionary_object(_K) is only


def test_structure_nodeinsert_objectable_before_accepts_raw_cos_dictionary() -> None:
    node = PDStructureNode("StructElem")
    a, b = COSDictionary(), COSDictionary()
    node.set_kids([a, b])
    new_kid = COSDictionary()  # no get_cos_object — passed through
    assert node.insert_objectable_before(new_kid, b) is True
    raw_k = node.get_cos_object().get_dictionary_object(_K)
    assert isinstance(raw_k, COSArray)
    assert raw_k.get_object(0) is a
    assert raw_k.get_object(1) is new_kid
    assert raw_k.get_object(2) is b


# ---------- PDStructureNode public type constants ----------


def test_structure_node_public_type_constants_match_dispatch_strings() -> None:
    assert PDStructureNode.STRUCT_TREE_ROOT_TYPE == "StructTreeRoot"
    assert PDStructureNode.STRUCT_ELEM_TYPE == "StructElem"


def test_structure_node_public_type_constants_drive_create_dispatch() -> None:
    # Build dictionaries using the public constants and round-trip through
    # PDStructureNode.create — this guarantees the constants stay in sync
    # with the dispatch literals.
    root_dic = COSDictionary()
    root_dic.set_name(_TYPE, PDStructureNode.STRUCT_TREE_ROOT_TYPE)
    assert isinstance(PDStructureNode.create(root_dic), PDStructureTreeRoot)

    elem_dic = COSDictionary()
    elem_dic.set_name(_TYPE, PDStructureNode.STRUCT_ELEM_TYPE)
    assert isinstance(PDStructureNode.create(elem_dic), PDStructureElement)


# ---------- PDStructureNode is_struct_tree_root / is_struct_elem ----------


def test_structure_node_is_struct_tree_root_true_for_root_type() -> None:
    node = PDStructureNode("StructTreeRoot")
    assert node.is_struct_tree_root() is True
    assert node.is_struct_elem() is False


def test_structure_node_is_struct_elem_true_for_elem_type() -> None:
    node = PDStructureNode("StructElem")
    assert node.is_struct_elem() is True
    assert node.is_struct_tree_root() is False


def test_structure_node_is_struct_elem_true_when_type_absent() -> None:
    # No /Type → upstream treats as StructElem; predicate mirrors that.
    node = PDStructureNode()
    assert node.is_struct_elem() is True
    assert node.is_struct_tree_root() is False


def test_structure_node_predicates_false_for_other_type() -> None:
    node = PDStructureNode("ZZNotARealTypeZZ")
    assert node.is_struct_elem() is False
    assert node.is_struct_tree_root() is False


# ---------- PDStructureNode has_kids / is_kids_empty / get_kids_count ----------


def test_structure_node_has_kids_false_when_k_absent() -> None:
    node = PDStructureNode("StructElem")
    assert node.has_kids() is False
    assert node.is_kids_empty() is True
    assert node.get_kids_count() == 0


def test_structure_node_has_kids_true_for_single_dict_kid() -> None:
    node = PDStructureNode("StructElem")
    node.append_kid(COSDictionary())
    assert node.has_kids() is True
    assert node.is_kids_empty() is False
    assert node.get_kids_count() == 1


def test_structure_node_kids_count_for_array() -> None:
    node = PDStructureNode("StructElem")
    node.set_kids([COSDictionary(), COSDictionary(), COSDictionary()])
    assert node.has_kids() is True
    assert node.get_kids_count() == 3


def test_structure_node_kids_count_empty_array_treated_as_no_kids() -> None:
    # set_kids([]) removes /K entirely (matches the upstream/empty-list
    # semantics), so has_kids should be False.
    node = PDStructureNode("StructElem")
    node.append_kid(COSDictionary())
    node.set_kids([])
    assert node.has_kids() is False
    assert node.is_kids_empty() is True
    assert node.get_kids_count() == 0


def test_structure_node_kids_count_for_explicit_empty_cos_array() -> None:
    # Defensive: a directly-installed empty COSArray under /K should
    # report zero kids.
    node = PDStructureNode("StructElem")
    node.get_cos_object().set_item(_K, COSArray())
    assert node.has_kids() is False
    assert node.is_kids_empty() is True
    assert node.get_kids_count() == 0


def test_structure_node_kids_count_for_int_mcid_kid() -> None:
    # Single integer MCID under /K (no array) — should still count as 1.
    node = PDStructureNode("StructElem")
    node.append_kid(7)
    assert node.has_kids() is True
    assert node.get_kids_count() == 1


# ---------- PDStructureNode contains_kid ----------


def test_structure_node_contains_kid_finds_in_array() -> None:
    node = PDStructureNode("StructElem")
    a, b = COSDictionary(), COSDictionary()
    node.set_kids([a, b])
    assert node.contains_kid(a) is True
    assert node.contains_kid(b) is True


def test_structure_node_contains_kid_false_when_absent() -> None:
    node = PDStructureNode("StructElem")
    node.append_kid(COSDictionary())
    assert node.contains_kid(COSDictionary()) is False


def test_structure_node_contains_kid_false_when_k_missing() -> None:
    node = PDStructureNode("StructElem")
    assert node.contains_kid(COSDictionary()) is False


def test_structure_node_contains_kid_finds_single_non_array_kid() -> None:
    node = PDStructureNode("StructElem")
    only = COSDictionary()
    node.append_kid(only)
    assert node.contains_kid(only) is True


def test_structure_node_contains_kid_int_mcid() -> None:
    node = PDStructureNode("StructElem")
    node.set_kids([1, 2, 3])
    assert node.contains_kid(2) is True
    assert node.contains_kid(99) is False


def test_structure_node_contains_kid_typed_wrapper() -> None:
    node = PDStructureNode("StructElem")
    elem = PDStructureElement(structure_type="P")
    node.append_kid(elem)
    assert node.contains_kid(elem) is True


def test_structure_node_contains_kid_none_returns_false() -> None:
    node = PDStructureNode("StructElem")
    node.append_kid(COSDictionary())
    assert node.contains_kid(None) is False
