"""Live PDFBox differential fuzz for the structure /K reference kid types
(wave 1557).

Targets the reference kid types of a tagged-PDF structure element —
``PDMarkedContentReference`` (``/Type /MCR``) and ``PDObjectReference``
(``/Type /OBJR``) — plus the polymorphic ``/K`` kid resolution
``PDStructureNode.get_kids`` performs (bare-int MCID vs MCR vs OBJR vs child
``PDStructureElement``). Wave 1540 fuzzed the broad PDStructureElement accessor
surface and 1545 the tree root; this wave drills the reference-kid accessors:

* ``PDMarkedContentReference.get_mcid`` / ``get_page`` / ``__str__`` with
  ``/MCID`` present / missing / non-int / float / name / negative / zero, and
  ``/Pg`` valid / non-dict / array / int.
* ``PDObjectReference.get_referenced_object`` / ``get_page`` with ``/Obj``
  missing / annotation dict (typed, /Type-only, subtype-only, empty) / Form /
  Image / PS XObject streams / subtype-less stream / non-dict.
* ``PDStructureElement.get_kids`` kid-kind ordering for single vs array vs
  mixed ``/K`` and for wrong-/Type dicts.

Each Python projection is asserted line-for-line against the live Apache PDFBox
3.0.7 ``MarkedContentReferenceFuzzProbe`` output. The same expectations are
pinned as a self-contained table so the suite is meaningful without the oracle.

Bugs this wave fixed in ``PDObjectReference.get_referenced_object`` (all
verified here against the live oracle):

* A ``/Obj`` stream with ``/Subtype /PS`` now dispatches to
  ``PDPostScriptXObject`` via ``PDXObject.create_x_object`` instead of being
  short-circuited to ``None`` (oracle ``obj_unknown_stream``).
* A ``/Obj`` dict with NO ``/Type`` (empty dict, or unknown ``/Subtype`` with
  no ``/Type``) now resolves to ``PDAnnotationUnknown``: upstream's
  ``createAnnotation`` stamps ``/Type /Annot`` onto a type-less dict, so the
  ``ANNOT.equals(getCOSName(TYPE))`` filter passes (oracle ``obj_empty_dict`` /
  ``obj_annot_nosubtype``). Previously pypdfbox returned ``None``.
* A ``/Obj`` stream with NO ``/Subtype`` now returns ``None`` and is NOT
  treated as an annotation: upstream's stream branch is wrapped in a try/catch
  that returns null directly when ``createXObject`` raises (oracle
  ``obj_stream_nosub``).
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
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
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name
_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE = COSName.get_pdf_name("Subtype")
_MCID = COSName.get_pdf_name("MCID")
_PG = COSName.get_pdf_name("Pg")
_OBJ = COSName.get_pdf_name("Obj")
_STM = COSName.get_pdf_name("Stm")
_K = COSName.get_pdf_name("K")


# ---------- builders (mirror the Java probe's helpers) ----------


def _array(*values) -> COSArray:
    out = COSArray()
    for value in values:
        out.add(value)
    return out


def _typed(type_name: str | None) -> COSDictionary:
    out = COSDictionary()
    if type_name is not None:
        out.set_name(_TYPE, type_name)
    return out


def _stream(subtype: str | None) -> COSStream:
    out = COSStream()
    if subtype is not None:
        out.set_name(_SUBTYPE, subtype)
    return out


def _page_dict() -> COSDictionary:
    page = COSDictionary()
    page.set_name(_TYPE, "Page")
    return page


def _annot_dict() -> COSDictionary:
    annot = COSDictionary()
    annot.set_name(_TYPE, "Annot")
    annot.set_name(_SUBTYPE, "Link")
    return annot


# ---------- Python projections (mirror the Java probe's emit shapes) ----------


def _safe(fn) -> str:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - mirror Java's catch-all label
        return f"ERR:{type(exc).__name__}"


def _mcr_line(name: str, d: COSDictionary) -> str:
    mcr = PDMarkedContentReference(d)
    mcid = _safe(lambda: str(mcr.get_mcid()))
    page = _safe(lambda: "null" if mcr.get_page() is None else "page")
    text = _safe(lambda: str(mcr))
    return f"MCR {name} mcid={mcid} page={page} str={text}"


def _objr_line(name: str, d: COSDictionary) -> str:
    objr = PDObjectReference(d)

    def ref() -> str:
        r = objr.get_referenced_object()
        return "null" if r is None else type(r).__name__

    page = _safe(lambda: "null" if objr.get_page() is None else "page")
    return f"OBJR {name} ref={_safe(ref)} page={page}"


def _kid_kind(kid) -> str:
    if kid is None:
        return "null"
    if isinstance(kid, int) and not isinstance(kid, bool):
        return f"mcid{kid}"
    if isinstance(kid, PDStructureElement):
        return "elem"
    if isinstance(kid, PDMarkedContentReference):
        return f"mcr{kid.get_mcid()}"
    if isinstance(kid, PDObjectReference):
        return "objr"
    return "other"


def _kids_line(name: str, k_entry) -> str:
    d = _typed("StructElem")
    if k_entry is not None:
        d.set_item(_K, k_entry)
    elem = PDStructureElement(d)

    def kinds() -> str:
        kid_list = elem.get_kids()
        if not kid_list:
            return "-"
        return ",".join(_kid_kind(kid) for kid in kid_list)

    return f"KIDS {name} kids={_safe(kinds)}"


# ---------- case construction (1:1 with MarkedContentReferenceFuzzProbe) ----------


def _build_lines() -> list[str]:
    lines: list[str] = []

    # ===== MCR =====
    m1 = _typed("MCR")
    m1.set_item(_MCID, COSInteger.get(7))
    lines.append(_mcr_line("mcid_present", m1))

    lines.append(_mcr_line("mcid_missing", _typed("MCR")))

    m3 = _typed("MCR")
    m3.set_item(_MCID, COSString("3"))
    lines.append(_mcr_line("mcid_string", m3))

    m4 = _typed("MCR")
    m4.set_item(_MCID, COSFloat(4.9))
    lines.append(_mcr_line("mcid_float", m4))

    m5 = _typed("MCR")
    m5.set_item(_MCID, _N("9"))
    lines.append(_mcr_line("mcid_name", m5))

    m6 = _typed("MCR")
    m6.set_item(_MCID, COSInteger.get(-2))
    lines.append(_mcr_line("mcid_negative", m6))

    m7 = _typed("MCR")
    m7.set_item(_MCID, COSInteger.get(0))
    lines.append(_mcr_line("mcid_zero", m7))

    m8 = _typed("MCR")
    m8.set_item(_MCID, COSInteger.get(1))
    m8.set_item(_PG, _page_dict())
    lines.append(_mcr_line("pg_valid", m8))

    m9 = _typed("MCR")
    m9.set_item(_PG, COSString("nope"))
    lines.append(_mcr_line("pg_string", m9))

    m10 = _typed("MCR")
    m10.set_item(_PG, _array(COSInteger.get(1)))
    lines.append(_mcr_line("pg_array", m10))

    m11 = _typed("MCR")
    m11.set_item(_PG, COSInteger.get(5))
    lines.append(_mcr_line("pg_int", m11))

    m12 = _typed("OBJR")
    m12.set_item(_MCID, COSInteger.get(11))
    lines.append(_mcr_line("wrong_type_objr", m12))

    m13 = COSDictionary()
    m13.set_item(_MCID, COSInteger.get(13))
    lines.append(_mcr_line("no_type", m13))

    m14 = _typed("MCR")
    m14.set_item(_MCID, COSInteger.get(2))
    m14.set_item(_STM, _stream(None))
    lines.append(_mcr_line("stm_present", m14))

    # ===== OBJR =====
    lines.append(_objr_line("obj_missing", _typed("OBJR")))

    o16 = _typed("OBJR")
    o16.set_item(_OBJ, _annot_dict())
    lines.append(_objr_line("obj_annot_link", o16))

    o17 = _typed("OBJR")
    annot_no_sub = COSDictionary()
    annot_no_sub.set_name(_TYPE, "Annot")
    o17.set_item(_OBJ, annot_no_sub)
    lines.append(_objr_line("obj_annot_nosubtype", o17))

    o18 = _typed("OBJR")
    sub_only = COSDictionary()
    sub_only.set_name(_SUBTYPE, "Widget")
    o18.set_item(_OBJ, sub_only)
    lines.append(_objr_line("obj_subtype_only", o18))

    o19 = _typed("OBJR")
    o19.set_item(_OBJ, COSDictionary())
    lines.append(_objr_line("obj_empty_dict", o19))

    o20 = _typed("OBJR")
    o20.set_item(_OBJ, _stream("Form"))
    lines.append(_objr_line("obj_form_xobject", o20))

    o21 = _typed("OBJR")
    o21.set_item(_OBJ, _stream("Image"))
    lines.append(_objr_line("obj_image_xobject", o21))

    o22 = _typed("OBJR")
    o22.set_item(_OBJ, _stream("PS"))
    lines.append(_objr_line("obj_unknown_stream", o22))

    o23 = _typed("OBJR")
    o23.set_item(_OBJ, COSString("nope"))
    lines.append(_objr_line("obj_string", o23))

    o24 = _typed("OBJR")
    o24.set_item(_OBJ, COSInteger.get(99))
    lines.append(_objr_line("obj_int", o24))

    o25 = _typed("OBJR")
    o25.set_item(_OBJ, _annot_dict())
    o25.set_item(_PG, _page_dict())
    lines.append(_objr_line("obj_annot_pg", o25))

    o26 = _typed("OBJR")
    o26.set_item(_PG, COSString("nope"))
    lines.append(_objr_line("pg_string", o26))

    # ===== KIDS =====
    lines.append(_kids_line("k_single_int", COSInteger.get(4)))

    kmcr = _typed("MCR")
    kmcr.set_item(_MCID, COSInteger.get(8))
    lines.append(_kids_line("k_single_mcr", kmcr))

    kobjr = _typed("OBJR")
    kobjr.set_item(_OBJ, _annot_dict())
    lines.append(_kids_line("k_single_objr", kobjr))

    lines.append(_kids_line("k_single_elem", _typed("StructElem")))

    mix_mcr = _typed("MCR")
    mix_mcr.set_item(_MCID, COSInteger.get(6))
    mix_objr = _typed("OBJR")
    mix_objr.set_item(_OBJ, _annot_dict())
    lines.append(
        _kids_line(
            "k_mixed_all",
            _array(COSInteger.get(2), mix_mcr, mix_objr, _typed("StructElem")),
        )
    )

    lines.append(_kids_line("k_mcr_no_mcid", _array(_typed("MCR"))))

    lines.append(_kids_line("k_bogus_type", _typed("Bogus")))

    k_no_type = COSDictionary()
    k_no_type.set_item(_MCID, COSInteger.get(3))
    lines.append(_kids_line("k_dict_no_type", k_no_type))

    mid = _typed("MCR")
    mid.set_item(_MCID, COSInteger.get(1))
    lines.append(
        _kids_line(
            "k_array_with_bogus",
            _array(COSInteger.get(0), _typed("Bogus"), mid, _typed("OBJR")),
        )
    )

    lines.append(
        _kids_line(
            "k_array_with_string",
            _array(COSInteger.get(5), COSString("x"), _typed("StructElem")),
        )
    )

    lines.append(_kids_line("k_string_scalar", COSString("nope")))

    lines.append(
        _kids_line("k_nested_array", _array(_array(COSInteger.get(1)), COSInteger.get(2)))
    )

    lines.append(_kids_line("k_negative_int", COSInteger.get(-5)))

    lines.append(_kids_line("k_empty_array", _array()))

    return lines


# Self-contained expectations — pinned from the live Apache PDFBox 3.0.7
# MarkedContentReferenceFuzzProbe so this file is meaningful without the oracle.
_EXPECTED = [
    "MCR mcid_present mcid=7 page=null str=mcid=7",
    "MCR mcid_missing mcid=-1 page=null str=mcid=-1",
    "MCR mcid_string mcid=-1 page=null str=mcid=-1",
    "MCR mcid_float mcid=4 page=null str=mcid=4",
    "MCR mcid_name mcid=-1 page=null str=mcid=-1",
    "MCR mcid_negative mcid=-2 page=null str=mcid=-2",
    "MCR mcid_zero mcid=0 page=null str=mcid=0",
    "MCR pg_valid mcid=1 page=page str=mcid=1",
    "MCR pg_string mcid=-1 page=null str=mcid=-1",
    "MCR pg_array mcid=-1 page=null str=mcid=-1",
    "MCR pg_int mcid=-1 page=null str=mcid=-1",
    "MCR wrong_type_objr mcid=11 page=null str=mcid=11",
    "MCR no_type mcid=13 page=null str=mcid=13",
    "MCR stm_present mcid=2 page=null str=mcid=2",
    "OBJR obj_missing ref=null page=null",
    "OBJR obj_annot_link ref=PDAnnotationLink page=null",
    "OBJR obj_annot_nosubtype ref=PDAnnotationUnknown page=null",
    "OBJR obj_subtype_only ref=PDAnnotationWidget page=null",
    "OBJR obj_empty_dict ref=PDAnnotationUnknown page=null",
    "OBJR obj_form_xobject ref=PDFormXObject page=null",
    "OBJR obj_image_xobject ref=PDImageXObject page=null",
    "OBJR obj_unknown_stream ref=PDPostScriptXObject page=null",
    "OBJR obj_string ref=null page=null",
    "OBJR obj_int ref=null page=null",
    "OBJR obj_annot_pg ref=PDAnnotationLink page=page",
    "OBJR pg_string ref=null page=null",
    "KIDS k_single_int kids=mcid4",
    "KIDS k_single_mcr kids=mcr8",
    "KIDS k_single_objr kids=objr",
    "KIDS k_single_elem kids=elem",
    "KIDS k_mixed_all kids=mcid2,mcr6,objr,elem",
    "KIDS k_mcr_no_mcid kids=mcr-1",
    "KIDS k_bogus_type kids=-",
    "KIDS k_dict_no_type kids=elem",
    "KIDS k_array_with_bogus kids=mcid0,mcr1,objr",
    "KIDS k_array_with_string kids=mcid5,elem",
    "KIDS k_string_scalar kids=-",
    "KIDS k_nested_array kids=mcid2",
    "KIDS k_negative_int kids=mcid-5",
    "KIDS k_empty_array kids=-",
]


def test_python_projection_matches_pinned_expectations() -> None:
    """pypdfbox emits the PDFBox-3.0.7-pinned projection (oracle-independent)."""
    assert _build_lines() == _EXPECTED


@requires_oracle
def test_marked_content_reference_fuzz_matches_pdfbox() -> None:
    """pypdfbox matches the live Apache PDFBox 3.0.7 probe line-for-line."""
    java = run_probe_text("MarkedContentReferenceFuzzProbe").splitlines()
    assert _build_lines() == java
    # Pinned table must also track the live oracle.
    assert java == _EXPECTED
