"""Differential fuzz audit for
``PDExtendedGraphicsState.copy_into_graphics_state`` over a MALFORMED
``/ExtGState`` parameter dictionary vs Apache PDFBox 3.0.7 (wave 1541, agent D).

Distinct from the accessor-leniency audit
(``test_extgstate_fuzz_wave1514.py``, which reads each typed getter in
isolation) and from the 6-mode ``test_ext_gstate_copy_edge_oracle.py``: this
audit exercises the FULL spec-default-substitution matrix of
``copy_into_graphics_state``. Each case constructs a fresh ``PDGraphicsState``
(every slot at its constructor default), optionally SEEDS one slot with a
non-default value, applies the mutated ExtGState, then projects the WHOLE
resulting graphics state. This co-tests three behaviours the prior audits do
not:

* spec-default push for a present-but-malformed numeric entry (upstream
  ``defaultIfNull``: /LW→1, /ML→10, /OPM→0, /FL→1, /SM→0, /CA→1, /ca→1,
  overwriting any seeded value);
* null-overwrite for /D, /RI, /TR, /TR2 (a malformed entry CLEARS a seeded
  value rather than leaving it intact);
* slots LEFT UNTOUCHED when the corresponding key is absent (the seed
  survives).

Both sides build the identical ExtGState dict + seed independently (the Java
probe ``oracle/probes/ExtGStateCopyFuzzProbe.java`` in Java, this module in
Python) and project the identical grammar through a real ``PDGraphicsState``,
then assert line-for-line parity. Java is ground truth.

Projection grammar (one line per mode)::

    MODE <name> lw=<f> lc=<int> lj=<int> ml=<f> ca=<f> cana=<f> bm=<name>
        ais=<0|1> tk=<0|1> sa=<0|1> op=<0|1> opns=<0|1> opm=<int> fl=<f>
        sm=<f> ri=<enum|null> dash=<proj> smask=<kind> tr=<marker>
"""

from __future__ import annotations

import math

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
from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.pdmodel.graphics.state.pd_graphics_state import PDGraphicsState
from pypdfbox.pdmodel.graphics.state.rendering_intent import RenderingIntent
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


# --------------------------------------------------------------------- helpers


def _base() -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.TYPE, _N("ExtGState"))
    return d


def _nums(*vals: float) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSFloat(float(v)))
    return a


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _smask_dict(subtype: str | None) -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.TYPE, _N("Mask"))
    if subtype is not None:
        d.set_item(_N("S"), _N(subtype))
    return d


# --------------------------------------------------------------------- corpus
#
# mode -> (seed_callable | None, extgstate_dict). The seed callable receives the
# fresh PDGraphicsState and mutates one slot to a non-default value so the
# default-push / null-overwrite behaviour is observable.

_MODES: dict[str, tuple] = {}


def _mode(name: str, d: COSDictionary, seed=None) -> None:
    _MODES[name] = (seed, d)


def _build_corpus() -> None:
    _MODES.clear()

    _mode("empty", _base())

    # --- /LW spec-default push on malformed; absent leaves seed -------------
    d = _base()
    d.set_item(_N("LW"), _N("x"))
    _mode("lw_malformed_pushes_default", d, lambda gs: gs.set_line_width(42))

    d = _base()
    d.set_item(_N("LW"), COSFloat(1.0e9))
    _mode("lw_huge", d)

    d = _base()
    d.set_item(_N("LW"), COSFloat(-5))
    _mode("lw_negative", d)

    _mode("lw_absent_seed_survives", _base(), lambda gs: gs.set_line_width(42))

    # --- /ML default 10 on malformed ---------------------------------------
    d = _base()
    d.set_item(_N("ML"), COSBoolean.TRUE)
    _mode("ml_malformed_pushes_default", d, lambda gs: gs.set_miter_limit(99))

    d = _base()
    d.set_item(_N("ML"), COSFloat(-3))
    _mode("ml_negative", d)

    # --- /LC /LJ sentinel -1 pushed verbatim -------------------------------
    d = _base()
    d.set_item(_N("LC"), _N("Round"))
    _mode("lc_malformed_pushes_sentinel", d, lambda gs: gs.set_line_cap(2))

    d = _base()
    d.set_item(_N("LJ"), COSInteger.get(2))
    _mode("lj_value", d)

    # --- /CA /ca default 1 on malformed ------------------------------------
    d = _base()
    d.set_item(_N("CA"), _N("x"))
    _mode("ca_malformed_pushes_default", d, lambda gs: gs.set_alpha_constant(0.1))

    d = _base()
    d.set_item(_N("CA"), COSFloat(0.5))
    _mode("ca_value", d)

    d = _base()
    d.set_item(_N("ca"), COSFloat(1.7))
    _mode("cana_out_of_range", d)

    d = _base()
    d.set_item(_N("ca"), COSString("0.5"))
    _mode(
        "cana_malformed_pushes_default",
        d,
        lambda gs: gs.set_non_stroke_alpha_constant(0.2),
    )

    # --- /OPM default 0 on malformed ---------------------------------------
    d = _base()
    d.set_item(_N("OPM"), _N("x"))
    _mode("opm_malformed_pushes_default", d, lambda gs: gs.set_overprint_mode(7))

    d = _base()
    d.set_item(_N("OPM"), COSInteger.get(1))
    _mode("opm_value", d)

    # --- /FL default 1, /SM default 0 on malformed -------------------------
    d = _base()
    d.set_item(_N("FL"), _N("x"))
    _mode("fl_malformed_pushes_default", d, lambda gs: gs.set_flatness(8))

    d = _base()
    d.set_item(_N("SM"), COSBoolean.FALSE)
    _mode("sm_malformed_pushes_default", d, lambda gs: gs.set_smoothness(0.9))

    # --- /BM blend mode ----------------------------------------------------
    d = _base()
    d.set_item(_N("BM"), _N("Multiply"))
    _mode("bm_known", d)

    d = _base()
    d.set_item(_N("BM"), _N("Frobnicate"))
    _mode("bm_unknown_to_normal", d)

    d = _base()
    d.set_item(_N("BM"), _arr(_N("Nope"), _N("Screen")))
    _mode("bm_array_first_known", d)

    d = _base()
    d.set_item(_N("BM"), COSString("Multiply"))
    _mode("bm_string_to_normal", d)

    # --- /RI null-overwrite + typed copy -----------------------------------
    d = _base()
    d.set_item(_N("RI"), _N("Perceptual"))
    _mode("ri_known", d)

    d = _base()
    d.set_item(_N("RI"), COSString("Saturation"))
    _mode("ri_string_resolves", d)

    d = _base()
    d.set_item(_N("RI"), _N("Frobnicate"))
    _mode("ri_unknown_to_relative", d)

    d = _base()
    d.set_item(_N("RI"), COSInteger.get(5))
    _mode(
        "ri_malformed_overwrites_seed",
        d,
        lambda gs: gs.set_rendering_intent(RenderingIntent.SATURATION),
    )

    _mode(
        "ri_absent_seed_survives",
        _base(),
        lambda gs: gs.set_rendering_intent(RenderingIntent.PERCEPTUAL),
    )

    # --- /D dash null-overwrite --------------------------------------------
    d = _base()
    d.set_item(_N("D"), _arr(_nums(3, 2), COSInteger.get(1)))
    _mode("dash_well_formed", d)

    d = _base()
    d.set_item(_N("D"), _arr(COSInteger.get(1)))
    _mode(
        "dash_malformed_overwrites_seed",
        d,
        lambda gs: gs.set_line_dash_pattern(PDLineDashPattern(_nums(7, 7), 9)),
    )

    d = _base()
    d.set_item(_N("D"), _arr(_nums(), COSInteger.get(0)))
    _mode("dash_empty_array", d)

    # --- /TR /TR2 null-overwrite + precedence ------------------------------
    d = _base()
    d.set_item(
        _N("TR"),
        _arr(_N("TRm"), _N("TRm"), _N("TRm"), _N("TRm")),
    )
    d.set_item(
        _N("TR2"),
        _arr(_N("TR2m"), _N("TR2m"), _N("TR2m"), _N("TR2m")),
    )
    _mode("tr2_wins_over_tr", d)

    d = _base()
    d.set_item(_N("TR"), _arr(_N("a"), _N("b"), _N("c")))
    _mode(
        "tr_malformed_overwrites_seed",
        d,
        lambda gs: gs.set_transfer(_N("seeded")),
    )

    d = _base()
    d.set_item(_N("TR"), _N("Identity"))
    _mode("tr_identity_name", d)

    # --- /SMask ------------------------------------------------------------
    d = _base()
    d.set_item(_N("SMask"), _N("None"))
    _mode("smask_none_name", d)

    d = _base()
    d.set_item(_N("SMask"), _smask_dict("Luminosity"))
    _mode("smask_dict", d)

    # --- booleans ----------------------------------------------------------
    d = _base()
    d.set_item(_N("AIS"), COSBoolean.TRUE)
    _mode("ais_true", d)

    d = _base()
    d.set_item(_N("TK"), COSBoolean.FALSE)
    _mode("tk_false", d)

    d = _base()
    d.set_item(_N("SA"), COSBoolean.TRUE)
    _mode("sa_true", d)

    d = _base()
    d.set_item(_N("OP"), COSBoolean.TRUE)
    _mode("op_true", d)

    d = _base()
    d.set_item(_N("OP"), COSBoolean.TRUE)
    _mode("opns_fallback_to_op", d)


# ------------------------------------------------------ Python-side projection


def _fmt(v: float) -> str:
    if math.isnan(v):
        return "nan"
    if math.isinf(v):
        return "inf" if v > 0 else "-inf"
    if v == math.floor(v):
        return str(int(v))
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return s


def _bm(gs: PDGraphicsState) -> str:
    b = gs.get_blend_mode()
    if b is None:
        return "null"
    cn = b.get_cos_name()
    return "null" if cn is None else cn.get_name()


def _ri(gs: PDGraphicsState) -> str:
    r = gs.get_rendering_intent()
    return "null" if r is None else r.name


def _dash(gs: PDGraphicsState) -> str:
    p = gs.get_line_dash_pattern()
    if p is None:
        return "null"
    body = " ".join(_fmt(float(x)) for x in p.get_dash_array())
    return f"[{body}]p{_fmt(float(p.get_phase()))}"


def _smask(gs: PDGraphicsState) -> str:
    sm = gs.get_soft_mask()
    if sm is None:
        return "null"
    st = sm.get_sub_type()
    return "dict:" + ("null" if st is None else st.get_name())


def _marker(b: COSBase | None) -> str:
    if b is None:
        return "null"
    if isinstance(b, COSName):
        return "name:" + b.get_name()
    if isinstance(b, COSArray) and b.size() > 0:
        first = b.get_object(0)
        if isinstance(first, COSName):
            return "arr:" + first.get_name()
        return f"arr{b.size()}"
    return type(b).__name__


def _project(gs: PDGraphicsState) -> str:
    parts = [
        f"lw={_fmt(gs.get_line_width())}",
        f"lc={gs.get_line_cap()}",
        f"lj={gs.get_line_join()}",
        f"ml={_fmt(gs.get_miter_limit())}",
        f"ca={_fmt(gs.get_alpha_constant())}",
        f"cana={_fmt(gs.get_non_stroke_alpha_constant())}",
        f"bm={_bm(gs)}",
        f"ais={'1' if gs.is_alpha_source() else '0'}",
        f"tk={'1' if gs.get_text_state().get_knockout_flag() else '0'}",
        f"sa={'1' if gs.is_stroke_adjustment() else '0'}",
        f"op={'1' if gs.is_overprint() else '0'}",
        f"opns={'1' if gs.is_non_stroking_overprint() else '0'}",
        f"opm={gs.get_overprint_mode()}",
        f"fl={_fmt(gs.get_flatness())}",
        f"sm={_fmt(gs.get_smoothness())}",
        f"ri={_ri(gs)}",
        f"dash={_dash(gs)}",
        f"smask={_smask(gs)}",
        f"tr={_marker(gs.get_transfer())}",
    ]
    return " ".join(parts)


def _python_line(mode: str) -> str:
    seed, d = _MODES[mode]
    try:
        gs = PDGraphicsState()
        if seed is not None:
            seed(gs)
        PDExtendedGraphicsState(d).copy_into_graphics_state(gs)
        return f"MODE {mode} " + _project(gs)
    except Exception as e:  # pragma: no cover - parity-divergence diagnostic
        return f"MODE {mode} ERR:{type(e).__name__}"


# --------------------------------------------------------------------- test


@requires_oracle
def test_extgstate_copy_fuzz_matches_pdfbox() -> None:
    """Applying each mutated ExtGState to a fresh (optionally seeded)
    PDGraphicsState lands the identical resulting state on pypdfbox and Apache
    PDFBox 3.0.7, projected across every graphics-state slot."""
    _build_corpus()
    modes = list(_MODES)

    raw = run_probe_text("ExtGStateCopyFuzzProbe", *modes)
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("MODE ")]
    assert len(java_lines) == len(modes), (
        f"probe emitted {len(java_lines)} lines for {len(modes)} modes:\n{raw}"
    )
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    mismatches: list[str] = []
    for mode in modes:
        java = java_by_name.get(mode, "<MISSING>")
        py = _python_line(mode)
        if py != java:
            mismatches.append(f"  {mode}\n    java: {java}\n    py  : {py}")

    assert not mismatches, (
        "ExtGState copy-into fuzz divergences:\n" + "\n".join(mismatches)
    )
