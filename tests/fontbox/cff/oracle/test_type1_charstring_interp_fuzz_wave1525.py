"""Live Apache FontBox differential parity for the Type 1 charstring
BYTE-LEVEL INTERPRETER (``org.apache.fontbox.cff.Type1CharStringParser``)
under malformed charstring bytecode (wave 1525 fuzz).

Where ``test_cff_subr_path_oracle`` / ``Type1GlyphPathProbe`` pin the
assembled *glyph path*, this oracle pins the parser's flat *token stream*
— the ``List<Object>`` of Integer operands interleaved with
``CharStringCommand``s that ``Type1CharStringParser.parse()`` produces
before any rendering. That isolates the operand-encoding decode (Adobe
Type 1 spec §6.2: 32-246 single byte, 247-254 two-byte, 255 = int32),
the ``callsubr`` unrolling (out-of-range / negative index, nested
recursion), and the ``callothersubr`` / ``pop`` OtherSubrs machinery
(flex OtherSubr 0/1/2, hint-replacement OtherSubr 3, the trailing ``pop``
peel loop, and the ``div`` expansion inside ``removeInteger``).

The probe (``Type1CharStringInterpFuzzProbe``) emits, per fuzz case, a
``"|"``-joined projection of the token list: an Integer operand as
``i<value>``, a ``CharStringCommand`` as ``c<Type1KeyWordName>`` (``c?``
when the command has no Type1KeyWord), an empty list as ``-``, and a
throw from ``parse()`` as ``ERR<ExceptionSimpleName>``.
``_pypdfbox_project`` reproduces that fingerprint from pypdfbox's parser.

Two kinds of cross-language normalisation are applied to the *exception*
names (they are language artifacts, not behavioural divergences):

  1. ``IOException`` (Java) <-> ``OSError`` (Python) — the documented
     mapping in CLAUDE.md's test-porting table. pypdfbox's truncation /
     EOF guards and the ``callothersubr`` pop-peek-at-EOF were aligned in
     wave 1525 to raise ``OSError`` exactly where upstream's
     ``DataInputByteArray`` throws ``IOException``.
  2. ``ArithmeticException`` (Java integer ``/`` by zero) <->
     ``ZeroDivisionError`` (Python ``//`` by zero) — the same throw, a
     different class name per language.

A small set of degenerate inputs (empty / short / non-int operand stack
feeding ``callsubr`` / ``callothersubr``) is an *intentional* pypdfbox
divergence: upstream throws an uncaught ``IndexOutOfBoundsException`` /
``ClassCastException`` (its ``parse`` is declared ``throws IOException``,
so these propagate as hard failures), whereas pypdfbox degrades
gracefully (warn-and-drop). Those cases are pinned on BOTH sides via
``_INTENTIONAL_DIVERGENCES`` so a future change to either engine is
caught.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import pytest

from pypdfbox.fontbox.cff.char_string_command import CharStringCommand
from pypdfbox.fontbox.cff.type1_char_string_parser import Type1CharStringParser
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "Type1CharStringInterpFuzzProbe"


# --------------------------------------------------------------------------
# Type 1 operand encoding (Adobe Type 1 Font Format §6.2) — shared helper.
# --------------------------------------------------------------------------
def _enc(n: int) -> bytes:
    if -107 <= n <= 107:
        return bytes([n + 139])
    if 108 <= n <= 1131:
        v = n - 108
        return bytes([(v >> 8) + 247, v & 0xFF])
    if -1131 <= n <= -108:
        v = -n - 108
        return bytes([(v >> 8) + 251, v & 0xFF])
    return bytes([255]) + n.to_bytes(4, "big", signed=True)


# 1-/2-byte operator bytes (Type1CharStringParser.java:42-47, keyword table).
_CALLSUBR = bytes([10])
_RET = bytes([11])
_ENDCHAR = bytes([14])
_HSBW = bytes([13])
_RLINETO = bytes([5])
_CALLOTHERSUBR = bytes([12, 16])
_POP = bytes([12, 17])
_DIV = bytes([12, 12])
_SEAC = bytes([12, 6])
_SBW = bytes([12, 7])
_SETCURRENTPOINT = bytes([12, 33])
_DOTSECTION = bytes([12, 0])
_VSTEM3 = bytes([12, 1])


def _hex(b: bytes) -> str:
    return b.hex() if b else "."


def _subrs_hex(subrs: list[bytes] | None) -> str:
    if not subrs:
        return "."
    return ",".join(_hex(s) for s in subrs)


# --------------------------------------------------------------------------
# Fuzz corpus: (label, charstring bytes, subrs). One row per surface.
# --------------------------------------------------------------------------
_CASES: list[tuple[str, bytes, list[bytes] | None]] = [
    # --- empty / trivial ---------------------------------------------------
    ("empty", b"", None),
    ("lone_end", _ENDCHAR, None),
    ("return_alone", _RET, None),
    # --- side bearing / width prologue ------------------------------------
    ("hsbw_ok", _enc(50) + _enc(700) + _ENDCHAR, None),
    ("hsbw_bare", _HSBW + _ENDCHAR, None),
    ("hsbw_1arg", _enc(50) + _HSBW + _ENDCHAR, None),
    ("sbw_ok", _enc(10) + _enc(20) + _enc(700) + _enc(0) + _SBW + _ENDCHAR, None),
    # --- operand encoding boundaries (§6.2) -------------------------------
    ("num_min", _enc(-107) + _ENDCHAR, None),
    ("num_max", _enc(107) + _ENDCHAR, None),
    ("num_108", _enc(108) + _ENDCHAR, None),
    ("num_1131", _enc(1131) + _ENDCHAR, None),
    ("num_neg108", _enc(-108) + _ENDCHAR, None),
    ("num_neg1131", _enc(-1131) + _ENDCHAR, None),
    ("int32_big", _enc(70000) + _ENDCHAR, None),
    ("int32_neg", _enc(-70000) + _ENDCHAR, None),
    ("int32_zero", bytes([255, 0, 0, 0, 0]) + _ENDCHAR, None),
    ("int32_minus1", bytes([255, 0xFF, 0xFF, 0xFF, 0xFF]) + _ENDCHAR, None),
    # --- truncated operands / escape (EOF -> IOException/OSError) ---------
    ("int32_trunc", bytes([255, 0, 1]), None),
    ("two_byte_trunc", bytes([247]), None),
    ("two_byte_neg_trunc", bytes([251]), None),
    ("escape_trunc", bytes([12]), None),
    # --- simple path op ----------------------------------------------------
    ("rlineto", _enc(10) + _enc(20) + _RLINETO + _ENDCHAR, None),
    ("no_endchar", _enc(10) + _enc(20) + _RLINETO, None),
    # --- callsubr ----------------------------------------------------------
    ("callsubr_ok", _enc(0) + _CALLSUBR + _ENDCHAR, [_enc(5) + _RLINETO + _RET]),
    ("callsubr_oor", _enc(99) + _CALLSUBR + _ENDCHAR, [_enc(5) + _RET]),
    ("callsubr_neg", _enc(-1) + _CALLSUBR + _ENDCHAR, [_enc(5) + _RET]),
    ("callsubr_empty", _CALLSUBR + _ENDCHAR, [_enc(5) + _RET]),
    ("callsubr_nonint", _DOTSECTION + _CALLSUBR + _ENDCHAR, [_enc(5) + _RET]),
    (
        "callsubr_oor_ints",
        _enc(1) + _enc(2) + _enc(99) + _CALLSUBR + _ENDCHAR,
        [_enc(5) + _RET],
    ),
    ("callsubr_emptysubr", _enc(0) + _CALLSUBR + _ENDCHAR, [b""]),
    (
        "subr_nested",
        _enc(0) + _CALLSUBR + _ENDCHAR,
        [_enc(1) + _CALLSUBR, _enc(7) + _RLINETO + _RET],
    ),
    ("subr_no_ret", _enc(0) + _CALLSUBR + _ENDCHAR, [_enc(7) + _RLINETO]),
    (
        "subr_chain3",
        _enc(0) + _CALLSUBR + _ENDCHAR,
        [
            _enc(1) + _CALLSUBR + _RET,
            _enc(2) + _CALLSUBR + _RET,
            _enc(9) + _RLINETO + _RET,
        ],
    ),
    # --- callothersubr / pop ----------------------------------------------
    ("othersubr1_begin", _enc(0) + _enc(1) + _CALLOTHERSUBR + _ENDCHAR, None),
    (
        "othersubr0_end",
        _enc(99) + _enc(20) + _enc(10) + _enc(3) + _enc(0) + _CALLOTHERSUBR
        + _ENDCHAR,
        None,
    ),
    (
        "othersubr0_nopop",
        _enc(99) + _enc(20) + _enc(10) + _enc(3) + _enc(0) + _CALLOTHERSUBR,
        None,
    ),
    ("othersubr3_hint", _enc(5) + _enc(1) + _enc(3) + _CALLOTHERSUBR + _ENDCHAR, None),
    (
        "othersubr3_pop",
        _enc(5) + _enc(1) + _enc(3) + _CALLOTHERSUBR + _POP + _ENDCHAR,
        None,
    ),
    ("othersubr_short", _enc(7) + _CALLOTHERSUBR + _ENDCHAR, None),
    (
        "othersubr_unknown",
        _enc(1) + _enc(2) + _enc(2) + _enc(7) + _CALLOTHERSUBR + _ENDCHAR,
        None,
    ),
    (
        "othersubr_def_pop2",
        _enc(1) + _enc(2) + _enc(2) + _enc(7) + _CALLOTHERSUBR + _POP + _POP
        + _ENDCHAR,
        None,
    ),
    (
        "othersubr_nonint",
        _DOTSECTION + _DOTSECTION + _CALLOTHERSUBR + _ENDCHAR,
        None,
    ),
    ("pop_alone", _POP + _ENDCHAR, None),
    # --- div inside removeInteger -----------------------------------------
    (
        "othersubr3_div",
        _enc(20) + _enc(4) + _DIV + _enc(1) + _enc(3) + _CALLOTHERSUBR + _ENDCHAR,
        None,
    ),
    (
        "othersubr3_divzero",
        _enc(20) + _enc(0) + _DIV + _enc(1) + _enc(3) + _CALLOTHERSUBR + _ENDCHAR,
        None,
    ),
    ("bare_div", _enc(20) + _enc(4) + _DIV + _ENDCHAR, None),
    # --- seac / setcurrentpoint / hints -----------------------------------
    (
        "seac",
        _enc(0) + _enc(100) + _enc(0) + _enc(65) + _enc(180) + _SEAC + _ENDCHAR,
        None,
    ),
    (
        "seac_badcodes",
        _enc(0) + _enc(0) + _enc(0) + _enc(300) + _enc(-5) + _SEAC + _ENDCHAR,
        None,
    ),
    ("setcurrentpoint", _enc(10) + _enc(20) + _SETCURRENTPOINT + _ENDCHAR, None),
    (
        "hints",
        _DOTSECTION + _enc(0) + _enc(10) + _enc(20) + _enc(30) + _enc(40)
        + _enc(50) + _VSTEM3 + _ENDCHAR,
        None,
    ),
]


# Degenerate inputs where pypdfbox intentionally degrades gracefully but
# upstream throws an uncaught runtime exception (its parse is declared
# ``throws IOException``). Pinned on both sides — value is the EXPECTED
# pypdfbox projection, the comment is the upstream behaviour.
_INTENTIONAL_DIVERGENCES: dict[str, str] = {
    # Java: IndexOutOfBoundsException (pops an empty operand stack).
    "callsubr_empty": "cENDCHAR",
    # Java: IndexOutOfBoundsException (callothersubr pops two from a
    # 1-element stack).
    "othersubr_short": "i7|cENDCHAR",
    # Java: ClassCastException (casts a CharStringCommand to Integer).
    "othersubr_nonint": "cENDCHAR",
}


# --------------------------------------------------------------------------
# pypdfbox projection — mirrors the Java probe's ``project`` exactly, then
# normalises the cross-language exception names.
# --------------------------------------------------------------------------
def _pypdfbox_project(cs: bytes, subrs: list[bytes] | None) -> str:
    try:
        parser = Type1CharStringParser("FuzzFont")
        seq = parser.parse(cs, list(subrs or []), "fuzzGlyph")
    except Exception as exc:  # noqa: BLE001 — fingerprint the throw class
        return "ERR" + _normalise_exc(type(exc).__name__)
    if not seq:
        return "-"
    parts: list[str] = []
    for tok in seq:
        if isinstance(tok, bool):
            parts.append("o" + type(tok).__name__)
        elif isinstance(tok, int):
            parts.append(f"i{tok}")
        elif isinstance(tok, float):
            parts.append(f"i{int(tok)}")
        elif isinstance(tok, CharStringCommand):
            kw = tok.get_type1_key_word()
            parts.append("c" + ("?" if kw is None else str(kw)))
        else:
            parts.append("o" + type(tok).__name__)
    return "|".join(parts)


def _normalise_exc(name: str) -> str:
    """Map a Python exception class name onto the Java probe's name.

    Java ``IOException`` <-> Python ``OSError`` (CLAUDE.md test-porting
    table); Java ``ArithmeticException`` <-> Python ``ZeroDivisionError``
    (integer divide-by-zero). Same throw, different language artifact.
    """
    return {
        "OSError": "IOException",
        "ZeroDivisionError": "ArithmeticException",
    }.get(name, name)


def _run_probe() -> dict[str, str]:
    """Write the corpus to a temp file, run the live probe, parse output."""
    corpus = "".join(
        f"{label} {_hex(cs)} {_subrs_hex(subrs)}\n" for label, cs, subrs in _CASES
    )
    # ``delete=False`` + explicit unlink so the probe (a separate process)
    # can reopen the file by name on Windows (CLAUDE.md cross-platform note).
    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8"
    ) as fd:
        fd.write(corpus)
        path = fd.name
    try:
        text = run_probe_text(_PROBE, path)
    finally:
        Path(path).unlink(missing_ok=True)
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        label, _, fp = line.partition(" ")
        out[label] = fp
    return out


@pytest.fixture(scope="module")
def _java() -> dict[str, str]:
    # Quiet pypdfbox's warn-and-drop logging during the parity sweep.
    logging.disable(logging.CRITICAL)
    try:
        return _run_probe()
    finally:
        logging.disable(logging.NOTSET)


@requires_oracle
@pytest.mark.parametrize("label", [c[0] for c in _CASES])
def test_type1_interp_fuzz_parity(label: str, _java: dict[str, str]) -> None:
    """pypdfbox's Type 1 charstring token stream matches Apache FontBox's
    for each malformed-input surface (modulo the cross-language exception
    name mapping and the pinned intentional-divergence set)."""
    cs, subrs = next((c, s) for (n, c, s) in _CASES if n == label)
    py = _pypdfbox_project(cs, subrs)
    if label in _INTENTIONAL_DIVERGENCES:
        # Pin pypdfbox's lenient projection; the matching upstream throw is
        # documented in ``_INTENTIONAL_DIVERGENCES``.
        assert py == _INTENTIONAL_DIVERGENCES[label]
        return
    assert py == _java[label], (
        f"{label}: pypdfbox={py!r} java={_java[label]!r}"
    )


# --------------------------------------------------------------------------
# Pure-Python pins (run without the oracle) so the corpus stays meaningful
# on a machine without the jar. These encode the agreed-upon outcomes that
# the oracle confirmed in wave 1525.
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("empty", "-"),
        ("hsbw_ok", "i50|i700|cENDCHAR"),
        ("int32_big", "i70000|cENDCHAR"),
        ("int32_minus1", "i-1|cENDCHAR"),
        ("int32_trunc", "ERRIOException"),
        ("escape_trunc", "ERRIOException"),
        ("callsubr_ok", "i5|cRLINETO|cENDCHAR"),
        ("callsubr_oor", "cENDCHAR"),
        ("subr_chain3", "i9|cRLINETO|cENDCHAR"),
        ("othersubr1_begin", "i1|cCALLOTHERSUBR|cENDCHAR"),
        ("othersubr0_end", "i0|cCALLOTHERSUBR|cENDCHAR"),
        ("othersubr0_nopop", "ERRIOException"),
        ("othersubr3_pop", "i5|cENDCHAR"),
        ("othersubr3_divzero", "ERRArithmeticException"),
        ("bare_div", "i20|i4|cDIV|cENDCHAR"),
        ("seac", "i0|i100|i0|i65|i180|cSEAC|cENDCHAR"),
        ("pop_alone", "cPOP|cENDCHAR"),
    ],
)
def test_type1_interp_fuzz_pinned(label: str, expected: str) -> None:
    """Oracle-confirmed projections, pinned for the no-jar path."""
    cs, subrs = next((c, s) for (n, c, s) in _CASES if n == label)
    logging.disable(logging.CRITICAL)
    try:
        assert _pypdfbox_project(cs, subrs) == expected
    finally:
        logging.disable(logging.NOTSET)
