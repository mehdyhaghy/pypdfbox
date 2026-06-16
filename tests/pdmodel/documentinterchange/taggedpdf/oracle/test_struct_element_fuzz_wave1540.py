"""Live PDFBox differential fuzz for PDStructureElement + PDMarkInfo (wave 1540).

Widens the wave-1531 ``StructureElementFuzzProbe`` coverage to accessor corners
that probe did not exercise, asserting pypdfbox emits the exact projection of
the live Apache PDFBox 3.0.7 ``StructElementFuzzProbe``:

* ``/C`` class names (``get_class_names`` → ``Revisions``) — single name vs
  array vs interleaved revision integers vs leading orphan integer vs wrong
  type (bare string / dict) vs array with a non-name entry skipped.
* ``/Pg`` page as array / integer / name (all dangling → ``get_page()`` is
  ``None``) and a valid ``/Page`` dict.
* ``/R`` revision at ``Integer.MAX_VALUE`` (identity, no 32-bit overflow), at
  ``0``, and as a ``/Name`` (non-numeric → default ``0``).
* ``/E`` expanded form + string slots as a ``/Name`` or integer: ``get_string``
  only decodes a ``COSString``, so a name / int leaves the slot ``None``; a real
  ``COSString`` decodes.
* ``get_standard_structure_type`` across a two-hop ``/RoleMap`` chain (upstream
  does a SINGLE lookup, so the second hop is NOT followed) and a remap of an
  already-standard ``/S`` (no short-circuit, the remap wins).
* ``/K`` single-dict, deeply nested subtree, raw MCID integer, and a float kid
  (skipped).
* A compact ``PDMarkInfo`` section over absent / all-true / marked-false /
  non-boolean values.

No production bug was found by this wave — the surface is already faithful to
PDFBox 3.0.7; this probe pins the previously-untested corners both-sides.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDMarkInfo,
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
    try:
        kid_list = elem.get_kids()
        if not kid_list:
            return "-"
        parts = [str(len(kid_list))]
        for i, kid in enumerate(kid_list):
            parts.append((":" if i == 0 else ",") + _kid_kind(kid))
        return "".join(parts)
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{type(exc).__name__}"


def _class_names(elem: PDStructureElement) -> str:
    try:
        rev = elem.get_class_names()
        parts = [str(rev.size())]
        for i in range(rev.size()):
            entry = rev.get_object_at(i)
            # pypdfbox stores Revisions[COSName]; upstream Revisions<String>.
            name = entry.get_name() if isinstance(entry, COSName) else str(entry)
            parts.append(f"|{_nv(name)}@{rev.get_revision_number_at(i)}")
        return "".join(parts)
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{type(exc).__name__}"


def _parent(elem: PDStructureElement) -> str:
    try:
        parent = elem.get_parent_node()
        return "null" if parent is None else type(parent).__name__
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
    parts.append("cls=" + _class_names(elem))
    return " ".join(parts)


def _mark_line(name: str, dictionary: COSDictionary) -> str:
    mi = PDMarkInfo(dictionary)
    return (
        f"MARK {name}"
        f" marked={str(mi.is_marked()).lower()}"
        f" up={str(mi.uses_user_properties()).lower()}"
        f" suspect={str(mi.is_suspect()).lower()}"
    )


def _struct_cases() -> list[tuple[str, COSDictionary]]:
    cases: list[tuple[str, COSDictionary]] = []

    # ---- /C class names ----
    c_name = COSDictionary()
    c_name.set_item(_N("C"), _N("ClsA"))
    cases.append(("c_name", c_name))

    c_array = COSDictionary()
    c_array.set_item(_N("C"), _array(_N("ClsA"), _N("ClsB")))
    cases.append(("c_array", c_array))

    c_array_rev = COSDictionary()
    c_array_rev.set_item(_N("C"), _array(_N("ClsA"), COSInteger.get(2), _N("ClsB")))
    cases.append(("c_array_rev", c_array_rev))

    c_orphan = COSDictionary()
    c_orphan.set_item(_N("C"), _array(COSInteger.get(9), _N("ClsA")))
    cases.append(("c_orphan_int", c_orphan))

    c_string = COSDictionary()
    c_string.set_item(_N("C"), COSString("ClsA"))
    cases.append(("c_string", c_string))

    c_dict = COSDictionary()
    c_dict.set_item(_N("C"), COSDictionary())
    cases.append(("c_dict", c_dict))

    c_array_mixed = COSDictionary()
    c_array_mixed.set_item(_N("C"), _array(_N("ClsA"), COSString("skip"), _N("ClsB")))
    cases.append(("c_array_mixed", c_array_mixed))

    # ---- /Pg page non-dict shapes ----
    pg_array = COSDictionary()
    pg_array.set_item(_N("Pg"), _array(COSInteger.get(1)))
    cases.append(("pg_array", pg_array))

    pg_int = COSDictionary()
    pg_int.set_item(_N("Pg"), COSInteger.get(1))
    cases.append(("pg_int", pg_int))

    pg_name = COSDictionary()
    pg_name.set_item(_N("Pg"), _N("nope"))
    cases.append(("pg_name", pg_name))

    # ---- /R revision corners ----
    r_max = COSDictionary()
    r_max.set_item(_N("R"), COSInteger.get(2147483647))
    cases.append(("r_max", r_max))

    r_zero = COSDictionary()
    r_zero.set_item(_N("R"), COSInteger.get(0))
    cases.append(("r_zero", r_zero))

    r_name = COSDictionary()
    r_name.set_item(_N("R"), _N("5"))
    cases.append(("r_name", r_name))

    # ---- /E expanded form + string slots as name/int ----
    e_name = COSDictionary()
    e_name.set_item(_N("E"), _N("etc"))
    e_name.set_item(_N("T"), _N("Title"))
    e_name.set_item(_N("Alt"), COSInteger.get(7))
    cases.append(("e_t_name_alt_int", e_name))

    e_str = COSDictionary()
    e_str.set_item(_N("E"), COSString("et cetera"))
    e_str.set_item(_N("ActualText"), COSString("act"))
    cases.append(("e_actual_string", e_str))

    # ---- /Pg valid dict ----
    pg_dict = COSDictionary()
    pg_dict.set_item(_N("Pg"), _typed("Page"))
    cases.append(("pg_dict", pg_dict))

    # ---- getStandardStructureType: two-hop /RoleMap chain (single lookup) ----
    chain_root = _typed("StructTreeRoot")
    chain_rm = COSDictionary()
    chain_rm.set_item(_N("Custom"), _N("Custom2"))
    chain_rm.set_item(_N("Custom2"), _N("P"))
    chain_root.set_item(_N("RoleMap"), chain_rm)
    chain_elem = COSDictionary()
    chain_elem.set_name(_N("S"), "Custom")
    chain_elem.set_item(_N("P"), chain_root)
    cases.append(("role_two_hop", chain_elem))

    # /S already standard but remapped: upstream does not short-circuit.
    std_remap_root = _typed("StructTreeRoot")
    std_rm = COSDictionary()
    std_rm.set_item(_N("P"), _N("H1"))
    std_remap_root.set_item(_N("RoleMap"), std_rm)
    std_remap_elem = COSDictionary()
    std_remap_elem.set_name(_N("S"), "P")
    std_remap_elem.set_item(_N("P"), std_remap_root)
    cases.append(("role_std_remapped", std_remap_elem))

    # ---- /K shapes ----
    k_single = COSDictionary()
    k_single.set_item(_N("K"), _typed("StructElem"))
    cases.append(("k_single_dict", k_single))

    deep_leaf = _typed("StructElem")
    deep_leaf.set_item(_N("K"), COSInteger.get(11))
    deep_mid = _typed("StructElem")
    deep_mid.set_item(_N("K"), deep_leaf)
    deep_top = COSDictionary()
    deep_top.set_item(_N("K"), deep_mid)
    cases.append(("k_deep", deep_top))

    k_mcid = COSDictionary()
    k_mcid.set_item(_N("K"), COSInteger.get(5))
    cases.append(("k_mcid", k_mcid))

    k_float = COSDictionary()
    k_float.set_item(_N("K"), COSFloat(2.5))
    cases.append(("k_float", k_float))

    return cases


def _mark_cases() -> list[tuple[str, COSDictionary]]:
    absent = COSDictionary()

    all_true = COSDictionary()
    all_true.set_boolean(_N("Marked"), True)
    all_true.set_boolean(_N("UserProperties"), True)
    all_true.set_boolean(_N("Suspects"), True)

    marked_false = COSDictionary()
    marked_false.set_boolean(_N("Marked"), False)

    nonbool = COSDictionary()
    nonbool.set_item(_N("Marked"), COSInteger.get(1))
    nonbool.set_item(_N("Suspects"), COSString("true"))

    return [
        ("absent", absent),
        ("all_true", all_true),
        ("marked_false", marked_false),
        ("nonbool", nonbool),
    ]


def _py_dump() -> str:
    lines = [_line(name, d) for name, d in _struct_cases()]
    lines += [_mark_line(name, d) for name, d in _mark_cases()]
    return "".join(line + "\n" for line in lines)


@requires_oracle
def test_struct_element_fuzz_matches_pdfbox() -> None:
    assert _py_dump() == run_probe_text("StructElementFuzzProbe")


def test_struct_element_fuzz_pinned_expectations() -> None:
    """Self-contained value pins (PDFBox-3.0.7-derived) so the corners stay
    green even when the live oracle jar is absent."""
    dump = _py_dump()
    # /C: bare string is NOT a class name; dict is not either (both empty).
    assert "CASE c_string" in dump and "cls=0\n" in dump.split("CASE c_string", 1)[1]
    # Interleaved revision integer updates the most-recent name; orphan dropped.
    assert "cls=2|ClsA@2|ClsB@0" in dump
    assert "CASE c_orphan_int" in dump
    assert "cls=1|ClsA@0" in dump.split("CASE c_orphan_int", 1)[1].split("\n", 1)[0]
    # /Pg array / int / name are all dangling (get_page None).
    for label in ("pg_array", "pg_int", "pg_name"):
        seg = dump.split(f"CASE {label}", 1)[1].split("\n", 1)[0]
        assert "pg=null" in seg
    # Valid /Page dict resolves.
    assert "pg=page" in dump.split("CASE pg_dict", 1)[1].split("\n", 1)[0]
    # /R at Integer.MAX_VALUE is identity (no overflow).
    assert "r=2147483647" in dump
    # /E + /ActualText as real strings decode; a name /E does not.
    assert "exp=et cetera actual=act" in dump
    assert "exp=- actual=-" in dump.split("CASE e_t_name_alt_int", 1)[1]
    # Role map: single lookup only — Custom -> Custom2, not followed to P.
    assert "std=Custom2" in dump.split("CASE role_two_hop", 1)[1]
    # Standard /S still remapped (no short-circuit).
    assert "std=H1" in dump.split("CASE role_std_remapped", 1)[1]
    # /K float kid skipped; deep/single/mcid kids counted.
    assert "kids=-" in dump.split("CASE k_float", 1)[1].split("\n", 1)[0]
    assert "kids=1:elem" in dump.split("CASE k_single_dict", 1)[1]
    assert "kids=1:mcid5" in dump.split("CASE k_mcid", 1)[1]
    # PDMarkInfo: non-bool values fall back to default false.
    assert _mark_line("nonbool", _mark_cases()[3][1]).endswith(
        "marked=false up=false suspect=false"
    )
