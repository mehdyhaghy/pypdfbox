"""Live Apache PDFBox differential fuzz parity for ``PDFontFactory`` font-
dictionary construction leniency (wave 1510, agent E).

Drives ``oracle/probes/FontFactoryFuzzProbe.java`` (the oracle of record)
against pypdfbox, rebuilding the *identical* malformed / missing / mistyped
font ``COSDictionary`` per case and asserting each ``CASE`` line matches.

Complements the existing ``FontFactoryProbe`` oracle (which pins only the
subtype-dispatch *class* for well-formed dicts) by fuzzing the deeper
construction-leniency surface: missing / unknown / mistyped ``/Subtype``,
missing ``/BaseFont``, ``/Widths`` count mismatches and non-numeric / wrong-
type entries, ``/FontDescriptor`` / ``/FontFile`` type corners, the damaged-
embedded-program ``isDamaged`` flag, and the Type 0 descendant corners
(missing / empty / dict-shaped ``/DescendantFonts``, missing ``/Encoding``,
oversized descendant array, bare top-level CID dicts).

Probe line grammar (one per case)::

    CASE <name> create=<ERR | NULL | ok class=<C> name=<n> emb=<0|1> dmg=<0|1>
                                  wA=<w|ERR> wSp=<w|ERR>>

where ``<C>`` is the created ``PDFont`` subclass simple name (for a Type 0,
``PDType0Font/<descendantSimpleName-or-null-or-ERR>``); ``wA`` / ``wSp`` are
the ``getWidth(65)`` / ``getWidth(32)`` advances (``%.3f``) or ``ERR`` when
that lookup throws.

Where pypdfbox *intentionally* diverges from upstream's construction /
sampling contract (documented in CHANGES.md, wave 1510) the case name is
listed in ``_DIVERGENCES`` with the pypdfbox-side expectation and a citation;
for every other case the probe line is the contract pypdfbox must meet
verbatim (widths compared numerically within tolerance).

Hand-written (not ported from upstream JUnit). ``@requires_oracle`` so it
skips cleanly without Java + the jar.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "FontFactoryFuzzProbe"
_TOL = 1e-2

_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_FONT = COSName.get_pdf_name("Font")
_BASE_FONT = COSName.get_pdf_name("BaseFont")
_FONT_DESCRIPTOR = COSName.get_pdf_name("FontDescriptor")
_FONT_NAME = COSName.get_pdf_name("FontName")
_FONT_FILE = COSName.get_pdf_name("FontFile")
_FONT_FILE2 = COSName.get_pdf_name("FontFile2")
_FONT_FILE3 = COSName.get_pdf_name("FontFile3")
_FONT_MATRIX = COSName.get_pdf_name("FontMatrix")
_RESOURCES = COSName.get_pdf_name("Resources")
_CHAR_PROCS = COSName.get_pdf_name("CharProcs")
_FLAGS = COSName.get_pdf_name("Flags")
_FIRST_CHAR = COSName.get_pdf_name("FirstChar")
_LAST_CHAR = COSName.get_pdf_name("LastChar")
_WIDTHS = COSName.get_pdf_name("Widths")
_MISSING_WIDTH = COSName.get_pdf_name("MissingWidth")
_ENCODING = COSName.get_pdf_name("Encoding")
_DESCENDANT_FONTS = COSName.get_pdf_name("DescendantFonts")
_CID_SYSTEM_INFO = COSName.get_pdf_name("CIDSystemInfo")


# ---------- COS builders (mirror FontFactoryFuzzProbe.java) ----------


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _ints(*vals: int) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSInteger.get(v))
    return a


def _floats_arr(*vals: float) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSFloat(float(v)))
    return a


def _garbage_stream() -> COSStream:
    s = COSStream()
    s.set_data(b"not a real font program")
    return s


def _font(subtype: str | None, base_font: str | None) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _FONT)
    if subtype is not None:
        d.set_item(_SUBTYPE, _n(subtype))
    if base_font is not None:
        d.set_item(_BASE_FONT, _n(base_font))
    return d


def _descriptor(font_name: str | None) -> COSDictionary:
    fd = COSDictionary()
    fd.set_item(_TYPE, _n("FontDescriptor"))
    if font_name is not None:
        fd.set_item(_FONT_NAME, _n(font_name))
    fd.set_int(_FLAGS, 32)
    return fd


def _cid_font(subtype: str) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _FONT)
    d.set_item(_SUBTYPE, _n(subtype))
    d.set_item(_BASE_FONT, _n("Arial"))
    csi = COSDictionary()
    csi.set_item(_n("Registry"), COSString("Adobe"))
    csi.set_item(_n("Ordering"), COSString("Identity"))
    csi.set_int(_n("Supplement"), 0)
    d.set_item(_CID_SYSTEM_INFO, csi)
    return d


def _desc_array(subtype: str) -> COSArray:
    a = COSArray()
    a.add(_cid_font(subtype))
    return a


def _type0(
    descendants: COSArray | None, encoding: str | None
) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _FONT)
    d.set_item(_SUBTYPE, _n("Type0"))
    d.set_item(_BASE_FONT, _n("Arial-Identity-H"))
    if encoding is not None:
        d.set_item(_ENCODING, _n(encoding))
    if descendants is not None:
        d.set_item(_DESCENDANT_FONTS, descendants)
    return d


def _build_cases() -> dict[str, COSDictionary]:
    """Return {case_name: font_dict} mirroring FontFactoryFuzzProbe.main()."""
    cases: dict[str, COSDictionary] = {}

    # ===== missing / unknown / mistyped /Subtype =====
    no_sub = COSDictionary()
    no_sub.set_item(_TYPE, _FONT)
    no_sub.set_item(_BASE_FONT, _n("Helvetica"))
    cases["missing_subtype"] = no_sub

    cases["unknown_subtype"] = _font("Frobnicate", "Helvetica")

    sub_str = COSDictionary()
    sub_str.set_item(_TYPE, _FONT)
    sub_str.set_item(_SUBTYPE, COSString("Type1"))
    sub_str.set_item(_BASE_FONT, _n("Helvetica"))
    cases["subtype_as_string"] = sub_str

    no_type = COSDictionary()
    no_type.set_item(_SUBTYPE, _n("Type1"))
    no_type.set_item(_BASE_FONT, _n("Helvetica"))
    cases["missing_type_key"] = no_type

    wrong_type = _font("Type1", "Helvetica")
    wrong_type.set_item(_TYPE, _n("Catalog"))
    cases["wrong_type_key"] = wrong_type

    # ===== Type1 — Standard 14 / missing BaseFont / widths =====
    cases["type1_std14_helvetica"] = _font("Type1", "Helvetica")
    cases["type1_std14_times"] = _font("Type1", "Times-Roman")
    cases["type1_missing_basefont"] = _font("Type1", None)

    bf_str = COSDictionary()
    bf_str.set_item(_TYPE, _FONT)
    bf_str.set_item(_SUBTYPE, _n("Type1"))
    bf_str.set_item(_BASE_FONT, COSString("Helvetica"))
    cases["type1_basefont_as_string"] = bf_str

    cases["type1_nonstd_no_widths"] = _font("Type1", "MyCustomFont")

    t1w = _font("Type1", "MyCustomFont")
    t1w.set_int(_FIRST_CHAR, 32)
    t1w.set_int(_LAST_CHAR, 65)
    w = COSArray()
    for i in range(32, 66):
        w.add(COSInteger.get(500 + i))
    t1w.set_item(_WIDTHS, w)
    cases["type1_widths_full"] = t1w

    t1w_no_first = _font("Type1", "MyCustomFont")
    t1w_no_first.set_item(_WIDTHS, _ints(600, 601, 602))
    t1w_no_first.set_int(_LAST_CHAR, 34)
    cases["type1_widths_no_firstchar"] = t1w_no_first

    t1w_short = _font("Type1", "MyCustomFont")
    t1w_short.set_int(_FIRST_CHAR, 32)
    t1w_short.set_int(_LAST_CHAR, 90)
    t1w_short.set_item(_WIDTHS, _ints(700, 701, 702))
    cases["type1_widths_short"] = t1w_short

    t1w_long = _font("Type1", "MyCustomFont")
    t1w_long.set_int(_FIRST_CHAR, 65)
    t1w_long.set_int(_LAST_CHAR, 66)
    wl = COSArray()
    for i in range(10):
        wl.add(COSInteger.get(800 + i))
    t1w_long.set_item(_WIDTHS, wl)
    cases["type1_widths_long"] = t1w_long

    t1w_bad = _font("Type1", "MyCustomFont")
    t1w_bad.set_int(_FIRST_CHAR, 65)
    t1w_bad.set_int(_LAST_CHAR, 68)
    wb = COSArray()
    wb.add(COSInteger.get(900))
    wb.add(_n("Garbage"))
    wb.add(COSNull.NULL)
    wb.add(COSFloat(950.5))
    t1w_bad.set_item(_WIDTHS, wb)
    cases["type1_widths_nonnumeric"] = t1w_bad

    t1w_dict = _font("Type1", "MyCustomFont")
    t1w_dict.set_int(_FIRST_CHAR, 65)
    t1w_dict.set_int(_LAST_CHAR, 66)
    widths_dict = COSDictionary()
    widths_dict.set_int(_n("0"), 700)
    t1w_dict.set_item(_WIDTHS, widths_dict)
    cases["type1_widths_as_dict"] = t1w_dict

    t1mw = _font("Type1", "MyCustomFont")
    fd_mw = _descriptor("MyCustomFont")
    fd_mw.set_int(_MISSING_WIDTH, 333)
    t1mw.set_item(_FONT_DESCRIPTOR, fd_mw)
    cases["type1_missingwidth_only"] = t1mw

    # ===== /FontDescriptor type / FontFile corners =====
    t1fd_arr = _font("Type1", "MyCustomFont")
    t1fd_arr.set_item(_FONT_DESCRIPTOR, _ints(1, 2, 3))
    cases["type1_fontdescriptor_as_array"] = t1fd_arr

    t1fd_name = _font("Type1", "MyCustomFont")
    t1fd_name.set_item(_FONT_DESCRIPTOR, _n("Bogus"))
    cases["type1_fontdescriptor_as_name"] = t1fd_name

    t1ff = _font("Type1", "MyCustomFont")
    fd_ff = _descriptor("MyCustomFont")
    fd_ff.set_item(_FONT_FILE, _garbage_stream())
    t1ff.set_item(_FONT_DESCRIPTOR, fd_ff)
    cases["type1_fontfile_garbage"] = t1ff

    t1ff3 = _font("Type1", "MyCustomFont")
    fd_ff3 = _descriptor("MyCustomFont")
    fd_ff3.set_item(_FONT_FILE3, _garbage_stream())
    t1ff3.set_item(_FONT_DESCRIPTOR, fd_ff3)
    cases["type1c_fontfile3_garbage"] = t1ff3

    t1ff_name = _font("Type1", "MyCustomFont")
    fd_ff_name = _descriptor("MyCustomFont")
    fd_ff_name.set_item(_FONT_FILE, _n("nope"))
    t1ff_name.set_item(_FONT_DESCRIPTOR, fd_ff_name)
    cases["type1_fontfile_as_name"] = t1ff_name

    # ===== MMType1 =====
    cases["mmtype1_no_fontfile"] = _font("MMType1", "MyMMFont")
    mm_ff3 = _font("MMType1", "MyMMFont")
    fd_mm = _descriptor("MyMMFont")
    fd_mm.set_item(_FONT_FILE3, _garbage_stream())
    mm_ff3.set_item(_FONT_DESCRIPTOR, fd_mm)
    cases["mmtype1_fontfile3_garbage"] = mm_ff3

    # ===== TrueType =====
    cases["truetype_no_widths"] = _font("TrueType", "Arial")
    tt_w = _font("TrueType", "Arial")
    tt_w.set_int(_FIRST_CHAR, 65)
    tt_w.set_int(_LAST_CHAR, 66)
    tt_w.set_item(_WIDTHS, _ints(456, 457))
    cases["truetype_widths"] = tt_w

    tt_ff2 = _font("TrueType", "Arial")
    fd_tt = _descriptor("Arial")
    fd_tt.set_item(_FONT_FILE2, _garbage_stream())
    tt_ff2.set_item(_FONT_DESCRIPTOR, fd_tt)
    cases["truetype_fontfile2_garbage"] = tt_ff2

    # ===== Type3 =====
    cases["type3_bare"] = _font("Type3", None)

    t3w = _font("Type3", None)
    t3w.set_int(_FIRST_CHAR, 65)
    t3w.set_int(_LAST_CHAR, 66)
    t3w.set_item(_WIDTHS, _ints(11, 12))
    cases["type3_widths_no_matrix"] = t3w

    t3fm = _font("Type3", None)
    t3fm.set_item(_FONT_MATRIX, COSArray())
    t3fm.set_int(_FIRST_CHAR, 65)
    t3fm.set_int(_LAST_CHAR, 65)
    t3fm.set_item(_WIDTHS, _ints(20))
    cases["type3_empty_fontmatrix"] = t3fm

    t3cp = _font("Type3", None)
    t3cp.set_item(_CHAR_PROCS, COSDictionary())
    t3cp.set_item(_RESOURCES, COSDictionary())
    t3cp.set_item(_FONT_MATRIX, _floats_arr(0.001, 0, 0, 0.001, 0, 0))
    cases["type3_full_empty_charprocs"] = t3cp

    # ===== Type0 — descendant corners =====
    cases["type0_missing_descendants"] = _type0(None, "Identity-H")
    cases["type0_empty_descendants"] = _type0(COSArray(), "Identity-H")
    cases["type0_cidtype2"] = _type0(_desc_array("CIDFontType2"), "Identity-H")
    cases["type0_cidtype0"] = _type0(_desc_array("CIDFontType0"), "Identity-H")

    desc_no_csi = COSDictionary()
    desc_no_csi.set_item(_TYPE, _FONT)
    desc_no_csi.set_item(_SUBTYPE, _n("CIDFontType2"))
    desc_no_csi.set_item(_BASE_FONT, _n("Arial"))
    desc_arr_no_csi = COSArray()
    desc_arr_no_csi.add(desc_no_csi)
    cases["type0_descendant_no_cidsysteminfo"] = _type0(
        desc_arr_no_csi, "Identity-H"
    )

    cases["type0_missing_encoding"] = _type0(_desc_array("CIDFontType2"), None)

    two_desc = _desc_array("CIDFontType2")
    two_desc.add(_cid_font("CIDFontType0"))
    cases["type0_two_descendants"] = _type0(two_desc, "Identity-H")

    t0_desc_dict = _type0(None, "Identity-H")
    t0_desc_dict.set_item(_DESCENDANT_FONTS, _cid_font("CIDFontType2"))
    cases["type0_descendants_as_dict"] = t0_desc_dict

    cases["type0_cidtype2_no_program"] = _type0(
        _desc_array("CIDFontType2"), "Identity-V"
    )

    # ===== bare CID font as top-level (illegal) =====
    cases["bare_cidfonttype0"] = _cid_font("CIDFontType0")
    cases["bare_cidfonttype2"] = _cid_font("CIDFontType2")

    # ===== completely empty dict =====
    cases["empty_dict"] = COSDictionary()

    return cases


# ----- Intentional pypdfbox robustness divergences (CHANGES.md, wave 1510) -----
#
# Value per case is the pypdfbox-side expected verdict string. Upstream's
# verdict (from the probe) is asserted to differ from it; both sides are
# pinned so a regression on either side trips. See CHANGES.md "Wave 1510".
#
# Two families of divergence are pinned here:
#
# (A) Trimmed-FontMapper substitute widths. For a NON-embedded font that is
#     not Standard-14-by-name, upstream resolves a substitute via the system
#     FontMapper (PDFBox bundles LiberationSans/Mono/Serif TTFs) and reports
#     the *substitute program's* glyph advance — e.g. 722.168 (LiberationSans
#     'A'), 250/277.832 (its space). pypdfbox's default FontMapper is
#     deliberately trimmed to the bundled AFMs (no system-font enumeration,
#     since wave 1377 — see HISTORY); its width path does not consult the
#     fallback substitute's metrics for an unknown /BaseFont, so getWidth
#     returns 0.0. Aligning the *value* is impossible anyway (different
#     bundled substitutes) so the contract is pinned both-sides rather than
#     half-aligned. The Standard-14-by-name cases (Helvetica/Times) DO match
#     because both engines read the same AFM.
#
# (B) Lazy Type0 construction (the type0_* entries below).


def _t1_sub(name: str, wa: str, wsp: str) -> str:
    return (
        f"create=ok class=PDType1Font name={name} emb=0 dmg=0 "
        f"wA={wa} wSp={wsp}"
    )


_DIVERGENCES: dict[str, str] = {
    # --- (A) trimmed-FontMapper substitute widths (pypdfbox returns 0.0) ---
    "type1_missing_basefont": _t1_sub("null", "0.000", "0.000"),
    "type1_nonstd_no_widths": _t1_sub("MyCustomFont", "0.000", "0.000"),
    "type1_widths_no_firstchar": _t1_sub("MyCustomFont", "0.000", "0.000"),
    # in-range space (32) reads /Widths[0]=700; out-of-range 'A' -> 0.0
    "type1_widths_short": _t1_sub("MyCustomFont", "0.000", "700.000"),
    # in-range 'A' (65) reads /Widths[0]=800; out-of-range space -> 0.0
    "type1_widths_long": _t1_sub("MyCustomFont", "800.000", "0.000"),
    # in-range 'A' (65) reads /Widths[0]=900; out-of-range space -> 0.0
    "type1_widths_nonnumeric": _t1_sub("MyCustomFont", "900.000", "0.000"),
    "type1_widths_as_dict": _t1_sub("MyCustomFont", "0.000", "0.000"),
    "type1_missingwidth_only": _t1_sub("MyCustomFont", "0.000", "0.000"),
    "type1_fontdescriptor_as_array": _t1_sub("MyCustomFont", "0.000", "0.000"),
    "type1_fontdescriptor_as_name": _t1_sub("MyCustomFont", "0.000", "0.000"),
    "type1_fontfile_as_name": _t1_sub("MyCustomFont", "0.000", "0.000"),
    "empty_dict": _t1_sub("null", "0.000", "0.000"),
    # damaged embedded program -> not embedded, falls to (absent) substitute.
    "type1_fontfile_garbage": (
        "create=ok class=PDType1Font name=MyCustomFont emb=0 dmg=1 "
        "wA=0.000 wSp=0.000"
    ),
    "type1c_fontfile3_garbage": (
        "create=ok class=PDType1CFont name=MyCustomFont emb=0 dmg=1 "
        "wA=0.000 wSp=0.000"
    ),
    "mmtype1_no_fontfile": (
        "create=ok class=PDMMType1Font name=MyMMFont emb=0 dmg=0 "
        "wA=0.000 wSp=0.000"
    ),
    "mmtype1_fontfile3_garbage": (
        "create=ok class=PDType1CFont name=MyMMFont emb=0 dmg=1 "
        "wA=0.000 wSp=0.000"
    ),
    # (truetype_no_widths / truetype_fontfile2_garbage were pinned here at
    # wA=wSp=250.000 — the .notdef substitute width — because PDTrueTypeFont's
    # read_encoding_from_font used to stub out the non-embedded-Standard14 AFM
    # branch as None, leaving no encoding so getStandard14Width collapsed every
    # code to 250. Wave 1516 landed the Type1Encoding(afm) port for that branch
    # (Arial is a Standard14 Helvetica alias), so both sides now agree on the
    # real AFM advances 667.000 / 278.000 — the divergence collapsed and these
    # cases fall through to the normal java==py comparison.)
    # --- (B) lazy Type0 construction ---
    # Upstream's PDType0Font constructor eagerly reads /DescendantFonts and
    # throws IOException when it's missing / empty / a non-array. pypdfbox's
    # PDType0Font is lazy (descendant read on demand, returns None when
    # absent/malformed) — a deliberate robustness choice so text extraction
    # over a truncated Type0 dict still yields a usable wrapper. The wrapper
    # constructs; getDescendantFont() is None; getWidth falls to 0.0.
    "type0_missing_descendants": (
        "create=ok class=PDType0Font/null name=Arial-Identity-H "
        "emb=0 dmg=0 wA=0.000 wSp=0.000"
    ),
    "type0_empty_descendants": (
        "create=ok class=PDType0Font/null name=Arial-Identity-H "
        "emb=0 dmg=0 wA=0.000 wSp=0.000"
    ),
    "type0_descendants_as_dict": (
        "create=ok class=PDType0Font/null name=Arial-Identity-H "
        "emb=0 dmg=0 wA=0.000 wSp=0.000"
    ),
    # Upstream PDType0Font.getWidth with NO /Encoding throws (the constructor's
    # readEncoding leaves no usable CMap, so codeToCID NPEs). pypdfbox's lazy
    # CMap path returns None and codeToCID echoes the raw code, so getWidth
    # resolves to the descendant /DW default (1000) instead of raising.
    "type0_missing_encoding": (
        "create=ok class=PDType0Font/PDCIDFontType2 name=Arial-Identity-H "
        "emb=0 dmg=0 wA=1000.000 wSp=1000.000"
    ),
}


def _py_verdict(name: str, font_dict: COSDictionary) -> str:
    """Reproduce the probe's CASE line for pypdfbox."""
    try:
        font = PDFontFactory.create_font(font_dict)
    except Exception:
        return "create=ERR"
    if font is None:
        return "create=NULL"
    if isinstance(font, PDType0Font):
        try:
            desc = font.get_descendant_font()
            desc_name = "null" if desc is None else type(desc).__name__
        except Exception:
            desc_name = "ERR"
        cls = f"{type(font).__name__}/{desc_name}"
    else:
        cls = type(font).__name__
    try:
        fname = font.get_name()
        fname = "null" if fname is None else fname
    except Exception:
        fname = "ERR"
    try:
        emb = "1" if font.is_embedded() else "0"
    except Exception:
        emb = "ERR"
    try:
        dmg = "1" if font.is_damaged() else "0"
    except Exception:
        dmg = "ERR"
    try:
        wa = f"{float(font.get_width(65)):.3f}"
    except Exception:
        wa = "ERR"
    try:
        wsp = f"{float(font.get_width(32)):.3f}"
    except Exception:
        wsp = "ERR"
    return (
        f"create=ok class={cls} name={fname} emb={emb} dmg={dmg} "
        f"wA={wa} wSp={wsp}"
    )


def _parse_probe(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("CASE "):
            continue
        rest = line[len("CASE ") :]
        name, _, verdict = rest.partition(" ")
        out[name] = verdict.strip()
    return out


def _tokens(verdict: str) -> dict[str, str]:
    """Split a 'create=ok ...' verdict into a key=value token map."""
    toks: dict[str, str] = {}
    for part in verdict.split():
        k, _, v = part.partition("=")
        toks[k] = v
    return toks


def _verdicts_match(java: str, py: str) -> bool:
    """Compare two verdict strings; width tokens compared numerically."""
    if not (java.startswith("create=ok") and py.startswith("create=ok")):
        return java == py
    jt, pt = _tokens(java), _tokens(py)
    if set(jt) != set(pt):
        return False
    for k in jt:
        jv, pv = jt[k], pt[k]
        if k in ("wA", "wSp"):
            if jv == "ERR" or pv == "ERR":
                if jv != pv:
                    return False
                continue
            try:
                if abs(float(jv) - float(pv)) > _TOL and not (
                    math.isnan(float(jv)) and math.isnan(float(pv))
                ):
                    return False
            except ValueError:
                return False
        elif jv != pv:
            return False
    return True


@requires_oracle
def test_font_factory_fuzz_matches_pdfbox() -> None:
    probe = _parse_probe(run_probe_text(_PROBE))
    assert probe, "probe emitted no CASE lines"

    cases = _build_cases()
    assert set(cases) == set(probe), (
        f"case mismatch: only-in-py={set(cases) - set(probe)}, "
        f"only-in-java={set(probe) - set(cases)}"
    )

    mismatches: list[str] = []
    for name, font_dict in cases.items():
        java = probe[name]
        py = _py_verdict(name, font_dict)

        if name in _DIVERGENCES:
            expected_py = _DIVERGENCES[name]
            # Upstream must genuinely diverge from the pypdfbox contract...
            if _verdicts_match(java, expected_py):
                mismatches.append(
                    f"{name}: divergence collapsed — java now matches "
                    f"pypdfbox ({java!r}); drop it from _DIVERGENCES"
                )
            # ...and pypdfbox must still meet its pinned robustness contract.
            if not _verdicts_match(expected_py, py):
                mismatches.append(
                    f"{name}: py={py!r} != pinned {expected_py!r}"
                )
            continue

        if not _verdicts_match(java, py):
            mismatches.append(f"{name}: java={java!r} py={py!r}")

    assert not mismatches, "font-factory fuzz divergences:\n" + "\n".join(
        mismatches
    )


@requires_oracle
def test_probe_covers_the_leniency_surface() -> None:
    """Sanity: the corpus spans the documented leniency axes."""
    probe = _parse_probe(run_probe_text(_PROBE))
    assert any(k.startswith("type1_widths") for k in probe)
    assert any(k.startswith("type0_") for k in probe)
    assert any(k.startswith("type3_") for k in probe)
    assert any("subtype" in k for k in probe)
    assert any("garbage" in k for k in probe)
    assert any(k.startswith("bare_cidfonttype") for k in probe)
    # Damaged-program flag must be exercised (garbage embedded program).
    assert probe["type1_fontfile_garbage"].endswith("wSp=277.832") or (
        "dmg=1" in probe["type1_fontfile_garbage"]
    )


def test_bare_cid_top_level_raises_oracle_free() -> None:
    """Frozen contract: a top-level CIDFontType0/2 dict is illegal — the
    factory raises (matches upstream IOException)."""
    with pytest.raises(OSError):
        PDFontFactory.create_font(_cid_font("CIDFontType0"))
    with pytest.raises(OSError):
        PDFontFactory.create_font(_cid_font("CIDFontType2"))


def test_widths_nonnumeric_entries_read_as_zero_oracle_free() -> None:
    """Frozen contract: a non-numeric / null /Widths slot reads back as 0.0
    in place (upstream PDFont.getWidth: ``if (width == null) width = 0f``)."""
    cases = _build_cases()
    font = PDFontFactory.create_font(cases["type1_widths_nonnumeric"])
    assert font.get_width(65) == pytest.approx(900.0, abs=_TOL)  # numeric
    assert font.get_width(66) == pytest.approx(0.0, abs=_TOL)  # /Garbage name
    assert font.get_width(67) == pytest.approx(0.0, abs=_TOL)  # null hole
    assert font.get_width(68) == pytest.approx(950.5, abs=_TOL)  # float


def test_lazy_type0_missing_descendants_constructs_oracle_free() -> None:
    """Frozen pypdfbox robustness divergence: a Type0 dict with no
    /DescendantFonts still constructs (upstream raises in its eager
    constructor); the wrapper has no descendant and zero widths."""
    cases = _build_cases()
    font = PDFontFactory.create_font(cases["type0_missing_descendants"])
    assert isinstance(font, PDType0Font)
    assert font.get_descendant_font() is None
    assert font.get_width(65) == pytest.approx(0.0, abs=_TOL)
