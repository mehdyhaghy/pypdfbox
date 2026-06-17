"""Live Apache PDFBox differential parity for ``PDFontFactory`` subtype
dispatch.

``oracle/probes/FontFactoryProbe.java`` builds one font ``COSDictionary``
per dispatch case in-process, calls upstream
``PDFontFactory.createFont(dict)`` on each, and emits a canonical
``CASE <id> <result>`` line where ``<result>`` is the resulting
``PDFont`` subclass simple-name (or, for a ``/Type0``,
``PDType0Font/<descendantClass>``), ``NULL`` when it returns ``null``, or
``RAISE:<ExceptionSimpleName>`` when ``createFont`` throws.

The Python side here reconstructs the *identical* font dictionaries with
pypdfbox COS objects, dispatches through ``PDFontFactory.create_font``,
and reduces the pypdfbox result to the same canonical string — so a
divergence (wrong subclass for a /Subtype, Type1C not detected from a
mere /FontFile3, wrong /Type0 descendant, a malformed-dict fallback that
differs from upstream's raise / Type1 fall-back) shows up as a single
differing line.

The pypdfbox ``PDFont`` subclasses carry the same simple names as their
upstream counterparts (``PDType1Font`` / ``PDType1CFont`` /
``PDMMType1Font`` / ``PDTrueTypeFont`` / ``PDType0Font`` / ``PDType3Font``
/ ``PDCIDFontType0`` / ``PDCIDFontType2``), so ``type(font).__name__``
maps to the upstream name directly.

Key dispatch contracts verified against the live oracle:

* ``/Type1`` (and ``/MMType1``) whose ``/FontDescriptor`` merely
  *contains* a ``/FontFile3`` -> ``PDType1CFont``, regardless of the
  FontFile3 ``/Subtype`` (Type1C / OpenType / subtype-less CFF all
  dispatch identically; upstream checks only ``containsKey``).
* ``/Type0`` -> ``PDType0Font`` with the descendant dispatched to
  ``PDCIDFontType0`` / ``PDCIDFontType2`` by the descendant ``/Subtype``.
* A *top-level* ``/CIDFontType0`` / ``/CIDFontType2`` -> raises (upstream
  ``IOException`` "Type N descendant font not allowed"; pypdfbox raises
  ``OSError``, reduced to ``RAISE:OSError`` <-> ``RAISE:IOException`` here).
* missing / unknown ``/Subtype`` -> ``PDType1Font`` (lenient fall-back).

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "FontFactoryProbe"

_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_FONT = COSName.get_pdf_name("Font")
_BASE_FONT = COSName.get_pdf_name("BaseFont")
_FONT_DESCRIPTOR = COSName.get_pdf_name("FontDescriptor")
_FONT_FILE = COSName.get_pdf_name("FontFile")
_FONT_FILE2 = COSName.get_pdf_name("FontFile2")
_FONT_FILE3 = COSName.get_pdf_name("FontFile3")
_DESCENDANT_FONTS = COSName.get_pdf_name("DescendantFonts")
_ENCODING = COSName.get_pdf_name("Encoding")
_CID_SYSTEM_INFO = COSName.get_pdf_name("CIDSystemInfo")


# ---------------------------------------------------------------------------
# pypdfbox font-dictionary builders — byte-for-byte the same shape as the
# corresponding builder in FontFactoryProbe.java.
# ---------------------------------------------------------------------------


def _font_dict(subtype: str | None) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _FONT)
    if subtype is not None:
        d.set_item(_SUBTYPE, COSName.get_pdf_name(subtype))
    return d


def _type1_standard14() -> COSDictionary:
    d = _font_dict("Type1")
    d.set_item(_BASE_FONT, COSName.get_pdf_name("Helvetica"))
    return d


def _type1_embedded_fontfile() -> COSDictionary:
    d = _font_dict("Type1")
    d.set_item(_BASE_FONT, COSName.get_pdf_name("ABCDEF+CustomType1"))
    fd = COSDictionary()
    fd.set_item(_TYPE, COSName.get_pdf_name("FontDescriptor"))
    fd.set_item(_FONT_FILE, COSStream())
    d.set_item(_FONT_DESCRIPTOR, fd)
    return d


def _type1_with_font_file3(subtype: str | None) -> COSDictionary:
    d = _font_dict("Type1")
    d.set_item(_BASE_FONT, COSName.get_pdf_name("ABCDEF+CFF"))
    fd = COSDictionary()
    fd.set_item(_TYPE, COSName.get_pdf_name("FontDescriptor"))
    ff3 = COSStream()
    if subtype is not None:
        ff3.set_item(_SUBTYPE, COSName.get_pdf_name(subtype))
    fd.set_item(_FONT_FILE3, ff3)
    d.set_item(_FONT_DESCRIPTOR, fd)
    return d


def _mm_type1() -> COSDictionary:
    d = _font_dict("MMType1")
    d.set_item(_BASE_FONT, COSName.get_pdf_name("MMType1Font"))
    return d


def _mm_type1_font_file3() -> COSDictionary:
    d = _font_dict("MMType1")
    d.set_item(_BASE_FONT, COSName.get_pdf_name("ABCDEF+MMCFF"))
    fd = COSDictionary()
    fd.set_item(_TYPE, COSName.get_pdf_name("FontDescriptor"))
    ff3 = COSStream()
    ff3.set_item(_SUBTYPE, COSName.get_pdf_name("Type1C"))
    fd.set_item(_FONT_FILE3, ff3)
    d.set_item(_FONT_DESCRIPTOR, fd)
    return d


def _truetype_font_file2() -> COSDictionary:
    d = _font_dict("TrueType")
    d.set_item(_BASE_FONT, COSName.get_pdf_name("ABCDEF+CustomTTF"))
    fd = COSDictionary()
    fd.set_item(_TYPE, COSName.get_pdf_name("FontDescriptor"))
    fd.set_item(_FONT_FILE2, COSStream())
    d.set_item(_FONT_DESCRIPTOR, fd)
    return d


def _type0(desc_subtype: str) -> COSDictionary:
    d = _font_dict("Type0")
    d.set_item(_BASE_FONT, COSName.get_pdf_name("ABCDEF+Composite"))
    d.set_item(_ENCODING, COSName.get_pdf_name("Identity-H"))
    desc = COSDictionary()
    desc.set_item(_TYPE, _FONT)
    desc.set_item(_SUBTYPE, COSName.get_pdf_name(desc_subtype))
    desc.set_item(_BASE_FONT, COSName.get_pdf_name("ABCDEF+Composite"))
    cidsysinfo = COSDictionary()
    cidsysinfo.set_item(COSName.get_pdf_name("Registry"), COSString("Adobe"))
    cidsysinfo.set_item(COSName.get_pdf_name("Ordering"), COSString("Identity"))
    cidsysinfo.set_int(COSName.get_pdf_name("Supplement"), 0)
    desc.set_item(_CID_SYSTEM_INFO, cidsysinfo)
    arr = COSArray()
    arr.add(desc)
    d.set_item(_DESCENDANT_FONTS, arr)
    return d


def _type3() -> COSDictionary:
    d = _font_dict("Type3")
    d.set_item(COSName.get_pdf_name("FontBBox"), COSArray())
    matrix = COSArray()
    for v in (0.001, 0.0, 0.0, 0.001, 0.0, 0.0):
        matrix.add(COSFloat(v))
    d.set_item(COSName.get_pdf_name("FontMatrix"), matrix)
    d.set_item(COSName.get_pdf_name("CharProcs"), COSDictionary())
    return d


def _missing_subtype() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _FONT)
    d.set_item(_BASE_FONT, COSName.get_pdf_name("Helvetica"))
    return d


def _unknown_subtype() -> COSDictionary:
    d = _font_dict("BogusSubtype")
    d.set_item(_BASE_FONT, COSName.get_pdf_name("Helvetica"))
    return d


def _bare_cid_font_type0() -> COSDictionary:
    d = _font_dict("CIDFontType0")
    d.set_item(_BASE_FONT, COSName.get_pdf_name("ABCDEF+BareCID0"))
    return d


def _bare_cid_font_type2() -> COSDictionary:
    d = _font_dict("CIDFontType2")
    d.set_item(_BASE_FONT, COSName.get_pdf_name("ABCDEF+BareCID2"))
    return d


# id -> builder, in the same order the probe emits them.
_BUILDERS: dict[str, object] = {
    "type1_standard14": _type1_standard14,
    "type1_embedded_fontfile": _type1_embedded_fontfile,
    "type1c_fontfile3_type1c": lambda: _type1_with_font_file3("Type1C"),
    "type1_fontfile3_no_subtype": lambda: _type1_with_font_file3(None),
    "type1_fontfile3_opentype": lambda: _type1_with_font_file3("OpenType"),
    "mmtype1": _mm_type1,
    "mmtype1_fontfile3": _mm_type1_font_file3,
    "truetype_fontfile2": _truetype_font_file2,
    "type0_cidfonttype0": lambda: _type0("CIDFontType0"),
    "type0_cidfonttype2": lambda: _type0("CIDFontType2"),
    "type3": _type3,
    "missing_subtype": _missing_subtype,
    "unknown_subtype": _unknown_subtype,
    "bare_cidfonttype0": _bare_cid_font_type0,
    "bare_cidfonttype2": _bare_cid_font_type2,
}


def _py_result(case_id: str) -> str:
    """Dispatch ``case_id`` through pypdfbox and reduce to the probe's
    canonical result string.

    pypdfbox raises ``OSError`` where upstream raises ``IOException``; the
    porting convention maps ``IOException`` -> ``OSError``, so we normalise
    a pypdfbox ``OSError`` to ``RAISE:IOException`` to compare against the
    Java side.
    """
    builder = _BUILDERS[case_id]
    font_dict = builder()  # type: ignore[operator]
    try:
        font = PDFontFactory.create_font(font_dict)
    except OSError:
        # Upstream raises java.io.IOException for the not-allowed CIDFont
        # top-level cases; the Python port raises OSError per the porting
        # convention (IOException -> OSError).
        return "RAISE:IOException"
    if font is None:
        return "NULL"
    name = type(font).__name__
    if name == "PDType0Font":
        descendant = font.get_descendant_font()
        desc_name = "null" if descendant is None else type(descendant).__name__
        return f"{name}/{desc_name}"
    return name


def _java_results() -> dict[str, str]:
    """Run the probe and parse its ``CASE <id> <result>`` lines."""
    out = run_probe_text(_PROBE)
    results: dict[str, str] = {}
    for line in out.splitlines():
        if not line.startswith("CASE\t"):
            continue
        _, case_id, result = line.split("\t", 2)
        results[case_id] = result
    return results


# ---------------------------------------------------------------------------
# Differential parity: every font dict must dispatch to the SAME upstream
# class (or raise / null) in pypdfbox as in Apache PDFBox.
# ---------------------------------------------------------------------------


@requires_oracle
def test_every_case_dispatches_identically_to_pdfbox() -> None:
    java = _java_results()
    # The probe must have emitted every case we know how to build (guards
    # against a probe edit that drops a case silently).
    assert set(java) == set(_BUILDERS), (
        f"probe/test case mismatch: java-only={set(java) - set(_BUILDERS)}, "
        f"test-only={set(_BUILDERS) - set(java)}"
    )
    py = {case_id: _py_result(case_id) for case_id in _BUILDERS}
    assert py == java


@requires_oracle
@pytest.mark.parametrize("case_id", list(_BUILDERS), ids=list(_BUILDERS))
def test_case_matches_pdfbox(case_id: str) -> None:
    java = _java_results()
    assert _py_result(case_id) == java[case_id]


# ---------------------------------------------------------------------------
# Targeted assertions on the contracts most prone to silent divergence — so a
# regression names the exact arm that broke, not just "some line differs".
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "case_id",
    [
        "type1c_fontfile3_type1c",
        "type1_fontfile3_no_subtype",
        "type1_fontfile3_opentype",
        "mmtype1_fontfile3",
    ],
    ids=[
        "type1c",
        "type1_no_subtype",
        "type1_opentype",
        "mmtype1_cff",
    ],
)
def test_fontfile3_routes_to_type1c_like_pdfbox(case_id: str) -> None:
    # Upstream routes any /Type1 or /MMType1 with a /FontFile3 (regardless
    # of that stream's own /Subtype) to PDType1CFont.
    java = _java_results()
    assert java[case_id] == "PDType1CFont"
    assert _py_result(case_id) == "PDType1CFont"


@requires_oracle
def test_type0_descendant_dispatch_matches_pdfbox() -> None:
    java = _java_results()
    assert java["type0_cidfonttype0"] == "PDType0Font/PDCIDFontType0"
    assert java["type0_cidfonttype2"] == "PDType0Font/PDCIDFontType2"
    assert _py_result("type0_cidfonttype0") == "PDType0Font/PDCIDFontType0"
    assert _py_result("type0_cidfonttype2") == "PDType0Font/PDCIDFontType2"


@requires_oracle
@pytest.mark.parametrize(
    "case_id", ["bare_cidfonttype0", "bare_cidfonttype2"]
)
def test_top_level_cid_font_raises_like_pdfbox(case_id: str) -> None:
    # A CIDFont is only legal as a /Type0 descendant; both engines reject a
    # top-level CIDFont dict (PDFBox IOException <-> pypdfbox OSError).
    java = _java_results()
    assert java[case_id] == "RAISE:IOException"
    assert _py_result(case_id) == "RAISE:IOException"


@requires_oracle
@pytest.mark.parametrize("case_id", ["missing_subtype", "unknown_subtype"])
def test_malformed_subtype_falls_back_to_type1_like_pdfbox(
    case_id: str,
) -> None:
    java = _java_results()
    assert java[case_id] == "PDType1Font"
    assert _py_result(case_id) == "PDType1Font"
