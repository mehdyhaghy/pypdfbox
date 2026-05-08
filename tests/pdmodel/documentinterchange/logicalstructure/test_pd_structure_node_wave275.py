from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSObject
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_marked_content_reference import (
    PDMarkedContentReference,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_node import (
    PDStructureNode,
)

_K = COSName.get_pdf_name("K")
_TYPE = COSName.TYPE  # type: ignore[attr-defined]


def test_wave275_insert_before_promotes_single_kid_to_array() -> None:
    node = PDStructureNode("StructElem")
    only = COSDictionary()
    inserted = COSDictionary()
    node.append_kid(only)

    assert node.insert_before(inserted, only) is True

    raw_k = node.get_cos_object().get_dictionary_object(_K)
    assert isinstance(raw_k, COSArray)
    assert raw_k.size() == 2
    assert raw_k.get_object(0) is inserted
    assert raw_k.get_object(1) is only


def test_wave275_insert_before_missing_reference_is_noop() -> None:
    node = PDStructureNode("StructElem")
    existing = COSDictionary()
    missing = COSDictionary()
    inserted = COSDictionary()
    node.append_kid(existing)

    assert node.insert_before(inserted, missing) is False

    assert node.get_cos_object().get_dictionary_object(_K) is existing
    assert node.contains_kid(inserted) is False


def test_wave275_insert_before_typed_wrapper_unwraps_to_cos_object() -> None:
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


def test_wave275_contains_kid_matches_int_query_to_cos_integer_kid() -> None:
    node = PDStructureNode("StructElem")
    node.get_cos_object().set_item(_K, COSInteger.get(42))

    assert node.contains_kid(42) is True
    assert node.contains_kid(COSInteger.get(42)) is True
    assert node.contains_kid(43) is False


def test_wave275_create_object_dispatches_indirect_marked_content_reference() -> None:
    node = PDStructureNode("StructElem")
    kid = COSDictionary()
    kid.set_name(_TYPE, "MCR")

    result = node.create_object(COSObject(7, 0, resolved=kid))

    assert isinstance(result, PDMarkedContentReference)
    assert result.get_cos_object() is kid


def test_wave275_count_and_emptiness_do_not_materialize_wrappers(monkeypatch) -> None:
    node = PDStructureNode("StructElem")
    kid = COSDictionary()
    kid.set_name(_TYPE, "StructElem")
    node.get_cos_object().set_item(_K, COSArray([kid, COSInteger.get(9)]))

    def fail_wrap(_kid: object) -> object:
        raise AssertionError("wrap_kid should not be called")

    monkeypatch.setattr(PDStructureNode, "wrap_kid", staticmethod(fail_wrap))

    assert node.has_kids() is True
    assert node.is_kids_empty() is False
    assert node.get_kids_count() == 2
