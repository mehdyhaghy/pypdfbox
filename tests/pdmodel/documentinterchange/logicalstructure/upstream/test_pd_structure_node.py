"""Upstream-ported tests for PDStructureNode.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/documentinterchange/
logicalstructure/PDStructureElementTest.java`` (PDFBox 3.0).

Apache PDFBox 3.0.x has no dedicated ``PDStructureNodeTest`` — the abstract
base class is exercised indirectly through ``PDStructureElementTest``. The
``testSimple`` test (PDStructureElementTest line 168) covers the subset of
``PDStructureNode`` behaviour that is reachable without loading a PDF
fixture: the ``/K`` kid-management contract (single → array promotion,
mixed integer / dictionary kids, round-tripping through ``getKids``),
typed-kid wrapping for marked-content references, and the ``/Type`` /
``getCOSObject`` accessors.

The fixture-loading parts of ``testPDFBox4197`` and ``testClassMap`` are
deferred (they require the full PDF reader). We port the *node-walking*
shape of those tests through a synthetic tree built directly with
``COSDictionary`` and ``COSArray`` — this exercises the same
``createObject`` / ``createObjectFromDic`` dispatch that the upstream
walker relies on.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
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

_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_K = COSName.get_pdf_name("K")


# ---------- Ported from PDStructureElementTest.testSimple (kid-management subset) ----------


def test_simple_append_kid_int_then_mcr_then_mc_gives_three_kids() -> None:
    """Port of ``PDStructureElementTest.testSimple`` (line 195-214) — only
    the kid-management portion that goes through ``PDStructureNode``.

    The upstream test asserts ``getKids().size() == 3`` after appending an
    integer MCID, a ``PDMarkedContentReference``, and a marked-content
    dictionary. We replicate just the tree-shape side: append 0, append a
    MCR with mcid=1, append a raw dict (in lieu of ``PDMarkedContent``,
    which lives in markedcontent), and round-trip via ``get_kids``.
    """
    element = PDStructureElement(structure_type="S")
    element.append_kid(0)
    mcr1 = PDMarkedContentReference()
    mcr1.set_mcid(1)
    element.append_kid(mcr1)
    mcr2 = PDMarkedContentReference()
    mcr2.set_mcid(2)
    element.append_kid(mcr2)

    kids = element.get_kids()
    assert len(kids) == 3
    assert kids[0] == 0
    assert isinstance(kids[1], PDMarkedContentReference)
    assert kids[1].get_cos_object().get_name(_TYPE) == PDMarkedContentReference.TYPE
    assert kids[1].get_mcid() == 1
    assert isinstance(kids[2], PDMarkedContentReference)
    assert kids[2].get_mcid() == 2


# ---------- PDStructureNode.create dispatch (mirrors create() in Java line 67) ----------


def test_create_dispatches_struct_tree_root() -> None:
    dic = COSDictionary()
    dic.set_name(_TYPE, "StructTreeRoot")
    node = PDStructureNode.create(dic)
    assert isinstance(node, PDStructureTreeRoot)
    assert node.get_cos_object() is dic


def test_create_dispatches_struct_elem() -> None:
    dic = COSDictionary()
    dic.set_name(_TYPE, "StructElem")
    node = PDStructureNode.create(dic)
    assert isinstance(node, PDStructureElement)


def test_create_dispatches_missing_type_to_struct_elem() -> None:
    dic = COSDictionary()
    node = PDStructureNode.create(dic)
    assert isinstance(node, PDStructureElement)


def test_create_rejects_unknown_type() -> None:
    dic = COSDictionary()
    dic.set_name(_TYPE, "Bogus")
    with pytest.raises(ValueError):
        PDStructureNode.create(dic)


# ---------- PDStructureNode.createObject dispatch (mirrors Java line 367) ----------


def test_create_object_returns_struct_element_for_struct_elem_dict() -> None:
    elem_dic = COSDictionary()
    elem_dic.set_name(_TYPE, PDStructureElement.TYPE)
    node = PDStructureNode("StructElem")
    out = node.create_object(elem_dic)
    assert isinstance(out, PDStructureElement)


def test_create_object_returns_struct_element_for_missing_type() -> None:
    untyped = COSDictionary()
    node = PDStructureNode("StructElem")
    out = node.create_object(untyped)
    assert isinstance(out, PDStructureElement)


def test_create_object_returns_marked_content_reference_for_mcr() -> None:
    mcr_dic = COSDictionary()
    mcr_dic.set_name(_TYPE, "MCR")
    node = PDStructureNode("StructElem")
    out = node.create_object(mcr_dic)
    assert isinstance(out, PDMarkedContentReference)


def test_create_object_returns_object_reference_for_objr() -> None:
    objr_dic = COSDictionary()
    objr_dic.set_name(_TYPE, "OBJR")
    node = PDStructureNode("StructElem")
    out = node.create_object(objr_dic)
    assert isinstance(out, PDObjectReference)


def test_create_object_returns_int_for_cos_integer() -> None:
    node = PDStructureNode("StructElem")
    assert node.create_object(COSInteger.get(7)) == 7


def test_create_object_returns_none_for_unknown_type() -> None:
    foo_dic = COSDictionary()
    foo_dic.set_name(_TYPE, "Foo")
    node = PDStructureNode("StructElem")
    assert node.create_object(foo_dic) is None


# ---------- PDStructureNode.appendKid / setKids round-trip (Java line 108-201) ----------


def test_set_kids_then_get_kids_round_trip_preserves_order() -> None:
    node = PDStructureNode("StructElem")
    a, b, c = COSDictionary(), COSDictionary(), COSDictionary()
    a.set_name(_TYPE, PDStructureElement.TYPE)
    b.set_name(_TYPE, PDStructureElement.TYPE)
    c.set_name(_TYPE, PDStructureElement.TYPE)
    node.set_kids([a, b, c])
    out = node.get_kids()
    assert len(out) == 3
    assert all(isinstance(o, PDStructureElement) for o in out)
    assert out[0].get_cos_object() is a
    assert out[1].get_cos_object() is b
    assert out[2].get_cos_object() is c


def test_append_kid_promotes_single_to_array_on_second_kid() -> None:
    node = PDStructureNode("StructElem")
    first = COSDictionary()
    first.set_name(_TYPE, PDStructureElement.TYPE)
    node.append_kid(first)
    raw_k = node.get_cos_object().get_dictionary_object(_K)
    assert raw_k is first  # single dict kid
    second = COSDictionary()
    second.set_name(_TYPE, PDStructureElement.TYPE)
    node.append_kid(second)
    raw_k = node.get_cos_object().get_dictionary_object(_K)
    assert isinstance(raw_k, COSArray)
    assert raw_k.size() == 2


def test_remove_kid_demotes_array_back_to_single_when_one_remains() -> None:
    node = PDStructureNode("StructElem")
    a = COSDictionary()
    a.set_name(_TYPE, PDStructureElement.TYPE)
    b = COSDictionary()
    b.set_name(_TYPE, PDStructureElement.TYPE)
    node.set_kids([a, b])
    assert node.remove_kid(a) is True
    raw_k = node.get_cos_object().get_dictionary_object(_K)
    assert raw_k is b


# ---------- PDStructureNode.appendObjectableKid / removeObjectableKid (protected) ----------


def test_append_objectable_kid_unwraps_via_get_cos_object() -> None:
    node = PDStructureNode("StructElem")
    elem = PDStructureElement(structure_type="P")
    node.append_objectable_kid(elem)
    raw_k = node.get_cos_object().get_dictionary_object(_K)
    assert raw_k is elem.get_cos_object()


def test_remove_objectable_kid_returns_true_on_success() -> None:
    node = PDStructureNode("StructElem")
    elem = PDStructureElement(structure_type="P")
    node.append_kid(elem)
    assert node.remove_objectable_kid(elem) is True
    assert node.get_kids() == []


def test_insert_objectable_before_inserts_in_array() -> None:
    node = PDStructureNode("StructElem")
    head = PDStructureElement(structure_type="P")
    tail = PDStructureElement(structure_type="P")
    node.set_kids([head, tail])
    middle = PDStructureElement(structure_type="P")
    assert node.insert_objectable_before(middle, tail) is True
    raw_k = node.get_cos_object().get_dictionary_object(_K)
    assert isinstance(raw_k, COSArray)
    assert raw_k.get_object(0) is head.get_cos_object()
    assert raw_k.get_object(1) is middle.get_cos_object()
    assert raw_k.get_object(2) is tail.get_cos_object()


# ---------- PDStructureNode.createObjectFromDic (Java line 395) ----------


def test_create_object_from_dic_returns_struct_element_when_type_missing() -> None:
    node = PDStructureNode("StructElem")
    untyped = COSDictionary()
    out = node.create_object_from_dic(untyped)
    assert isinstance(out, PDStructureElement)
    assert out.get_cos_object() is untyped


def test_create_object_from_dic_returns_none_for_unknown_type() -> None:
    node = PDStructureNode("StructElem")
    weird = COSDictionary()
    weird.set_name(_TYPE, "NotAStructureKind")
    assert node.create_object_from_dic(weird) is None


# ---------- COSObject indirection (Java insertBefore lines 260-264, removeKid 340-344) ----------


def test_remove_kid_through_cos_object_indirection_single_kid() -> None:
    """Upstream's ``removeKid(COSBase)`` (Java line 339-344) treats a single
    indirect-reference ``/K`` as equal to the dereferenced kid. Mirrors the
    ``onlyKid = kObj.equals(object)`` branch.
    """
    from pypdfbox.cos import COSObject

    node = PDStructureNode("StructElem")
    target = COSDictionary()
    target.set_name(_TYPE, PDStructureElement.TYPE)
    indirect = COSObject(1, 0, resolved=target)
    node.get_cos_object().set_item(_K, indirect)

    assert node.remove_kid(target) is True
    assert node.get_cos_object().get_dictionary_object(_K) is None


def test_insert_before_through_cos_object_indirection_single_kid() -> None:
    """Upstream's ``insertBefore`` (Java line 257-271) handles the single-kid
    indirect-reference case via ``kObj.equals(refKidBase)``.
    """
    from pypdfbox.cos import COSObject

    node = PDStructureNode("StructElem")
    target = COSDictionary()
    target.set_name(_TYPE, PDStructureElement.TYPE)
    indirect = COSObject(2, 0, resolved=target)
    node.get_cos_object().set_item(_K, indirect)

    new_kid = COSDictionary()
    new_kid.set_name(_TYPE, PDStructureElement.TYPE)
    assert node.insert_before(new_kid, target) is True

    raw_k = node.get_cos_object().get_dictionary_object(_K)
    assert isinstance(raw_k, COSArray)
    assert raw_k.get_object(0) is new_kid


# ---------- PDStructureNode.appendKid(PDStructureElement) parent contract (Java 150-154) ----------


def test_append_kid_structure_element_sets_parent_to_node() -> None:
    """Mirrors upstream ``appendKid(PDStructureElement)`` (Java line 150-154):
    after ``appendObjectableKid`` returns, the structure element's parent
    is set to ``this`` unconditionally.
    """
    parent = PDStructureNode("StructElem")
    child = PDStructureElement(structure_type="P")
    parent.append_kid(child)
    # ``/P`` should now point at the parent's backing dictionary.
    assert child.get_parent() is parent.get_cos_object()


def test_append_two_structure_element_kids_each_have_parent_set() -> None:
    """Each appended structure element gets its parent set, even after the
    single-kid → array promotion path (Java appendKid via appendObjectableKid).
    """
    parent = PDStructureNode("StructElem")
    first = PDStructureElement(structure_type="P")
    second = PDStructureElement(structure_type="P")
    parent.append_kid(first)
    parent.append_kid(second)
    assert first.get_parent() is parent.get_cos_object()
    assert second.get_parent() is parent.get_cos_object()


# ---------- PDStructureNode.removeKid(PDStructureElement) parent contract (Java 281-289) ----------


def test_remove_kid_structure_element_clears_parent_on_success() -> None:
    """Mirrors upstream ``removeKid(PDStructureElement)`` (Java line 281-289):
    when ``removeObjectableKid`` returns ``true``, the structure element's
    parent is set to ``null``.
    """
    parent = PDStructureNode("StructElem")
    child = PDStructureElement(structure_type="P")
    parent.append_kid(child)
    assert child.get_parent() is parent.get_cos_object()
    assert parent.remove_kid(child) is True
    assert child.get_parent() is None


def test_remove_kid_unknown_structure_element_does_not_clear_parent() -> None:
    """Upstream only clears the parent when removal succeeds (Java line
    285-287's ``if (removed)`` guard). A no-op remove must leave the
    element's existing parent untouched.
    """
    parent_a = PDStructureNode("StructElem")
    parent_b = PDStructureNode("StructElem")
    child = PDStructureElement(structure_type="P")
    parent_a.append_kid(child)
    # child belongs to parent_a, not parent_b, so parent_b can't remove it.
    assert parent_b.remove_kid(child) is False
    # Parent must still point at parent_a's backing dictionary.
    assert child.get_parent() is parent_a.get_cos_object()


# ---------- PDStructureNode.removeKid array → single demotion (Java line 329-333) ----------


def test_remove_kid_demotes_array_to_single_then_remove_again_clears_k() -> None:
    """After array-shrink demotes ``/K`` back to a single dict (Java line
    329-333), a follow-up remove of that last kid must clear ``/K`` entirely.
    """
    node = PDStructureNode("StructElem")
    a, b = COSDictionary(), COSDictionary()
    node.set_kids([a, b])
    assert node.remove_kid(a) is True
    raw_k = node.get_cos_object().get_dictionary_object(_K)
    assert raw_k is b
    assert node.remove_kid(b) is True
    assert node.get_cos_object().get_dictionary_object(_K) is None


# ---------- PDStructureNode.getKids on single (non-array) kid (Java line 122-130) ----------


def test_get_kids_with_single_non_array_kid_returns_list_of_one() -> None:
    """Mirrors upstream ``getKids`` (Java line 122-130) — the ``else`` branch
    that wraps a single non-array ``/K`` into a one-element list.
    """
    node = PDStructureNode("StructElem")
    only = COSDictionary()
    only.set_name(_TYPE, PDStructureElement.TYPE)
    node.get_cos_object().set_item(_K, only)
    kids = node.get_kids()
    assert len(kids) == 1
    assert isinstance(kids[0], PDStructureElement)
    assert kids[0].get_cos_object() is only


def test_get_kids_with_single_int_mcid_returns_list_of_int() -> None:
    """Single integer MCID under ``/K`` (no array) — Java's ``getKids`` runs
    the ``else`` branch through ``createObject(COSInteger)`` returning an
    ``Integer`` per line 386-391.
    """
    node = PDStructureNode("StructElem")
    node.get_cos_object().set_item(_K, COSInteger.get(42))
    kids = node.get_kids()
    assert kids == [42]


# ---------- PDStructureNode.getCOSObject identity (Java line 88-91) ----------


def test_get_cos_object_returns_same_dictionary_instance() -> None:
    """Mirrors ``getCOSObject`` returning the exact backing dictionary
    (Java line 88-91 — ``return dictionary`` on a final field). The
    constructor that wraps an existing dictionary must hand the same
    instance back.
    """
    backing = COSDictionary()
    backing.set_name(_TYPE, PDStructureElement.TYPE)
    node = PDStructureNode(backing)
    assert node.get_cos_object() is backing


# ---------- PDStructureNode.getType (Java line 98-101) ----------


def test_get_type_returns_none_when_type_absent() -> None:
    """Mirrors ``getType`` (Java line 98-101) — the underlying call to
    ``getNameAsString(COSName.TYPE)`` returns ``null`` when the entry is
    absent, which the Python port surfaces as ``None``.
    """
    node = PDStructureNode()
    assert node.get_type() is None


# ---------- PDStructureNode.setKids null/empty (Java 139-143 via converterToCOSArray) ----------


def test_set_kids_none_removes_k_entry() -> None:
    """Mirrors upstream ``setKids(null)`` — ``COSArrayList.converterToCOSArray
    (null)`` returns ``null``, then ``setItem(K, null)`` removes ``/K``.
    """
    node = PDStructureNode("StructElem")
    node.append_kid(COSDictionary())
    node.set_kids(None)
    assert node.get_cos_object().get_dictionary_object(_K) is None


# ---------- PDStructureNode.appendKid null guard (Java line 163-166) ----------


def test_append_kid_none_is_silent_noop() -> None:
    """Upstream protected ``appendKid(COSBase)`` returns early when the
    object is ``null`` (Java line 163-166). The public ``appendKid
    (PDStructureElement)`` first calls ``appendObjectableKid`` (also a
    null-guard) so a null kid is a silent no-op rather than an exception.
    """
    node = PDStructureNode("StructElem")
    node.append_kid(None)
    assert node.get_cos_object().get_dictionary_object(_K) is None


# ---------- PDStructureNode.removeKid null guard (Java line 314-317) ----------


def test_remove_kid_none_returns_false() -> None:
    """Upstream ``removeKid(COSBase)`` (Java line 312-317) returns ``false``
    immediately when given ``null``.
    """
    node = PDStructureNode("StructElem")
    node.append_kid(COSDictionary())
    assert node.remove_kid(None) is False
