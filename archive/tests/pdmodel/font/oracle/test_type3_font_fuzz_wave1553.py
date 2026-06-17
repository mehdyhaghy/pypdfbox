"""Live Apache PDFBox differential fuzz parity for ``PDType3Font`` /
``PDType3CharProc`` — second fuzz wave covering the metric / descriptor surface
the wave-1522 probe never touched (wave 1553, agent A).

Drives ``oracle/probes/Type3FontFuzzProbe2.java`` (the oracle of record)
against pypdfbox, rebuilding the *identical* Type 3 font ``COSDictionary`` per
case and asserting each ``CASE`` line matches.

The wave-1522 fuzz probe (``Type3FontFuzzProbe`` / ``test_type3_font_fuzz_
wave1522``) projects ``get_font_matrix`` / ``get_font_bbox`` /
``get_char_procs`` / ``get_width`` / ``get_char_proc(int).get_width/
get_glyph_bbox``. This wave fuzzes the surfaces it left untested:

* the ``/FontDescriptor`` ``/MissingWidth`` width branch (code out of the
  ``/Widths`` window, no ``/Widths``, descriptor with no ``/MissingWidth``);
* non-numeric / null ``/Widths`` entries, ``/Widths`` not an array, an int
  ``/Widths`` entry;
* the ``get_width_from_font`` d0 path and the empty-proc short-circuit;
* ``get_displacement`` over default / scaled / translated / singular / shear
  matrices and the 6-int identity matrix;
* ``get_height`` via descriptor ``/FontBBox`` / ``/CapHeight`` / none;
* ``has_glyph(name)`` over present / ``.notdef`` / name-only / dict-entry
  glyphs;
* d0/d1 with the wrong operand count (short / long) and a non-numeric ``wx``;
* codes outside the byte range (256, -1).

Probe line grammar (one per case)::

    CASE <name> create=<ok|ERR:X|NotType3>
         w<code>=<float|ERR> disp<code>=<tx,ty|ERR> h<code>=<float|ERR>
         hgN=<true|false|ERR> gw=<float|null|ERR> ggb=<...|null|ERR>

Float fields render via ``_f`` (shortest decimal round-tripping to float32) so
600 and 600.0 are byte-identical across both languages.

Two intentional pypdfbox robustness / representation divergences are pinned
both-sides (CHANGES.md wave 1553):

1. ``PDType3CharProc.get_width`` returns ``0.0`` on a char proc whose first
   metric operand is non-numeric (``d1_bad_wx``) or whose stream is empty
   (``widthfromfont_empty``) where upstream raises ``IOException``. This
   propagates up through ``get_width`` / ``get_displacement`` for the no-
   ``/Widths`` path: upstream emits ``ERR``, pypdfbox emits ``0``.
2. ``get_displacement`` does the ``/FontMatrix`` affine transform in Python
   float64 against the spec-default matrix's float64 literals, whereas
   upstream ``Matrix.transform`` keeps float32 throughout. For width 444 and
   the default matrix this yields ``0.444`` (pypdfbox) vs ``0.44400004``
   (upstream float32 product ``444f * 0.001f``). All other widths/matrices in
   this corpus round to the identical float32 string.

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

_PROBE = "Type3FontFuzzProbe2"

_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_FONT = COSName.get_pdf_name("Font")
_ENCODING = COSName.get_pdf_name("Encoding")
_DIFFERENCES = COSName.get_pdf_name("Differences")
_CHAR_PROCS = COSName.get_pdf_name("CharProcs")
_FONT_MATRIX = COSName.get_pdf_name("FontMatrix")
_FIRST_CHAR = COSName.get_pdf_name("FirstChar")
_LAST_CHAR = COSName.get_pdf_name("LastChar")
_WIDTHS = COSName.get_pdf_name("Widths")
_FONT_DESCRIPTOR = COSName.get_pdf_name("FontDescriptor")


# ---------- COS builders (mirror Type3FontFuzzProbe2.java) ----------


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


def _d1_short() -> COSStream:
    return _stream("600 0 0 0 d1\n")


def _d1_long() -> COSStream:
    return _stream("600 0 0 0 500 700 9 d1\n")


def _d1_bad_wx() -> COSStream:
    return _stream("/X 0 0 0 500 700 d1\n")


def _empty_proc() -> COSStream:
    return _stream("")


def _f(v: float) -> str:
    """Render a float the way the Java probe's ``f()`` does.

    Integral -> plain int string; non-integral -> the shortest decimal that
    round-trips to the same 32-bit float (Java's ``Float.toString``). Custom
    matrix / width values reach the COS layer through ``COSFloat`` (float32),
    so this keeps both sides byte-identical (e.g. ``0.002``).
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


# ---------- font-dict builders ----------


def _type3() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _FONT)
    d.set_item(_SUBTYPE, _n("Type3"))
    return d


def _encoding(codes: list[int], names: list[str]) -> COSDictionary:
    enc = COSDictionary()
    enc.set_item(_TYPE, _n("Encoding"))
    diffs = COSArray()
    for k in range(len(codes)):
        diffs.add(_i(codes[k]))
        diffs.add(_n(names[k]))
    enc.set_item(_DIFFERENCES, diffs)
    return enc


def _descriptor(missing_width: float) -> COSDictionary:
    fd = COSDictionary()
    fd.set_item(_TYPE, _n("FontDescriptor"))
    fd.set_item(_n("FontName"), _n("T3Probe"))
    fd.set_item(_n("MissingWidth"), _fl(missing_width))
    return fd


def _with_alpha(proc: COSStream) -> COSDictionary:
    d = _type3()
    d.set_item(_ENCODING, _encoding([65], ["alpha"]))
    cp = COSDictionary()
    cp.set_item(_n("alpha"), proc)
    d.set_item(_CHAR_PROCS, cp)
    return d


def _build_cases() -> dict[str, tuple[COSDictionary, int]]:
    """Return {case_name: (font_dict, code)} mirroring the probe."""
    cases: dict[str, tuple[COSDictionary, int]] = {}

    # ===== /MissingWidth descriptor branch =====
    mw_out = _with_alpha(_d1_proc(600))
    mw_out.set_item(_FIRST_CHAR, _i(70))
    mw_out.set_item(_LAST_CHAR, _i(80))
    mw_out.set_item(_WIDTHS, _arr(_fl(610)))
    mw_out.set_item(_FONT_DESCRIPTOR, _descriptor(250))
    cases["mw_out_of_range"] = (mw_out, 65)

    mw_no_widths = _with_alpha(_d1_proc(600))
    mw_no_widths.set_item(_FONT_DESCRIPTOR, _descriptor(333))
    cases["mw_no_widths_desc"] = (mw_no_widths, 65)

    mw_default = _with_alpha(_d1_proc(600))
    fd_no_mw = COSDictionary()
    fd_no_mw.set_item(_TYPE, _n("FontDescriptor"))
    fd_no_mw.set_item(_n("FontName"), _n("T3Probe"))
    mw_default.set_item(_FONT_DESCRIPTOR, fd_no_mw)
    cases["mw_default_zero"] = (mw_default, 65)

    # ===== /Widths edge entries =====
    w_null = _with_alpha(_d1_proc(600))
    w_null.set_item(_FIRST_CHAR, _i(65))
    w_null.set_item(_LAST_CHAR, _i(65))
    w_null.set_item(_WIDTHS, _arr(COSNull.NULL))
    cases["w_null_entry"] = (w_null, 65)

    w_name = _with_alpha(_d1_proc(600))
    w_name.set_item(_FIRST_CHAR, _i(65))
    w_name.set_item(_LAST_CHAR, _i(65))
    w_name.set_item(_WIDTHS, _arr(_n("X")))
    cases["w_name_entry"] = (w_name, 65)

    w_not_array = _with_alpha(_d1_proc(600))
    w_not_array.set_item(_FIRST_CHAR, _i(65))
    w_not_array.set_item(_LAST_CHAR, _i(65))
    w_not_array.set_item(_WIDTHS, _n("Nope"))
    cases["w_not_array"] = (w_not_array, 65)

    w_int = _with_alpha(_d1_proc(600))
    w_int.set_item(_FIRST_CHAR, _i(65))
    w_int.set_item(_LAST_CHAR, _i(65))
    w_int.set_item(_WIDTHS, _arr(_i(555)))
    cases["w_int_entry"] = (w_int, 65)

    # ===== get_width_from_font paths (no /Widths) =====
    cases["widthfromfont_d0"] = (_with_alpha(_d0_proc(444)), 65)
    cases["widthfromfont_empty"] = (_with_alpha(_empty_proc()), 65)

    # ===== get_displacement over matrices =====
    cases["disp_default_matrix"] = (_with_alpha(_d1_proc(600)), 65)

    disp_custom = _with_alpha(_d1_proc(600))
    disp_custom.set_item(
        _FONT_MATRIX, _arr(_fl(0.002), _fl(0), _fl(0), _fl(0.002), _fl(0), _fl(0))
    )
    cases["disp_scaled_matrix"] = (disp_custom, 65)

    disp_trans = _with_alpha(_d1_proc(600))
    disp_trans.set_item(
        _FONT_MATRIX, _arr(_fl(0.001), _fl(0), _fl(0), _fl(0.001), _fl(5), _fl(7))
    )
    cases["disp_translate_matrix"] = (disp_trans, 65)

    disp_zero = _with_alpha(_d1_proc(600))
    disp_zero.set_item(
        _FONT_MATRIX, _arr(_fl(0), _fl(0), _fl(0), _fl(0), _fl(0), _fl(0))
    )
    cases["disp_singular_matrix"] = (disp_zero, 65)

    disp_shear = _with_alpha(_d1_proc(600))
    disp_shear.set_item(
        _FONT_MATRIX,
        _arr(_fl(0.001), _fl(0.0005), _fl(0), _fl(0.001), _fl(0), _fl(0)),
    )
    cases["disp_shear_matrix"] = (disp_shear, 65)

    # ===== get_height via descriptor =====
    h_bbox = _with_alpha(_d1_proc(600))
    fd_bbox = COSDictionary()
    fd_bbox.set_item(_TYPE, _n("FontDescriptor"))
    fd_bbox.set_item(_n("FontName"), _n("T3Probe"))
    fd_bbox.set_item(_n("FontBBox"), _arr(_i(0), _i(0), _i(750), _i(1000)))
    h_bbox.set_item(_FONT_DESCRIPTOR, fd_bbox)
    cases["h_descriptor_bbox"] = (h_bbox, 65)

    h_cap = _with_alpha(_d1_proc(600))
    fd_cap = COSDictionary()
    fd_cap.set_item(_TYPE, _n("FontDescriptor"))
    fd_cap.set_item(_n("FontName"), _n("T3Probe"))
    fd_cap.set_item(_n("CapHeight"), _fl(683))
    h_cap.set_item(_FONT_DESCRIPTOR, fd_cap)
    cases["h_descriptor_capheight"] = (h_cap, 65)

    cases["h_no_descriptor"] = (_with_alpha(_d1_proc(600)), 65)

    # ===== has_glyph(name) / glyph resolution =====
    cases["glyph_present"] = (_with_alpha(_d1_proc(600)), 65)

    g_notdef = _type3()
    g_notdef.set_item(_ENCODING, _encoding([65], [".notdef"]))
    g_notdef_cp = COSDictionary()
    g_notdef_cp.set_item(_n(".notdef"), _d1_proc(600))
    g_notdef_cp.set_item(_n("alpha"), _d1_proc(700))
    g_notdef.set_item(_CHAR_PROCS, g_notdef_cp)
    cases["glyph_notdef_code"] = (g_notdef, 65)

    g_name_only = _type3()
    g_name_only.set_item(_ENCODING, _encoding([66], ["beta"]))
    g_name_only_cp = COSDictionary()
    g_name_only_cp.set_item(_n("alpha"), _d1_proc(600))
    g_name_only.set_item(_CHAR_PROCS, g_name_only_cp)
    cases["glyph_name_only"] = (g_name_only, 65)

    g_entry_dict = _type3()
    g_entry_dict.set_item(_ENCODING, _encoding([65], ["alpha"]))
    g_entry_dict_cp = COSDictionary()
    g_entry_dict_cp.set_item(_n("alpha"), COSDictionary())
    g_entry_dict.set_item(_CHAR_PROCS, g_entry_dict_cp)
    cases["glyph_entry_dict"] = (g_entry_dict, 65)

    # ===== d0/d1 operand-count + non-numeric wx =====
    cases["d1_short_operands"] = (_with_alpha(_d1_short()), 65)
    cases["d1_long_operands"] = (_with_alpha(_d1_long()), 65)
    cases["d1_bad_wx"] = (_with_alpha(_d1_bad_wx()), 65)
    cases["d0_no_bbox"] = (_with_alpha(_d0_proc(444)), 65)

    # ===== out-of-byte-range codes =====
    cases["code_256"] = (_with_alpha(_d1_proc(600)), 256)
    cases["code_neg1"] = (_with_alpha(_d1_proc(600)), -1)

    # ===== /FontMatrix singular + width interaction =====
    fm_identity = _with_alpha(_d1_proc(600))
    fm_identity.set_item(
        _FONT_MATRIX, _arr(_i(1), _i(0), _i(0), _i(1), _i(0), _i(0))
    )
    cases["fm_identity_disp"] = (fm_identity, 65)

    fm_bad = _with_alpha(_d1_proc(600))
    fm_bad.set_item(
        _FONT_MATRIX, _arr(_fl(0.002), _n("X"), _fl(0), _fl(0.002), _fl(0), _fl(0))
    )
    cases["fm_bad_disp"] = (fm_bad, 65)

    return cases


# ---------- pypdfbox-side verdict (mirror probe's emit/projection) ----------


def _width_str(font: PDType3Font, code: int) -> str:
    try:
        return _f(font.get_width(code))
    except Exception:  # noqa: BLE001 — match probe's Throwable catch
        return "ERR"


def _disp_str(font: PDType3Font, code: int) -> str:
    try:
        tx, ty = font.get_displacement(code)
        return f"{_f(tx)},{_f(ty)}"
    except Exception:  # noqa: BLE001
        return "ERR"


def _height_str(font: PDType3Font, code: int) -> str:
    try:
        return _f(font.get_height(code))
    except Exception:  # noqa: BLE001
        return "ERR"


def _has_glyph_name_str(font: PDType3Font, name: str) -> str:
    try:
        return "true" if font.has_glyph(name) else "false"
    except Exception:  # noqa: BLE001
        return "ERR"


def _glyph_width_str(font: PDType3Font, code: int) -> str:
    try:
        cp = font.get_char_proc(code)
        if cp is None:
            return "null"
        return _f(cp.get_width())
    except Exception:  # noqa: BLE001
        return "ERR"


def _glyph_bbox_str(font: PDType3Font, code: int) -> str:
    try:
        cp = font.get_char_proc(code)
        if cp is None:
            return "null"
        r = cp.get_glyph_bbox()
        if r is None:
            return "null"
        return (
            f"{_f(r.get_lower_left_x())},{_f(r.get_lower_left_y())},"
            f"{_f(r.get_upper_right_x())},{_f(r.get_upper_right_y())}"
        )
    except Exception:  # noqa: BLE001
        return "ERR"


def _py_verdict(font_dict: COSDictionary, code: int) -> str:
    font = PDFontFactory.create_font(font_dict)
    if not isinstance(font, PDType3Font):
        return "create=NotType3"
    return (
        f"create=ok w{code}={_width_str(font, code)} "
        f"disp{code}={_disp_str(font, code)} "
        f"h{code}={_height_str(font, code)} "
        f"hgN={_has_glyph_name_str(font, 'alpha')} "
        f"gw={_glyph_width_str(font, code)} "
        f"ggb={_glyph_bbox_str(font, code)}"
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


# ----- Intentional pypdfbox divergences (CHANGES.md, wave 1553) -----
#
# (1) Lenient char-proc width: PDType3CharProc.get_width / parse_width return
# 0.0 on a non-numeric leading metric operand (d1_bad_wx) or an empty stream
# (widthfromfont_empty) where upstream raises IOException. This propagates up
# through get_width / get_displacement on the no-/Widths path: upstream emits
# ERR, pypdfbox emits 0. Mirrors the wave-1522 garbage-proc divergence.
#
# (2) Displacement float width: get_displacement applies the /FontMatrix affine
# in Python float64 against the spec-default matrix's float64 literals, while
# upstream Matrix.transform keeps float32. For width 444 + the default matrix
# this gives 0.444 (pypdfbox) vs 0.44400004 (upstream's float32 product
# 444f * 0.001f). All other widths/matrices round to the identical float32
# string, so only the d0/444 cases differ.
_DIVERGENCES: dict[str, str] = {
    "widthfromfont_empty": (
        "create=ok w65=0 disp65=0,0 h65=0 hgN=true gw=0 ggb=null"
    ),
    "d1_bad_wx": (
        "create=ok w65=0 disp65=0,0 h65=0 hgN=true gw=0 ggb=null"
    ),
    "widthfromfont_d0": (
        "create=ok w65=444 disp65=0.444,0 h65=0 hgN=true gw=444 ggb=null"
    ),
    "d0_no_bbox": (
        "create=ok w65=444 disp65=0.444,0 h65=0 hgN=true gw=444 ggb=null"
    ),
}


@requires_oracle
def test_type3_font_fuzz2_matches_pdfbox() -> None:
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
                mismatches.append(
                    f"{name}: py={py!r} != pinned {expected_py!r}"
                )
            continue

        if java != py:
            mismatches.append(f"{name}: java={java!r} py={py!r}")

    assert not mismatches, "type3 font fuzz2 divergences:\n" + "\n".join(
        mismatches
    )


@requires_oracle
def test_probe2_covers_the_type3_metric_surface() -> None:
    """Sanity: the corpus spans the documented Type 3 metric fuzz axes."""
    probe = _parse_probe(run_probe_text(_PROBE))
    assert any(k.startswith("mw_") for k in probe)
    assert any(k.startswith("w_") for k in probe)
    assert any(k.startswith("disp_") for k in probe)
    assert any(k.startswith("h_") for k in probe)
    assert any(k.startswith("glyph_") for k in probe)
    assert any(k.startswith("d1_") for k in probe)
    # The MissingWidth branch must be observable in the oracle.
    assert probe["mw_out_of_range"].split()[1] == "w65=250"


# ---------- oracle-free frozen contracts (no Java needed) ----------


def test_missing_width_branch_oracle_free() -> None:
    """Frozen contract: a code outside the /Widths window falls back to the
    descriptor's /MissingWidth (mirrors upstream getWidth's descriptor
    branch)."""
    cases = _build_cases()
    font_dict, code = cases["mw_out_of_range"]
    font = PDFontFactory.create_font(font_dict)
    assert isinstance(font, PDType3Font)
    assert font.get_width(code) == 250.0
    # No /Widths at all + descriptor: default window 0/0 excludes 65.
    font_dict, code = cases["mw_no_widths_desc"]
    font = PDFontFactory.create_font(font_dict)
    assert isinstance(font, PDType3Font)
    assert font.get_width(code) == 333.0
    # Descriptor without /MissingWidth -> default 0.
    font_dict, code = cases["mw_default_zero"]
    font = PDFontFactory.create_font(font_dict)
    assert isinstance(font, PDType3Font)
    assert font.get_width(code) == 0.0


def test_widths_non_numeric_entry_oracle_free() -> None:
    """Frozen contract: a null / non-numeric in-window /Widths entry yields a
    0.0 advance (mirrors upstream's null-entry-as-0 width)."""
    cases = _build_cases()
    for case in ("w_null_entry", "w_name_entry"):
        font_dict, code = cases[case]
        font = PDFontFactory.create_font(font_dict)
        assert isinstance(font, PDType3Font)
        assert font.get_width(code) == 0.0, case


def test_out_of_byte_range_code_oracle_free() -> None:
    """Frozen contract: a code with no /Encoding name (256, -1) resolves to no
    glyph proc -> width 0, displacement (0,0), char proc None."""
    cases = _build_cases()
    for case in ("code_256", "code_neg1"):
        font_dict, code = cases[case]
        font = PDFontFactory.create_font(font_dict)
        assert isinstance(font, PDType3Font)
        assert font.get_width(code) == 0.0, case
        assert font.get_displacement(code) == (0.0, 0.0), case
        assert font.get_char_proc(code) is None, case


def test_d1_wrong_operand_count_oracle_free() -> None:
    """Frozen contract: a leading d1 with != 6 operands yields no glyph bbox
    (mirrors upstream getGlyphBBox's arguments.size() == 6 guard) while the
    width op (arguments[0]) is still honoured."""
    cases = _build_cases()
    for case in ("d1_short_operands", "d1_long_operands"):
        font_dict, code = cases[case]
        font = PDFontFactory.create_font(font_dict)
        assert isinstance(font, PDType3Font)
        cp = font.get_char_proc(code)
        assert cp is not None, case
        assert cp.get_glyph_bbox() is None, case
        assert cp.get_width() == 600.0, case
