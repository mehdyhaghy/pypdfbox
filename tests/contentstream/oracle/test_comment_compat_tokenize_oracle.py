"""Live PDFBox differential parity for tokenizer comment / BX-EX edge cases.

Targets the content-stream tokenizer surfaces that are easy to get subtly
wrong: ``%``-comment skipping (a comment runs to end-of-line and is
discarded — it never becomes a token), and the ``BX`` / ``EX`` compatibility
operators (ISO 32000-1 §8.10.1) that bracket a section where *unrecognised*
operators must be tolerated rather than raising. Crucially PDFBox does NOT
treat ``BX``/``EX`` specially in the tokenizer — they are ordinary operator
keywords, and an unknown operator anywhere (inside or outside a ``BX``/``EX``
block) is simply emitted as an :class:`Operator`. This test pins that
behaviour against Apache PDFBox 3.0.7's ``PDFStreamParser.parse()`` via the
``CommentCompatTokenizeProbe`` Java oracle.

Each case is a small in-memory content stream (no binary fixture). The Java
probe carries the identical bytes keyed by case name, so a divergence can
only come from the tokenizer, never from differing input. Both sides reduce
the token list to the same canonical one-line-per-token grammar (the grammar
shared with ``TokenizeProbe``)::

    OP:<name>          operator keyword
    INT:<n>            COSInteger
    REAL:<canon>       COSFloat (canonical, locale-independent)
    NAME:/<n>          COSName
    STR:<hexbytes>     COSString (raw bytes, lower-hex)
    BOOL:true|false    COSBoolean
    NULL               COSNull
    ARRAY:<n>          COSArray header, then n element tokens
    DICT:<n>           COSDictionary header, then n key/value token pairs
"""

from __future__ import annotations

import struct
from decimal import ROUND_HALF_EVEN, Decimal

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from tests.oracle.harness import requires_oracle, run_probe_text

# Fixed bank of content streams kept byte-for-byte identical to the Java
# probe's ``caseBytes`` switch — same keys, same bytes. Plain ``str`` here is
# encoded to US-ASCII below, matching the probe's ``getBytes(US_ASCII)``.
_CASES: dict[str, str] = {
    "leading_comment": "% a leading comment\nq\n1 0 0 1 0 0 cm\nQ\n",
    "trailing_comment": "q\nQ\n% trailing comment with no newline",
    "inline_comment": "10 % comment mid-operand-run\n20 m % after operator\n",
    "comment_crlf": "% first\r\nq\r\n% second\r\nQ\r\n",
    "comment_cr_only": "% bare cr\rq\rQ\r",
    "comment_no_space": "%100%off\nq\nQ\n",
    "empty_comment": "%\n%\nq\nQ\n",
    "bx_ex_unknown": "q\nBX\n/Foo 5 fooUnknownOp\n2.5 3 anotherUnknownOp\nEX\nQ\n",
    "bx_ex_empty": "BX\nEX\n",
    "bx_ex_nested": "BX\nBX\nweirdOp\nEX\nEX\n",
    "unknown_op_bare": "1 2 totallyMadeUpOperator\n",
    "bx_ex_comment_mix": (
        "BX % begin compat\n"
        "/X 1 unknownA % an unknown op\n"
        "% standalone comment\n"
        "true unknownB\n"
        "EX % end compat\n"
    ),
}


def _float32_shortest(value: float) -> str:
    """Shortest decimal string that round-trips through IEEE-754 single
    precision — the Python equivalent of Java's ``Float.toString(float)``."""
    target = struct.unpack("f", struct.pack("f", value))[0]
    for prec in range(1, 18):
        candidate = f"{value:.{prec}g}"
        if struct.unpack("f", struct.pack("f", float(candidate)))[0] == target:
            return candidate
    return repr(value)


def _canon_float(value: float) -> str:
    """Mirror of ``CommentCompatTokenizeProbe.canonFloat`` — round the
    shortest float32 string to 5 decimals (half-even), strip trailing zeros,
    normalize ``-0`` to ``0``."""
    if value != value:  # NaN
        return "nan"
    if value == float("inf"):
        return "inf"
    if value == float("-inf"):
        return "-inf"
    bd = (
        Decimal(_float32_shortest(value))
        .quantize(Decimal("0.00001"), rounding=ROUND_HALF_EVEN)
        .normalize()
    )
    s = format(bd, "f")
    if s == "-0":
        s = "0"
    return s


def _emit_base(out: list[str], b: COSBase) -> None:
    if isinstance(b, COSInteger):
        out.append(f"INT:{b.long_value()}")
    elif isinstance(b, COSFloat):
        out.append(f"REAL:{_canon_float(b.float_value())}")
    elif isinstance(b, COSName):
        out.append(f"NAME:/{b.get_name()}")
    elif isinstance(b, COSString):
        out.append(f"STR:{b.get_bytes().hex()}")
    elif isinstance(b, COSBoolean):
        out.append(f"BOOL:{'true' if b.get_value() else 'false'}")
    elif isinstance(b, COSNull):
        out.append("NULL")
    elif isinstance(b, COSArray):
        out.append(f"ARRAY:{b.size()}")
        for i in range(b.size()):
            _emit_base(out, b.get(i))
    elif isinstance(b, COSDictionary):
        out.append(f"DICT:{b.size()}")
        for key in b.key_set():
            out.append(f"NAME:/{key.get_name()}")
            _emit_base(out, b.get_dictionary_object(key))
    else:
        out.append(f"COS:{type(b).__name__}")


def _emit(out: list[str], tok: object) -> None:
    if isinstance(tok, Operator):
        out.append(f"OP:{tok.get_name()}")
    elif isinstance(tok, COSBase):
        _emit_base(out, tok)
    else:
        out.append(f"UNKNOWN:{type(tok).__name__}")


def _render(tokens: list[object]) -> str:
    out: list[str] = []
    for tok in tokens:
        _emit(out, tok)
    return "".join(line + "\n" for line in out)


def _pypdfbox_tokens(content: str) -> str:
    data = content.encode("ascii")
    return _render(PDFStreamParser.from_bytes(data).parse())


@requires_oracle
@pytest.mark.parametrize("case", list(_CASES), ids=list(_CASES))
def test_comment_compat_tokenize_matches_pdfbox(case: str) -> None:
    # The probe carries the bytes itself (keyed by case name) so input is
    # guaranteed identical on both sides.
    java = run_probe_text("CommentCompatTokenizeProbe", case)
    py = _pypdfbox_tokens(_CASES[case])
    assert py == java, f"divergence for {case!r}:\n  java:\n{java}\n  py:\n{py}"
