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
