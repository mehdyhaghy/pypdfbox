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
