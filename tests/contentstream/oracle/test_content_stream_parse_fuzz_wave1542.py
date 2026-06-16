"""Differential CONTENT-STREAM tokenizer fuzz vs Apache PDFBox 3.0.7
(wave 1542).

Pushes ``PDFStreamParser`` (the operand/operator tokenizer) over ~70
malformed / edge-case content-stream byte blobs and compares the full token
sequence against Apache PDFBox's ``PDFStreamParser.parseNextToken()`` loop via
the ``ContentStreamParseFuzzProbe`` Java oracle. Complements the existing
``TokenizeProbe`` (clean page streams), ``ParseEdgeTokenProbe`` (scalar parse
paths) and ``CommentCompatTokenizeProbe`` (comment / BX-EX) coverage by
hammering the *lenient-recovery corners*:

* numbers — leading ``+`` / ``-``, double-minus, multiple dots, just-a-dot,
  just-a-minus, just-a-plus, mid-number ``-``, exponent ``1e3``, dot-lead,
  trailing dot, 23-digit huge ints, huge reals.
* names — ``#``-hex escapes (valid / truncated 1-digit / truncated 0-digit /
  non-hex / lowercase / ``#00`` null escape), empty name.
* literal strings — nested parens, unbalanced open / close, octal escapes
  (long + short), backslash line-continuation, unknown escape, trailing
  backslash at EOF, EOF before close.
* hex strings — odd length, embedded whitespace, embedded non-hex, empty,
  EOF before close.
* arrays / dicts — unterminated at EOF, nested, mixed-type elements, an
  indirect-reference triple ``[1 0 R]`` (no bound document), corrupt
  mid-element.
* operator/operand adjacency with no whitespace, comments mid-token, null
  bytes as separators / leaders, true / false / null keyword disambiguation,
  stray ``]`` / ``>``, mid-token truncation, the Type 3 ``d0`` / ``d1`` glyph
  operators, and the apostrophe / quote text-show operators.

Each blob is written to a temp file handed BYTE-IDENTICALLY to both the Java
probe and pypdfbox, so any divergence is purely tokenizer behaviour. Both
sides reduce every token to the same one-line tag grammar (mirroring
``ContentStreamParseFuzzProbe.tag``)::

    int(<decimal>)
    real(<float32-bits-hex>)        raw IEEE-754 bits, exact + locale-free
    name(/Foo)
    str(<hex-of-bytes>)
    bool(true|false)
    null
    op(<operator>)                  ID/BI carry image data on the next line
    imgdata(<len>:<hex>)
    array[...]                      nested tags joined by ','
    dict{/K->tag,...}               keys sorted
    ref(<num> <gen>)                unresolved COSObject (indirect ref)
    ERR:<name>                      parse threw; final line

Honest divergence (pinned, not silenced): PDFBox raises ``IOException`` where
pypdfbox raises ``PDFParseError`` (the project's documented IOException
analogue, CLAUDE.md test-porting table). The probe emits ``ERR:IOException``
and pypdfbox emits ``ERR:PDFParseError``; both are normalised to ``ERR`` for
the comparison so the *fact of a parse failure* is compared, not the Java
class name. Wave 1542 fixed a real tokenizer bug here: the content-stream
array/dict parsers previously used the strict document-loader recovery
(raising on a missing ``]`` / a stray operator-in-array and emitting
``COSObject`` indirect references) instead of delegating to
``BaseParser.parseCOSArray`` / ``parseCOSDictionary`` the way Java's
``PDFStreamParser`` does. The four cases ``[1 0 R]``, ``[1 2 3 q``,
``<< /A 1 /B 2 q`` and ``[1 R 2]`` now match byte-for-byte.
"""

from __future__ import annotations

import struct
from pathlib import Path

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
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------------------------------------------------------------------------
# Deterministic fuzz corpus: (name, raw content-stream bytes). Every blob ends
# with a trailing ``q`` operator (where it parses cleanly) so the test also
# observes whether the tokenizer recovers and keeps tokenizing past the fault.
# ---------------------------------------------------------------------------
_CORPUS: dict[str, bytes] = {
    # -- numbers ----------------------------------------------------------
    "num_plain_int": b"123 q",
    "num_leading_plus": b"+5 q",
    "num_leading_minus": b"-5 q",
    "num_double_minus": b"--5 q",
    "num_multi_dot": b"1.2.3 q",
    "num_just_dot": b". q",
    "num_just_minus": b"- q",
    "num_just_plus": b"+ q",
    "num_minus_mid": b"34-5 q",
    "num_exponent": b"1e3 q",
    "num_dot_lead": b".5 q",
    "num_trailing_dot": b"5. q",
    "num_huge": b"99999999999999999999999 q",
    "num_huge_neg": b"-99999999999999999999999 q",
    "num_huge_real": b"123456789012345.6789 q",
    "num_plus_dot": b"+.5 q",
    "num_minus_dot": b"-.5 q",
    # -- names + #-escapes ------------------------------------------------
    "name_simple": b"/Foo q",
    "name_hex_ok": b"/A#42B q",
    "name_hex_trunc1": b"/AB#4",
    "name_hex_trunc0": b"/AB#",
    "name_hex_nonhex": b"/A#GB q",
    "name_hex_lower": b"/x#6a q",
    "name_empty": b"/ q",
    "name_null_escape": b"/A#00B q",
    # -- literal strings --------------------------------------------------
    "str_simple": b"(hello) q",
    "str_nested": b"(a(b)c) q",
    "str_unbalanced_open": b"(a(b q",
    "str_unbalanced_close": b"(a)b) q",
    "str_octal": b"(\\101\\102) q",
    "str_octal_short": b"(\\1) q",
    "str_line_cont": b"(a\\\nb) q",
    "str_unknown_escape": b"(\\q) q",
    "str_trailing_backslash": b"(abc\\",
    "str_eof_open": b"(no close",
    # -- hex strings ------------------------------------------------------
    "hex_simple": b"<48656c6c6f> q",
    "hex_odd": b"<abc> q",
    "hex_ws": b"<48 65 6c> q",
    "hex_nonhex": b"<48zz65> q",
    "hex_empty": b"<> q",
    "hex_eof": b"<4865",
    # -- arrays / dicts ---------------------------------------------------
    "arr_simple": b"[1 2 3] q",
    "arr_unterminated": b"[1 2 3 q",
    "arr_nested": b"[1 [2 3] 4] q",
    "arr_mixed": b"[/A (b) 3 <04>] q",
    "dict_simple": b"<</A 1 /B 2>> q",
    "dict_unterminated": b"<</A 1 /B 2 q",
    "dict_nested": b"<</A <</B 2>>>> q",
    "arr_ref": b"[1 0 R] q",
    "arr_ref_mid": b"[1 R 2] q",
    # -- operator/operand adjacency (no whitespace) -----------------------
    "op_no_ws": b"1 2re",
    "name_op_adjacent": b"/Foo Do",
    "num_op_adjacent": b"5Tj",
    "str_op_adjacent": b"(x)Tj",
    "bracket_op": b"[1]TJ",
    # -- comments ---------------------------------------------------------
    "comment_mid": b"12 % comment\n34 q",
    "comment_in_op": b"q%c\nQ",
    "comment_eof": b"12 %trailing",
    # -- null bytes / control ---------------------------------------------
    "nullbyte_sep": b"12\x0034 q",
    "nullbyte_lead": b"\x00 q",
    # -- keywords ---------------------------------------------------------
    "kw_true": b"true q",
    "kw_false": b"false q",
    "kw_null": b"null q",
    "kw_truex": b"trueX q",
    # -- stray close delimiters -------------------------------------------
    "stray_close_bracket": b"] q",
    "stray_gt": b"> q",
    # -- truncation mid-token ---------------------------------------------
    "trunc_mid_name": b"12 /Fo",
    "trunc_mid_op": b"12 BT 34 T",
    # -- Type 3 d0 / d1 glyph quirk ---------------------------------------
    "type3_d0": b"0 0 d0",
    "type3_d1": b"0 0 10 0 0 10 d1",
    # -- apostrophe / quote text-show -------------------------------------
    "apostrophe": b"(x)'",
    "quote": b"1 2 (x)\"",
    # -- star operators ---------------------------------------------------
    "op_star": b"f*",
    "op_b_star": b"B*",
}


# ---------------------------------------------------------------------------
# pypdfbox side: reproduce ContentStreamParseFuzzProbe.tag exactly.
# ---------------------------------------------------------------------------
def _real_bits(value: float) -> str:
    """Raw IEEE-754 single-precision bits as lower-hex — the Python mirror of
    Java's ``Integer.toHexString(Float.floatToIntBits(f))`` (no leading
    zeros, exact, locale-free)."""
    return format(struct.unpack("<I", struct.pack("<f", value))[0], "x")


def _cos_tag(b: COSBase | None) -> str:
    if b is None or isinstance(b, COSNull):
        return "null"
    if isinstance(b, COSObject):
        return f"ref({b.get_object_number()} {b.get_generation_number()})"
    if isinstance(b, COSBoolean):
        return f"bool({'true' if b.get_value() else 'false'})"
    if isinstance(b, COSInteger):
        return f"int({b.long_value()})"
    if isinstance(b, COSFloat):
        return f"real({_real_bits(b.float_value())})"
    if isinstance(b, COSName):
        return f"name(/{b.get_name()})"
    if isinstance(b, COSString):
        return f"str({b.get_bytes().hex()})"
    if isinstance(b, COSArray):
        return "array[" + ",".join(_cos_tag(b.get(i)) for i in range(b.size())) + "]"
    if isinstance(b, COSDictionary):
        keys = sorted(b.key_set(), key=lambda k: k.get_name())
        return (
            "dict{"
            + ",".join(f"/{k.get_name()}->{_cos_tag(b.get_item(k))}" for k in keys)
            + "}"
        )
    return f"unknown({type(b).__name__})"


def _tag(tok: object) -> str:
    if isinstance(tok, Operator):
        s = f"op({tok.get_name()})"
        img = tok.get_image_data()
        if img is not None:
            s += f"\nimgdata({len(img)}:{img.hex()})"
        return s
    return _cos_tag(tok)


def _pypdfbox_dump(data: bytes) -> str:
    parser = PDFStreamParser.from_bytes(data)
    out: list[str] = []
    try:
        while True:
            tok = parser.parse_next_token()
            if tok is None:
                break
            out.append(_tag(tok))
    except Exception as exc:  # noqa: BLE001 - parse error is a comparable observation
        out.append(f"ERR:{type(exc).__name__}")
    return "".join(line + "\n" for line in out)


def _normalize_err(text: str) -> str:
    """Collapse ``ERR:<class>`` to bare ``ERR`` on both sides. PDFBox raises
    ``IOException`` where pypdfbox raises ``PDFParseError`` (the documented
    IOException analogue) — the *fact* of a parse failure is the comparable
    behaviour, not the language-specific exception class name."""
    return "".join(
        ("ERR" if line.startswith("ERR:") else line) + "\n"
        for line in text.splitlines()
    )


# ---------------------------------------------------------------------------
# Live differential parity: every blob must tokenize identically on both sides.
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.parametrize("case", list(_CORPUS), ids=list(_CORPUS))
def test_content_stream_parse_fuzz_matches_pdfbox(case: str, tmp_path: Path) -> None:
    blob = _CORPUS[case]
    blob_file = tmp_path / f"{case}.bin"
    blob_file.write_bytes(blob)
    java = _normalize_err(run_probe_text("ContentStreamParseFuzzProbe", str(blob_file)))
    py = _normalize_err(_pypdfbox_dump(blob))
    assert py == java, f"divergence on {case!r}:\n java={java!r}\n  py={py!r}"


# ---------------------------------------------------------------------------
# Value-pinned regressions (run without the oracle): the wave-1542 fixes to
# content-stream array/dict recovery, pinned to the PDFBox-3.0.7-derived
# expected tags so the contract is enforced on every machine, oracle or not.
# ---------------------------------------------------------------------------
_PINNED: dict[str, str] = {
    # Indirect-reference triple with no bound document: BaseParser folds
    # ``1 0 R`` into an object key, get_object_from_pool raises (no document),
    # PDFStreamParser discards the whole array token -> no output at all.
    "arr_ref": "",
    # Unterminated array recovers the partial array; the stray operator ``q``
    # is skipped as a corrupt element (NOT appended as a null), then EOF.
    "arr_unterminated": "array[int(1),int(2),int(3)]\n",
    # Unterminated dict recovers the partial dict; ``q`` triggers
    # read_until_end_of_cos_dictionary recovery, then EOF.
    "dict_unterminated": "dict{/A->int(1),/B->int(2)}\n",
    # ``R`` mid-array (only one preceding int) is a corrupt element -> skipped;
    # the array recovers to [1 2] and ``q`` follows.
    "arr_ref_mid": "array[int(1),int(2)]\nop(q)\n",
    # ``<< /A`` (final key with no value): partial recovery -> empty dict.
    "dict_key_no_value": "dict{}\n",
}


@pytest.mark.parametrize("case", list(_PINNED), ids=list(_PINNED))
def test_content_stream_array_dict_recovery_pinned(case: str) -> None:
    blobs = dict(_CORPUS)
    blobs["dict_key_no_value"] = b"<< /A"
    assert _pypdfbox_dump(blobs[case]) == _PINNED[case]
