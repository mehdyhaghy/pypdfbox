"""Live PDFBox differential fuzz for PDFStreamParser token-sequence assembly.

Wave 1528. Drives ``parse_next_token`` in a loop over malformed content-stream
bytes and projects the WHOLE token sequence (operator names, operand
type/value, inline-image BI/ID/EI markers). The angle is how
``PDFStreamParser`` accumulates operands and emits ``Operator`` objects under
malformed input — distinct from the single-token escape probes and the
page-level ``TokenizeProbe``.
"""

from __future__ import annotations

import hashlib

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
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from tests.oracle.harness import requires_oracle, run_probe_text


def _b(s: str) -> bytes:
    return s.encode("latin-1")


def _bytes(*vals: int) -> bytes:
    return bytes(vals)


def _long_run() -> bytes:
    return _b("".join(f"{i} " for i in range(200)) + "op")


_CASES: list[tuple[str, bytes]] = [
    ("empty", _b("")),
    ("only_ws", _b("   \r\n\t ")),
    ("op_no_operands", _b("Q")),
    ("two_bare_ops", _b("q Q")),
    ("dangling_operands_eof", _b("1 2 3")),
    ("operands_then_op", _b("1 0 0 1 0 0 cm")),
    ("trailing_operand_no_op", _b("BT /F1 12 Tf 1 2")),
    ("unbalanced_array_open", _b("[1 2 3")),
    ("balanced_array", _b("[1 2 3] 4 d0")),
    ("nested_array", _b("[[1 2][3 4]] op")),
    ("unbalanced_dict_open", _b("<< /A 1 /B 2")),
    ("balanced_dict_operand", _b("<< /A 1 >> op")),
    ("nested_dict_array", _b("[<< /A [1 2] >> 3] op")),
    ("stray_close_bracket", _b("] 1 2 op")),
    ("stray_close_dict", _b(">> 1 op")),
    ("comment_midstream", _b("1 % comment here\n2 op")),
    ("comment_no_eol", _b("1 2 % trailing comment")),
    ("garbage_between", _b("1 @ 2 # op")),
    ("name_operand", _b("/Name1 /Name2#41 op")),
    ("malformed_name_hash", _b("/Bad#G op")),
    ("double_negative", _b("--5 op")),
    ("mid_dash", _b("5-3 op")),
    ("lone_plus", _b("+ op")),
    ("lone_dot", _b(". op")),
    ("lone_dash", _b("- op")),
    ("real_numbers", _b("1.5 -2.25 .5 3. op")),
    ("string_operand", _b("(hello) Tj")),
    ("hex_string_operand", _b("<48656c6c6f> Tj")),
    ("bool_null_operands", _b("true false null op")),
    ("apostrophe_op", _b("(line) '")),
    ("quote_op", _b('0 0 (line) "')),
    ("star_op", _b("W* n f* B*")),
    ("d0_d1_op", _b("0 0 d0 1 1 0 0 0 0 d1")),
    ("long_operand_run", _long_run()),
    (
        "bi_id_ei_basic",
        _b("BI /W 2 /H 2 /BPC 8 /CS /G ID ") + _bytes(0x00, 0x11, 0x22, 0x33) + _b(" EI Q"),
    ),
    ("bi_no_ei", _b("BI /W 2 /H 2 ID ") + _bytes(0xAA, 0xBB, 0xCC, 0xDD, 0xEE)),
    (
        "bi_embedded_ei",
        _b("BI /W 8 /H 1 ID ") + _bytes(0x00, ord("E"), ord("I"), 0x00, 0x99) + _b(" EI Q"),
    ),
    ("bi_truncated_after_id", _b("BI /W 2 /H 2 ID")),
    ("bi_no_dict", _b("BI ID ") + _bytes(0x01, 0x02) + _b(" EI")),
    ("bi_nested", _b("BI /W 1 ID x EI BI /W 1 ID y EI")),
    ("id_no_bi", _b("ID ") + _bytes(0x01, 0x02) + _b(" EI Q")),
    ("ei_alone", _b("EI Q")),
    ("bi_malformed_dict_value", _b("BI /W /H ID xy EI")),
]


def _canon_float(value: float) -> str:
    if value != value:
        return "nan"
    if value in (float("inf"), float("-inf")):
        return "inf" if value > 0 else "-inf"
    from decimal import ROUND_HALF_EVEN, Decimal

    bd = Decimal(repr(float(value))).quantize(Decimal("1.00000"), rounding=ROUND_HALF_EVEN)
    s = format(bd.normalize(), "f")
    if s == "-0":
        s = "0"
    return s


def _emit_base(lines: list[str], b: object) -> None:
    if isinstance(b, COSInteger):
        lines.append(f"INT:{b.long_value()}")
    elif isinstance(b, COSFloat):
        lines.append(f"REAL:{_canon_float(b.float_value())}")
    elif isinstance(b, COSName):
        lines.append(f"NAME:/{b.get_name()}")
    elif isinstance(b, COSString):
        lines.append(f"STR:{b.get_bytes().hex()}")
    elif isinstance(b, COSBoolean):
        lines.append(f"BOOL:{'true' if b.get_value() else 'false'}")
    elif isinstance(b, COSNull):
        lines.append("NULL")
    elif isinstance(b, COSArray):
        lines.append(f"ARRAY:{len(b)}")
        for item in b:
            _emit_base(lines, item)
    elif isinstance(b, COSDictionary):
        lines.append(f"DICT:{len(b)}")
        for key in b.key_set():
            lines.append(f"NAME:/{key.get_name()}")
            _emit_base(lines, b.get_dictionary_object(key))
    else:
        lines.append(f"COS:{type(b).__name__}")


def _emit(lines: list[str], tok: object) -> None:
    if isinstance(tok, Operator):
        lines.append(f"OP:{tok.get_name()}")
        if tok.get_image_data() is not None:
            d = tok.get_image_data()
            sha = hashlib.sha1(d).hexdigest()
            lines.append(f"IMG:{len(d)}:{sha}")
    else:
        _emit_base(lines, tok)


def _py_dump() -> str:
    lines: list[str] = []
    for name, data in _CASES:
        lines.append(f"CASE {name}")
        parser = PDFStreamParser.from_bytes(data)
        err = False
        try:
            while True:
                tok = parser.parse_next_token()
                if tok is None:
                    break
                _emit(lines, tok)
        except Exception:
            err = True
        finally:
            parser.close()
        lines.append(f"END {name} {'err' if err else 'ok'}")
    return "".join(line + "\n" for line in lines)


@requires_oracle
def test_stream_parser_fuzz_matches_pdfbox() -> None:
    assert _py_dump() == run_probe_text("StreamParserFuzzProbe")
