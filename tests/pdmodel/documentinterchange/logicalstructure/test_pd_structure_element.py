from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)
from pypdfbox.pdmodel.pd_page import PDPage

_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_PG = COSName.get_pdf_name("Pg")
_S = COSName.get_pdf_name("S")
_P = COSName.get_pdf_name("P")
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


def test_standard_structure_type_resolves_two_hops() -> None:
    root = _make_root_with_role_map({"MyHeader": "MyAlias", "MyAlias": "P"})
    elem = PDStructureElement(structure_type="MyHeader")
    elem.get_cos_object().set_item(_P, root)
    assert elem.get_standard_structure_type() == "P"


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


def test_standard_structure_type_role_map_with_non_name_value_is_ignored() -> None:
    root = COSDictionary()
    root.set_name(_TYPE, "StructTreeRoot")
    rm = COSDictionary()
    rm.set_string("MyHeader", "NotAName")  # /MyHeader (string) — not a /Name.
    root.set_item(_ROLE_MAP, rm)

    elem = PDStructureElement(structure_type="MyHeader")
    elem.get_cos_object().set_item(_P, root)
    # Non-name role-map entry skipped → /S returned as-is.
    assert elem.get_standard_structure_type() == "MyHeader"


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
