"""Live PDFBox differential fuzz parity for ``PDCIDFont`` width-table parsing.

Wave 1528, agent D. Fuzzes the descendant-CIDFont ``/W`` / ``/W2`` / ``/DW`` /
``/DW2`` width machinery (PDF 32000-1 §9.7.4.3) with deliberately malformed
dictionaries built in memory and wrapped in a minimal Identity-H
:class:`PDType0Font` (so ``code_to_cid(code) == code`` for in-range codes).

This is a distinct surface from the two adjacent CID oracle tests:

* ``test_cid_width_oracle`` loads real, well-formed Type0 fixtures and pins the
  value-parity of ``get_width`` / ``has_explicit_width`` / ``/DW``.
* ``test_cid_to_gid_stream_oracle`` covers ``/CIDToGIDMap``.

Neither fuzzes the width *arrays* themselves. Here we exercise both ``/W`` run
forms (``c [w1 w2 ...]`` list, ``c1 c2 w`` range), mixed forms, malformed runs
(non-numeric c/w, array-vs-number swaps, odd trailing tokens, premature end,
``c2 < c1``, negative/huge CIDs, ``null`` entries, overlap), the ``/DW`` default
(missing → 1000 / non-numeric → 1000 / float), and the ``/W2`` + ``/DW2``
vertical-metrics tables.

The oracle output is produced by ``oracle/probes/CidFontWidthFuzzProbe.java``;
the Python side rebuilds the identical dicts and reconstructs the identical line
grammar so a divergence shows up as a single differing token.

Two classes of upstream behaviour are pinned:

* **Parity cases** — pypdfbox must match Apache PDFBox exactly (the bulk).
* **Divergent cases** — Apache PDFBox's ``readVerticalDisplacements`` /
  ``/DW2`` reader uses *unchecked* casts and unconditional ``getObject(0/1)``,
  so a malformed ``/W2`` or one-element ``/DW2`` throws
  ``ClassCastException`` / ``IndexOutOfBoundsException`` from the CIDFont
  constructor. pypdfbox parses these leniently (no crash). These four cases are
  pinned BOTH sides per CHANGES.md (Wave 1528): the Java side is asserted to
  fail at construction, the Python side is asserted to construct and answer.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSNumber,
)
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE_CIDS = (0, 1, 5, 10, 11, 12, 13, 20, 21, 22, 23, 100, 200, 1000, 65535, -1)

# Cases where Apache PDFBox's unchecked-cast /W2 reader (or unconditional /DW2
# getObject) crashes at CIDFont construction while pypdfbox parses leniently.
# Pinned both sides — see module docstring + CHANGES.md (Wave 1528).
_DIVERGENT = {
    "dw2_short",
    "w2_nonnumeric_c",
    "w2_ragged_inner",
    "w2_range_nonnumeric",
}


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _i(v: int) -> COSInteger:
    return COSInteger.get(v)


def _fl(v: float) -> COSFloat:
    return COSFloat(v)


def _arr(*items: object) -> COSArray:
    a = COSArray()
    for b in items:
        a.add(b)
    return a


def _f(v: float) -> str:
    """Match the Java probe's ``f(float)`` (integral -> no decimals, -0.0 -> 0)."""
    if v == 0.0:
        v = 0.0
    if v == int(v) and v not in (float("inf"), float("-inf")):
        return str(int(v))
    import struct

    return repr(struct.unpack("f", struct.pack("f", v))[0])


def _cid_font() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Font"))
    d.set_item(_n("Subtype"), _n("CIDFontType2"))
    d.set_item(_n("BaseFont"), _n("Test"))
    return d


def _wrap(cid: COSDictionary) -> COSDictionary:
    t0 = COSDictionary()
    t0.set_item(_n("Type"), _n("Font"))
    t0.set_item(_n("Subtype"), _n("Type0"))
    t0.set_item(_n("BaseFont"), _n("Test"))
    t0.set_item(_n("Encoding"), _n("Identity-H"))
    t0.set_item(_n("DescendantFonts"), _arr(cid))
    return t0


def _read_dw(descendant: object) -> float:
    dw = descendant._dict.get_dictionary_object(_n("DW"))
    if isinstance(dw, COSNumber):
        return dw.float_value()
    return 1000.0


def _build_cases() -> list[tuple[str, COSDictionary]]:
    """Build the identical fuzz corpus as CidFontWidthFuzzProbe.main, in order."""
    cases: list[tuple[str, COSDictionary]] = []

    cases.append(("w_missing", _cid_font()))

    e = _cid_font()
    e.set_item(_n("W"), COSArray())
    cases.append(("w_empty", e))

    e = _cid_font()
    e.set_item(_n("W"), _arr(_i(10), _arr(_i(100), _i(200), _i(300))))
    cases.append(("w_list", e))

    e = _cid_font()
    e.set_item(_n("W"), _arr(_i(20), _i(22), _i(500)))
    cases.append(("w_range", e))

    e = _cid_font()
    e.set_item(
        _n("W"),
        _arr(_i(10), _arr(_i(100), _i(200), _i(300)), _i(20), _i(22), _i(500)),
    )
    cases.append(("w_mixed", e))

    e = _cid_font()
    e.set_item(_n("W"), _arr(_i(10), _arr(_fl(100.5), _fl(200.25))))
    cases.append(("w_float", e))

    e = _cid_font()
    e.set_item(_n("W"), _arr(_n("X"), _arr(_i(100), _i(200))))
    cases.append(("w_nonnumeric_c", e))

    e = _cid_font()
    e.set_item(_n("W"), _arr(_i(10), _arr(_i(100), _n("Y"), _i(300))))
    cases.append(("w_inner_nonnumeric", e))

    e = _cid_font()
    e.set_item(_n("W"), _arr(_i(20), _i(22), _n("Z")))
    cases.append(("w_range_nonnumeric_w", e))

    e = _cid_font()
    e.set_item(_n("W"), _arr(_i(10), _arr(_i(100)), _i(99)))
    cases.append(("w_odd_trailing", e))

    e = _cid_font()
    e.set_item(_n("W"), _arr(_i(10), _i(20)))
    cases.append(("w_premature_end", e))

    e = _cid_font()
    e.set_item(_n("W"), _arr(_i(22), _i(20), _i(500)))
    cases.append(("w_range_reversed", e))

    e = _cid_font()
    e.set_item(_n("W"), _arr(_i(-1), _arr(_i(100), _i(200))))
    cases.append(("w_negative_cid", e))

    e = _cid_font()
    e.set_item(_n("W"), _arr(_i(65535), _arr(_i(700))))
    cases.append(("w_huge_cid", e))

    e = _cid_font()
    e.set_item(_n("W"), _arr(COSNull.NULL, _arr(_i(100))))
    cases.append(("w_null_c", e))

    e = _cid_font()
    e.set_item(_n("W"), _arr(_i(10), _i(12), _i(111), _i(11), _arr(_i(999))))
    cases.append(("w_overlap", e))

    e = _cid_font()
    e.set_item(_n("W"), _n("Nope"))
    cases.append(("w_not_array", e))

    e = _cid_font()
    e.set_item(_n("DW"), _i(222))
    cases.append(("dw_int", e))

    e = _cid_font()
    e.set_item(_n("DW"), _fl(333.5))
    cases.append(("dw_float", e))

    e = _cid_font()
    e.set_item(_n("DW"), _n("Big"))
    cases.append(("dw_nonnumeric", e))

    e = _cid_font()
    e.set_item(_n("DW"), _i(222))
    e.set_item(
        _n("W"),
        _arr(_i(10), _arr(_i(100), _i(200), _i(300)), _i(20), _i(22), _i(500)),
    )
    cases.append(("dw_and_w", e))

    e = _cid_font()
    e.set_item(
        _n("W2"),
        _arr(
            _i(10),
            _arr(_i(-1000), _i(500), _i(880), _i(-1100), _i(510), _i(890)),
        ),
    )
    cases.append(("w2_list", e))

    e = _cid_font()
    e.set_item(_n("W2"), _arr(_i(20), _i(22), _i(-1000), _i(500), _i(880)))
    cases.append(("w2_range", e))

    cases.append(("w2_missing", _cid_font()))

    e = _cid_font()
    e.set_item(_n("DW2"), _arr(_i(900), _i(-1100)))
    cases.append(("dw2_explicit", e))

    e = _cid_font()
    e.set_item(_n("DW2"), _arr(_i(900)))
    cases.append(("dw2_short", e))

    e = _cid_font()
    e.set_item(_n("DW2"), _arr(_n("A"), _n("B")))
    cases.append(("dw2_nonnumeric", e))

    e = _cid_font()
    e.set_item(_n("W2"), _arr(_n("X"), _arr(_i(-1000), _i(500), _i(880))))
    cases.append(("w2_nonnumeric_c", e))

    e = _cid_font()
    e.set_item(_n("W2"), _arr(_i(10), _arr(_i(-1000), _i(500))))
    cases.append(("w2_ragged_inner", e))

    e = _cid_font()
    e.set_item(_n("W2"), _arr(_i(20), _i(22), _i(-1000), _n("Y"), _i(880)))
    cases.append(("w2_range_nonnumeric", e))

    e = _cid_font()
    e.set_item(_n("W2"), _arr(_i(22), _i(20), _i(-1000), _i(500), _i(880)))
    cases.append(("w2_range_reversed", e))

    return cases


def _py_emit(name: str, cid: COSDictionary) -> str:
    """Reconstruct one CidFontWidthFuzzProbe CASE line from pypdfbox."""
    try:
        t0 = PDType0Font(_wrap(cid))
    except Exception as exc:  # noqa: BLE001 - mirror the probe's Throwable catch
        return f"CASE {name} create=ERR:{type(exc).__name__}"
    descendant = t0.get_descendant_font()
    if descendant is None:
        return f"CASE {name} create=nodesc"
    parts = ["CASE", name, "create=ok", f"dw={_f(_read_dw(descendant))}"]
    for c in _PROBE_CIDS:
        try:
            parts.append(f"w{c}={_f(descendant.get_width(c))}")
        except Exception:  # noqa: BLE001
            parts.append(f"w{c}=ERR")
        try:
            parts.append(
                f"hx{c}={'true' if descendant.has_explicit_width(c) else 'false'}"
            )
        except Exception:  # noqa: BLE001
            parts.append(f"hx{c}=ERR")
    for c in _PROBE_CIDS:
        try:
            parts.append(f"vy{c}={_f(descendant.get_vertical_displacement_vector_y(c))}")
        except Exception:  # noqa: BLE001
            parts.append(f"vy{c}=ERR")
        try:
            v = descendant.get_position_vector(c)
            parts.append(f"pv{c}={_f(v[0])},{_f(v[1])}")
        except Exception:  # noqa: BLE001
            parts.append(f"pv{c}=ERR")
    return " ".join(parts)


@requires_oracle
def test_cid_font_width_fuzz_matches_pdfbox() -> None:
    """Every parity-class fuzz case must match Apache PDFBox token-for-token.

    Builds the identical malformed-dict corpus, runs the Java oracle, and
    diffs each CASE line. The four divergent cases (upstream unchecked-cast /
    OOB crashes) are skipped here and pinned by the dedicated test below.
    """
    java_lines = {
        ln.split()[1]: ln
        for ln in run_probe_text("CidFontWidthFuzzProbe").splitlines()
        if ln.startswith("CASE ")
    }
    py_lines = {name: _py_emit(name, cid) for name, cid in _build_cases()}

    assert set(java_lines) == set(py_lines), (
        f"case-name set mismatch: java-only={set(java_lines) - set(py_lines)} "
        f"py-only={set(py_lines) - set(java_lines)}"
    )

    diffs: list[str] = []
    for name in sorted(py_lines):
        if name in _DIVERGENT:
            continue
        j = java_lines[name].split()
        p = py_lines[name].split()
        if j != p:
            mism = [
                f"{a}|{b}"
                for a, b in zip(j, p, strict=False)
                if a != b
            ] or [f"LEN{len(j)}|LEN{len(p)}"]
            diffs.append(f"  {name}: " + ", ".join(mism[:6]))
    assert not diffs, "CID width fuzz parity broken:\n" + "\n".join(diffs)


@requires_oracle
def test_divergent_cases_pinned_both_sides() -> None:
    """Pin the four unalignable cases: Apache PDFBox crashes at construction,
    pypdfbox parses leniently.

    Upstream ``readVerticalDisplacements`` casts ``/W2`` elements without an
    ``instanceof`` guard and reads ``/DW2`` ``getObject(0/1)`` unconditionally,
    so a malformed ``/W2`` (non-number leading CID, ragged inner triple,
    non-number range metric) or a one-element ``/DW2`` throws from the CIDFont
    constructor. pypdfbox guards every access, so construction succeeds. This
    test asserts BOTH sides of that documented divergence (CHANGES.md Wave 1528).
    """
    java_lines = {
        ln.split()[1]: ln
        for ln in run_probe_text("CidFontWidthFuzzProbe").splitlines()
        if ln.startswith("CASE ")
    }
    for name, cid in _build_cases():
        if name not in _DIVERGENT:
            continue
        # Java side: crashed at construction.
        assert java_lines[name].split()[2].startswith("create=ERR:"), (
            f"expected upstream crash for {name}, got {java_lines[name]}"
        )
        # Python side: lenient construction + answers.
        py = _py_emit(name, cid)
        assert "create=ok" in py, f"expected lenient pypdfbox parse for {name}: {py}"


def test_position_vector_resolves_code_to_cid() -> None:
    """Regression pin for the wave-1528 fix (no oracle needed).

    Upstream ``PDCIDFont.getPositionVector(int code)`` resolves ``code -> CID``
    via ``codeToCID`` before the ``/W2`` lookup and default-vector fallback;
    pypdfbox's ``get_position_vector`` previously treated its argument as an
    already-resolved CID and skipped ``code_to_cid``. For an identity CMap the
    two agree, so this builds a font whose ``/W`` gives a CID a distinct width
    and checks the default position vector's ``v_x`` equals ``get_width(code)/2``
    (i.e. it went through the same ``code -> CID -> width`` path as get_width).
    """
    from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

    cid = _cid_font()
    cid.set_item(_n("DW"), _i(1000))
    # CID 10 -> 100, CID 11 -> 200 (list form); no /W2 so position vector is the
    # default-vector fallback (width/2, dw2[0]=880).
    cid.set_item(_n("W"), _arr(_i(10), _arr(_i(100), _i(200))))
    font = PDCIDFontType2(cid)

    # codeToCID is identity for a bare CIDFontType2, so code == CID here.
    for code in (10, 11, 0, 99):
        v_x, v_y = font.get_position_vector(code)
        assert v_x == font.get_width(code) / 2.0, code
        assert v_y == 880.0, code
