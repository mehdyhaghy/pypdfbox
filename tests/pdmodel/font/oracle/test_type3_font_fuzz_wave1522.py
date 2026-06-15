"""Live Apache PDFBox differential fuzz parity for ``PDType3Font`` /
``PDType3CharProc`` over MALFORMED Type 3 font dictionaries (wave 1522, agent
D).

Drives ``oracle/probes/Type3FontFuzzProbe.java`` (the oracle of record) against
pypdfbox, rebuilding the *identical* Type 3 font ``COSDictionary`` per case and
asserting each ``CASE`` line matches.

The four existing Type-3 oracle suites (``test_type3_font_oracle``,
``test_type3_char_proc_accessor_oracle``, and the d0/d1/edge probes) all build a
*well-formed* Type 3 font and verify value-parity of the accessors. This suite
fuzzes the dictionary itself:

* ``/FontMatrix`` missing / wrong length / non-numeric / null / name / 6-int;
* ``/FontBBox`` missing / wrong length (2,3,5) / non-numeric / name / reversed;
* ``/CharProcs`` missing / non-dict / a glyph entry that is a dict / scalar /
  null instead of a stream / a name with no matching proc;
* ``/Encoding`` missing / a predefined name / a ``.notdef`` glyph that *has* a
  char proc;
* ``/Widths`` in-window / short array / code below window / no ``/Widths``;
* per-glyph char-proc ``getWidth`` / ``getGlyphBBox`` over d0 / d1 / empty /
  garbage procs.

Probe line grammar (one per case)::

    CASE <name> create=<ok|ERR:X|NotType3> fm=<a,b,c,d,e,f|ERR>
         bbox=<llx,lly,urx,ury|null|ERR> cp=<sorted,glyph,names|-|ERR>
         w<code>=<float|ERR> gc<code>=<cw=<float>,gb=<...|null>|null|ERR>

Two production divergences this wave UNCOVERED and FIXED (both verified live
below):

1. ``get_font_bbox`` required a 4+ entry numeric array and returned ``None`` (or
   raised) otherwise; upstream ``getFontBBox`` builds a ``PDRectangle`` from
   *any* COSArray — short arrays are zero-padded to four, long arrays keep the
   first four, non-numeric entries coerce to 0, corners normalise via min/max.
   Fixed in ``pd_type3_font.py`` (cases ``bbox_len2`` / ``bbox_len3`` /
   ``bbox_len5`` / ``bbox_nonnumeric`` / ``bbox_reversed``).
2. ``getCharProc(int)`` special-cased ``.notdef`` and returned ``None`` even
   when a ``.notdef`` char proc existed; upstream resolves the code to a glyph
   name and looks that exact name up in ``/CharProcs`` with no ``.notdef``
   filter. Fixed in ``pd_type3_font.py`` (case ``enc_notdef_has_proc``).

The lenient char-proc width path (``cp.get_width()`` returning ``0.0`` on an
empty / garbage proc where upstream raises ``IOException``) is an intentional
pypdfbox robustness divergence pinned both-sides below (CHANGES.md wave 1522).

Hand-written (not ported from upstream JUnit). ``@requires_oracle`` so it skips
cleanly without Java + the jar.
"""

from __future__ import annotations

import struct

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
)
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "Type3FontFuzzProbe"

_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_FONT = COSName.get_pdf_name("Font")
_ENCODING = COSName.get_pdf_name("Encoding")
_DIFFERENCES = COSName.get_pdf_name("Differences")
_CHAR_PROCS = COSName.get_pdf_name("CharProcs")
_FONT_MATRIX = COSName.get_pdf_name("FontMatrix")
_FONT_BBOX = COSName.get_pdf_name("FontBBox")
_FIRST_CHAR = COSName.get_pdf_name("FirstChar")
_LAST_CHAR = COSName.get_pdf_name("LastChar")
_WIDTHS = COSName.get_pdf_name("Widths")


# ---------- COS builders (mirror Type3FontFuzzProbe.java) ----------


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _i(v: int) -> COSInteger:
    return COSInteger.get(v)


def _fl(v: float) -> COSFloat:
    return COSFloat(float(v))


def _arr(*items: object) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _stream(body: str) -> COSStream:
    s = COSStream()
    s.set_data(body.encode("ascii"))
    return s


def _d1_proc(wx: float) -> COSStream:
    return _stream(f"{_f(wx)} 0 0 0 500 700 d1\n0 0 500 700 re f\n")


def _d0_proc(wx: float) -> COSStream:
    return _stream(f"{_f(wx)} 0 d0\n0 0 500 700 re f\n")


def _empty_proc() -> COSStream:
    return _stream("")


def _garbage_proc() -> COSStream:
    return _stream("0 0 500 700 re f\n")


def _type3() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _FONT)
    d.set_item(_SUBTYPE, _n("Type3"))
    return d


def _encoding(codes: list[int], names: list[str]) -> COSDictionary:
    enc = COSDictionary()
    enc.set_item(_TYPE, _n("Encoding"))
    diffs = COSArray()
    for code, name in zip(codes, names, strict=True):
        diffs.add(_i(code))
        diffs.add(_n(name))
    enc.set_item(_DIFFERENCES, diffs)
    return enc


# ---------- float formatting (mirror probe's f(float)) ----------


def _f(v: float) -> str:
    """Render a float the way the Java probe's ``f()`` does.

    The probe emits ``Long.toString((long) v)`` for integral values and
    ``Float.toString(v)`` otherwise. Mirroring it exactly matters because
    custom matrix values reach the COS layer through ``COSFloat`` which
    stores a 32-bit float, and Java's ``Float.toString`` prints the
    *shortest* decimal that round-trips to that ``float`` (e.g. ``0.002``),
    whereas Python's ``repr`` of the 64-bit-widened value would print the
    long form ``0.0020000000949949026``. So integral -> plain int string,
    non-integral -> shortest decimal that round-trips to the same float32.
    """
    fv = float(v)
    if fv == int(fv):
        return str(int(fv))
    target = struct.unpack("f", struct.pack("f", fv))[0]
    for prec in range(1, 18):
        candidate = f"%.{prec}g" % target
        if struct.unpack("f", struct.pack("f", float(candidate)))[0] == target:
            return candidate
    return repr(target)


# ---------- case corpus (mirror Type3FontFuzzProbe.main, with probe code) ----------


def _build_cases() -> dict[str, tuple[COSDictionary, int]]:
    """Return {case_name: (font_dict, code)} mirroring the probe."""
    cases: dict[str, tuple[COSDictionary, int]] = {}
    codes = [65]
    names = ["alpha"]

    # ===== /FontMatrix =====
    fm_ok = _type3()
    fm_ok.set_item(
        _FONT_MATRIX, _arr(_fl(0.002), _fl(0), _fl(0), _fl(0.002), _fl(0), _fl(0))
    )
    cases["fm_ok"] = (fm_ok, 65)

    cases["fm_missing"] = (_type3(), 65)

    fm4 = _type3()
    fm4.set_item(_FONT_MATRIX, _arr(_fl(1), _fl(0), _fl(0), _fl(1)))
    cases["fm_len4"] = (fm4, 65)

    fm8 = _type3()
    fm8.set_item(
        _FONT_MATRIX,
        _arr(_fl(1), _fl(0), _fl(0), _fl(1), _fl(0), _fl(0), _fl(9), _fl(9)),
    )
    cases["fm_len8"] = (fm8, 65)

    fm_name = _type3()
    fm_name.set_item(
        _FONT_MATRIX, _arr(_fl(0.002), _n("X"), _fl(0), _fl(0.002), _fl(0), _fl(0))
    )
    cases["fm_nonnumeric"] = (fm_name, 65)

    fm_null = _type3()
    fm_null.set_item(
        _FONT_MATRIX,
        _arr(_fl(0.002), COSNull.NULL, _fl(0), _fl(0.002), _fl(0), _fl(0)),
    )
    cases["fm_null_entry"] = (fm_null, 65)

    fm_is_name = _type3()
    fm_is_name.set_item(_FONT_MATRIX, _n("Identity"))
    cases["fm_is_name"] = (fm_is_name, 65)

    fm_ints = _type3()
    fm_ints.set_item(_FONT_MATRIX, _arr(_i(1), _i(0), _i(0), _i(1), _i(0), _i(0)))
    cases["fm_six_ints"] = (fm_ints, 65)

    # ===== /FontBBox =====
    bb_ok = _type3()
    bb_ok.set_item(_FONT_BBOX, _arr(_i(0), _i(0), _i(750), _i(1000)))
    cases["bbox_ok"] = (bb_ok, 65)

    cases["bbox_missing"] = (_type3(), 65)

    bb2 = _type3()
    bb2.set_item(_FONT_BBOX, _arr(_i(0), _i(0)))
    cases["bbox_len2"] = (bb2, 65)

    bb3 = _type3()
    bb3.set_item(_FONT_BBOX, _arr(_i(0), _i(0), _i(750)))
    cases["bbox_len3"] = (bb3, 65)

    bb5 = _type3()
    bb5.set_item(_FONT_BBOX, _arr(_i(0), _i(0), _i(750), _i(1000), _i(99)))
    cases["bbox_len5"] = (bb5, 65)

    bb_name = _type3()
    bb_name.set_item(_FONT_BBOX, _arr(_i(0), _n("X"), _i(750), _i(1000)))
    cases["bbox_nonnumeric"] = (bb_name, 65)

    bb_is_name = _type3()
    bb_is_name.set_item(_FONT_BBOX, _n("Big"))
    cases["bbox_is_name"] = (bb_is_name, 65)

    bb_rev = _type3()
    bb_rev.set_item(_FONT_BBOX, _arr(_i(750), _i(1000), _i(0), _i(0)))
    cases["bbox_reversed"] = (bb_rev, 65)

    # ===== /CharProcs =====
    cp_ok = _type3()
    cp_ok.set_item(_ENCODING, _encoding(codes, names))
    cp_dict = COSDictionary()
    cp_dict.set_item(_n("alpha"), _d1_proc(600))
    cp_ok.set_item(_CHAR_PROCS, cp_dict)
    cases["cp_ok_d1"] = (cp_ok, 65)

    cp_d0 = _type3()
    cp_d0.set_item(_ENCODING, _encoding(codes, names))
    cp_d0_dict = COSDictionary()
    cp_d0_dict.set_item(_n("alpha"), _d0_proc(444))
    cp_d0.set_item(_CHAR_PROCS, cp_d0_dict)
    cases["cp_d0"] = (cp_d0, 65)

    cp_empty = _type3()
    cp_empty.set_item(_ENCODING, _encoding(codes, names))
    cp_empty_dict = COSDictionary()
    cp_empty_dict.set_item(_n("alpha"), _empty_proc())
    cp_empty.set_item(_CHAR_PROCS, cp_empty_dict)
    cases["cp_empty_proc"] = (cp_empty, 65)

    cp_garbage = _type3()
    cp_garbage.set_item(_ENCODING, _encoding(codes, names))
    cp_garbage_dict = COSDictionary()
    cp_garbage_dict.set_item(_n("alpha"), _garbage_proc())
    cp_garbage.set_item(_CHAR_PROCS, cp_garbage_dict)
    cases["cp_garbage_proc"] = (cp_garbage, 65)

    cp_missing = _type3()
    cp_missing.set_item(_ENCODING, _encoding(codes, names))
    cases["cp_missing"] = (cp_missing, 65)

    cp_not_dict = _type3()
    cp_not_dict.set_item(_ENCODING, _encoding(codes, names))
    cp_not_dict.set_item(_CHAR_PROCS, _n("Nope"))
    cases["cp_not_dict"] = (cp_not_dict, 65)

    cp_entry_dict = _type3()
    cp_entry_dict.set_item(_ENCODING, _encoding(codes, names))
    cp_entry_dict_dict = COSDictionary()
    cp_entry_dict_dict.set_item(_n("alpha"), COSDictionary())
    cp_entry_dict.set_item(_CHAR_PROCS, cp_entry_dict_dict)
    cases["cp_entry_dict"] = (cp_entry_dict, 65)

    cp_entry_int = _type3()
    cp_entry_int.set_item(_ENCODING, _encoding(codes, names))
    cp_entry_int_dict = COSDictionary()
    cp_entry_int_dict.set_item(_n("alpha"), _i(7))
    cp_entry_int.set_item(_CHAR_PROCS, cp_entry_int_dict)
    cases["cp_entry_int"] = (cp_entry_int, 65)

    cp_entry_null = _type3()
    cp_entry_null.set_item(_ENCODING, _encoding(codes, names))
    cp_entry_null_dict = COSDictionary()
    cp_entry_null_dict.set_item(_n("alpha"), COSNull.NULL)
    cp_entry_null.set_item(_CHAR_PROCS, cp_entry_null_dict)
    cases["cp_entry_null"] = (cp_entry_null, 65)

    cp_no_name = _type3()
    cp_no_name.set_item(_ENCODING, _encoding(codes, names))
    cp_no_name_dict = COSDictionary()
    cp_no_name_dict.set_item(_n("beta"), _d1_proc(600))
    cp_no_name.set_item(_CHAR_PROCS, cp_no_name_dict)
    cases["cp_name_absent"] = (cp_no_name, 65)

    # ===== /Encoding =====
    enc_missing = _type3()
    enc_missing_cp = COSDictionary()
    enc_missing_cp.set_item(_n("alpha"), _d1_proc(600))
    enc_missing.set_item(_CHAR_PROCS, enc_missing_cp)
    cases["enc_missing"] = (enc_missing, 65)

    enc_name = _type3()
    enc_name.set_item(_ENCODING, _n("WinAnsiEncoding"))
    enc_name_cp = COSDictionary()
    enc_name_cp.set_item(_n("A"), _d1_proc(321))
    enc_name.set_item(_CHAR_PROCS, enc_name_cp)
    cases["enc_name_winansi"] = (enc_name, 65)

    enc_notdef = _type3()
    enc_notdef.set_item(_ENCODING, _encoding([65], [".notdef"]))
    enc_notdef_cp = COSDictionary()
    enc_notdef_cp.set_item(_n(".notdef"), _d1_proc(123))
    enc_notdef.set_item(_CHAR_PROCS, enc_notdef_cp)
    cases["enc_notdef_has_proc"] = (enc_notdef, 65)

    # ===== /Widths =====
    w_ok = _type3()
    w_ok.set_item(_ENCODING, _encoding(codes, names))
    w_ok_cp = COSDictionary()
    w_ok_cp.set_item(_n("alpha"), _d1_proc(600))
    w_ok.set_item(_CHAR_PROCS, w_ok_cp)
    w_ok.set_item(_FIRST_CHAR, _i(65))
    w_ok.set_item(_LAST_CHAR, _i(65))
    w_ok.set_item(_WIDTHS, _arr(_fl(610)))
    cases["w_in_window"] = (w_ok, 65)

    w_short = _type3()
    w_short.set_item(_ENCODING, _encoding(codes, names))
    w_short_cp = COSDictionary()
    w_short_cp.set_item(_n("alpha"), _d1_proc(600))
    w_short.set_item(_CHAR_PROCS, w_short_cp)
    w_short.set_item(_FIRST_CHAR, _i(65))
    w_short.set_item(_LAST_CHAR, _i(70))
    w_short.set_item(_WIDTHS, _arr(_fl(610)))
    cases["w_short_array"] = (w_short, 67)

    w_below = _type3()
    w_below.set_item(_ENCODING, _encoding(codes, names))
    w_below_cp = COSDictionary()
    w_below_cp.set_item(_n("alpha"), _d1_proc(600))
    w_below.set_item(_CHAR_PROCS, w_below_cp)
    w_below.set_item(_FIRST_CHAR, _i(70))
    w_below.set_item(_LAST_CHAR, _i(80))
    w_below.set_item(_WIDTHS, _arr(_fl(610)))
    cases["w_code_below"] = (w_below, 65)

    w_none = _type3()
    w_none.set_item(_ENCODING, _encoding(codes, names))
    w_none_cp = COSDictionary()
    w_none_cp.set_item(_n("alpha"), _d1_proc(600))
    w_none.set_item(_CHAR_PROCS, w_none_cp)
    cases["w_no_widths"] = (w_none, 65)

    w_garbage = _type3()
    w_garbage.set_item(_ENCODING, _encoding(codes, names))
    w_garbage_cp = COSDictionary()
    w_garbage_cp.set_item(_n("alpha"), _garbage_proc())
    w_garbage.set_item(_CHAR_PROCS, w_garbage_cp)
    cases["w_no_widths_garbage"] = (w_garbage, 65)

    return cases


# ---------- pypdfbox-side verdict (mirror probe's emit/projection) ----------


def _matrix_str(font: PDType3Font) -> str:
    try:
        m = font.get_font_matrix()
        return ",".join(_f(x) for x in m)
    except Exception:  # noqa: BLE001 — match probe's Throwable catch
        return "ERR"


def _bbox_str(font: PDType3Font) -> str:
    try:
        r = font.get_font_bbox()
        if r is None:
            return "null"
        return (
            f"{_f(r.get_lower_left_x())},{_f(r.get_lower_left_y())},"
            f"{_f(r.get_upper_right_x())},{_f(r.get_upper_right_y())}"
        )
    except Exception:  # noqa: BLE001
        return "ERR"


def _char_procs_str(font: PDType3Font) -> str:
    try:
        cp = font.get_char_procs()
        if cp is None:
            return "-"
        keys = sorted(k.get_name() for k in cp.key_set())
        return ",".join(keys)
    except Exception:  # noqa: BLE001
        return "ERR"


def _width_str(font: PDType3Font, code: int) -> str:
    try:
        return _f(font.get_width(code))
    except Exception:  # noqa: BLE001
        return "ERR"


def _char_proc_str(font: PDType3Font, code: int) -> str:
    try:
        cp = font.get_char_proc(code)
        if cp is None:
            return "null"
        try:
            cw = _f(cp.get_width())
        except Exception:  # noqa: BLE001
            cw = "ERR"
        try:
            r = cp.get_glyph_bbox()
            if r is None:
                gb = "null"
            else:
                gb = (
                    f"{_f(r.get_lower_left_x())},{_f(r.get_lower_left_y())},"
                    f"{_f(r.get_upper_right_x())},{_f(r.get_upper_right_y())}"
                )
        except Exception:  # noqa: BLE001
            gb = "ERR"
        return f"cw={cw},gb={gb}"
    except Exception:  # noqa: BLE001
        return "ERR"


def _py_verdict(font_dict: COSDictionary, code: int) -> str:
    font = PDFontFactory.create_font(font_dict)
    if not isinstance(font, PDType3Font):
        return "create=NotType3"
    return (
        f"create=ok fm={_matrix_str(font)} bbox={_bbox_str(font)} "
        f"cp={_char_procs_str(font)} "
        f"w{code}={_width_str(font, code)} "
        f"gc{code}={_char_proc_str(font, code)}"
    )


def _parse_probe(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("CASE "):
            continue
        rest = line[len("CASE ") :]
        case_name, _, verdict = rest.partition(" ")
        out[case_name] = verdict.strip()
    return out


# ----- Intentional pypdfbox robustness divergences (CHANGES.md, wave 1522) -----
#
# Upstream PDType3CharProc.getWidth() / parseWidth() throw IOException on a char
# proc whose first operator is not d0/d1 (a "garbage" proc) or whose first
# operand is missing (an empty proc that nonetheless reaches getWidth). pypdfbox
# returns 0.0 in those malformed cases so the text-extraction / rendering loop
# keeps walking the font's other glyphs instead of aborting on one broken proc.
# This surfaces in the per-proc projection (gc<code>): upstream emits cw=ERR,
# pypdfbox emits cw=0. Pinned both-sides so the comparison stays
# apples-to-apples; see CHANGES.md wave 1522.
#
# Note: getWidth(code) at the FONT level (w<code>) still matches upstream for
# the empty proc (both 0: the getWidthFromFont length-0 short-circuit) but
# diverges for the GARBAGE proc (upstream ERR via getWidthFromFont ->
# charProc.getWidth IOException; pypdfbox 0). Both are pinned here.
_DIVERGENCES: dict[str, str] = {
    "cp_empty_proc": (
        "create=ok fm=0.001,0,0,0.001,0,0 bbox=null cp=alpha "
        "w65=0 gc65=cw=0,gb=null"
    ),
    "cp_garbage_proc": (
        "create=ok fm=0.001,0,0,0.001,0,0 bbox=null cp=alpha "
        "w65=0 gc65=cw=0,gb=null"
    ),
    "w_no_widths_garbage": (
        "create=ok fm=0.001,0,0,0.001,0,0 bbox=null cp=alpha "
        "w65=0 gc65=cw=0,gb=null"
    ),
}


@requires_oracle
def test_type3_font_fuzz_matches_pdfbox() -> None:
    probe = _parse_probe(run_probe_text(_PROBE))
    assert probe, "probe emitted no CASE lines"

    cases = _build_cases()
    assert set(cases) == set(probe), (
        f"case mismatch: only-in-py={set(cases) - set(probe)}, "
        f"only-in-java={set(probe) - set(cases)}"
    )

    mismatches: list[str] = []
    for name, (font_dict, code) in cases.items():
        java = probe[name]
        py = _py_verdict(font_dict, code)

        if name in _DIVERGENCES:
            expected_py = _DIVERGENCES[name]
            if java == expected_py:
                mismatches.append(
                    f"{name}: divergence collapsed — java now matches "
                    f"pypdfbox ({java!r}); drop it from _DIVERGENCES"
                )
            if py != expected_py:
                mismatches.append(f"{name}: py={py!r} != pinned {expected_py!r}")
            continue

        if java != py:
            mismatches.append(f"{name}: java={java!r} py={py!r}")

    assert not mismatches, "type3 font fuzz divergences:\n" + "\n".join(
        mismatches
    )


@requires_oracle
def test_probe_covers_the_type3_leniency_surface() -> None:
    """Sanity: the corpus spans the documented Type 3 fuzz axes."""
    probe = _parse_probe(run_probe_text(_PROBE))
    assert any(k.startswith("fm_") for k in probe)
    assert any(k.startswith("bbox_") for k in probe)
    assert any(k.startswith("cp_") for k in probe)
    assert any(k.startswith("enc_") for k in probe)
    assert any(k.startswith("w_") for k in probe)
    # The two fixed-this-wave behaviours must be observable in the oracle.
    assert "bbox=0,0,0,0" in probe["bbox_len2"]
    assert "gc65=cw=123" in probe["enc_notdef_has_proc"]


def test_font_bbox_short_array_padded_oracle_free() -> None:
    """Frozen contract (production fix this wave): get_font_bbox builds a
    rectangle from any COSArray — short arrays zero-pad to four, long arrays
    keep the first four, non-numeric entries coerce to 0. Drives the same
    dicts the probe's bbox_* cases use, without needing Java."""
    cases = _build_cases()
    expected = {
        "bbox_len2": (0.0, 0.0, 0.0, 0.0),
        "bbox_len3": (0.0, 0.0, 750.0, 0.0),
        "bbox_len5": (0.0, 0.0, 750.0, 1000.0),
        "bbox_nonnumeric": (0.0, 0.0, 750.0, 1000.0),
        "bbox_reversed": (0.0, 0.0, 750.0, 1000.0),
    }
    for case, want in expected.items():
        font_dict, _ = cases[case]
        font = PDFontFactory.create_font(font_dict)
        assert isinstance(font, PDType3Font)
        r = font.get_font_bbox()
        assert r is not None, case
        got = (
            r.get_lower_left_x(),
            r.get_lower_left_y(),
            r.get_upper_right_x(),
            r.get_upper_right_y(),
        )
        assert got == want, f"{case}: {got} != {want}"


def test_get_char_proc_notdef_with_proc_oracle_free() -> None:
    """Frozen contract (production fix this wave): get_char_proc(code) does NOT
    special-case .notdef — when /Encoding maps a code to .notdef and a
    .notdef char proc exists, the proc is returned (matching upstream
    getCharProc(int))."""
    cases = _build_cases()
    font_dict, code = cases["enc_notdef_has_proc"]
    font = PDFontFactory.create_font(font_dict)
    assert isinstance(font, PDType3Font)
    proc = font.get_char_proc(code)
    assert proc is not None
    assert proc.get_width() == 123.0
    assert font.get_width(code) == 123.0
