"""Differential AFM-parse fuzz vs Apache FontBox 3.0.7 (wave 1548).

A complementary sibling of the wave-1522 AFM parse-fuzz battery
(``test_afm_parser_fuzz_wave1522.py``). Wave 1522 projected the header /
font-bbox / aggregate counts / first-char-metric slice; this wave drives the
SAME ``org.apache.fontbox.afm.AFMParser`` but projects a *different, deeper*
slice so the two waves cover complementary sections of the parsed
``FontMetrics``:

  * global vertical metrics — ``CapHeight`` / ``XHeight`` / ``Ascender`` /
    ``Descender`` / ``ItalicAngle`` / ``IsFixedPitch`` (untouched by 1522);
  * the three kern-pair lists *separately* (``KernPairs`` / ``KernPairs0`` /
    ``KernPairs1``), plus ``KPH`` hex pairs and ``StartTrackKern`` entries;
  * per-char extended width vectors (``W`` / ``W0`` / ``W1`` / ``VV`` / ``WY``)
    and ``L`` ligatures, which wave 1522 never reached.

The mutant corpus therefore targets track-kern framing, ``KPH`` hex pair
parsing, vertical kern-pair lists, ligature lines, multi-float ``W*`` width
vectors, ``VVector`` / ``CharWidth`` two-float arity, and the global vertical
metrics — angles that the wave-1522 corpus did not exercise.

Both engines parse the *identical* bytes and are compared on the projection
emitted by ``oracle/probes/AfmParseFuzzProbe.java``:

    ok=true
    name=<FontName or NULL>
    vm=<capHeight,xHeight,ascender,descender,italicAngle>  (4dp each)
    fixedpitch=<true|false>
    nchar=<CharMetric count>
    nkp=<KernPairs size>   nkp0=<KernPairs0 size>   nkp1=<KernPairs1 size>
    ntrack=<TrackKern count>
    ncomp=<Composite count>
    nlig=<total ligatures across all CharMetrics>
    cm0=<name,code,wx,wy,w,w0,w1,vv,bbox of first CharMetric or NULL>
    kp0=<first,second,x,y of first KernPair sorted, or NULL>
    tk0=<degree,minPt,minKern,maxPt,maxKern of first TrackKern, or NULL>

or the sole line ``ok=false`` on any throw. ``_py_dump`` reproduces the same
fingerprint on the pypdfbox side; the parity assertion is a single string
compare.

REAL BUG FIXED THIS WAVE (now asserted, both engines agree):

  * *Spurious ``TrackKern`` keyword in track-kern entries.* pypdfbox's
    ``parse_kern_data`` read a literal ``read_command("TrackKern")`` before
    each track-kern entry. Upstream ``AFMParser.parseKernData`` reads each
    entry as five bare numeric tokens (degree + four floats) directly after
    the ``StartTrackKern`` count — there is no per-entry keyword. The old
    behaviour both *rejected* valid keyword-less track-kern data and
    *accepted* a spurious leading keyword. Removed; the ``track_kern_ok``
    (keyword-less, now ok=true both sides) and ``track_kern_spurious_keyword``
    (now ok=false both sides) cases pin the fix.

DOCUMENTED UNALIGNABLE DIVERGENCE (pinned both-sides, pre-existing leniency):

  * *Missing trailing semicolon in a CharMetric command.* Upstream's
    ``verifySemicolon`` unconditionally requires a ``;`` token after every
    command and throws "CharMetrics is missing a semicolon after a command"
    at end-of-line; pypdfbox deliberately tolerates the absence of a trailing
    ``;`` (matching the bundled Core-14 AFMs — see ``verify_semicolon``). The
    ``ligature_missing_second`` case (``L i ;`` — only a successor, no
    ligature, before the ``;``) surfaces this: Java consumes ``;`` as the
    ligature value then throws on the missing terminator (ok=false), while
    pypdfbox builds ``Ligature("i", ";")`` and accepts (ok=true). Pinned both
    sides in ``_LENIENT_CASES``, NOT a pypdfbox bug.
"""

from __future__ import annotations

import math
import os
import tempfile
from contextlib import suppress

import pytest

from pypdfbox.fontbox.afm.afm_parser import AFMParser
from tests.oracle.harness import requires_oracle, run_probe_text


def _fmt(value: float) -> str:
    """4-decimal float formatting matching Java ``String.format("%.4f", v)``."""
    v = float(value)
    if math.isnan(v):
        return "NaN"
    if math.isinf(v):
        return "Infinity" if v > 0 else "-Infinity"
    if v == 0.0:
        v = 0.0
    return f"{v:.4f}"


def _nz(value: str | None) -> str:
    return "NULL" if value is None else value


def _pair(p: object) -> str:
    if p is None:
        return "NULL"
    return f"{_fmt(p[0])}/{_fmt(p[1])}"  # type: ignore[index]


def _bbox(bbox: object) -> str:
    if bbox is None:
        return "NULL"
    return ",".join(
        _fmt(v)
        for v in (
            bbox.get_lower_left_x(),  # type: ignore[attr-defined]
            bbox.get_lower_left_y(),  # type: ignore[attr-defined]
            bbox.get_upper_right_x(),  # type: ignore[attr-defined]
            bbox.get_upper_right_y(),  # type: ignore[attr-defined]
        )
    )


def _cm0(metrics: list) -> str:
    if not metrics:
        return "NULL"
    cm = sorted(metrics, key=lambda m: _nz(m.get_name()))[0]
    return ",".join(
        [
            _nz(cm.get_name()),
            str(cm.get_character_code()),
            _fmt(cm.get_wx()),
            _fmt(cm.get_wy()),
            _pair(cm.get_w()),
            _pair(cm.get_w0()),
            _pair(cm.get_w1()),
            _pair(cm.get_vv()),
            _bbox(cm.get_bounding_box()),
        ]
    )


def _kp0(pairs: list) -> str:
    if not pairs:
        return "NULL"
    kp = sorted(
        pairs,
        key=lambda k: (
            _nz(k.get_first_kern_character()),
            _nz(k.get_second_kern_character()),
        ),
    )[0]
    return ",".join(
        [
            _nz(kp.get_first_kern_character()),
            _nz(kp.get_second_kern_character()),
            _fmt(kp.get_x()),
            _fmt(kp.get_y()),
        ]
    )


def _tk0(tracks: list) -> str:
    if not tracks:
        return "NULL"
    tk = tracks[0]
    return ",".join(
        [
            str(tk.get_degree()),
            _fmt(tk.get_min_point_size()),
            _fmt(tk.get_min_kern()),
            _fmt(tk.get_max_point_size()),
            _fmt(tk.get_max_kern()),
        ]
    )


def _py_dump(data: bytes, reduced: bool) -> str:
    try:
        fm = AFMParser(data).parse(reduced_dataset=reduced)
    except Exception:
        return "ok=false\n"
    try:
        metrics = fm.get_char_metrics()
        nlig = sum(len(m.get_ligatures()) for m in metrics)
        lines = [
            "ok=true",
            f"name={_nz(fm.get_font_name())}",
            "vm="
            + ",".join(
                _fmt(v)
                for v in (
                    fm.get_cap_height(),
                    fm.get_x_height(),
                    fm.get_ascender(),
                    fm.get_descender(),
                    fm.get_italic_angle(),
                )
            ),
            f"fixedpitch={'true' if fm.get_is_fixed_pitch() else 'false'}",
            f"nchar={len(metrics)}",
            f"nkp={len(fm.get_kern_pairs())}",
            f"nkp0={len(fm.get_kern_pairs0())}",
            f"nkp1={len(fm.get_kern_pairs1())}",
            f"ntrack={len(fm.get_track_kern())}",
            f"ncomp={len(fm.get_composites())}",
            f"nlig={nlig}",
            f"cm0={_cm0(metrics)}",
            f"kp0={_kp0(fm.get_kern_pairs())}",
            f"tk0={_tk0(fm.get_track_kern())}",
        ]
        return "\n".join(lines) + "\n"
    except Exception:
        return "ok=false\n"


def _java_dump(data: bytes, reduced: bool) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".afm")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        return run_probe_text("AfmParseFuzzProbe", tmp, "1" if reduced else "0")
    finally:
        with suppress(OSError):
            os.unlink(tmp)


# A fully-populated valid AFM exercising every section the projection reads.
_VALID = (
    b"StartFontMetrics 4.1\n"
    b"FontName Test\n"
    b"CapHeight 718\n"
    b"XHeight 523\n"
    b"Ascender 718\n"
    b"Descender -207\n"
    b"ItalicAngle -12.5\n"
    b"IsFixedPitch true\n"
    b"FontBBox -10 -20 100 200\n"
    b"StartCharMetrics 2\n"
    b"C 70 ; WX 611 ; N f ; B 0 0 600 700 ; L i fi ; L l fl ;\n"
    b"C 65 ; WX 700 ; N A ; B 10 0 690 700 ;\n"
    b"EndCharMetrics\n"
    b"StartKernData\n"
    b"StartTrackKern 1\n"
    b"0 1 -0.5 10 -2.0\n"
    b"EndTrackKern\n"
    b"StartKernPairs 1\n"
    b"KPX A V -80\n"
    b"EndKernPairs\n"
    b"StartKernPairs0 1\n"
    b"KPX A W -60\n"
    b"EndKernPairs\n"
    b"EndKernData\n"
    b"StartComposites 1\n"
    b"CC Aacute 2 ; PCC A 0 0 ; PCC acute 160 220 ;\n"
    b"EndComposites\n"
    b"EndFontMetrics\n"
)

# (id, bytes) -- exercised under BOTH full and reduced parse modes. Both engines
# agree on the projection for every case here.
_CASES: list[tuple[str, bytes]] = [
    ("valid_full", _VALID),
    # ----- global vertical metrics -----
    (
        "vm_negative_descender",
        b"StartFontMetrics 4.1\nFontName T\nDescender -250\n"
        b"CapHeight 700\nEndFontMetrics\n",
    ),
    (
        "vm_float_capheight",
        b"StartFontMetrics 4.1\nCapHeight 717.5\nEndFontMetrics\n",
    ),
    (
        "vm_capheight_nonnum",
        b"StartFontMetrics 4.1\nCapHeight abc\nEndFontMetrics\n",
    ),
    (
        "vm_capheight_missing_val",
        b"StartFontMetrics 4.1\nCapHeight\nEndFontMetrics\n",
    ),
    (
        "vm_italic_inf",
        b"StartFontMetrics 4.1\nItalicAngle Infinity\nEndFontMetrics\n",
    ),
    (
        "fixedpitch_false",
        b"StartFontMetrics 4.1\nIsFixedPitch false\nEndFontMetrics\n",
    ),
    (
        "fixedpitch_garbage",
        b"StartFontMetrics 4.1\nIsFixedPitch yes\nEndFontMetrics\n",
    ),
    (
        "fixedpitch_caps_true",
        b"StartFontMetrics 4.1\nIsFixedPitch TRUE\nEndFontMetrics\n",
    ),
    # ----- ligatures (L successor ligature) -----
    (
        "ligature_ok",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"C 70 ; WX 611 ; N f ; L i fi ;\nEndCharMetrics\nEndFontMetrics\n",
    ),
    (
        "ligature_two",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"C 70 ; WX 611 ; N f ; L i fi ; L l fl ;\n"
        b"EndCharMetrics\nEndFontMetrics\n",
    ),
    # ----- extended width vectors -----
    (
        "w_two_floats",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"C 65 ; W 700 0 ; N A ;\nEndCharMetrics\nEndFontMetrics\n",
    ),
    (
        "w_short_arity",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"C 65 ; W 700 ; N A ;\nEndCharMetrics\nEndFontMetrics\n",
    ),
    (
        "w0_w1_vv",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"C 65 ; W0 700 0 ; W1 0 880 ; VV 0 880 ; N A ;\n"
        b"EndCharMetrics\nEndFontMetrics\n",
    ),
    (
        "wy_only",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"C 65 ; WX 700 ; WY 50 ; N A ;\nEndCharMetrics\nEndFontMetrics\n",
    ),
    (
        "vv_nonnum",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"C 65 ; VV a b ; N A ;\nEndCharMetrics\nEndFontMetrics\n",
    ),
    # ----- track kern framing (keyword-less entries, matching upstream) -----
    (
        "track_kern_ok",
        b"StartFontMetrics 4.1\nStartKernData\nStartTrackKern 1\n"
        b"0 1 -0.5 10 -2.0\nEndTrackKern\nEndKernData\nEndFontMetrics\n",
    ),
    (
        # A spurious per-entry ``TrackKern`` keyword is rejected by both engines
        # (the keyword is read as the degree -> non-numeric). Pins the bug fix.
        "track_kern_spurious_keyword",
        b"StartFontMetrics 4.1\nStartKernData\nStartTrackKern 1\n"
        b"TrackKern 0 1 -0.5 10 -2.0\nEndTrackKern\nEndKernData\nEndFontMetrics\n",
    ),
    (
        "track_kern_count_mismatch",
        b"StartFontMetrics 4.1\nStartKernData\nStartTrackKern 2\n"
        b"0 1 -0.5 10 -2.0\nEndTrackKern\nEndKernData\nEndFontMetrics\n",
    ),
    (
        "track_kern_bad_degree",
        b"StartFontMetrics 4.1\nStartKernData\nStartTrackKern 1\n"
        b"x 1 -0.5 10 -2.0\nEndTrackKern\nEndKernData\nEndFontMetrics\n",
    ),
    (
        "track_kern_no_endtrack",
        b"StartFontMetrics 4.1\nStartKernData\nStartTrackKern 1\n"
        b"0 1 -0.5 10 -2.0\nEndKernData\nEndFontMetrics\n",
    ),
    (
        "track_kern_two",
        b"StartFontMetrics 4.1\nStartKernData\nStartTrackKern 2\n"
        b"0 1 -0.5 10 -2.0\n1 6 0 24 0.5\n"
        b"EndTrackKern\nEndKernData\nEndFontMetrics\n",
    ),
    # ----- KPH hex kern pairs -----
    (
        "kph_ok",
        b"StartFontMetrics 4.1\nStartKernData\nStartKernPairs 1\n"
        b"KPH <0041> <0056> -80\nEndKernPairs\nEndKernData\nEndFontMetrics\n",
    ),
    (
        "kph_no_brackets",
        b"StartFontMetrics 4.1\nStartKernData\nStartKernPairs 1\n"
        b"KPH 0041 0056 -80\nEndKernPairs\nEndKernData\nEndFontMetrics\n",
    ),
    (
        "kph_odd_hex",
        b"StartFontMetrics 4.1\nStartKernData\nStartKernPairs 1\n"
        b"KPH <041> <0056> -80\nEndKernPairs\nEndKernData\nEndFontMetrics\n",
    ),
    # ----- KP (both axes) and KPY -----
    (
        "kp_both_axes",
        b"StartFontMetrics 4.1\nStartKernData\nStartKernPairs 1\n"
        b"KP A V -80 -10\nEndKernPairs\nEndKernData\nEndFontMetrics\n",
    ),
    (
        "kpy_only",
        b"StartFontMetrics 4.1\nStartKernData\nStartKernPairs 1\n"
        b"KPY A V -10\nEndKernPairs\nEndKernData\nEndFontMetrics\n",
    ),
    # ----- vertical kern-pair lists -----
    (
        "kernpairs0",
        b"StartFontMetrics 4.1\nStartKernData\nStartKernPairs0 1\n"
        b"KPX A V -80\nEndKernPairs\nEndKernData\nEndFontMetrics\n",
    ),
    (
        "kernpairs1",
        b"StartFontMetrics 4.1\nStartKernData\nStartKernPairs1 1\n"
        b"KPX A V -80\nEndKernPairs\nEndKernData\nEndFontMetrics\n",
    ),
    (
        "kern_unknown_subsection",
        b"StartFontMetrics 4.1\nStartKernData\nBogusKern 1\n"
        b"KPX A V -80\nEndKernPairs\nEndKernData\nEndFontMetrics\n",
    ),
    (
        "kern_pair_count_mismatch",
        b"StartFontMetrics 4.1\nStartKernData\nStartKernPairs 3\n"
        b"KPX A V -80\nEndKernPairs\nEndKernData\nEndFontMetrics\n",
    ),
    # ----- composites with parts -----
    (
        "composite_two_parts",
        b"StartFontMetrics 4.1\nStartComposites 1\n"
        b"CC Aacute 2 ; PCC A 0 0 ; PCC acute 160 220 ;\n"
        b"EndComposites\nEndFontMetrics\n",
    ),
    (
        "composite_pcc_float_disp",
        b"StartFontMetrics 4.1\nStartComposites 1\n"
        b"CC Aacute 1 ; PCC A 0.5 0 ;\nEndComposites\nEndFontMetrics\n",
    ),
    (
        "composite_no_endcomposites",
        b"StartFontMetrics 4.1\nStartComposites 1\n"
        b"CC Aacute 1 ; PCC A 0 0 ;\nEndFontMetrics\n",
    ),
    # ----- whole-document framing combined with the new sections -----
    (
        "vvector_two_floats",
        b"StartFontMetrics 4.1\nVVector 0 880\nIsFixedV true\nEndFontMetrics\n",
    ),
    (
        "vvector_short_arity",
        b"StartFontMetrics 4.1\nVVector 0\nEndFontMetrics\n",
    ),
    (
        "charwidth_two_floats",
        b"StartFontMetrics 4.1\nCharWidth 600 0\nEndFontMetrics\n",
    ),
    (
        "charwidth_short_arity",
        b"StartFontMetrics 4.1\nCharWidth 600\nEndFontMetrics\n",
    ),
]

# pypdfbox intentionally tolerates a missing trailing semicolon after a
# CharMetric command; upstream's verifySemicolon requires one. UNALIGNABLE —
# pinned both observed sides (Java ok=false, pypdfbox ok=true).
_LENIENT_CASES: list[tuple[str, bytes]] = [
    (
        "ligature_missing_second",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"C 70 ; WX 611 ; N f ; L i ;\nEndCharMetrics\nEndFontMetrics\n",
    ),
]

_IDS = [c[0] for c in _CASES]
_LENIENT_IDS = [c[0] for c in _LENIENT_CASES]


@requires_oracle
@pytest.mark.parametrize(("name", "data"), _CASES, ids=_IDS)
@pytest.mark.parametrize("reduced", [False, True], ids=["full", "reduced"])
def test_afm_parse_fuzz_parity(name: str, data: bytes, reduced: bool) -> None:
    java = _java_dump(data, reduced)
    py = _py_dump(data, reduced)
    assert py == java, (
        f"divergence on AFM mutant {name!r} reduced={reduced}:\n"
        f" java={java!r}\n  py={py!r}"
    )


@requires_oracle
@pytest.mark.parametrize(("name", "data"), _LENIENT_CASES, ids=_LENIENT_IDS)
def test_afm_trailing_semicolon_leniency_divergence_pinned(
    name: str, data: bytes
) -> None:
    # pypdfbox accepts a missing trailing semicolon that upstream rejects.
    # Pin both observed sides.
    java = _java_dump(data, False)
    py = _py_dump(data, False)
    assert java == "ok=false\n"
    assert py.startswith("ok=true\n")
    assert "nchar=1" in py
    assert "nlig=1" in py


def test_clean_valid_projection_non_trivial() -> None:
    dump = _py_dump(_VALID, False)
    assert dump.startswith("ok=true\n")
    assert "name=Test\n" in dump
    assert "vm=718.0000,523.0000,718.0000,-207.0000,-12.5000\n" in dump
    assert "fixedpitch=true\n" in dump
    assert "nchar=2\n" in dump
    assert "nkp=1\n" in dump
    assert "nkp0=1\n" in dump
    assert "ntrack=1\n" in dump
    assert "ncomp=1\n" in dump
    assert "nlig=2\n" in dump
    assert "tk0=0,1.0000,-0.5000,10.0000,-2.0000\n" in dump
