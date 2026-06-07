"""Differential fuzz audit for ``PDExtendedGraphicsState`` accessor leniency
over a MALFORMED ``/ExtGState`` graphics-state parameter dictionary vs Apache
PDFBox 3.0.7 (wave 1514, agent A).

Complements the well-formed ExtGState parity suites (round-trip getters,
``copy_into_graphics_state`` application) — none of which exercise the
malformed / wrong-type subset this audit targets:

* ``/CA`` ``/ca`` alpha as number / out-of-range / wrong type / missing
* ``/BM`` blend mode as name / array / unknown / missing
* ``/LW`` line width, ``/LC`` line cap, ``/LJ`` line join, ``/ML`` miter limit
  — wrong type / missing
* ``/D`` dash array ``[dashArray phase]`` malformed (wrong arity, non-numeric,
  empty)
* ``/Font`` ``[font size]`` array malformed
* ``/SMask`` as name ``/None`` / dict / bad
* ``/AIS`` ``/TK`` ``/SA`` ``/OP`` ``/op`` ``/OPM`` booleans/ints wrong type
* ``/FL`` flatness, ``/SM`` smoothness, ``/RI`` rendering intent name / unknown
  / wrong type
* ``/TR`` ``/TR2`` transfer (array arity != 4 filtered)

Both sides are driven on the SAME bytes: the corpus builder writes a one-page
PDF per case (the mutated ExtGState dict installed as resource
``/ExtGState/GS1``) plus a ``manifest.txt`` into a tmp dir. The Java probe
(``oracle/probes/ExtGStateFuzzProbe.java``) loads each ``<case>.pdf`` and
projects a stable framed line through ``PDResources.getExtGState`` + the typed
accessors; this module reads the exact same files and projects the identical
grammar through pypdfbox, then asserts line-for-line parity.

Line grammar (one per case, manifest order)::

    CASE <name> lw=<f|null> lc=<int> lj=<int> ml=<f|null> ca=<f|null>
        cana=<f|null> bm=<name> ais=<0|1> tk=<0|1> sa=<0|1> op=<0|1>
        opns=<0|1> opm=<int|null> fl=<f|null> sm=<f|null> ri=<enum|null>
        dash=<proj|null> font=<set|null> fontsize=<f|null> smask=<kind>
        tr=<arity|null> tr2=<arity|null>

Java is ground truth: a real divergence is a production fix in
``pypdfbox/pdmodel/graphics/state/pd_extended_graphics_state.py``; a defensible
divergence is pinned in ``_PINNED`` with a matching CHANGES.md row.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------- helpers

_N = COSName.get_pdf_name


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _nums(*vals: float) -> COSArray:
    return _arr(*[COSFloat(float(v)) for v in vals])


def _identity_func() -> COSDictionary:
    """A minimal Type 2 (exponential) function dict — used as a /TR member."""
    f = COSDictionary()
    f.set_int(_N("FunctionType"), 2)
    f.set_item(_N("Domain"), _nums(0, 1))
    f.set_item(_N("C0"), _nums(0))
    f.set_item(_N("C1"), _nums(1))
    f.set_float(_N("N"), 1.0)
    return f


def _smask_dict(subtype: str | None) -> COSDictionary:
    d = COSDictionary()
    d.set_name(_N("Type"), "Mask")
    if subtype is not None:
        d.set_name(_N("S"), subtype)
    # A bare /G group stream is optional for accessor projection (getSubType
    # only reads /S), so we leave it out to keep the corpus minimal.
    return d


# --------------------------------------------------------------------- corpus


def _cases() -> dict[str, COSDictionary]:
    cases: dict[str, COSDictionary] = {}

    def gs(name: str, d: COSDictionary) -> None:
        cases[name] = d

    # --- empty / baseline ---------------------------------------------------
    gs("empty", COSDictionary())

    # --- /CA stroking alpha -------------------------------------------------
    d = COSDictionary()
    d.set_float(_N("CA"), 0.5)
    gs("ca_number", d)

    d = COSDictionary()
    d.set_float(_N("CA"), 1.7)  # out of [0,1] — accessor must not clamp
    gs("ca_out_of_range_high", d)

    d = COSDictionary()
    d.set_float(_N("CA"), -0.3)
    gs("ca_negative", d)

    d = COSDictionary()
    d.set_name(_N("CA"), "Half")  # wrong type → null
    gs("ca_name", d)

    d = COSDictionary()
    d.set_item(_N("CA"), COSString("0.5"))  # string → null
    gs("ca_string", d)

    d = COSDictionary()
    d.set_int(_N("CA"), 1)  # integer is a COSNumber → 1
    gs("ca_int", d)

    # --- /ca non-stroking alpha --------------------------------------------
    d = COSDictionary()
    d.set_float(_N("ca"), 0.25)
    gs("cana_number", d)

    d = COSDictionary()
    d.set_item(_N("ca"), _arr(COSFloat(0.5)))  # array → null
    gs("cana_array", d)

    # --- /BM blend mode -----------------------------------------------------
    d = COSDictionary()
    d.set_name(_N("BM"), "Multiply")
    gs("bm_known_name", d)

    d = COSDictionary()
    d.set_name(_N("BM"), "Frobnicate")  # unknown → Normal
    gs("bm_unknown_name", d)

    d = COSDictionary()
    d.set_name(_N("BM"), "Compatible")  # legacy alias → Normal
    gs("bm_compatible", d)

    d = COSDictionary()
    d.set_item(_N("BM"), _arr(_N("Frobnicate"), _N("Screen")))  # first known
    gs("bm_array_fallback", d)

    d = COSDictionary()
    d.set_item(_N("BM"), _arr(_N("Nope"), _N("AlsoNope")))  # none known → Normal
    gs("bm_array_all_unknown", d)

    d = COSDictionary()
    d.set_item(_N("BM"), COSString("Multiply"))  # string value → Normal
    gs("bm_string", d)

    d = COSDictionary()
    d.set_int(_N("BM"), 3)  # integer → Normal
    gs("bm_int", d)

    # --- /LW line width -----------------------------------------------------
    d = COSDictionary()
    d.set_float(_N("LW"), 2.5)
    gs("lw_number", d)

    d = COSDictionary()
    d.set_name(_N("LW"), "Thick")  # wrong type → null
    gs("lw_name", d)

    # --- /LC line cap / /LJ line join (int sentinel -1) ---------------------
    d = COSDictionary()
    d.set_int(_N("LC"), 2)
    gs("lc_int", d)

    d = COSDictionary()
    d.set_name(_N("LC"), "Round")  # wrong type → sentinel -1
    gs("lc_name", d)

    d = COSDictionary()
    d.set_float(_N("LC"), 1.9)  # real → getInt truncates? oracle decides
    gs("lc_real", d)

    d = COSDictionary()
    d.set_int(_N("LJ"), 1)
    gs("lj_int", d)

    d = COSDictionary()
    d.set_item(_N("LJ"), COSString("0"))  # string → sentinel -1
    gs("lj_string", d)

    # --- /ML miter limit ----------------------------------------------------
    d = COSDictionary()
    d.set_float(_N("ML"), 4.0)
    gs("ml_number", d)

    d = COSDictionary()
    d.set_item(_N("ML"), COSBoolean.TRUE)  # bool → null
    gs("ml_bool", d)

    # --- /D dash pattern [dashArray phase] ----------------------------------
    d = COSDictionary()
    d.set_item(_N("D"), _arr(_nums(3, 2), COSInteger.get(0)))
    gs("dash_well_formed", d)

    d = COSDictionary()
    d.set_item(_N("D"), _arr(_nums(), COSInteger.get(0)))  # empty dash, solid
    gs("dash_empty_array", d)

    d = COSDictionary()
    d.set_item(_N("D"), _arr(_nums(3, 2)))  # arity 1, missing phase → null
    gs("dash_arity_one", d)

    d = COSDictionary()
    d.set_item(_N("D"), _arr(_nums(3, 2), COSInteger.get(0), COSInteger.get(9)))
    gs("dash_arity_three", d)  # arity 3 → null

    d = COSDictionary()
    d.set_item(_N("D"), _arr(_N("Foo"), COSInteger.get(0)))  # inner not array
    gs("dash_inner_not_array", d)

    d = COSDictionary()
    d.set_item(_N("D"), _arr(_nums(3, 2), _N("zero")))  # phase not number
    gs("dash_phase_not_number", d)

    d = COSDictionary()
    d.set_name(_N("D"), "Solid")  # /D as name → null
    gs("dash_name", d)

    d = COSDictionary()
    d.set_item(_N("D"), _arr())  # empty outer array → null
    gs("dash_empty_outer", d)

    # --- /Font [font size] --------------------------------------------------
    d = COSDictionary()
    font_dict = COSDictionary()
    font_dict.set_name(_N("Type"), "Font")
    font_dict.set_name(_N("Subtype"), "Type1")
    font_dict.set_name(_N("BaseFont"), "Helvetica")
    d.set_item(_N("Font"), _arr(font_dict, COSFloat(12.0)))
    gs("font_well_formed", d)

    d = COSDictionary()
    d.set_item(_N("Font"), _arr())  # empty array → setting present, size 0
    gs("font_empty_array", d)

    d = COSDictionary()
    d.set_name(_N("Font"), "Helv")  # /Font as name → no setting
    gs("font_name", d)

    d = COSDictionary()
    d.set_item(_N("Font"), _arr(COSFloat(14.0)))  # size only, no font
    gs("font_size_only", d)

    # --- /SMask -------------------------------------------------------------
    d = COSDictionary()
    d.set_name(_N("SMask"), "None")  # literal /None → no soft mask
    gs("smask_none_name", d)

    d = COSDictionary()
    d.set_item(_N("SMask"), _smask_dict("Alpha"))
    gs("smask_dict_alpha", d)

    d = COSDictionary()
    d.set_item(_N("SMask"), _smask_dict("Luminosity"))
    gs("smask_dict_luminosity", d)

    d = COSDictionary()
    d.set_item(_N("SMask"), _smask_dict(None))  # dict missing /S
    gs("smask_dict_no_subtype", d)

    d = COSDictionary()
    d.set_item(_N("SMask"), COSString("None"))  # string instead of name
    gs("smask_string", d)

    d = COSDictionary()
    d.set_item(_N("SMask"), _arr(COSInteger.get(1)))  # array → bad
    gs("smask_array", d)

    # --- /AIS /TK /SA /OP /op booleans --------------------------------------
    d = COSDictionary()
    d.set_item(_N("AIS"), COSBoolean.TRUE)
    gs("ais_true", d)

    d = COSDictionary()
    d.set_int(_N("AIS"), 1)  # int → default False (getBoolean wrong type)
    gs("ais_int", d)

    d = COSDictionary()
    d.set_item(_N("TK"), COSBoolean.FALSE)  # /TK default True; explicit F
    gs("tk_false", d)

    d = COSDictionary()
    d.set_name(_N("TK"), "yes")  # wrong type → default True
    gs("tk_name", d)

    d = COSDictionary()
    d.set_item(_N("SA"), COSBoolean.TRUE)
    gs("sa_true", d)

    d = COSDictionary()
    d.set_item(_N("OP"), COSBoolean.TRUE)
    gs("op_true", d)

    d = COSDictionary()
    d.set_item(_N("OP"), COSBoolean.TRUE)  # /op falls back to /OP
    gs("op_only_opns_fallback", d)

    d = COSDictionary()
    d.set_item(_N("OP"), COSBoolean.TRUE)
    d.set_item(_N("op"), COSBoolean.FALSE)  # explicit /op overrides
    gs("op_and_opns", d)

    # --- /OPM overprint mode (boxed Integer; null when absent) --------------
    d = COSDictionary()
    d.set_int(_N("OPM"), 1)
    gs("opm_int", d)

    d = COSDictionary()
    d.set_name(_N("OPM"), "one")  # wrong type → null
    gs("opm_name", d)

    d = COSDictionary()
    d.set_float(_N("OPM"), 1.5)  # real → int truncation
    gs("opm_real", d)

    # --- /FL flatness / /SM smoothness (boxed Float; null when absent) ------
    d = COSDictionary()
    d.set_float(_N("FL"), 0.5)
    gs("fl_number", d)

    d = COSDictionary()
    d.set_name(_N("FL"), "Flat")  # wrong type → null
    gs("fl_name", d)

    d = COSDictionary()
    d.set_float(_N("SM"), 0.02)
    gs("sm_number", d)

    # --- /RI rendering intent ----------------------------------------------
    d = COSDictionary()
    d.set_name(_N("RI"), "Perceptual")
    gs("ri_known", d)

    d = COSDictionary()
    d.set_name(_N("RI"), "Frobnicate")  # unknown → RELATIVE_COLORIMETRIC
    gs("ri_unknown", d)

    d = COSDictionary()
    d.set_item(_N("RI"), COSString("Perceptual"))  # string → ?
    gs("ri_string", d)

    # --- /TR /TR2 transfer functions ---------------------------------------
    d = COSDictionary()
    d.set_name(_N("TR"), "Identity")
    gs("tr_identity_name", d)

    d = COSDictionary()
    d.set_item(
        _N("TR"),
        _arr(
            _identity_func(),
            _identity_func(),
            _identity_func(),
            _identity_func(),
        ),
    )
    gs("tr_array_four", d)

    d = COSDictionary()
    d.set_item(_N("TR"), _arr(_identity_func(), _identity_func()))  # arity 2
    gs("tr_array_two", d)  # != 4 → filtered to null

    d = COSDictionary()
    d.set_name(_N("TR2"), "Default")
    gs("tr2_default_name", d)

    d = COSDictionary()
    d.set_item(_N("TR2"), _arr(_identity_func()))  # arity 1 → filtered
    gs("tr2_array_one", d)

    return cases


# ----------------------------------------------------- corpus writer


def _write_case_pdf(path: Path, entry: COSDictionary) -> None:
    """Build a one-page PDF whose first page carries the mutated ExtGState dict
    as resource ``/ExtGState/GS1`` and save it to ``path``."""
    from pypdfbox.pdmodel.pd_page import PDPage

    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        resources = COSDictionary()
        sub = COSDictionary()
        sub.set_item(_N("GS1"), entry)
        resources.set_item(_N("ExtGState"), sub)
        page.set_resources(resources)
        doc.save(str(path))
    finally:
        doc.close()


# ----------------------------------------------------- Python-side projection


def _fmt(value: float | None) -> str:
    if value is None:
        return "null"
    if math.isnan(value):
        return "nan"
    if value == math.floor(value) and not math.isinf(value):
        return str(int(value))
    # The accessors return a Python float carrying a float32-rounded value
    # (COSFloat stores single precision). Java's probe formats via
    # ``Float.toString`` (shortest decimal that round-trips for float32);
    # ``str(np.float32(value))`` produces the identical shortest form, so
    # 1.7f prints "1.7" on both sides rather than the float64 expansion.
    return str(np.float32(value))


def _arity(base: COSBase | None) -> str:
    if base is None:
        return "absent"
    if isinstance(base, COSArray):
        return f"arr{base.size()}"
    return type(base).__name__


def _bm_proj(gs) -> str:  # type: ignore[no-untyped-def]
    try:
        bm = gs.get_blend_mode()
        if bm is None:
            return "null"
        cn = bm.get_cos_name()
        return "null" if cn is None else cn.get_name()
    except Exception:
        return "ERR"


def _ri_proj(gs) -> str:  # type: ignore[no-untyped-def]
    try:
        ri = gs.get_rendering_intent_typed()
        return "null" if ri is None else ri.name
    except Exception:
        return "ERR"


def _dash_proj(gs) -> str:  # type: ignore[no-untyped-def]
    try:
        d = gs.get_line_dash_pattern()
        if d is None:
            return "null"
        return f"dash{len(d.get_dash_array())}:{_fmt(float(d.get_phase()))}"
    except Exception:
        return "ERR"


def _font_proj(gs) -> str:  # type: ignore[no-untyped-def]
    try:
        fs = gs.get_font_setting()
        return "null" if fs is None else "set"
    except Exception:
        return "ERR"


def _font_size_proj(gs) -> str:  # type: ignore[no-untyped-def]
    try:
        fs = gs.get_font_setting()
        if fs is None:
            return "null"
        return _fmt(float(fs.get_font_size()))
    except Exception:
        return "ERR"


def _smask_proj(gs) -> str:  # type: ignore[no-untyped-def]
    try:
        sm = gs.get_soft_mask_typed()
        if sm is None:
            return "null"
        st = sm.get_sub_type()
        return f"dict:{'null' if st is None else st.get_name()}"
    except Exception:
        return "ERR"


def _f(fn) -> str:  # type: ignore[no-untyped-def]
    try:
        return _fmt(fn())
    except Exception:
        return "ERR"


def _i(fn) -> str:  # type: ignore[no-untyped-def]
    try:
        return str(fn())
    except Exception:
        return "ERR"


def _b(fn) -> str:  # type: ignore[no-untyped-def]
    try:
        return "1" if fn() else "0"
    except Exception:
        return "ERR"


def _opm_proj(gs) -> str:  # type: ignore[no-untyped-def]
    try:
        om = gs.get_overprint_mode()
        return "null" if om is None else str(om)
    except Exception:
        return "ERR"


def _project_state(gs) -> str:  # type: ignore[no-untyped-def]
    parts = [
        f"lw={_f(gs.get_line_width)}",
        f"lc={_i(gs.get_line_cap_style)}",
        f"lj={_i(gs.get_line_join_style)}",
        f"ml={_f(gs.get_miter_limit)}",
        f"ca={_f(gs.get_stroking_alpha_constant)}",
        f"cana={_f(gs.get_non_stroking_alpha_constant)}",
        f"bm={_bm_proj(gs)}",
        f"ais={_b(gs.get_alpha_source_flag)}",
        f"tk={_b(gs.get_text_knockout_flag)}",
        f"sa={_b(gs.get_stroke_adjustment)}",
        f"op={_b(gs.get_stroke_overprint)}",
        f"opns={_b(gs.get_non_stroking_overprint)}",
        f"opm={_opm_proj(gs)}",
        f"fl={_f(gs.get_flatness)}",
        f"sm={_f(gs.get_smoothness)}",
        f"ri={_ri_proj(gs)}",
        f"dash={_dash_proj(gs)}",
        f"font={_font_proj(gs)}",
        f"fontsize={_font_size_proj(gs)}",
        f"smask={_smask_proj(gs)}",
        f"tr={_arity(gs.get_transfer())}",
        f"tr2={_arity(gs.get_transfer2())}",
    ]
    return " ".join(parts)


def _java_exc(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return "IOException"
    return type(exc).__name__


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:
        return prefix + f"STATE=ERR:{_java_exc(e)}"
    try:
        page = doc.get_page(0)
        resources = page.get_resources()
        try:
            gs = resources.get_ext_g_state(_N("GS1"))
        except Exception as e:
            return prefix + f"STATE=ERR:{_java_exc(e)}"
        if gs is None:
            return prefix + "STATE=null"
        return prefix + _project_state(gs)
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
# Java is ground truth; only defensible robustness divergences are pinned here.

# Defensible robustness divergence (pinned both-sides): a malformed /Font
# array whose size < 2 (or whose size-1 slot is not a COSNumber) makes upstream
# PDFontSetting.getFontSize() throw — it does a raw COSArray.get(1) + a
# (COSNumber) cast, so an empty or size-only array raises
# IndexOutOfBoundsException / ClassCastException (the probe reports
# fontsize=ERR). pypdfbox's PDFontSetting.get_font_size() guards the size and
# the type and returns the spec-neutral 0.0 instead of raising, so a broken
# /Font entry can't crash a consumer mid-render. The font *setting* itself
# resolves identically (font=set on both sides); only the size-accessor's
# fault tolerance differs. Pinned rather than forced to throw: introducing a
# raise would regress the established lenient contract (see
# tests/pdmodel/graphics/state/test_pd_font_setting*.py) for no parity benefit
# on well-formed input. See CHANGES.md wave 1514.
_FONTSIZE_LENIENCY = (
    "pypdfbox PDFontSetting.get_font_size() returns 0.0 for a /Font array of "
    "size < 2 (or non-numeric size slot) where upstream throws "
    "IndexOutOfBounds/ClassCast; the font setting resolves identically."
)


def _pin_fontsize(name: str) -> tuple[str, str, str]:
    base = (
        f"CASE {name} lw=null lc=-1 lj=-1 ml=null ca=null cana=null bm=Normal "
        f"ais=0 tk=1 sa=0 op=0 opns=0 opm=null fl=null sm=null ri=null "
        f"dash=null font=set fontsize={{size}} smask=null tr=absent tr2=absent"
    )
    return (base.format(size="0"), base.format(size="ERR"), _FONTSIZE_LENIENCY)


_PINNED: dict[str, tuple[str, str, str]] = {
    "font_empty_array": _pin_fontsize("font_empty_array"),
    "font_size_only": _pin_fontsize("font_size_only"),
}


# --------------------------------------------------------------------- test


@requires_oracle
def test_extgstate_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every mutated ExtGState dict projects through the typed accessors
    identically on pypdfbox and Apache PDFBox 3.0.7. Divergences are pinned
    explicitly in ``_PINNED`` (with a matching CHANGES.md row)."""
    corpus = _cases()
    for name, entry in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", entry)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("ExtGStateFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines for {len(corpus)} cases:\n{raw}"
    )
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    mismatches: list[str] = []
    for name in corpus:
        java = java_by_name.get(name, "<MISSING>")
        py = _python_line(tmp_path, name)
        if name in _PINNED:
            py_exp, java_exp, _reason = _PINNED[name]
            if py == py_exp and java == java_exp:
                continue
        if py != java:
            mismatches.append(f"  {name}\n    java: {java}\n    py  : {py}")

    assert not mismatches, "ExtGState fuzz divergences:\n" + "\n".join(mismatches)
