"""Hand-written fuzz for the tagged-PDF logical-structure tree (wave 1573).

Hammers the ``PDStructureTreeRoot`` / ``PDStructureElement`` /
``PDStructureNode`` accessor surface with deliberately type-confused and
edge-shaped inputs, pinning the exact behaviour pypdfbox shares with Apache
PDFBox 3.0.7:

* ``/RoleMap`` dict round-trip via ``set_role_map`` / ``get_role_map`` and
  the ``convertBasicTypesToMap`` all-or-nothing collapse rule.
* ``get_kids`` normalising single-element vs single-int vs array ``/K``.
* ``append_kid`` / ``insert_before`` / ``remove_kid`` promoting a single
  ``/K`` to a ``COSArray`` and collapsing it back, and wiring/clearing the
  ``/P`` parent pointer on ``PDStructureElement`` kids.
* ``/S`` get/set decoding both ``COSName`` and ``COSString``.
* ``get_standard_structure_type`` resolving through the parent-chain
  ``/RoleMap`` with a **single** lookup (upstream does NOT chain and does NOT
  short-circuit on standard types), while the root-level
  ``resolve_role_map`` helper DOES chain (pypdfbox addition).
* ``/P`` parent linkage, ``/Pg`` page reference, ``/A`` attributes, ``/ID``,
  ``/Lang``, ``/ActualText`` / ``/Alt`` / ``/E``.
* Marked-content kids: integer MCIDs and ``/MCR`` / ``/OBJR`` dict kids.

No production change in this wave — every assertion already holds; the cases
guard the surface against regression.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDStructureElement,
    PDStructureTreeRoot,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_marked_content_reference import (
    PDMarkedContentReference,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_object_reference import (
    PDObjectReference,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_node import (
    PDStructureNode,
)

_K = COSName.get_pdf_name("K")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")
_TYPE = COSName.get_pdf_name("Type")


# --------------------------------------------------------------------------
# /RoleMap dict round-trip
# --------------------------------------------------------------------------


def test_role_map_round_trip_basic():
    root = PDStructureTreeRoot()
    root.set_role_map({"Chapter": "Sect", "MyP": "P"})
    assert root.get_role_map() == {"Chapter": "Sect", "MyP": "P"}
    assert root.has_role_map()


def test_role_map_none_removes_entry():
    root = PDStructureTreeRoot()
    root.set_role_map({"A": "P"})
    root.set_role_map(None)
    assert root.get_role_map() == {}
    assert not root.has_role_map()


def test_role_map_empty_dict_present_but_empty():
    root = PDStructureTreeRoot()
    root.set_role_map({})
    # set_role_map({}) writes an empty /RoleMap dictionary (truthy presence).
    assert root.has_role_map()
    assert root.get_role_map() == {}


def test_role_map_absent_returns_empty():
    root = PDStructureTreeRoot()
    assert root.get_role_map() == {}
    assert not root.has_role_map()


def test_role_map_int_value_kept_as_int():
    # convertBasicTypesToMap converts COSInteger -> int; get_role_map exposes it.
    root = PDStructureTreeRoot()
    rm = COSDictionary()
    rm.set_item(COSName.get_pdf_name("Custom"), COSInteger.get(7))
    root.get_cos_object().set_item(_ROLE_MAP, rm)
    assert root.get_role_map() == {"Custom": 7}


def test_role_map_string_value_decoded():
    root = PDStructureTreeRoot()
    rm = COSDictionary()
    rm.set_item(COSName.get_pdf_name("Custom"), COSString("Sect"))
    root.get_cos_object().set_item(_ROLE_MAP, rm)
    assert root.get_role_map() == {"Custom": "Sect"}


def test_role_map_unconvertible_value_collapses_to_empty():
    # An array value is not a basic type -> upstream IOException -> empty map.
    root = PDStructureTreeRoot()
    rm = COSDictionary()
    rm.set_item(COSName.get_pdf_name("Custom"), COSName.get_pdf_name("Sect"))
    rm.set_item(COSName.get_pdf_name("Bad"), COSArray())
    root.get_cos_object().set_item(_ROLE_MAP, rm)
    assert root.get_role_map() == {}


def test_role_map_non_dictionary_is_empty():
    root = PDStructureTreeRoot()
    root.get_cos_object().set_item(_ROLE_MAP, COSArray())
    assert root.get_role_map() == {}
    assert not root.has_role_map()


# --------------------------------------------------------------------------
# get_kids normalisation: single vs array vs int
# --------------------------------------------------------------------------


def test_get_kids_single_element_normalised_to_list():
    parent = PDStructureElement("Sect")
    child = PDStructureElement("P")
    parent.append_kid(child)
    kids = parent.get_kids()
    assert len(kids) == 1
    assert isinstance(kids[0], PDStructureElement)
    # /K stays a single dictionary, not an array, for one kid.
    assert isinstance(parent.get_cos_object().get_dictionary_object(_K), COSDictionary)


def test_get_kids_single_int_mcid_normalised():
    elem = PDStructureElement("P")
    elem.append_kid(3)
    assert elem.get_kids() == [3]
    assert elem.get_kids_count() == 1


def test_get_kids_array_mixed():
    elem = PDStructureElement("P")
    elem.append_kid(PDStructureElement("Span"))
    elem.append_kid(4)
    kids = elem.get_kids()
    assert len(kids) == 2
    assert isinstance(kids[0], PDStructureElement)
    assert kids[1] == 4
    assert isinstance(elem.get_cos_object().get_dictionary_object(_K), COSArray)


def test_get_kids_absent_is_empty():
    elem = PDStructureElement("P")
    assert elem.get_kids() == []
    assert not elem.has_kids()
    assert elem.is_kids_empty()
    assert elem.get_kids_count() == 0


def test_get_kids_skips_unknown_type():
    # A dictionary with an unrecognised /Type is dropped by create_object.
    elem = PDStructureElement("P")
    weird = COSDictionary()
    weird.set_item(_TYPE, COSName.get_pdf_name("Bogus"))
    arr = COSArray()
    arr.add(weird)
    arr.add(COSInteger.get(9))
    elem.get_cos_object().set_item(_K, arr)
    kids = elem.get_kids()
    assert kids == [9]


# --------------------------------------------------------------------------
# append_kid: single -> array promotion, parent wiring
# --------------------------------------------------------------------------


def test_append_kid_promotes_single_to_array():
    parent = PDStructureElement("Sect")
    c1 = PDStructureElement("P")
    c2 = PDStructureElement("P")
    parent.append_kid(c1)
    assert isinstance(parent.get_cos_object().get_dictionary_object(_K), COSDictionary)
    parent.append_kid(c2)
    assert isinstance(parent.get_cos_object().get_dictionary_object(_K), COSArray)
    assert parent.get_kids_count() == 2


def test_append_kid_sets_parent_pointer():
    parent = PDStructureElement("Sect")
    child = PDStructureElement("P")
    parent.append_kid(child)
    assert child.get_parent() is parent.get_cos_object()


def test_append_kid_sets_parent_on_second_kid():
    parent = PDStructureElement("Sect")
    c1 = PDStructureElement("P")
    c2 = PDStructureElement("P")
    parent.append_kid(c1)
    parent.append_kid(c2)
    assert c2.get_parent() is parent.get_cos_object()


def test_root_append_kid_wires_parent():
    root = PDStructureTreeRoot()
    child = PDStructureElement("Document")
    root.append_kid(child)
    assert child.get_parent() is root.get_cos_object()


def test_append_kid_negative_mcid_rejected():
    elem = PDStructureElement("P")
    with pytest.raises(ValueError):
        elem.append_kid(-1)


def test_append_kid_bool_rejected():
    elem = PDStructureElement("P")
    with pytest.raises(TypeError):
        elem.append_kid(True)


def test_append_kid_none_noop():
    elem = PDStructureElement("P")
    elem.append_kid(None)
    assert elem.get_kids() == []


# --------------------------------------------------------------------------
# insert_before / remove_kid
# --------------------------------------------------------------------------


def test_insert_before_promotes_single_to_array():
    parent = PDStructureElement("Sect")
    ref = PDStructureElement("P")
    parent.append_kid(ref)
    new = PDStructureElement("H1")
    assert parent.insert_before(new, ref)
    kids = parent.get_kids()
    assert len(kids) == 2
    assert kids[0].get_cos_object() is new.get_cos_object()
    assert kids[1].get_cos_object() is ref.get_cos_object()


def test_insert_before_missing_ref_returns_false():
    parent = PDStructureElement("Sect")
    parent.append_kid(PDStructureElement("P"))
    other = PDStructureElement("H1")
    new = PDStructureElement("Span")
    assert parent.insert_before(new, other) is False


def test_remove_kid_clears_parent_and_collapses():
    parent = PDStructureElement("Sect")
    c1 = PDStructureElement("P")
    c2 = PDStructureElement("P")
    parent.append_kid(c1)
    parent.append_kid(c2)
    assert parent.remove_kid(c2)
    assert c2.get_parent() is None
    # 2-array minus one collapses back to single dictionary.
    assert isinstance(parent.get_cos_object().get_dictionary_object(_K), COSDictionary)


def test_remove_kid_single_removes_entry():
    parent = PDStructureElement("Sect")
    child = PDStructureElement("P")
    parent.append_kid(child)
    assert parent.remove_kid(child)
    assert parent.get_cos_object().get_dictionary_object(_K) is None
    assert child.get_parent() is None


def test_remove_kid_absent_returns_false():
    parent = PDStructureElement("Sect")
    assert parent.remove_kid(PDStructureElement("P")) is False


def test_remove_kid_mcid_integer():
    elem = PDStructureElement("P")
    elem.append_kid(2)
    elem.append_kid(5)
    assert elem.remove_kid(2)
    assert elem.get_kids() == [5]


def test_contains_kid_int_and_element():
    elem = PDStructureElement("P")
    child = PDStructureElement("Span")
    elem.append_kid(child)
    elem.append_kid(8)
    assert elem.contains_kid(child)
    assert elem.contains_kid(8)
    assert not elem.contains_kid(99)


# --------------------------------------------------------------------------
# /S structure type get/set
# --------------------------------------------------------------------------


def test_structure_type_name_round_trip():
    elem = PDStructureElement()
    elem.set_structure_type("Sect")
    assert elem.get_structure_type() == "Sect"


def test_structure_type_decodes_cos_string():
    # Upstream getNameAsString decodes a /S COSString to text.
    elem = PDStructureElement()
    elem.get_cos_object().set_item(COSName.get_pdf_name("S"), COSString("Custom"))
    assert elem.get_structure_type() == "Custom"


def test_structure_type_absent_is_none():
    elem = PDStructureElement()
    elem.get_cos_object().remove_item(COSName.get_pdf_name("S"))
    assert elem.get_structure_type() is None


# --------------------------------------------------------------------------
# get_standard_structure_type: single lookup through role map
# --------------------------------------------------------------------------


def test_standard_type_unmapped_returns_itself():
    root = PDStructureTreeRoot()
    root.set_role_map({"Foo": "P"})
    elem = PDStructureElement("Unmapped", root)
    root.append_kid(elem)
    assert elem.get_standard_structure_type() == "Unmapped"


def test_standard_type_mapped_single_lookup():
    root = PDStructureTreeRoot()
    root.set_role_map({"MyHead": "H1"})
    elem = PDStructureElement("MyHead", root)
    root.append_kid(elem)
    assert elem.get_standard_structure_type() == "H1"


def test_standard_type_no_chaining_upstream_parity():
    # Upstream getStandardStructureType does a SINGLE lookup: MyHead -> SubHead.
    # It does NOT chain SubHead -> H1.
    root = PDStructureTreeRoot()
    root.set_role_map({"MyHead": "SubHead", "SubHead": "H1"})
    elem = PDStructureElement("MyHead", root)
    root.append_kid(elem)
    assert elem.get_standard_structure_type() == "SubHead"


def test_standard_type_no_root_returns_s():
    elem = PDStructureElement("Whatever")
    assert elem.get_standard_structure_type() == "Whatever"


def test_standard_type_int_role_target_keeps_s():
    # A role-map target that is not a String does not resolve /S.
    root = PDStructureTreeRoot()
    rm = COSDictionary()
    rm.set_item(COSName.get_pdf_name("Custom"), COSInteger.get(3))
    root.get_cos_object().set_item(_ROLE_MAP, rm)
    elem = PDStructureElement("Custom", root)
    root.append_kid(elem)
    assert elem.get_standard_structure_type() == "Custom"


def test_standard_type_absent_s_is_none():
    root = PDStructureTreeRoot()
    root.set_role_map({"A": "P"})
    elem = PDStructureElement()
    root.append_kid(elem)
    elem.get_cos_object().remove_item(COSName.get_pdf_name("S"))
    assert elem.get_standard_structure_type() is None


# --------------------------------------------------------------------------
# root-level resolve_role_map: DOES chain (pypdfbox addition)
# --------------------------------------------------------------------------


def test_resolve_role_map_chains_to_standard():
    root = PDStructureTreeRoot()
    root.set_role_map({"MyHead": "SubHead", "SubHead": "H1"})
    assert root.resolve_role_map("MyHead") == "H1"


def test_resolve_role_map_unmapped_returns_itself():
    root = PDStructureTreeRoot()
    root.set_role_map({"A": "P"})
    assert root.resolve_role_map("Zed") == "Zed"


def test_resolve_role_map_standard_short_circuits():
    root = PDStructureTreeRoot()
    root.set_role_map({"H1": "ShouldNotFollow"})
    # H1 is already standard -> returned unchanged, no further hop.
    assert root.resolve_role_map("H1") == "H1"


def test_resolve_role_map_cycle_terminates():
    root = PDStructureTreeRoot()
    root.set_role_map({"A": "B", "B": "A"})
    result = root.resolve_role_map("A")
    assert result in {"A", "B"}


def test_resolve_role_map_none_input():
    root = PDStructureTreeRoot()
    assert root.resolve_role_map(None) is None


def test_resolve_role_map_no_role_map_returns_input():
    root = PDStructureTreeRoot()
    assert root.resolve_role_map("Custom") == "Custom"


# --------------------------------------------------------------------------
# /P parent linkage, /Pg page, /ID, /Lang, /ActualText, /Alt, /E
# --------------------------------------------------------------------------


def test_parent_linkage_typed_dispatch():
    root = PDStructureTreeRoot()
    elem = PDStructureElement("Document", root)
    parent_node = elem.get_parent_node()
    assert isinstance(parent_node, PDStructureTreeRoot)
    assert parent_node.get_cos_object() is root.get_cos_object()


def test_parent_chain_reaches_root():
    root = PDStructureTreeRoot()
    mid = PDStructureElement("Sect", root)
    leaf = PDStructureElement("P", mid)
    found = leaf.get_structure_tree_root()
    assert found is not None
    assert found.get_cos_object() is root.get_cos_object()
    assert leaf.is_root_attached()


def test_set_parent_none_removes():
    elem = PDStructureElement("P")
    root = PDStructureTreeRoot()
    elem.set_parent(root)
    assert elem.has_parent()
    elem.set_parent(None)
    assert not elem.has_parent()
    assert elem.get_parent() is None


def test_page_reference_round_trip():
    elem = PDStructureElement("P")
    page_dict = COSDictionary()
    page_dict.set_item(_TYPE, COSName.get_pdf_name("Page"))
    elem.set_page(page_dict)
    assert elem.has_page()
    page = elem.get_page()
    assert page is not None
    assert page.get_cos_object() is page_dict
    elem.set_page(None)
    assert not elem.has_page()


def test_id_round_trip():
    elem = PDStructureElement("P")
    elem.set_id("elem-1")
    assert elem.get_id() == "elem-1"
    assert elem.get_element_identifier() == "elem-1"
    assert elem.has_id()


def test_id_absent():
    elem = PDStructureElement("P")
    assert elem.get_id() is None
    assert not elem.has_id()


def test_lang_round_trip():
    elem = PDStructureElement("P")
    elem.set_language("en-US")
    assert elem.get_language() == "en-US"
    assert elem.has_language()


def test_actual_text_alt_expanded_round_trip():
    elem = PDStructureElement("Span")
    elem.set_actual_text("ff")
    elem.set_alternate_description("a figure")
    elem.set_expanded_form("for example")
    assert elem.get_actual_text() == "ff"
    assert elem.get_alternate_description() == "a figure"
    assert elem.get_alt_text() == "a figure"
    assert elem.get_expanded_form() == "for example"
    assert elem.has_actual_text()
    assert elem.has_alternate_description()
    assert elem.has_expanded_form()


def test_string_slots_decode_only_cos_string():
    # get_string returns None for a COSName value (matches upstream getString).
    elem = PDStructureElement("P")
    elem.get_cos_object().set_item(COSName.get_pdf_name("Lang"), COSName.get_pdf_name("en"))
    assert elem.get_language() is None


# --------------------------------------------------------------------------
# /A attributes
# --------------------------------------------------------------------------


def test_attributes_single_dictionary():
    elem = PDStructureElement("P")
    attr = COSDictionary()
    attr.set_item(COSName.get_pdf_name("O"), COSName.get_pdf_name("Layout"))
    elem.get_cos_object().set_item(COSName.get_pdf_name("A"), attr)
    revs = elem.get_attributes()
    assert revs.size() == 1
    assert revs.get_revision_number_at(0) == 0


def test_attributes_array_with_revision():
    elem = PDStructureElement("P")
    attr = COSDictionary()
    attr.set_item(COSName.get_pdf_name("O"), COSName.get_pdf_name("Layout"))
    arr = COSArray()
    arr.add(attr)
    arr.add(COSInteger.get(2))
    elem.get_cos_object().set_item(COSName.get_pdf_name("A"), arr)
    revs = elem.get_attributes()
    assert revs.size() == 1
    assert revs.get_revision_number_at(0) == 2


def test_attributes_orphan_leading_integer_dropped():
    elem = PDStructureElement("P")
    arr = COSArray()
    arr.add(COSInteger.get(5))  # no preceding dict -> dropped
    attr = COSDictionary()
    attr.set_item(COSName.get_pdf_name("O"), COSName.get_pdf_name("Layout"))
    arr.add(attr)
    elem.get_cos_object().set_item(COSName.get_pdf_name("A"), arr)
    revs = elem.get_attributes()
    assert revs.size() == 1
    assert revs.get_revision_number_at(0) == 0


def test_attributes_absent_empty():
    elem = PDStructureElement("P")
    assert elem.get_attributes().size() == 0
    assert elem.get_attribute_objects() == []


# --------------------------------------------------------------------------
# marked-content kids: int MCIDs and /MCR /OBJR dict kids
# --------------------------------------------------------------------------


def test_mcr_kid_wrapped():
    elem = PDStructureElement("P")
    mcr_dict = COSDictionary()
    mcr_dict.set_item(_TYPE, COSName.get_pdf_name("MCR"))
    elem.get_cos_object().set_item(_K, mcr_dict)
    kids = elem.get_kids()
    assert len(kids) == 1
    assert isinstance(kids[0], PDMarkedContentReference)


def test_objr_kid_wrapped():
    elem = PDStructureElement("P")
    objr_dict = COSDictionary()
    objr_dict.set_item(_TYPE, COSName.get_pdf_name("OBJR"))
    elem.get_cos_object().set_item(_K, objr_dict)
    kids = elem.get_kids()
    assert len(kids) == 1
    assert isinstance(kids[0], PDObjectReference)


def test_mixed_mcid_mcr_objr_kids():
    elem = PDStructureElement("P")
    arr = COSArray()
    arr.add(COSInteger.get(0))
    mcr = COSDictionary()
    mcr.set_item(_TYPE, COSName.get_pdf_name("MCR"))
    arr.add(mcr)
    objr = COSDictionary()
    objr.set_item(_TYPE, COSName.get_pdf_name("OBJR"))
    arr.add(objr)
    se = COSDictionary()
    se.set_item(_TYPE, COSName.get_pdf_name("StructElem"))
    arr.add(se)
    elem.get_cos_object().set_item(_K, arr)
    kids = elem.get_kids()
    assert len(kids) == 4
    assert kids[0] == 0
    assert isinstance(kids[1], PDMarkedContentReference)
    assert isinstance(kids[2], PDObjectReference)
    assert isinstance(kids[3], PDStructureElement)


def test_marked_content_references_filter():
    elem = PDStructureElement("P")
    elem.append_kid(PDStructureElement("Span"))
    elem.append_kid(3)
    mcr = COSDictionary()
    mcr.set_item(_TYPE, COSName.get_pdf_name("MCR"))
    elem.append_kid(mcr)
    refs = elem.get_marked_content_references()
    # int MCID + MCR; structure-element kid excluded.
    assert len(refs) == 2
    assert 3 in refs


def test_wrap_kid_struct_elem_dispatch():
    se = COSDictionary()
    se.set_item(_TYPE, COSName.get_pdf_name("StructElem"))
    assert isinstance(PDStructureNode.wrap_kid(se), PDStructureElement)
    assert PDStructureNode.wrap_kid(COSInteger.get(4)) == 4
