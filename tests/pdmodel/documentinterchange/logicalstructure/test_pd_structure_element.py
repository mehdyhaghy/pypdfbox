from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)
from pypdfbox.pdmodel.pd_page import PDPage

_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_PG = COSName.get_pdf_name("Pg")
_S = COSName.get_pdf_name("S")
_P = COSName.get_pdf_name("P")
_A = COSName.get_pdf_name("A")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")


# ---------- /Pg get_page / set_page ----------


def test_get_page_returns_none_when_pg_absent() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_page() is None


def test_set_page_then_get_page_round_trip() -> None:
    elem = PDStructureElement(structure_type="P")
    page = PDPage()
    elem.set_page(page)
    got = elem.get_page()
    assert isinstance(got, PDPage)
    # Same underlying COSDictionary — no copy.
    assert got.get_cos_object() is page.get_cos_object()
    assert elem.get_cos_object().get_dictionary_object(_PG) is page.get_cos_object()


def test_set_page_none_removes_pg_entry() -> None:
    elem = PDStructureElement(structure_type="P")
    page = PDPage()
    elem.set_page(page)
    elem.set_page(None)
    assert elem.get_page() is None
    assert elem.get_cos_object().get_dictionary_object(_PG) is None


def test_set_page_accepts_raw_cos_dictionary() -> None:
    elem = PDStructureElement(structure_type="P")
    raw = COSDictionary()
    raw.set_name(_TYPE, "Page")
    elem.set_page(raw)
    got = elem.get_page()
    assert isinstance(got, PDPage)
    assert got.get_cos_object() is raw


def test_get_page_returns_none_when_pg_is_not_a_dictionary() -> None:
    # Defensive: malformed PDF where /Pg is not a dict (e.g. a name).
    elem = PDStructureElement(structure_type="P")
    elem.get_cos_object().set_name(_PG, "SomethingWeird")
    assert elem.get_page() is None


# ---------- get_standard_structure_type ----------


def _make_root_with_role_map(role_map: dict[str, str]) -> COSDictionary:
    root = COSDictionary()
    root.set_name(_TYPE, "StructTreeRoot")
    rm = COSDictionary()
    for k, v in role_map.items():
        rm.set_name(k, v)
    root.set_item(_ROLE_MAP, rm)
    return root


def test_standard_structure_type_returns_none_when_s_absent() -> None:
    elem = PDStructureElement()
    assert elem.get_standard_structure_type() is None


def test_standard_structure_type_already_standard_no_role_map() -> None:
    elem = PDStructureElement(structure_type="H1")
    # No parent chain at all — return /S unchanged.
    assert elem.get_standard_structure_type() == "H1"


def test_standard_structure_type_already_standard_with_root_no_mapping() -> None:
    root = _make_root_with_role_map({"Other": "P"})
    elem = PDStructureElement(structure_type="H1")
    elem.get_cos_object().set_item(_P, root)
    # /S not in role map → returned as-is.
    assert elem.get_standard_structure_type() == "H1"


def test_standard_structure_type_resolves_one_hop() -> None:
    root = _make_root_with_role_map({"MyHeader": "H2"})
    elem = PDStructureElement(structure_type="MyHeader")
    elem.get_cos_object().set_item(_P, root)
    assert elem.get_standard_structure_type() == "H2"


def test_standard_structure_type_resolves_single_hop_only() -> None:
    # Upstream PDFBox getStandardStructureType() does exactly ONE role-map
    # lookup — it does NOT chase a multi-hop chain. /S=MyHeader maps to
    # MyAlias, so resolution stops at MyAlias even though MyAlias would itself
    # map to the standard type P. Verified against the live oracle
    # (RoleMapResolveProbe).
    root = _make_root_with_role_map({"MyHeader": "MyAlias", "MyAlias": "P"})
    elem = PDStructureElement(structure_type="MyHeader")
    elem.get_cos_object().set_item(_P, root)
    assert elem.get_standard_structure_type() == "MyAlias"


def test_standard_structure_type_walks_parent_chain_to_root() -> None:
    # elem -> intermediate parent -> StructTreeRoot
    root = _make_root_with_role_map({"MyHeader": "H3"})
    parent = COSDictionary()
    parent.set_name(_TYPE, "StructElem")
    parent.set_name(_S, "Section")
    parent.set_item(_P, root)

    elem = PDStructureElement(structure_type="MyHeader")
    elem.get_cos_object().set_item(_P, parent)
    assert elem.get_standard_structure_type() == "H3"


def test_standard_structure_type_cycle_protection_a_to_b_to_a() -> None:
    # Pathological: A -> B -> A. Must not loop forever.
    root = _make_role_map_root_with_cycle()
    elem = PDStructureElement(structure_type="A")
    elem.get_cos_object().set_item(_P, root)
    result = elem.get_standard_structure_type()
    # We don't pin which side of the cycle wins — just that we terminate
    # and return one of the cycle participants.
    assert result in {"A", "B"}


def _make_role_map_root_with_cycle() -> COSDictionary:
    return _make_root_with_role_map({"A": "B", "B": "A"})


def test_standard_structure_type_no_root_in_chain_returns_raw_s() -> None:
    # Parent chain leads nowhere useful (no StructTreeRoot reachable).
    parent = COSDictionary()
    parent.set_name(_TYPE, "StructElem")
    parent.set_name(_S, "Section")

    elem = PDStructureElement(structure_type="MyHeader")
    elem.get_cos_object().set_item(_P, parent)
    # No role map reachable → /S returned unchanged.
    assert elem.get_standard_structure_type() == "MyHeader"


def test_standard_structure_type_role_map_with_string_value_resolves() -> None:
    # Retargeted in wave 1531 from the pre-fix contract (which assumed a
    # COSString role-map value was ignored). The live oracle
    # ``StructureElementFuzzProbe`` (case ``role_string``) proves upstream
    # builds the role map via ``COSDictionaryMap.convertBasicTypesToMap`` —
    # which decodes a COSString value to a Java String — and
    # ``getStandardStructureType`` substitutes any value that is
    # ``instanceof String`` (COSName *or* COSString).
    root = COSDictionary()
    root.set_name(_TYPE, "StructTreeRoot")
    rm = COSDictionary()
    rm.set_string("MyHeader", "NotAName")  # /MyHeader (string) — resolves.
    root.set_item(_ROLE_MAP, rm)

    elem = PDStructureElement(structure_type="MyHeader")
    elem.get_cos_object().set_item(_P, root)
    assert elem.get_standard_structure_type() == "NotAName"


# ---------- /Alt alias ----------


def test_get_alt_text_aliases_alternate_description() -> None:
    elem = PDStructureElement(structure_type="Figure")
    elem.set_alternate_description("a duck")
    assert elem.get_alt_text() == "a duck"


def test_set_alt_text_writes_alt_entry() -> None:
    elem = PDStructureElement(structure_type="Figure")
    elem.set_alt_text("a goose")
    assert elem.get_alternate_description() == "a goose"
    # Round-trip through the alias too.
    assert elem.get_alt_text() == "a goose"


def test_set_alt_text_none_clears_alt_entry() -> None:
    elem = PDStructureElement(structure_type="Figure")
    elem.set_alt_text("transient")
    elem.set_alt_text(None)
    assert elem.get_alt_text() is None


# ---------- traversal helpers ----------


def _make_struct_elem(role: str) -> PDStructureElement:
    return PDStructureElement(structure_type=role)


def _build_sample_tree() -> tuple[
    PDStructureElement,
    dict[str, PDStructureElement],
]:
    """Build a small structure tree:

        Document
          ├── H1 (h1_a)
          ├── P  (p_a)
          │     └── Span (span_a)
          ├── Figure (fig_a)
          │     └── P  (p_b)
          └── H1 (h1_b)
                └── Figure (fig_b)
    """
    root = _make_struct_elem("Document")
    h1_a = _make_struct_elem("H1")
    p_a = _make_struct_elem("P")
    span_a = _make_struct_elem("Span")
    fig_a = _make_struct_elem("Figure")
    p_b = _make_struct_elem("P")
    h1_b = _make_struct_elem("H1")
    fig_b = _make_struct_elem("Figure")

    p_a.append_kid(span_a)
    fig_a.append_kid(p_b)
    h1_b.append_kid(fig_b)

    root.append_kid(h1_a)
    root.append_kid(p_a)
    root.append_kid(fig_a)
    root.append_kid(h1_b)

    return root, {
        "h1_a": h1_a,
        "p_a": p_a,
        "span_a": span_a,
        "fig_a": fig_a,
        "p_b": p_b,
        "h1_b": h1_b,
        "fig_b": fig_b,
    }


def _cos_ids(items: list[PDStructureElement]) -> list[int]:
    return [id(it.get_cos_object()) for it in items]


def test_iter_kids_yields_direct_children_only() -> None:
    root, nodes = _build_sample_tree()
    kids = list(root.iter_kids())
    assert _cos_ids([k for k in kids if isinstance(k, PDStructureElement)]) == _cos_ids(
        [nodes["h1_a"], nodes["p_a"], nodes["fig_a"], nodes["h1_b"]]
    )


def test_iter_kids_includes_mcid_int_entries() -> None:
    elem = _make_struct_elem("P")
    elem.append_kid(7)  # /K integer MCID
    span = _make_struct_elem("Span")
    elem.append_kid(span)
    elem.append_kid(11)
    kids = list(elem.iter_kids())
    assert kids[0] == 7
    assert isinstance(kids[1], PDStructureElement)
    assert kids[1].get_cos_object() is span.get_cos_object()
    assert kids[2] == 11


def test_iter_descendants_dfs_pre_order() -> None:
    root, nodes = _build_sample_tree()
    seen = list(root.iter_descendants())
    seen_ids = _cos_ids(seen)
    expected = _cos_ids(
        [
            nodes["h1_a"],
            nodes["p_a"],
            nodes["span_a"],
            nodes["fig_a"],
            nodes["p_b"],
            nodes["h1_b"],
            nodes["fig_b"],
        ]
    )
    assert seen_ids == expected


def test_iter_descendants_skips_non_element_kids() -> None:
    elem = _make_struct_elem("P")
    elem.append_kid(42)  # MCID
    span = _make_struct_elem("Span")
    elem.append_kid(span)
    desc = list(elem.iter_descendants())
    assert len(desc) == 1
    assert desc[0].get_cos_object() is span.get_cos_object()


def test_iter_descendants_terminates_on_cycle() -> None:
    a = _make_struct_elem("Section")
    b = _make_struct_elem("Section")
    a.append_kid(b)
    # Forge a cycle b -> a directly via /K.
    b.append_kid(a)
    desc = list(a.iter_descendants())
    # Each element appears at most once — walk terminates.
    assert len(desc) <= 2
    seen_ids = _cos_ids(desc)
    assert len(set(seen_ids)) == len(seen_ids)


def test_find_by_role_figure() -> None:
    root, nodes = _build_sample_tree()
    figs = list(root.find_by_role("Figure"))
    assert _cos_ids(figs) == _cos_ids([nodes["fig_a"], nodes["fig_b"]])


def test_find_by_role_h1_yields_both_headings() -> None:
    root, nodes = _build_sample_tree()
    h1s = list(root.find_by_role("H1"))
    assert _cos_ids(h1s) == _cos_ids([nodes["h1_a"], nodes["h1_b"]])


def test_find_by_role_no_matches_returns_empty() -> None:
    root, _ = _build_sample_tree()
    assert list(root.find_by_role("DoesNotExist")) == []


def test_find_first_by_role_returns_first_match() -> None:
    root, nodes = _build_sample_tree()
    first = root.find_first_by_role("Figure")
    assert first is not None
    assert first.get_cos_object() is nodes["fig_a"].get_cos_object()


def test_find_first_by_role_returns_none_when_missing() -> None:
    root, _ = _build_sample_tree()
    assert root.find_first_by_role("Caption") is None


def test_find_by_role_resolves_through_role_map() -> None:
    # Build a tree where descendants use a non-standard /S that the
    # parent StructTreeRoot remaps to a standard one. find_by_role
    # should match against the *resolved* role.
    tree_root = COSDictionary()
    tree_root.set_name(_TYPE, "StructTreeRoot")
    rm = COSDictionary()
    rm.set_name("MyFig", "Figure")
    tree_root.set_item(_ROLE_MAP, rm)

    doc = _make_struct_elem("Document")
    doc.get_cos_object().set_item(_P, tree_root)
    fig_custom = _make_struct_elem("MyFig")
    fig_custom.get_cos_object().set_item(_P, doc.get_cos_object())
    doc.append_kid(fig_custom)

    matches = list(doc.find_by_role("Figure"))
    assert _cos_ids(matches) == _cos_ids([fig_custom])


def test_find_first_by_role_resolves_through_role_map() -> None:
    tree_root = COSDictionary()
    tree_root.set_name(_TYPE, "StructTreeRoot")
    rm = COSDictionary()
    rm.set_name("Title", "H1")
    tree_root.set_item(_ROLE_MAP, rm)

    doc = _make_struct_elem("Document")
    doc.get_cos_object().set_item(_P, tree_root)
    title = _make_struct_elem("Title")
    title.get_cos_object().set_item(_P, doc.get_cos_object())
    doc.append_kid(title)

    first = doc.find_first_by_role("H1")
    assert first is not None
    assert first.get_cos_object() is title.get_cos_object()


# ---------- typed append_kid overloads ----------


def test_append_kid_element_sets_parent_pointer() -> None:
    parent = PDStructureElement(structure_type="Document")
    child = PDStructureElement(structure_type="P")
    parent.append_kid_element(child)
    kids = parent.get_kids()
    assert len(kids) == 1
    assert kids[0].get_cos_object() is child.get_cos_object()
    # /P parent pointer should now reference parent's COSDictionary.
    assert child.get_parent() is parent.get_cos_object()


def test_append_kid_element_none_is_silent_noop() -> None:
    parent = PDStructureElement(structure_type="Document")
    parent.append_kid_element(None)  # type: ignore[arg-type]
    assert parent.get_kids() == []


def test_append_kid_marked_content_appends() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_marked_content_reference import (
        PDMarkedContentReference,
    )

    elem = PDStructureElement(structure_type="P")
    mcr = PDMarkedContentReference()
    mcr.set_mcid(7)
    elem.append_kid_marked_content(mcr)
    kids = elem.get_kids()
    assert len(kids) == 1
    assert isinstance(kids[0], PDMarkedContentReference)
    assert kids[0].get_mcid() == 7


def test_append_kid_object_reference_appends() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_object_reference import (
        PDObjectReference,
    )

    elem = PDStructureElement(structure_type="P")
    objr = PDObjectReference()
    elem.append_kid_object_reference(objr)
    kids = elem.get_kids()
    assert len(kids) == 1
    assert isinstance(kids[0], PDObjectReference)


def test_append_kid_mcid_accepts_zero_and_positive() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.append_kid_mcid(0)
    elem.append_kid_mcid(42)
    assert elem.get_kids() == [0, 42]


def test_append_kid_mcid_rejects_negative() -> None:
    import pytest

    elem = PDStructureElement(structure_type="P")
    with pytest.raises(ValueError):
        elem.append_kid_mcid(-1)


# ---------- /S setter aliases ----------


def test_set_standard_structure_type_writes_s() -> None:
    elem = PDStructureElement()
    elem.set_standard_structure_type("H1")
    assert elem.get_structure_type() == "H1"


def test_set_standard_structure_type_rejects_none() -> None:
    import pytest

    elem = PDStructureElement()
    with pytest.raises(ValueError):
        elem.set_standard_structure_type(None)  # type: ignore[arg-type]


def test_get_standard_structure_type_name_alias() -> None:
    elem = PDStructureElement(structure_type="H1")
    assert elem.get_standard_structure_type_name() == elem.get_standard_structure_type()


# ---------- add_attribute / remove_attribute / attribute_changed ----------


def test_add_attribute_appends_to_a_array() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
        PDAttributeObject,
    )

    elem = PDStructureElement(structure_type="P")
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    elem.add_attribute(attr)
    revs = elem.get_attributes()
    assert revs.size() == 1
    assert revs.get_revision_number_at(0) == 0
    assert attr.get_structure_element() is elem


def test_add_attribute_uses_current_revision_number() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
        PDAttributeObject,
    )

    elem = PDStructureElement(structure_type="P")
    elem.set_revision_number(3)
    attr = PDAttributeObject()
    attr.set_owner("List")
    elem.add_attribute(attr)
    assert elem.get_attributes().get_revision_number_at(0) == 3


def test_add_attribute_appending_two_creates_array() -> None:
    from pypdfbox.cos import COSArray
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
        PDAttributeObject,
    )

    elem = PDStructureElement(structure_type="P")
    a1 = PDAttributeObject()
    a1.set_owner("Layout")
    a2 = PDAttributeObject()
    a2.set_owner("List")
    elem.add_attribute(a1)
    elem.add_attribute(a2)
    a_value = elem.get_cos_object().get_dictionary_object(_A)
    assert isinstance(a_value, COSArray)
    assert elem.get_attributes().size() == 2


def test_add_attribute_silent_on_none() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.add_attribute(None)
    assert elem.get_attributes().size() == 0


def test_remove_attribute_removes_match() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
        PDAttributeObject,
    )

    elem = PDStructureElement(structure_type="P")
    a1 = PDAttributeObject()
    a1.set_owner("Layout")
    a2 = PDAttributeObject()
    a2.set_owner("List")
    elem.add_attribute(a1)
    elem.add_attribute(a2)
    elem.remove_attribute(a1)
    revs = elem.get_attributes()
    assert revs.size() == 1
    assert a1.get_structure_element() is None


def test_remove_attribute_clears_a_when_empty() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
        PDAttributeObject,
    )

    elem = PDStructureElement(structure_type="P")
    a1 = PDAttributeObject()
    a1.set_owner("Layout")
    elem.add_attribute(a1)
    elem.remove_attribute(a1)
    assert elem.get_attributes().size() == 0
    # Upstream parity (verified against StructAttrMutateProbe): removing the
    # only attribute from [dict, 0] leaves an orphan [0] array — upstream's
    # removeAttribute only drops the dict, and the size==2/getInt(1)==0
    # collapse never fires (size is now 1). getAttributes() drops the
    # orphan integer, so the projection is empty while the COS slot is [0].
    leftover = elem.get_cos_object().get_dictionary_object(_A)
    assert isinstance(leftover, COSArray)
    assert leftover.size() == 1
    assert leftover.get_int(0) == 0


def test_remove_attribute_silent_when_missing() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
        PDAttributeObject,
    )

    elem = PDStructureElement(structure_type="P")
    a1 = PDAttributeObject()
    a1.set_owner("Layout")
    # Not added — remove should be a quiet no-op.
    elem.remove_attribute(a1)
    assert elem.get_attributes().size() == 0


def test_attribute_changed_bumps_revision() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
        PDAttributeObject,
    )

    elem = PDStructureElement(structure_type="P")
    elem.set_revision_number(2)
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    elem.add_attribute(attr)
    elem.set_revision_number(5)
    elem.attribute_changed(attr)
    assert elem.get_attributes().get_revision_number_at(0) == 5


def test_attribute_changed_silent_when_missing() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
        PDAttributeObject,
    )

    elem = PDStructureElement(structure_type="P")
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    elem.attribute_changed(attr)  # not added — no error


# ---------- add_class_name / remove_class_name / class_name_changed ----------


def test_add_class_name_round_trip() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.add_class_name("Bold")
    revs = elem.get_class_names()
    assert revs.size() == 1
    val = revs.get_object_at(0)
    assert (val.get_name() if hasattr(val, "get_name") else val) == "Bold"
    assert revs.get_revision_number_at(0) == 0


def test_add_class_name_uses_current_revision() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_revision_number(4)
    elem.add_class_name("Italic")
    assert elem.get_class_names().get_revision_number_at(0) == 4


def test_add_two_class_names_creates_array() -> None:
    from pypdfbox.cos import COSArray

    elem = PDStructureElement(structure_type="P")
    elem.add_class_name("A")
    elem.add_class_name("B")
    c_value = elem.get_cos_object().get_dictionary_object(COSName.get_pdf_name("C"))
    assert isinstance(c_value, COSArray)
    assert elem.get_class_names().size() == 2


def test_add_class_name_none_is_noop() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.add_class_name(None)
    assert elem.get_class_names().size() == 0


def test_remove_class_name_removes_match() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.add_class_name("Bold")
    elem.add_class_name("Italic")
    elem.remove_class_name("Bold")
    revs = elem.get_class_names()
    assert revs.size() == 1
    val = revs.get_object_at(0)
    assert (val.get_name() if hasattr(val, "get_name") else val) == "Italic"


def test_remove_class_name_clears_c_when_empty() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.add_class_name("Bold")
    elem.remove_class_name("Bold")
    assert elem.get_class_names().size() == 0
    # Upstream parity: removing the only class name from [name, 0] leaves the
    # orphan [0] array (size==2/getInt(1)==0 collapse never fires at size 1).
    leftover = elem.get_cos_object().get_dictionary_object(COSName.get_pdf_name("C"))
    assert isinstance(leftover, COSArray)
    assert leftover.size() == 1
    assert leftover.get_int(0) == 0


def test_remove_class_name_silent_when_missing() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.remove_class_name("Bold")
    assert elem.get_class_names().size() == 0


def test_class_name_changed_bumps_revision() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_revision_number(2)
    elem.add_class_name("Bold")
    elem.set_revision_number(7)
    elem.class_name_changed("Bold")
    assert elem.get_class_names().get_revision_number_at(0) == 7


def test_class_name_changed_silent_when_missing() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.class_name_changed("Bold")  # not added — no error


# ---------- get_marked_content_references ----------


def test_get_marked_content_references_collects_mcids_and_mcrs() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_marked_content_reference import (
        PDMarkedContentReference,
    )

    elem = PDStructureElement(structure_type="P")
    elem.append_kid(3)
    mcr = PDMarkedContentReference()
    mcr.set_mcid(7)
    elem.append_kid(mcr)
    elem.append_kid(11)
    refs = elem.get_marked_content_references()
    assert len(refs) == 3
    assert refs[0] == 3
    assert isinstance(refs[1], PDMarkedContentReference)
    assert refs[2] == 11


def test_get_marked_content_references_skips_struct_elements() -> None:
    elem = PDStructureElement(structure_type="P")
    child = PDStructureElement(structure_type="Span")
    elem.append_kid_element(child)
    elem.append_kid(5)
    refs = elem.get_marked_content_references()
    assert refs == [5]


def test_get_marked_content_references_skips_object_references() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_object_reference import (
        PDObjectReference,
    )

    elem = PDStructureElement(structure_type="P")
    elem.append_kid(PDObjectReference())
    elem.append_kid(2)
    refs = elem.get_marked_content_references()
    assert refs == [2]


def test_get_marked_content_references_empty_when_no_kids() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_marked_content_references() == []


# ---------- /ID upstream-spelled accessors ----------


def test_get_element_identifier_returns_none_when_absent() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_element_identifier() is None


def test_set_element_identifier_round_trip() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_element_identifier("e-42")
    assert elem.get_element_identifier() == "e-42"
    # Shorter spelling is the same slot.
    assert elem.get_id() == "e-42"


def test_get_element_identifier_reads_value_set_via_set_id() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_id("identical")
    assert elem.get_element_identifier() == "identical"


# ---------- /R increment ----------


def test_increment_revision_number_from_default_zero() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_revision_number() == 0
    elem.increment_revision_number()
    assert elem.get_revision_number() == 1


def test_increment_revision_number_from_existing_value() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_revision_number(5)
    elem.increment_revision_number()
    elem.increment_revision_number()
    assert elem.get_revision_number() == 7


# ---------- typed /K remove + insert overloads ----------


def test_remove_kid_element_clears_parent_on_success() -> None:
    parent = PDStructureElement(structure_type="P")
    child = PDStructureElement(structure_type="Span")
    parent.append_kid_element(child)
    # /P should be wired by append_kid_element.
    assert child.get_parent() is parent.get_cos_object()
    removed = parent.remove_kid_element(child)
    assert removed is True
    assert child.get_parent() is None


def test_remove_kid_element_returns_false_when_not_a_kid() -> None:
    parent = PDStructureElement(structure_type="P")
    stranger = PDStructureElement(structure_type="Span")
    # Manually wire /P so we can verify it is *not* cleared on a failed remove.
    stranger.set_parent(parent)
    removed = parent.remove_kid_element(stranger)
    assert removed is False
    # /P stays put — upstream contract: only successful remove clears /P.
    assert stranger.get_parent() is parent.get_cos_object()


def test_remove_kid_element_silent_on_none() -> None:
    parent = PDStructureElement(structure_type="P")
    assert parent.remove_kid_element(None) is False  # type: ignore[arg-type]


def test_insert_before_element_inserts_typed_kid() -> None:
    parent = PDStructureElement(structure_type="P")
    a = PDStructureElement(structure_type="Span")
    b = PDStructureElement(structure_type="Span")
    parent.append_kid_element(a)
    inserted = parent.insert_before_element(b, a)
    assert inserted is True
    kids = parent.get_kids()
    assert len(kids) == 2
    assert kids[0].get_cos_object() is b.get_cos_object()
    assert kids[1].get_cos_object() is a.get_cos_object()


def test_insert_before_element_returns_false_when_ref_missing() -> None:
    parent = PDStructureElement(structure_type="P")
    a = PDStructureElement(structure_type="Span")
    b = PDStructureElement(structure_type="Span")
    # Don't append a — ref is missing.
    assert parent.insert_before_element(b, a) is False


def test_insert_before_element_silent_on_none_args() -> None:
    parent = PDStructureElement(structure_type="P")
    a = PDStructureElement(structure_type="Span")
    parent.append_kid_element(a)
    assert parent.insert_before_element(None, a) is False  # type: ignore[arg-type]
    assert parent.insert_before_element(a, None) is False


# ---------- append_kid_marked_content_object (PDMarkedContent overload) ----------


def test_append_kid_marked_content_object_appends_mcid() -> None:
    """Mirror upstream ``appendKid(PDMarkedContent)``: the mcid of the
    marked-content sequence is appended as a raw integer ``/K`` entry."""
    from pypdfbox.pdmodel.documentinterchange.markedcontent.pd_marked_content import (
        PDMarkedContent,
    )

    elem = PDStructureElement(structure_type="P")
    props = COSDictionary()
    props.set_int(COSName.get_pdf_name("MCID"), 5)
    mc = PDMarkedContent(tag=COSName.get_pdf_name("Span"), properties=props)
    elem.append_kid_marked_content_object(mc)
    kids = elem.get_kids()
    assert kids == [5]


def test_append_kid_marked_content_object_none_is_silent_noop() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.append_kid_marked_content_object(None)
    assert elem.get_kids() == []


def test_append_kid_marked_content_object_missing_mcid_raises() -> None:
    """Mirror upstream IllegalArgumentException — when ``MCID`` is absent
    from the marked-content properties (or properties is ``None``),
    :meth:`PDMarkedContent.get_mcid` returns ``-1`` and we reject the
    append, matching upstream's "mcid is negative or doesn't exist"
    contract."""
    import pytest

    from pypdfbox.pdmodel.documentinterchange.markedcontent.pd_marked_content import (
        PDMarkedContent,
    )

    elem = PDStructureElement(structure_type="P")
    # properties=None -> get_mcid() returns -1 (mirrors upstream).
    mc = PDMarkedContent(tag=COSName.get_pdf_name("Span"), properties=None)
    with pytest.raises(ValueError):
        elem.append_kid_marked_content_object(mc)


# ---------- insert_before_mcid (COSInteger overload) ----------


def test_insert_before_mcid_inserts_integer_kid() -> None:
    parent = PDStructureElement(structure_type="P")
    parent.append_kid_mcid(2)
    inserted = parent.insert_before_mcid(1, 2)
    assert inserted is True
    assert parent.get_kids() == [1, 2]


def test_insert_before_mcid_returns_false_when_ref_missing() -> None:
    parent = PDStructureElement(structure_type="P")
    parent.append_kid_mcid(5)
    # Ref kid 99 is not present.
    assert parent.insert_before_mcid(7, 99) is False


def test_insert_before_mcid_silent_on_none_ref() -> None:
    parent = PDStructureElement(structure_type="P")
    parent.append_kid_mcid(5)
    assert parent.insert_before_mcid(7, None) is False


# ---------- remove_kid_mcid / _marked_content / _object_reference ----------


def test_remove_kid_mcid_removes_integer_entry() -> None:
    parent = PDStructureElement(structure_type="P")
    parent.append_kid_mcid(0)
    parent.append_kid_mcid(7)
    removed = parent.remove_kid_mcid(7)
    assert removed is True
    assert parent.get_kids() == [0]


def test_remove_kid_mcid_returns_false_when_absent() -> None:
    parent = PDStructureElement(structure_type="P")
    parent.append_kid_mcid(0)
    assert parent.remove_kid_mcid(99) is False


def test_remove_kid_marked_content_removes_mcr_kid() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_marked_content_reference import (
        PDMarkedContentReference,
    )

    parent = PDStructureElement(structure_type="P")
    mcr = PDMarkedContentReference()
    mcr.set_mcid(3)
    parent.append_kid_marked_content(mcr)
    assert len(parent.get_kids()) == 1
    removed = parent.remove_kid_marked_content(mcr)
    assert removed is True
    assert parent.get_kids() == []


def test_remove_kid_marked_content_silent_on_none() -> None:
    parent = PDStructureElement(structure_type="P")
    assert parent.remove_kid_marked_content(None) is False


def test_remove_kid_object_reference_removes_objr_kid() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_object_reference import (
        PDObjectReference,
    )

    parent = PDStructureElement(structure_type="P")
    objr = PDObjectReference()
    parent.append_kid_object_reference(objr)
    assert len(parent.get_kids()) == 1
    removed = parent.remove_kid_object_reference(objr)
    assert removed is True
    assert parent.get_kids() == []


def test_remove_kid_object_reference_silent_on_none() -> None:
    parent = PDStructureElement(structure_type="P")
    assert parent.remove_kid_object_reference(None) is False


# ---------- iter_kid_elements / count_kids / clear_kids / get_role_map ----


def test_iter_kid_elements_filters_to_struct_elements() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_object_reference import (
        PDObjectReference,
    )

    parent = PDStructureElement(structure_type="Sect")
    child_a = PDStructureElement(structure_type="P")
    child_b = PDStructureElement(structure_type="H1")
    objr = PDObjectReference()
    parent.append_kid_element(child_a)
    parent.append_kid_object_reference(objr)
    parent.append_kid_mcid(7)
    parent.append_kid_element(child_b)

    got = list(parent.iter_kid_elements())
    assert len(got) == 2
    assert all(isinstance(g, PDStructureElement) for g in got)
    got_cos = [g.get_cos_object() for g in got]
    assert got_cos == [child_a.get_cos_object(), child_b.get_cos_object()]


def test_iter_kid_elements_empty_when_no_struct_element_kids() -> None:
    parent = PDStructureElement(structure_type="P")
    parent.append_kid_mcid(0)
    assert list(parent.iter_kid_elements()) == []


def test_count_kids_matches_get_kids_length() -> None:
    parent = PDStructureElement(structure_type="P")
    assert parent.count_kids() == 0
    parent.append_kid_mcid(0)
    parent.append_kid_mcid(1)
    parent.append_kid_mcid(2)
    assert parent.count_kids() == 3
    assert parent.count_kids() == len(parent.get_kids())


def test_clear_kids_removes_k_entry() -> None:
    parent = PDStructureElement(structure_type="P")
    parent.append_kid_mcid(0)
    parent.append_kid_mcid(1)
    assert parent.count_kids() == 2
    parent.clear_kids()
    assert parent.count_kids() == 0
    assert parent.get_cos_object().get_dictionary_object(COSName.get_pdf_name("K")) is None


def test_get_role_map_returns_role_map_when_root_reachable() -> None:
    root = _make_root_with_role_map({"MyHeader": "H1", "MyPara": "P"})
    elem = PDStructureElement(structure_type="MyHeader")
    elem.get_cos_object().set_item(_P, root)
    assert elem.get_role_map() == {"MyHeader": "H1", "MyPara": "P"}


def test_get_role_map_empty_when_no_root() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_role_map() == {}


# ---------- standard-structure-type constants ----------


def test_standard_structure_type_constants_match_pdf_spec() -> None:
    # Spot-check a representative subset across the four PDF 32000-1 §14.8.4
    # categories: grouping, block-level, inline, illustration.
    assert PDStructureElement.DOCUMENT == "Document"
    assert PDStructureElement.PART == "Part"
    assert PDStructureElement.SECT == "Sect"
    assert PDStructureElement.DIV == "Div"
    assert PDStructureElement.NON_STRUCT == "NonStruct"
    assert PDStructureElement.P == "P"
    assert PDStructureElement.H1 == "H1"
    assert PDStructureElement.H6 == "H6"
    assert PDStructureElement.LBL == "Lbl"
    assert PDStructureElement.L_BODY == "LBody"
    assert PDStructureElement.T_HEAD == "THead"
    assert PDStructureElement.T_BODY == "TBody"
    assert PDStructureElement.T_FOOT == "TFoot"
    assert PDStructureElement.SPAN == "Span"
    assert PDStructureElement.BIB_ENTRY == "BibEntry"
    assert PDStructureElement.LINK == "Link"
    assert PDStructureElement.RUBY == "Ruby"
    assert PDStructureElement.WARICHU == "Warichu"
    assert PDStructureElement.FIGURE == "Figure"
    assert PDStructureElement.FORMULA == "Formula"
    assert PDStructureElement.FORM == "Form"


def test_constants_usable_with_set_structure_type() -> None:
    elem = PDStructureElement()
    elem.set_structure_type(PDStructureElement.H1)
    assert elem.get_structure_type() == "H1"
    elem.set_standard_structure_type(PDStructureElement.FIGURE)
    assert elem.get_structure_type() == "Figure"


# ---------- is_standard_structure_type ----------


def test_is_standard_structure_type_true_for_known_types() -> None:
    assert PDStructureElement.is_standard_structure_type("H1") is True
    assert PDStructureElement.is_standard_structure_type("Document") is True
    assert PDStructureElement.is_standard_structure_type("Figure") is True
    assert PDStructureElement.is_standard_structure_type("Span") is True
    assert PDStructureElement.is_standard_structure_type("Lbl") is True
    assert PDStructureElement.is_standard_structure_type("LBody") is True
    assert PDStructureElement.is_standard_structure_type("TBody") is True


def test_is_standard_structure_type_false_for_unknown_types() -> None:
    assert PDStructureElement.is_standard_structure_type("MyHeader") is False
    assert PDStructureElement.is_standard_structure_type("h1") is False  # case-sensitive
    assert PDStructureElement.is_standard_structure_type("") is False
    assert PDStructureElement.is_standard_structure_type(None) is False


def test_is_resolved_structure_type_standard_for_direct_standard_s() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.is_resolved_structure_type_standard() is True


def test_is_resolved_structure_type_standard_false_when_s_absent() -> None:
    elem = PDStructureElement()
    assert elem.is_resolved_structure_type_standard() is False


def test_is_resolved_structure_type_standard_false_for_non_standard_no_role_map() -> None:
    elem = PDStructureElement(structure_type="MyCustomType")
    # No parent / no role-map — resolved is the raw name, which isn't standard.
    assert elem.is_resolved_structure_type_standard() is False


def test_is_resolved_structure_type_standard_true_after_role_map_remap() -> None:
    root = _make_root_with_role_map({"MyHeader": "H1"})
    elem = PDStructureElement(structure_type="MyHeader")
    elem.get_cos_object().set_item(_P, root)
    # Resolved type is "H1", which IS standard.
    assert elem.is_resolved_structure_type_standard() is True


def test_is_resolved_structure_type_standard_false_when_role_map_targets_nonstandard() -> None:
    # Non-standard /S maps to another non-standard name (chain of aliases that
    # never reaches a standard type).
    root = _make_root_with_role_map({"A": "B"})
    elem = PDStructureElement(structure_type="A")
    elem.get_cos_object().set_item(_P, root)
    # Resolved is "B" — still not in the standard set.
    assert elem.is_resolved_structure_type_standard() is False


# ---------- has_* predicates ----------


def test_has_id_false_when_absent() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.has_id() is False


def test_has_id_true_after_set_id() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_id("e-1")
    assert elem.has_id() is True


def test_has_id_false_for_empty_string() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_id("")
    # Empty /ID is treated as "not set" by the predicate, mirroring upstream
    # null-or-empty checks at PDF/UA validation call sites.
    assert elem.has_id() is False


def test_has_page_false_when_absent() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.has_page() is False


def test_has_page_true_after_set_page() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_page(PDPage())
    assert elem.has_page() is True


def test_has_page_false_when_pg_is_not_a_dictionary() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.get_cos_object().set_name(_PG, "Bogus")
    assert elem.has_page() is False


def test_has_title_round_trip() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.has_title() is False
    elem.set_title("Heading")
    assert elem.has_title() is True
    elem.set_title("")
    assert elem.has_title() is False


def test_has_language_round_trip() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.has_language() is False
    elem.set_language("en-US")
    assert elem.has_language() is True


def test_has_alternate_description_round_trip() -> None:
    elem = PDStructureElement(structure_type="Figure")
    assert elem.has_alternate_description() is False
    elem.set_alternate_description("a duck")
    assert elem.has_alternate_description() is True


def test_has_expanded_form_round_trip() -> None:
    elem = PDStructureElement(structure_type="Span")
    assert elem.has_expanded_form() is False
    elem.set_expanded_form("World Health Organization")
    assert elem.has_expanded_form() is True


def test_has_actual_text_round_trip() -> None:
    elem = PDStructureElement(structure_type="Span")
    assert elem.has_actual_text() is False
    elem.set_actual_text("hello")
    assert elem.has_actual_text() is True


def test_has_structure_type_false_when_s_absent() -> None:
    elem = PDStructureElement()
    assert elem.has_structure_type() is False


def test_has_structure_type_true_after_set_structure_type() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.has_structure_type() is True


def test_has_parent_false_when_absent() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.has_parent() is False


def test_has_parent_true_after_set_parent() -> None:
    parent = PDStructureElement(structure_type="Document")
    child = PDStructureElement(structure_type="P")
    child.set_parent(parent)
    assert child.has_parent() is True


def test_has_parent_false_when_p_is_not_a_dictionary() -> None:
    elem = PDStructureElement(structure_type="P")
    # /P set to a name (malformed input) — predicate must be False.
    elem.get_cos_object().set_name(_P, "NotADict")
    assert elem.has_parent() is False


# ---------- is_root_attached ----------


def test_is_root_attached_false_for_orphan_element() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.is_root_attached() is False


def test_is_root_attached_true_when_p_chain_reaches_root() -> None:
    root = COSDictionary()
    root.set_name(_TYPE, "StructTreeRoot")
    elem = PDStructureElement(structure_type="P")
    elem.get_cos_object().set_item(_P, root)
    assert elem.is_root_attached() is True


def test_is_root_attached_true_via_intermediate_element() -> None:
    root = COSDictionary()
    root.set_name(_TYPE, "StructTreeRoot")
    parent = COSDictionary()
    parent.set_name(_TYPE, "StructElem")
    parent.set_item(_P, root)

    child = PDStructureElement(structure_type="P")
    child.get_cos_object().set_item(_P, parent)
    assert child.is_root_attached() is True


def test_is_root_attached_false_when_chain_dangles() -> None:
    parent = COSDictionary()
    parent.set_name(_TYPE, "StructElem")
    # parent has no /P — chain ends without hitting StructTreeRoot.
    elem = PDStructureElement(structure_type="P")
    elem.get_cos_object().set_item(_P, parent)
    assert elem.is_root_attached() is False
