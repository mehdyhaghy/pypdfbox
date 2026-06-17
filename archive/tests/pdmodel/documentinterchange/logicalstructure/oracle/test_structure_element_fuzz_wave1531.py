"""Live PDFBox differential fuzz for PDStructureElement accessors (wave 1531).

Drives the ``PDStructureElement`` accessor surface (``/S`` structure type and
its ``/RoleMap`` resolution, the string slots ``/T //Lang //Alt //E
//ActualText //ID``, ``/R`` revision, ``/P`` typed parent, ``/K`` polymorphic
kids, ``/A`` attribute objects, ``/Pg`` page) with deliberately type-confused
dictionaries and asserts pypdfbox emits the exact same projection as the live
Apache PDFBox 3.0.7 ``StructureElementFuzzProbe``.

Bugs this wave fixed (both verified here):

* ``get_structure_type`` / ``get_standard_structure_type`` now decode a ``/S``
  that is a ``COSString`` (upstream uses ``getNameAsString``) — case
  ``s_string``.
* ``_read_role_map`` now keeps ``COSString`` values (upstream builds the role
  map via ``COSDictionaryMap.convertBasicTypesToMap`` and substitutes any
  ``instanceof String`` value), drops integer/float/boolean values, and
  discards the whole map on an unconvertible value — cases ``role_string`` /
  ``role_int`` / ``role_badmap``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDAttributeObject,
    PDStructureElement,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


def _array(*values) -> COSArray:
    out = COSArray()
    for value in values:
        out.add(value)
    return out


def _typed(type_name: str | None) -> COSDictionary:
    out = COSDictionary()
    if type_name is not None:
        out.set_name(_N("Type"), type_name)
    return out


def _nv(value: str | None) -> str:
    return "-" if value is None else value


def _acc(label: str, fn) -> str:
    try:
        return f"{label}={_nv(fn())}"
    except Exception as exc:  # noqa: BLE001 - mirror Java's catch-all label
        return f"{label}=ERR:{type(exc).__name__}"


def _kid_kind(kid) -> str:
    if kid is None:
        return "null"
    if isinstance(kid, int) and not isinstance(kid, bool):
        return f"mcid{kid}"
    if isinstance(kid, PDStructureElement):
        return "elem"
    return type(kid).__name__


def _kids(elem: PDStructureElement) -> str:
    kid_list = elem.get_kids()
    if not kid_list:
        return "-"
    return ",".join(_kid_kind(kid) for kid in kid_list)


def _parent(elem: PDStructureElement) -> str:
    try:
        parent = elem.get_parent_node()
        return "null" if parent is None else type(parent).__name__
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{type(exc).__name__}"


def _owner(attr) -> str:
    if attr is None:
        return "-"
    # get_attributes() is COSArray-backed, so get_object_at returns the raw
    # COSDictionary; re-wrap to read /O owner (matches Java getOwner()).
    if isinstance(attr, COSDictionary):
        attr = PDAttributeObject.create(attr)
    return _nv(attr.get_owner())


def _attrs(elem: PDStructureElement) -> str:
    try:
        rev = elem.get_attributes()
        parts = [str(rev.size())]
        for i in range(rev.size()):
            parts.append(
                f"|{_owner(rev.get_object_at(i))}@{rev.get_revision_number_at(i)}"
            )
        return "".join(parts)
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{type(exc).__name__}"


def _page(elem: PDStructureElement) -> str:
    try:
        return "null" if elem.get_page() is None else "page"
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{type(exc).__name__}"


def _revision(elem: PDStructureElement) -> str:
    try:
        return str(elem.get_revision_number())
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{type(exc).__name__}"


def _line(name: str, dictionary: COSDictionary) -> str:
    elem = PDStructureElement(dictionary)
    parts = [f"CASE {name}"]
    parts.append(_acc("s", elem.get_structure_type))
    parts.append(_acc("std", elem.get_standard_structure_type))
    parts.append(_acc("t", elem.get_title))
    parts.append(_acc("lang", elem.get_language))
    parts.append(_acc("alt", elem.get_alternate_description))
    parts.append(_acc("exp", elem.get_expanded_form))
    parts.append(_acc("actual", elem.get_actual_text))
    parts.append(_acc("id", elem.get_element_identifier))
    parts.append("r=" + _revision(elem))
    parts.append("parent=" + _parent(elem))
    parts.append("pg=" + _page(elem))
    parts.append("kids=" + _kids(elem))
    parts.append("attr=" + _attrs(elem))
    return " ".join(parts)


def _role_root(value) -> COSDictionary:
    root = _typed("StructTreeRoot")
    rm = COSDictionary()
    rm.set_item(_N("Custom"), value)
    root.set_item(_N("RoleMap"), rm)
    elem = COSDictionary()
    elem.set_name(_N("S"), "Custom")
    elem.set_item(_N("P"), root)
    return elem


def _string_slots(setter) -> COSDictionary:
    out = COSDictionary()
    for key, value in [
        ("T", "Title"),
        ("Lang", "en"),
        ("Alt", "alt"),
        ("E", "exp"),
        ("ActualText", "act"),
        ("ID", "id1"),
    ]:
        setter(out, _N(key), value)
    return out


def _cases() -> list[tuple[str, COSDictionary]]:
    s_string = COSDictionary()
    s_string.set_item(_N("S"), COSString("P"))
    s_int = COSDictionary()
    s_int.set_item(_N("S"), COSInteger.get(3))

    role_badmap_root = _typed("StructTreeRoot")
    rm_bad = COSDictionary()
    rm_bad.set_item(_N("Custom"), _N("P"))
    rm_bad.set_item(_N("Other"), _array(COSInteger.get(1)))
    role_badmap_root.set_item(_N("RoleMap"), rm_bad)
    role_badmap = COSDictionary()
    role_badmap.set_name(_N("S"), "Custom")
    role_badmap.set_item(_N("P"), role_badmap_root)

    r_float = COSDictionary()
    r_float.set_item(_N("R"), COSFloat(2.9))
    r_string = COSDictionary()
    r_string.set_item(_N("R"), COSString("5"))
    r_neg = COSDictionary()
    r_neg.set_item(_N("R"), COSInteger.get(-3))

    p_string = COSDictionary()
    p_string.set_item(_N("P"), COSString("nope"))
    p_array = COSDictionary()
    p_array.set_item(_N("P"), _array(COSInteger.get(1)))
    p_elem = COSDictionary()
    p_elem.set_item(_N("P"), _typed("StructElem"))

    k_int = COSDictionary()
    k_int.set_item(_N("K"), COSInteger.get(4))
    k_dict = COSDictionary()
    k_dict.set_item(_N("K"), _typed("StructElem"))
    k_mixed = COSDictionary()
    k_mixed.set_item(
        _N("K"),
        _array(
            COSInteger.get(2),
            _typed("StructElem"),
            _typed("MCR"),
            _typed("OBJR"),
            _typed("Bogus"),
            COSString("x"),
        ),
    )

    a_string = COSDictionary()
    a_string.set_item(_N("A"), COSString("nope"))
    ao = COSDictionary()
    ao.set_name(_N("O"), "Layout")
    a_dict = COSDictionary()
    a_dict.set_item(_N("A"), ao)
    ao1 = COSDictionary()
    ao1.set_name(_N("O"), "Layout")
    ao2 = COSDictionary()
    ao2.set_name(_N("O"), "List")
    a_array = COSDictionary()
    a_array.set_item(_N("A"), _array(ao1, COSInteger.get(2), ao2))
    ao_orphan = COSDictionary()
    ao_orphan.set_name(_N("O"), "Layout")
    a_orphan = COSDictionary()
    a_orphan.set_item(_N("A"), _array(COSInteger.get(9), ao_orphan))

    pg_string = COSDictionary()
    pg_string.set_item(_N("Pg"), COSString("nope"))
    pg_dict = COSDictionary()
    pg_dict.set_item(_N("Pg"), COSDictionary())

    return [
        ("empty", COSDictionary()),
        ("s_string", s_string),
        ("s_int", s_int),
        ("role_name", _role_root(_N("P"))),
        ("role_string", _role_root(COSString("P"))),
        ("role_int", _role_root(COSInteger.get(7))),
        ("role_badmap", role_badmap),
        ("name_slots", _string_slots(COSDictionary.set_name)),
        ("str_slots", _string_slots(COSDictionary.set_string)),
        ("r_float", r_float),
        ("r_string", r_string),
        ("r_neg", r_neg),
        ("p_string", p_string),
        ("p_array", p_array),
        ("p_elem", p_elem),
        ("k_int", k_int),
        ("k_dict", k_dict),
        ("k_mixed", k_mixed),
        ("a_string", a_string),
        ("a_dict", a_dict),
        ("a_array", a_array),
        ("a_orphan_int", a_orphan),
        ("pg_string", pg_string),
        ("pg_dict", pg_dict),
    ]


def _py_dump() -> str:
    return "".join(_line(name, dictionary) + "\n" for name, dictionary in _cases())


@requires_oracle
def test_structure_element_fuzz_matches_pdfbox() -> None:
    assert _py_dump() == run_probe_text("StructureElementFuzzProbe")
