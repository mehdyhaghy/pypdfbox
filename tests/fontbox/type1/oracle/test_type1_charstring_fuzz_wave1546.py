"""Live Apache FontBox differential fuzz for the Type 1 charstring
*interpreter* — the assembled glyph PATH + advance WIDTH — under malformed /
edge-case (post-eexec-decryption) charstring bytecode (wave 1546).

This sits one layer below ``test_type1_glyph_path_oracle.py`` /
``test_type1_seac_oracle.py`` (which pin WELL-FORMED program glyphs) and one
layer above ``oracle/probes/Type1CharStringInterpFuzzProbe.java`` (which stops
at the byte-level token stream). It targets the EXECUTION step: turning a Type 1
operand+command sequence into an outline via the ``hsbw`` / ``sbw`` width
prologue, the ``rmoveto`` / ``rlineto`` / ``rrcurveto`` / ``closepath`` path
ops, ``seac`` accent composites, the flex / hint-replacement ``OtherSubrs``
(0/1/2/3) machinery, ``div``, ``callsubr``, and ``endchar``.

Strategy (mirrored on both sides): load a real ``.pfb`` program (``DemoType1``
— the parent supplies StandardSubrs + the real ``A`` / ``B`` glyphs so flex /
``seac`` resolve), then OVERWRITE glyph ``C``'s raw charstring bytes with the
fuzz bytecode and ask the font for that glyph's path + width. ``C`` is chosen so
a ``seac`` case can reference the still-valid base / accent glyphs ``A`` / ``B``
without the overwritten glyph recursively composing itself.

* Java (``oracle/probes/Type1CharStringFuzzProbe.java``):
  ``Type1Font.createWithPFB`` → (reflection) overwrite the backing
  ``charstrings`` map's ``C`` entry → ``getPath("C")`` / ``getWidth("C")``.
  (``getCharStringsDict()`` returns an *unmodifiable* view, hence reflection.)
* pypdfbox: ``Type1Font.create_with_pfb`` → construct a ``Type1CharString``
  over the fuzz bytes (the same wrapper ``get_path`` / ``get_width`` build
  internally for an in-memory program) → ``get_path()`` / ``get_width()``.

Each case is fingerprinted exactly as the probe emits:
``minX minY maxX maxY nseg typeSeq width`` (control-point bbox rounded,
segment count, M/L/Q/C/Z PathIterator sequence with ``-`` for empty, integer
advance). The fingerprint is COORDINATE-TOLERANT but STRUCTURALLY-STRICT (the
same strategy the well-formed glyph-path oracle uses).

DIVERGENCE NOTE — error handling. Apache FontBox's hand-written interpreter
``Type1CharString.render()`` swallows most malformed operand counts and LOGS +
continues (a missing-arg ``rlineto`` is skipped, a missing ``hsbw`` leaves
width 0, ``100 0 div`` yields ``Long.MAX_VALUE`` rather than throwing), while a
*structurally* broken othersubr / garbage byte throws and ``getPath`` bubbles
the IOException. pypdfbox wraps fontTools' ``T1OutlineExtractor``, whose
operand-stack discipline raises on several of the same malformations;
``Type1CharString.get_path`` / ``get_width`` catch it and degrade to ``[]`` /
``0.0``. So on the *malformed* cases the two legitimately diverge — FontBox
yields a partial outline (or throws), pypdfbox a clean empty one. Every case is
pinned on the pypdfbox side (``_PY_EXPECTED``, self-contained, no oracle) and the
live FontBox value is recorded in ``_JAVA_EXPECTED`` (captured from PDFBox
3.0.7); the WELL-FORMED control cases must agree verbatim, and ``_DIVERGENT``
enumerates exactly which labels differ so any future convergence/regression on
either side is caught.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdfbox.fontbox.cff.type1_char_string import Type1CharString
from pypdfbox.fontbox.type1.type1_font import Type1Font
from tests.oracle.harness import requires_oracle, run_probe

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "fontbox" / "type1"
_PFB = "DemoType1.pfb"
_GLYPH = "C"


# ---------------------------------------------------------------------------
# Type 1 (decrypted) charstring encoders.
# ---------------------------------------------------------------------------
def _num(v: int) -> bytes:
    """Adobe Type 1 spec §6.2 number operand encoding (decrypted bytecode)."""
    if -107 <= v <= 107:
        return bytes([v + 139])
    if 108 <= v <= 1131:
        w = v - 108
        return bytes([(w >> 8) + 247, w & 0xFF])
    if -1131 <= v <= -108:
        w = -v - 108
        return bytes([(w >> 8) + 251, w & 0xFF])
    return bytes([255]) + v.to_bytes(4, "big", signed=True)


# One-byte operators.
_HSBW = bytes([13])
_ENDCHAR = bytes([14])
_RLINETO = bytes([5])
_RRCURVETO = bytes([8])
_RMOVETO = bytes([21])
_HMOVETO = bytes([22])
_VMOVETO = bytes([4])
_CLOSEPATH = bytes([9])
_CALLSUBR = bytes([10])
# Escape (12 xx) operators.
_SBW = bytes([12, 7])
_SEAC = bytes([12, 6])
_CALLOTHERSUBR = bytes([12, 16])
_POP = bytes([12, 17])
_DIV = bytes([12, 12])
_SETCURRENTPOINT = bytes([12, 33])


def _flex() -> bytes:
    """A well-formed Adobe flex sequence (OtherSubrs 1 / 2 / 0) drawn as a
    near-straight 7-point flex, ending with ``setcurrentpoint``."""
    out = bytearray()
    out += _num(0) + _num(1) + _CALLOTHERSUBR  # 1 0 callothersubr (begin flex)
    points = [(0, 0), (10, 10), (10, 10), (10, 10), (10, 0), (10, 0), (10, 0)]
    for dx, dy in points:
        out += _num(dx) + _num(dy) + _RMOVETO
        out += _num(0) + _num(2) + _CALLOTHERSUBR  # 2 0 callothersubr
    out += _num(50) + _num(60) + _num(0)  # flex_height end_x end_y
    out += _num(3) + _num(0) + _CALLOTHERSUBR  # 3 0 callothersubr (end flex)
    out += _POP + _POP + _SETCURRENTPOINT
    return bytes(out)


def _hint_replace() -> bytes:
    """OtherSubr 3 (hint replacement): ``subr# 1 3 callothersubr pop callsubr``."""
    return _num(0) + _num(1) + _num(3) + _CALLOTHERSUBR + _POP + _CALLSUBR


# A valid prologue + a single 100x100 box contour (4 lines), endchar.
_BOX = (
    _num(40) + _num(600) + _HSBW
    + _num(0) + _num(0) + _RMOVETO
    + _num(100) + _num(0) + _RLINETO
    + _num(0) + _num(100) + _RLINETO
    + _num(-100) + _num(0) + _RLINETO
    + _CLOSEPATH
    + _ENDCHAR
)


def _cases() -> list[tuple[str, bytes]]:
    """~39 malformed / edge charstring byte sequences (label, decrypted bytes)."""
    cases: list[tuple[str, bytes]] = []

    # --- WELL-FORMED CONTROLS (must agree verbatim) -----------------------
    cases.append(("ctrl_box", _BOX))
    cases.append(("ctrl_hsbw_endchar", _num(50) + _num(700) + _HSBW + _ENDCHAR))
    cases.append(
        (
            "ctrl_curve",
            _num(0) + _num(500) + _HSBW
            + _num(0) + _num(0) + _RMOVETO
            + _num(50) + _num(0) + _num(50) + _num(50) + _num(0) + _num(50)
            + _RRCURVETO
            + _CLOSEPATH + _ENDCHAR,
        )
    )
    cases.append(
        (
            "ctrl_hmoveto_vmoveto",
            _num(0) + _num(400) + _HSBW
            + _num(30) + _HMOVETO
            + _num(40) + _VMOVETO
            + _num(10) + _num(0) + _RLINETO
            + _CLOSEPATH + _ENDCHAR,
        )
    )
    # sbw: the vertical/full side-bearing prologue (sbx sby wx wy sbw).
    cases.append(
        ("ctrl_sbw", _num(10) + _num(0) + _num(800) + _num(0) + _SBW + _ENDCHAR)
    )

    # --- FLEX (documented fontTools-leniency divergence) ------------------
    cases.append(("flex_documented", _num(0) + _num(600) + _HSBW + _flex() + _ENDCHAR))

    # --- HSBW EDGES -------------------------------------------------------
    cases.append(
        (
            "hsbw_missing",
            _num(0) + _num(0) + _RMOVETO + _num(100) + _num(0) + _RLINETO
            + _CLOSEPATH + _ENDCHAR,
        )
    )
    cases.append(("hsbw_one_arg", _num(600) + _HSBW + _ENDCHAR))
    cases.append(("hsbw_no_args", _HSBW + _ENDCHAR))
    cases.append(
        ("hsbw_extra_args", _num(1) + _num(2) + _num(3) + _num(700) + _HSBW + _ENDCHAR)
    )
    cases.append(("hsbw_neg_width", _num(0) + _num(-200) + _HSBW + _ENDCHAR))
    cases.append(("hsbw_big_width", _num(0) + _num(9999) + _HSBW + _ENDCHAR))

    # --- SEAC EDGES (asb adx ady bchar achar seac) ------------------------
    cases.append(
        ("seac_valid", _num(0) + _num(700) + _HSBW
         + _num(0) + _num(0) + _num(0) + _num(65) + _num(66) + _SEAC))
    cases.append(
        ("seac_bad_bchar", _num(0) + _num(700) + _HSBW
         + _num(0) + _num(0) + _num(0) + _num(1) + _num(66) + _SEAC))
    cases.append(
        ("seac_bad_achar", _num(0) + _num(700) + _HSBW
         + _num(0) + _num(0) + _num(0) + _num(65) + _num(200) + _SEAC))
    cases.append(
        ("seac_neg_codes", _num(0) + _num(700) + _HSBW
         + _num(0) + _num(0) + _num(0) + _num(-5) + _num(-9) + _SEAC))
    cases.append(
        ("seac_too_few", _num(0) + _num(700) + _HSBW
         + _num(0) + _num(0) + _num(65) + _SEAC))
    cases.append(
        ("seac_no_hsbw", _num(0) + _num(0) + _num(0) + _num(65) + _num(66) + _SEAC))

    # --- CALLOTHERSUBR / FLEX EDGES --------------------------------------
    cases.append(
        ("flex_othersubr0_bad_argcount", _num(0) + _num(600) + _HSBW
         + _num(99) + _num(0) + _CALLOTHERSUBR + _ENDCHAR))
    cases.append(
        ("flex_othersubr1_only", _num(0) + _num(600) + _HSBW
         + _num(0) + _num(1) + _CALLOTHERSUBR + _ENDCHAR))
    cases.append(
        ("flex_othersubr2_only", _num(0) + _num(600) + _HSBW
         + _num(0) + _num(2) + _CALLOTHERSUBR + _ENDCHAR))
    cases.append(
        ("othersubr_unknown", _num(0) + _num(600) + _HSBW
         + _num(0) + _num(99) + _CALLOTHERSUBR + _ENDCHAR))
    cases.append(
        ("othersubr_neg_count", _num(0) + _num(600) + _HSBW
         + _num(-1) + _num(0) + _CALLOTHERSUBR + _ENDCHAR))
    cases.append(
        ("hint_replace_othersubr3", _num(0) + _num(600) + _HSBW
         + _hint_replace() + _ENDCHAR))
    cases.append(
        ("pop_without_othersubr", _num(0) + _num(600) + _HSBW + _POP + _ENDCHAR))

    # --- DIV EDGES --------------------------------------------------------
    cases.append(
        ("div_normal", _num(0) + _num(600) + _HSBW
         + _num(100) + _num(2) + _DIV + _num(0) + _RMOVETO + _ENDCHAR))
    cases.append(
        ("div_by_zero", _num(0) + _num(600) + _HSBW
         + _num(100) + _num(0) + _DIV + _num(0) + _RMOVETO + _ENDCHAR))
    cases.append(
        ("div_no_args", _num(0) + _num(600) + _HSBW + _DIV + _ENDCHAR))

    # --- CALLSUBR EDGES ---------------------------------------------------
    cases.append(
        ("callsubr_oob_high", _num(0) + _num(600) + _HSBW
         + _num(9999) + _CALLSUBR + _ENDCHAR))
    cases.append(
        ("callsubr_negative", _num(0) + _num(600) + _HSBW
         + _num(-1) + _CALLSUBR + _ENDCHAR))
    cases.append(
        ("callsubr_no_index", _num(0) + _num(600) + _HSBW + _CALLSUBR + _ENDCHAR))

    # --- STACK UNDERFLOW / PATH-OP EDGES ---------------------------------
    cases.append(
        ("rlineto_underflow", _num(0) + _num(600) + _HSBW
         + _num(0) + _num(0) + _RMOVETO + _num(5) + _RLINETO + _ENDCHAR))
    cases.append(
        ("rrcurveto_underflow", _num(0) + _num(600) + _HSBW
         + _num(0) + _num(0) + _RMOVETO
         + _num(1) + _num(2) + _num(3) + _RRCURVETO + _ENDCHAR))
    cases.append(
        ("rmoveto_one_arg", _num(0) + _num(600) + _HSBW
         + _num(5) + _RMOVETO + _ENDCHAR))

    # --- ENDCHAR / TERMINATION EDGES -------------------------------------
    cases.append(
        ("endchar_mid_path", _num(0) + _num(600) + _HSBW
         + _num(0) + _num(0) + _RMOVETO + _num(50) + _num(0) + _RLINETO
         + _ENDCHAR + _num(50) + _num(0) + _RLINETO + _CLOSEPATH))
    cases.append(
        ("no_endchar", _num(0) + _num(600) + _HSBW
         + _num(0) + _num(0) + _RMOVETO + _num(50) + _num(0) + _RLINETO))
    cases.append(("empty_charstring", b""))
    cases.append(("only_endchar", _ENDCHAR))
    cases.append(("garbage_bytes", bytes([0xFF, 0xFF, 0xFF])))

    return cases


# ---------------------------------------------------------------------------
# pypdfbox-side fingerprint (mirror the probe's PathIterator projection).
# ---------------------------------------------------------------------------
def _py_fingerprint(font: Type1Font, fuzz: bytes) -> str:
    """Build a ``Type1CharString`` over ``fuzz`` (bound to ``font`` for seac
    component resolution) and project its path+width into the probe's
    ``minX minY maxX maxY nseg typeSeq width`` line."""
    wrapper = Type1CharString(
        font=font,
        font_name=font.get_name(),
        glyph_name=_GLYPH,
        sequence=fuzz,
    )
    try:
        commands = list(wrapper.get_path() or [])
    except Exception:  # noqa: BLE001 — match get_path's swallow
        commands = []
    try:
        width = int(round(float(wrapper.get_width() or 0.0)))
    except Exception:  # noqa: BLE001
        width = 0
    return _fingerprint_commands(commands) + " " + str(width)


def _fingerprint_commands(commands: list[tuple[Any, ...]]) -> str:
    """``minX minY maxX maxY nseg typeSeq`` from a moveto/lineto/curveto/
    closepath command list, mirroring the AWT PathIterator projection.

    Java's ``closeCharString1Path`` appends a ``moveTo(current)`` after every
    ``closePath`` and a ``GeneralPath`` collapses consecutive moveTos, so we
    reproduce both normalisations (identical to the well-formed glyph-path
    oracle). The control-point bbox uses the raw control points: for these
    fuzz boxes / short curves the control hull and the swept bbox coincide,
    and any deviation would surface as a divergence to investigate rather than
    be silently absorbed."""
    ops: list[tuple[str, tuple[float, ...]]] = []
    current: tuple[float, float] = (0.0, 0.0)
    for cmd in commands:
        tag = cmd[0]
        if tag == "moveto":
            current = (float(cmd[1]), float(cmd[2]))
            ops.append(("M", current))
        elif tag == "lineto":
            current = (float(cmd[1]), float(cmd[2]))
            ops.append(("L", current))
        elif tag == "curveto":
            ops.append(
                (
                    "C",
                    (
                        float(cmd[1]), float(cmd[2]), float(cmd[3]),
                        float(cmd[4]), float(cmd[5]), float(cmd[6]),
                    ),
                )
            )
            current = (float(cmd[5]), float(cmd[6]))
        elif tag == "closepath":
            ops.append(("Z", ()))
            ops.append(("M", current))

    types: list[str] = []
    xs: list[float] = []
    ys: list[float] = []
    for i, (kind, vals) in enumerate(ops):
        if kind == "M":
            if i + 1 < len(ops) and ops[i + 1][0] == "M":
                continue
            types.append("M")
            xs.append(vals[0])
            ys.append(vals[1])
        elif kind == "L":
            types.append("L")
            xs.append(vals[0])
            ys.append(vals[1])
        elif kind == "C":
            types.append("C")
            xs.extend((vals[0], vals[2], vals[4]))
            ys.extend((vals[1], vals[3], vals[5]))
        elif kind == "Z":
            types.append("Z")

    nseg = len(types)
    if nseg == 0:
        return "0 0 0 0 0 -"
    return (
        f"{round(min(xs))} {round(min(ys))} {round(max(xs))} {round(max(ys))} "
        f"{nseg} {''.join(types)}"
    )


# ---------------------------------------------------------------------------
# Pinned pypdfbox fingerprints (self-contained — no oracle needed). Captured
# from this very module against pypdfbox after the wave-1546 ``sbw`` width fix.
# ---------------------------------------------------------------------------
_PY_EXPECTED: dict[str, str] = {
    "ctrl_box": "40 0 140 100 6 MLLLZM 600",
    "ctrl_hsbw_endchar": "0 0 0 0 0 - 700",
    "ctrl_curve": "0 0 100 100 4 MCZM 500",
    "ctrl_hmoveto_vmoveto": "30 40 40 40 4 MLZM 400",
    "ctrl_sbw": "0 0 0 0 0 - 800",
    "flex_documented": "0 0 60 30 3 MCC 600",
    "hsbw_missing": "0 0 100 0 4 MLZM 0",
    "hsbw_one_arg": "0 0 0 0 0 - 0",
    "hsbw_no_args": "0 0 0 0 0 - 0",
    "hsbw_extra_args": "0 0 0 0 0 - 0",
    "hsbw_neg_width": "0 0 0 0 0 - -200",
    "hsbw_big_width": "0 0 0 0 0 - 9999",
    "seac_valid": "35 0 140 100 11 MLLLZMLLLZM 700",
    "seac_bad_bchar": "0 0 135 100 11 MLLLZMLLLZM 700",
    "seac_bad_achar": "0 0 140 100 11 MLLLZMLLLZM 700",
    "seac_neg_codes": "0 0 100 100 11 MLLLZMLLLZM 700",
    "seac_too_few": "0 0 0 0 0 - 0",
    "seac_no_hsbw": "35 0 140 100 11 MLLLZMLLLZM 0",
    "flex_othersubr0_bad_argcount": "0 0 0 0 0 - 600",
    "flex_othersubr1_only": "0 0 0 0 0 - 600",
    "flex_othersubr2_only": "0 0 0 0 0 - 600",
    "othersubr_unknown": "0 0 0 0 0 - 600",
    "othersubr_neg_count": "0 0 0 0 0 - 600",
    "hint_replace_othersubr3": "0 0 0 0 0 - 0",
    "pop_without_othersubr": "0 0 0 0 0 - 600",
    "div_normal": "50 0 50 0 1 M 600",
    "div_by_zero": "0 0 0 0 0 - 0",
    "div_no_args": "0 0 0 0 0 - 0",
    "callsubr_oob_high": "0 0 0 0 0 - 0",
    "callsubr_negative": "0 0 0 0 0 - 0",
    "callsubr_no_index": "0 0 0 0 0 - 0",
    "rlineto_underflow": "0 0 0 0 0 - 0",
    "rrcurveto_underflow": "0 0 0 0 0 - 0",
    "rmoveto_one_arg": "0 0 0 0 0 - 0",
    "endchar_mid_path": "0 0 100 0 6 MLMLZM 600",
    "no_endchar": "0 0 50 0 2 ML 600",
    "empty_charstring": "0 0 0 0 0 - 0",
    "only_endchar": "0 0 0 0 0 - 0",
    "garbage_bytes": "0 0 0 0 0 - 0",
}

# Live Apache PDFBox 3.0.7 fingerprints (oracle/probes/Type1CharStringFuzzProbe).
# Where this differs from _PY_EXPECTED the label is in _DIVERGENT (below).
_JAVA_EXPECTED: dict[str, str] = {
    "ctrl_box": "40 0 140 100 6 MLLLZM 600",
    "ctrl_hsbw_endchar": "0 0 0 0 0 - 700",
    "ctrl_curve": "0 0 100 100 4 MCZM 500",
    "ctrl_hmoveto_vmoveto": "30 40 40 40 4 MLZM 400",
    "ctrl_sbw": "0 0 0 0 0 - 800",
    # Documented flex divergence: FontBox validates the flex arg count and
    # keeps only the 2 reference cubics; fontTools is lenient and keeps 3.
    "flex_documented": "30 30 60 30 2 MC 600",
    "hsbw_missing": "0 0 100 0 4 MLZM 0",
    "hsbw_one_arg": "0 0 0 0 0 - 0",
    "hsbw_no_args": "0 0 0 0 0 - 0",
    # FontBox pops the LAST two pushed values as (sbx, wx) -> width 2;
    # fontTools requires exactly two operands and raises -> empty/0.
    "hsbw_extra_args": "0 0 0 0 0 - 2",
    "hsbw_neg_width": "0 0 0 0 0 - -200",
    "hsbw_big_width": "0 0 0 0 0 - 9999",
    "seac_valid": "35 0 140 100 11 MLLLZMLLLZM 700",
    "seac_bad_bchar": "0 0 135 100 11 MLLLZMLLLZM 700",
    "seac_bad_achar": "0 0 140 100 11 MLLLZMLLLZM 700",
    "seac_neg_codes": "0 0 100 100 11 MLLLZMLLLZM 700",
    # FontBox runs hsbw (width 700) THEN fails the short seac; pypdfbox/
    # fontTools raises on the short seac and drops the whole glyph (width 0).
    "seac_too_few": "0 0 0 0 0 - 700",
    "seac_no_hsbw": "35 0 140 100 11 MLLLZMLLLZM 0",
    # FontBox's IOException on a structurally-invalid othersubr bubbles out of
    # getPath -> ERR; fontTools tolerates it and yields an empty path.
    "flex_othersubr0_bad_argcount": "ERR ERR ERR ERR ERR ERR ERR",
    "flex_othersubr1_only": "0 0 0 0 0 - 600",
    "flex_othersubr2_only": "0 0 0 0 0 - 600",
    "othersubr_unknown": "0 0 0 0 0 - 600",
    "othersubr_neg_count": "ERR ERR ERR ERR ERR ERR ERR",
    # FontBox keeps width 600 through the hint-replacement subr; pypdfbox's
    # wrapped extractor loses it in the callothersubr/pop unwind (width 0).
    "hint_replace_othersubr3": "0 0 0 0 0 - 600",
    # FontBox: getPath throws on the unbalanced pop (ERR) but getWidth, run
    # separately, still reports 600. pypdfbox tolerates the pop -> empty/600.
    "pop_without_othersubr": "ERR ERR ERR ERR ERR ERR 600",
    "div_normal": "50 0 50 0 1 M 600",
    # FontBox: 100/0 = Long.MAX_VALUE (no throw) then moveTo; pypdfbox/
    # fontTools raises ZeroDivisionError -> empty/0.
    "div_by_zero": "9223372036854775807 0 0 0 1 M 600",
    # FontBox tolerates the under-fed div (width 600 survives); fontTools
    # underflows the stack and raises -> empty/0.
    "div_no_args": "0 0 0 0 0 - 600",
    # Out-of-range / negative callsubr: FontBox logs + skips (width 600);
    # fontTools indexes its subrs list and raises -> empty/0.
    "callsubr_oob_high": "0 0 0 0 0 - 600",
    "callsubr_negative": "0 0 0 0 0 - 600",
    "callsubr_no_index": "0 0 0 0 0 - 0",
    # FontBox skips the under-fed path op but keeps width 600; fontTools
    # underflows and raises -> empty/0.
    "rlineto_underflow": "0 0 0 0 1 M 600",
    "rrcurveto_underflow": "0 0 0 0 1 M 600",
    "rmoveto_one_arg": "0 0 0 0 0 - 600",
    # FontBox honours endchar mid-path (5 segs); fontTools keeps decoding the
    # trailing rlineto/closepath after endchar (6 segs).
    "endchar_mid_path": "0 0 100 0 5 MLLZM 600",
    "no_endchar": "0 0 50 0 2 ML 600",
    "empty_charstring": "0 0 0 0 0 - 0",
    "only_endchar": "0 0 0 0 0 - 0",
    # Pure garbage bytes: FontBox throws in both getPath and getWidth (all
    # ERR); fontTools yields a clean empty/0.
    "garbage_bytes": "ERR ERR ERR ERR ERR ERR ERR",
}

# Labels where pypdfbox (fontTools) legitimately differs from FontBox's lenient
# hand interpreter (see per-line comments in _JAVA_EXPECTED). Controls
# (``ctrl_*``) must NOT appear here.
_DIVERGENT: frozenset[str] = frozenset(
    label
    for label in _PY_EXPECTED
    if _PY_EXPECTED[label] != _JAVA_EXPECTED[label]
)


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------
def test_expected_tables_cover_all_cases() -> None:
    """Both expected tables enumerate exactly the generated cases, and no
    control case is in the divergent set."""
    labels = {label for label, _ in _cases()}
    assert set(_PY_EXPECTED) == labels
    assert set(_JAVA_EXPECTED) == labels
    assert not any(label.startswith("ctrl_") for label in _DIVERGENT)


def test_type1_charstring_fuzz_pypdfbox_pinned() -> None:
    """Self-contained pin of pypdfbox's own fingerprints over every fuzz case
    (runs without the oracle). Locks the wrapped Type 1 charstring
    interpreter's behaviour so any regression — including a re-break of the
    wave-1546 ``sbw`` width fix — is caught."""
    fixture = _FIXTURES / _PFB
    for label, fuzz in _cases():
        font = Type1Font.create_with_pfb(fixture.read_bytes())
        got = _py_fingerprint(font, fuzz)
        assert got == _PY_EXPECTED[label], f"{label}: {got!r} != {_PY_EXPECTED[label]!r}"


def test_sbw_width_is_recorded() -> None:
    """Regression pin for the wave-1546 fix: an ``sbw`` (vertical writing-mode)
    prologue must yield its real advance (wx), not 0. fontTools' stock
    ``op_sbw`` is a no-op stub that discarded the operands; pypdfbox now
    overrides it to record (sbx, sby, wx) like Apache FontBox."""
    fixture = _FIXTURES / _PFB
    font = Type1Font.create_with_pfb(fixture.read_bytes())
    sbw = _num(10) + _num(0) + _num(800) + _num(0) + _SBW + _ENDCHAR
    wrapper = Type1CharString(
        font=font, font_name=font.get_name(), glyph_name=_GLYPH, sequence=sbw
    )
    assert wrapper.get_width() == 800.0


def test_type1_charstring_fuzz_no_crash() -> None:
    """Defensive: no fuzz case may raise out of pypdfbox's path/width API —
    every malformation degrades to an empty path / zero width, never a crash."""
    fixture = _FIXTURES / _PFB
    for label, fuzz in _cases():
        font = Type1Font.create_with_pfb(fixture.read_bytes())
        cs_map = font._charstrings_dict()
        cs_map[_GLYPH] = fuzz
        font._widths.pop(_GLYPH, None)
        path = font.get_path(_GLYPH)
        width = font.get_width(_GLYPH)
        assert isinstance(path, list), label
        assert isinstance(width, float), label


@requires_oracle
def test_type1_charstring_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Differential: live FontBox vs pypdfbox over every fuzz case. The pinned
    ``_JAVA_EXPECTED`` table must still equal the live oracle (catches an
    upstream/jar drift), the WELL-FORMED controls must agree verbatim with
    pypdfbox, and the divergent set must exactly match the labels that differ
    (catches a silent convergence/regression on either side)."""
    fixture = _FIXTURES / _PFB
    cases = _cases()
    cases_file = tmp_path / "type1_charstring_fuzz_cases.txt"
    cases_file.write_text(
        "\n".join(
            f"{label} {data.hex() if data else '.'}" for label, data in cases
        )
        + "\n",
        encoding="utf-8",
    )
    raw = run_probe(
        "Type1CharStringFuzzProbe", str(fixture), str(cases_file)
    ).decode("utf-8")
    java: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        label, _, payload = line.partition(" ")
        java[label] = payload.strip()

    assert set(java) == {label for label, _ in cases}

    observed_divergent: set[str] = set()
    for label, fuzz in cases:
        # Live FontBox must still match the pinned table.
        assert java[label] == _JAVA_EXPECTED[label], (
            f"{label}: live FontBox {java[label]!r} != pinned "
            f"{_JAVA_EXPECTED[label]!r}"
        )
        font = Type1Font.create_with_pfb(fixture.read_bytes())
        py = _py_fingerprint(font, fuzz)
        assert py == _PY_EXPECTED[label], (
            f"{label}: pypdfbox {py!r} != pinned {_PY_EXPECTED[label]!r}"
        )
        if py != java[label]:
            observed_divergent.add(label)
            assert not label.startswith("ctrl_"), (
                f"{label}: control diverged pypdfbox {py!r} != FontBox "
                f"{java[label]!r}"
            )

    assert observed_divergent == set(_DIVERGENT), (
        f"divergence set drift: observed {sorted(observed_divergent)} != "
        f"pinned {sorted(_DIVERGENT)}"
    )
