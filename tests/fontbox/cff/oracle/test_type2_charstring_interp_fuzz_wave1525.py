"""Live Apache PDFBox differential parity for the FontBox **Type 2
char-string INTERPRETER / stack-execution layer**
(``org.apache.fontbox.cff.Type2CharStringParser``), fed MALFORMED bytecode
crafted directly rather than through a parsed CFF file.

The companion ``test_cff_type2_parse_oracle`` pins the token stream of
well-formed glyphs reached through a real CFF. This wave-1525 suite instead
drives the parser with hand-built byte sequences that stress how each operator
manipulates the operand stack, unrolls subroutines (bias-adjusted index,
trailing ``RET`` trimmed), counts stem hints, and skips hint-mask bytes:

* empty charstring, stack underflow, odd operand counts;
* ``hintmask`` / ``cntrmask`` with truncated mask bytes / before any stem;
* ``callsubr`` / ``callgsubr`` with empty / out-of-range / negative
  (post-bias) index, a non-integer subr operand, deep recursion;
* ``endchar`` with 2 / 4 / 5 operands (the legacy ``seac`` path);
* every numeric operand encoding edge case (28 int16, 255 16.16 fixed,
  32-246 single byte, 247-254 two byte) plus their truncated forms;
* the arithmetic / escape (``12 xx``) operators and the flex family.

Each case is run through the live PDFBox 3.0.7 jar
(``Type2CharStringInterpFuzzProbe``) and through pypdfbox's
``Type2CharStringParser`` on the *same* bytes. The probe emits either
``OK<TAB>count<TAB>tokens`` (parse succeeded) or ``ERR<TAB>ExceptionClass``
(parse threw).

Wave 1525 fixed five real interpreter divergences where pypdfbox silently
succeeded on malformed subroutine / hint-mask input that upstream rejects with
a runtime exception:

1. ``get_subr_bytes`` on an empty stack returned ``None`` instead of raising
   (upstream ``remove(size-1)`` -> ``IndexOutOfBoundsException``).
2. ``get_subr_bytes`` with a non-integer (e.g. ``255`` fixed) operand returned
   ``None`` instead of raising (upstream ``(Integer)`` cast ->
   ``ClassCastException``).
3. ``get_subr_bytes`` with a negative post-bias subr number silently wrapped to
   the list tail (Python negative indexing) instead of raising (upstream
   ``array[negativeIndex]`` -> ``ArrayIndexOutOfBoundsException``).
4. An out-of-range (too-large) subr number was swallowed by a ``None`` guard in
   ``process_call_subr`` / ``process_call_g_subr`` instead of propagating
   (upstream forwards the ``null`` into ``processSubr`` -> ``new
   DataInputByteArray(null)`` -> ``NullPointerException``).
5. ``hintmask`` / ``cntrmask`` with truncated mask bytes silently advanced past
   the end of the program instead of raising (upstream reads each mask byte via
   ``DataInput.readUnsignedByte()`` -> ``IOException`` past EOF).

The exact exception *class* is an unalignable Java-vs-Python taxonomy
difference (``IndexOutOfBoundsException`` vs ``IndexError``, ``IOException`` vs
``ValueError`` etc.), so those cases are pinned BOTH sides: the probe must emit
``ERR`` and pypdfbox must raise the mapped Python exception type.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.char_string_command import CharStringCommand
from pypdfbox.fontbox.cff.type2_char_string_parser import Type2CharStringParser
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "Type2CharStringInterpFuzzProbe"


def _op(n: int) -> bytes:
    """Single-byte Type 2 operand encoding (-107..107)."""
    return bytes([n + 139])


def _short(v: int) -> bytes:
    """The ``28`` short-int (signed 16-bit) operand encoding."""
    return bytes([28]) + (v & 0xFFFF).to_bytes(2, "big")


_E = b"\x0e"  # endchar

# Each case: (id, charstring bytes, gsubr list, lsubr list).
# gsubr / lsubr are lists of raw subr byte programs (possibly empty).
_OK_RET = _op(0) + b"\x0b"  # "0 return" subr body
_CASES: list[tuple[str, bytes, list[bytes], list[bytes]]] = [
    ("empty", b"", [], []),
    ("endchar_only", _E, [], []),
    ("endchar_4arg", _op(1) + _op(2) + _op(3) + _op(4) + _E, [], []),
    ("endchar_5arg", _op(0) + _op(1) + _op(2) + _op(3) + _op(4) + _E, [], []),
    ("endchar_2arg", _op(1) + _op(2) + _E, [], []),
    ("rmoveto_underflow", b"\x15" + _E, [], []),
    ("hstem_hintmask", _op(0) + _op(10) + b"\x01" + b"\x13" + b"\xff" + _E, [], []),
    ("hintmask_implicit_vstem", _op(0) + _op(10) + b"\x13" + b"\xff" + _E, [], []),
    ("cntrmask", _op(0) + _op(10) + b"\x14" + b"\xff" + _E, [], []),
    ("callsubr_no_index", _op(0) + b"\x0a" + _E, [], []),
    ("callgsubr_no_index", _op(0) + b"\x1d" + _E, [], []),
    ("fixed_value", bytes([255, 0, 2, 128, 0]) + _E, [], []),
    ("neg_fixed", bytes([255, 255, 254, 128, 0]) + _E, [], []),
    ("two_byte_pos", bytes([247, 0]) + _E, [], []),
    ("two_byte_neg", bytes([251, 0]) + _E, [], []),
    ("short_int", _short(-200) + _E, [], []),
    ("escape_abs", _op(5) + bytes([12, 9]) + _E, [], []),
    ("escape_div", _op(10) + _op(2) + bytes([12, 12]) + _E, [], []),
    ("escape_ifelse", _op(1) + _op(2) + _op(3) + _op(4) + bytes([12, 22]) + _E, [], []),
    ("escape_flex", (_op(0) * 13) + bytes([12, 35]) + _E, [], []),
    ("escape_hflex", (_op(0) * 7) + bytes([12, 34]) + _E, [], []),
    ("escape_unknown", bytes([12, 99]) + _E, [], []),
    ("rrcurveto_odd", (_op(0) * 5) + b"\x08" + _E, [], []),
    ("rlineto_odd", (_op(0) * 3) + b"\x05" + _E, [], []),
    ("return_alone", _op(0) + b"\x0b" + _E, [], []),
    ("callgsubr_valid", _short(-107) + b"\x1d" + _E, [_op(0) * 2 + b"\x0b"], []),
]

# Malformed cases where BOTH engines must raise (error-class taxonomy differs,
# so we pin pypdfbox to the mapped Python exception type and the probe to ERR).
_ERR_CASES: list[tuple[str, bytes, list[bytes], list[bytes], type[Exception]]] = [
    # truncated mask bytes -> upstream IOException / pypdfbox ValueError
    ("hintmask_trunc_mask", (_op(0) + _op(10)) * 9 + b"\x01" + b"\x13", [], [], ValueError),
    # stack underflow on callsubr -> IndexOutOfBoundsException / IndexError
    ("callsubr_underflow", b"\x0a" + _E, [], [_OK_RET], IndexError),
    # out-of-range (too large) post-bias index -> NullPointerException / TypeError
    ("callsubr_oor_pos", _short(5000) + b"\x0a" + _E, [], [_OK_RET], TypeError),
    # negative post-bias index -> ArrayIndexOutOfBoundsException / IndexError
    ("callsubr_neg_index", _short(-200) + b"\x0a" + _E, [], [_OK_RET], IndexError),
    # non-integer (255 fixed) subr operand -> ClassCastException / TypeError
    (
        "callsubr_float_operand",
        bytes([255, 0, 5, 128, 0]) + b"\x0a" + _E,
        [],
        [_OK_RET],
        TypeError,
    ),
    # infinite subr self-recursion -> StackOverflowError / RecursionError
    (
        "infinite_recursion",
        _short(-107) + b"\x0a" + _E,
        [],
        [_short(-107) + b"\x0a"],
        RecursionError,
    ),
    # truncated 28 short operand -> IOException / ValueError
    ("trunc_short28", bytes([28, 0]), [], [], ValueError),
    # truncated 255 fixed operand -> IOException / ValueError
    ("trunc_fixed255", bytes([255, 0, 0]), [], [], ValueError),
    # truncated 247 two-byte operand -> IOException / ValueError
    ("trunc_two_byte", bytes([247]), [], [], ValueError),
    # truncated escape (12 with no second byte) -> IOException / ValueError
    ("trunc_escape", bytes([12]), [], [], ValueError),
]


def _token(obj: object) -> str:
    """Canonical token for one parsed-sequence entry — mirrors the probe's
    ``Type2CharStringInterpFuzzProbe.token`` field-for-field."""
    if isinstance(obj, CharStringCommand):
        return str(obj).rstrip("|")
    if isinstance(obj, bool):  # pragma: no cover - guard; bool is not a token
        raise TypeError("unexpected bool token")
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, float):
        return f"{obj:.4f}"
    return str(obj)  # pragma: no cover - defensive


def _subr_arg(subrs: list[bytes]) -> str:
    """Encode a subr list as the probe's comma-separated hex argument."""
    if not subrs:
        return "-"
    return ",".join(s.hex() for s in subrs)


def _probe(cs: bytes, gsubr: list[bytes], lsubr: list[bytes]) -> str:
    cs_hex = cs.hex()
    return run_probe_text(
        _PROBE, "run", cs_hex, _subr_arg(gsubr), _subr_arg(lsubr)
    ).strip()


def _py_tokens(cs: bytes, gsubr: list[bytes], lsubr: list[bytes]) -> list[str]:
    parser = Type2CharStringParser("FuzzFont")
    seq = parser.parse(cs, gsubr, lsubr, "g")
    return [_token(x) for x in seq]


@requires_oracle
@pytest.mark.parametrize(
    ("cid", "cs", "gsubr", "lsubr"),
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_type2_interp_ok_token_stream_matches_pdfbox(
    cid: str, cs: bytes, gsubr: list[bytes], lsubr: list[bytes]
) -> None:
    """Well-formed (or gracefully-tolerated) malformed inputs: the emitted
    token stream must match upstream verbatim."""
    java = _probe(cs, gsubr, lsubr)
    assert java.startswith("OK\t"), (cid, "expected probe OK", java)
    _, j_count, *rest = java.split("\t")
    j_tokens = rest[0].split("|") if rest and rest[0] else []
    py_tokens = _py_tokens(cs, gsubr, lsubr)
    assert py_tokens == j_tokens, (cid, "py", py_tokens, "java", j_tokens)
    assert len(py_tokens) == int(j_count), (cid, len(py_tokens), int(j_count))


@requires_oracle
@pytest.mark.parametrize(
    ("cid", "cs", "gsubr", "lsubr", "exc"),
    _ERR_CASES,
    ids=[c[0] for c in _ERR_CASES],
)
def test_type2_interp_malformed_both_engines_raise(
    cid: str,
    cs: bytes,
    gsubr: list[bytes],
    lsubr: list[bytes],
    exc: type[Exception],
) -> None:
    """Malformed inputs that upstream rejects with a runtime exception:
    pypdfbox must raise too (the exact class is an unalignable Java/Python
    taxonomy difference, so we pin the probe to ERR and pypdfbox to the mapped
    Python exception type)."""
    java = _probe(cs, gsubr, lsubr)
    assert java.startswith("ERR\t"), (cid, "expected probe ERR", java)
    with pytest.raises(exc):
        _py_tokens(cs, gsubr, lsubr)
