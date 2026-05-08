from __future__ import annotations

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
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser


def parser(data: bytes) -> PDFStreamParser:
    return PDFStreamParser(RandomAccessReadBuffer(data))


def tokens(data: bytes) -> list[object]:
    return list(parser(data).tokens())


# ---------- basic operands + operators ----------


def test_single_operator_with_operands() -> None:
    toks = tokens(b"100 200 m")
    assert len(toks) == 3
    assert isinstance(toks[0], COSInteger) and toks[0].value == 100
    assert isinstance(toks[1], COSInteger) and toks[1].value == 200
    assert isinstance(toks[2], Operator) and toks[2].name == "m"


def test_begin_end_text_block() -> None:
    toks = tokens(b"BT /F1 12 Tf (hello) Tj ET")
    assert [type(t).__name__ for t in toks] == [
        "Operator",
        "COSName",
        "COSInteger",
        "Operator",
        "COSString",
        "Operator",
        "Operator",
    ]
    assert isinstance(toks[0], Operator) and toks[0].name == "BT"
    assert toks[1] is COSName.get_pdf_name("F1")
    assert isinstance(toks[2], COSInteger) and toks[2].value == 12
    assert isinstance(toks[3], Operator) and toks[3].name == "Tf"
    assert isinstance(toks[4], COSString) and toks[4].get_bytes() == b"hello"
    assert isinstance(toks[5], Operator) and toks[5].name == "Tj"
    assert isinstance(toks[6], Operator) and toks[6].name == "ET"


def test_numeric_and_name_operands_mixed() -> None:
    toks = tokens(b"0.5 0.5 0.5 /Pattern cs /P1 scn")
    assert isinstance(toks[0], COSFloat) and toks[0].value == 0.5
    assert isinstance(toks[3], COSName) and toks[3].get_name() == "Pattern"
    assert isinstance(toks[4], Operator) and toks[4].name == "cs"
    assert isinstance(toks[5], COSName) and toks[5].get_name() == "P1"
    assert isinstance(toks[6], Operator) and toks[6].name == "scn"


def test_literal_and_hex_string_operands() -> None:
    toks = tokens(b"(plain) Tj <48656C6C6F> Tj")
    assert isinstance(toks[0], COSString) and toks[0].get_bytes() == b"plain"
    assert isinstance(toks[1], Operator) and toks[1].name == "Tj"
    assert isinstance(toks[2], COSString) and toks[2].get_bytes() == b"Hello"
    assert isinstance(toks[3], Operator) and toks[3].name == "Tj"


def test_array_operand() -> None:
    toks = tokens(b"[(a) -2 (b)] TJ")
    assert isinstance(toks[0], COSArray)
    items = toks[0].to_list()
    assert isinstance(items[0], COSString) and items[0].get_bytes() == b"a"
    assert isinstance(items[1], COSInteger) and items[1].value == -2
    assert isinstance(items[2], COSString) and items[2].get_bytes() == b"b"
    assert isinstance(toks[1], Operator) and toks[1].name == "TJ"


def test_dict_operand() -> None:
    toks = tokens(b"<< /A 1 >> def")
    assert isinstance(toks[0], COSDictionary)
    assert toks[0].get_int("A") == 1
    assert isinstance(toks[1], Operator) and toks[1].name == "def"


def test_malformed_dictionary_stops_parsing_and_closes() -> None:
    p = parser(b"q << /A 1")
    toks = p.parse()
    assert len(toks) == 1
    assert isinstance(toks[0], Operator) and toks[0].name == "q"
    assert p.is_closed()


def test_malformed_array_stops_parsing_and_closes() -> None:
    p = parser(b"q [1 2")
    toks = p.parse()
    assert len(toks) == 1
    assert isinstance(toks[0], Operator) and toks[0].name == "q"
    assert p.is_closed()


def test_apostrophe_text_show_operator() -> None:
    toks = tokens(b"(line) '")
    assert isinstance(toks[0], COSString)
    assert isinstance(toks[1], Operator) and toks[1].name == "'"


def test_quote_text_show_operator() -> None:
    toks = tokens(b'5 10 (line) "')
    assert isinstance(toks[0], COSInteger) and toks[0].value == 5
    assert isinstance(toks[1], COSInteger) and toks[1].value == 10
    assert isinstance(toks[2], COSString)
    assert isinstance(toks[3], Operator) and toks[3].name == '"'


def test_boolean_and_null_operands() -> None:
    toks = tokens(b"true false null Tj")
    assert toks[0] is COSBoolean.TRUE
    assert toks[1] is COSBoolean.FALSE
    assert toks[2] is COSNull.NULL
    assert isinstance(toks[3], Operator) and toks[3].name == "Tj"


def test_b_star_and_f_star_operators() -> None:
    toks = tokens(b"B* f* n")
    ops = [t for t in toks if isinstance(t, Operator)]
    assert len(ops) == len(toks)
    assert [op.name for op in ops] == ["B*", "f*", "n"]


def test_d0_and_d1_type3_operators() -> None:
    toks = tokens(b"100 0 d0 100 200 0 0 800 800 d1")
    # d0 operator carries the embedded '0' digit per PDFBox readOperator quirk.
    assert any(isinstance(t, Operator) and t.name == "d0" for t in toks)
    assert any(isinstance(t, Operator) and t.name == "d1" for t in toks)


def test_uppercase_i_operator_is_not_inline_image_data() -> None:
    toks = tokens(b"I Q")
    assert len(toks) == 2
    assert isinstance(toks[0], Operator) and toks[0].name == "I"
    assert isinstance(toks[1], Operator) and toks[1].name == "Q"


def test_id_prefix_operator_is_not_inline_image_data() -> None:
    toks = tokens(b"IDx Q")
    assert len(toks) == 2
    assert isinstance(toks[0], Operator) and toks[0].name == "IDx"
    assert isinstance(toks[1], Operator) and toks[1].name == "Q"


def test_close_bracket_returns_cosnull() -> None:
    # Stray ']' becomes COSNull.NULL (matches upstream PDFBox).
    toks = tokens(b"]")
    assert toks == [COSNull.NULL]


# ---------- inline images ----------


def test_inline_image_basic() -> None:
    # Per PDFBox: when ``BI`` is parsed it consumes the parameter dict and
    # the trailing ``ID``-data block, and the resulting ``BI`` operator
    # carries both ``image_parameters`` and ``image_data`` — the
    # intermediate ``ID`` token is absorbed.
    raw = b"BI /W 10 /H 1 /BPC 8 ID\n0123456789\nEI Q"
    toks = tokens(raw)
    assert isinstance(toks[0], Operator) and toks[0].name == "BI"
    params = toks[0].image_parameters
    assert isinstance(params, COSDictionary)
    assert params.get_int("W") == 10
    assert params.get_int("H") == 1
    assert params.get_int("BPC") == 8
    # Captured bytes are everything from the byte after the ``ID``-newline
    # separator up to (but not including) the terminating ``EI``. The LF
    # immediately before ``EI`` is part of the image data.
    assert toks[0].image_data == b"0123456789\n"
    assert isinstance(toks[1], Operator) and toks[1].name == "Q"


def test_inline_image_payload_can_contain_ei_bytes() -> None:
    # 'EI' embedded in the image bytes must NOT terminate the segment;
    # the real terminator is 'EI' followed by whitespace + plausible op.
    raw = b"BI /W 5 /H 1 /BPC 8 ID\n12EI5EI Q"
    toks = tokens(raw)
    assert isinstance(toks[0], Operator) and toks[0].name == "BI"
    assert toks[0].image_data == b"12EI5"
    assert isinstance(toks[1], Operator) and toks[1].name == "Q"


def test_nested_bi_raises() -> None:
    with pytest.raises(PDFParseError):
        tokens(b"BI /W 1 BI")


# ---------- whitespace & comments ----------


def test_comments_between_tokens() -> None:
    raw = b"100 % first coord\n 200 % second\n m"
    toks = tokens(raw)
    assert len(toks) == 3
    assert isinstance(toks[0], COSInteger) and toks[0].value == 100
    assert isinstance(toks[1], COSInteger) and toks[1].value == 200
    assert isinstance(toks[2], Operator) and toks[2].name == "m"


def test_extra_whitespace_between_tokens() -> None:
    toks = tokens(b"   1\t2\r\n3   m\n")
    assert [type(t).__name__ for t in toks] == [
        "COSInteger",
        "COSInteger",
        "COSInteger",
        "Operator",
    ]


def test_empty_stream_yields_no_tokens() -> None:
    assert tokens(b"") == []
    assert tokens(b"   \n  ") == []


def test_parse_returns_full_token_list() -> None:
    p = parser(b"q 1 0 0 1 0 0 cm Q")
    out = p.parse()
    names = [t.name for t in out if isinstance(t, Operator)]
    assert names == ["q", "cm", "Q"]


def test_parse_next_token_returns_none_at_eof() -> None:
    p = parser(b"q")
    assert isinstance(p.parse_next_token(), Operator)
    assert p.parse_next_token() is None


# ---------- numeric quirks ----------


def test_isolated_plus_returns_null() -> None:
    # PDFBOX-5906 — isolated '+' yields COSNull.
    toks = tokens(b"+ Tj")
    assert toks[0] is COSNull.NULL
    assert isinstance(toks[1], Operator) and toks[1].name == "Tj"


def test_double_negative_collapses() -> None:
    # PDFBox quirk: a double negative consumes the second '-' but keeps
    # the first sign — so ``--5`` parses as ``-5`` (not ``+5``). Matches
    # Adobe Reader behaviour per the upstream comment.
    toks = tokens(b"--5 Tj")
    assert isinstance(toks[0], COSInteger) and toks[0].value == -5


def test_dash_inside_number_dropped() -> None:
    # PDFBOX-4064 — internal '-' is silently discarded.
    toks = tokens(b"1-2 Tj")
    assert isinstance(toks[0], COSInteger) and toks[0].value == 12


# ---------- alternate constructors / lifecycle ----------


def test_from_bytes_constructor_parses_same_as_buffer() -> None:
    raw = b"100 200 m"
    via_factory = PDFStreamParser.from_bytes(raw).parse()
    via_buffer = parser(raw).parse()
    assert len(via_factory) == len(via_buffer) == 3
    assert isinstance(via_factory[2], Operator) and via_factory[2].name == "m"
    assert isinstance(via_buffer[2], Operator) and via_buffer[2].name == "m"


def test_close_is_idempotent_and_marks_closed() -> None:
    p = PDFStreamParser.from_bytes(b"q Q")
    assert not p.is_closed()
    p.parse()
    p.close()
    assert p.is_closed()
    # Second close must be a no-op, not raise.
    p.close()
    assert p.is_closed()


def test_is_closed_initially_false_after_construction() -> None:
    p = parser(b"q Q")
    assert p.is_closed() is False
