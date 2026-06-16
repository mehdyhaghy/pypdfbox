"""PDFStreamParser tokenizer fuzz — wave 1574 (Agent A).

Hammers ``PDFStreamParser.parse_next_token`` over a mix of operands and
operators, malformed numbers, strings, names, inline containers, the
inline-image ``BI``/``ID``/``EI`` special case, comments and truncated input.

Every expectation here was checked branch-for-branch against the PDFBox 3.0.7
source ``pdfbox/src/main/java/org/apache/pdfbox/pdfparser/PDFStreamParser.java``
``parseNextToken`` / ``readOperator`` and ``org.apache.pdfbox.cos.COSNumber.get``
(the token-sequence semantics the live ``StreamParserFuzzProbe`` oracle pins).
"""

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
from pypdfbox.pdfparser import PDFParseError
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser


def tokens(data: bytes) -> list[object]:
    return list(PDFStreamParser.from_bytes(data).tokens())


def names(toks: list[object]) -> list[str]:
    """Project operators to their keyword string for compact assertions."""
    return [t.name for t in toks if isinstance(t, Operator)]


# ---------- operand / operator interleaving ----------


def test_cm_matrix_six_operands_one_operator() -> None:
    toks = tokens(b"1 0 0 1 100 200 cm")
    assert toks[:6] == [
        COSInteger.get(1),
        COSInteger.get(0),
        COSInteger.get(0),
        COSInteger.get(1),
        COSInteger.get(100),
        COSInteger.get(200),
    ]
    assert isinstance(toks[6], Operator) and toks[6].name == "cm"


def test_re_rectangle_operands_then_operator() -> None:
    toks = tokens(b"10 20 100 50 re f")
    assert names(toks) == ["re", "f"]
    assert toks[0] == COSInteger.get(10)


def test_number_immediately_followed_by_operator_no_space() -> None:
    # readOperator stops on a digit; the number loop stops on a letter — so a
    # bare ``5g`` tokenizes as int 5 then operator g with no separator.
    toks = tokens(b"5g")
    assert toks[0] == COSInteger.get(5)
    assert isinstance(toks[1], Operator) and toks[1].name == "g"


def test_operator_immediately_followed_by_number() -> None:
    toks = tokens(b"q1")
    assert isinstance(toks[0], Operator) and toks[0].name == "q"
    assert toks[1] == COSInteger.get(1)


def test_two_bare_operators() -> None:
    assert names(tokens(b"q Q")) == ["q", "Q"]


# ---------- numbers (int / real / lenient sign + dot handling) ----------


def test_plain_integer() -> None:
    assert tokens(b"42 g")[0] == COSInteger.get(42)


def test_leading_plus_integer_is_kept() -> None:
    # COSNumber.get strips one leading '+' via Long.parseLong.
    assert tokens(b"+3 g")[0] == COSInteger.get(3)


def test_leading_minus_integer() -> None:
    assert tokens(b"-7 g")[0] == COSInteger.get(-7)


def test_isolated_plus_becomes_null() -> None:
    # PDFBOX-5906: an isolated '+' token is ignored -> COSNull.NULL.
    toks = tokens(b"+ g")
    assert toks[0] is COSNull.NULL
    assert isinstance(toks[1], Operator) and toks[1].name == "g"


def test_lone_dot_is_zero() -> None:
    # COSNumber.get single-char '.' -> COSInteger.ZERO.
    assert tokens(b". g")[0] == COSInteger.get(0)


def test_lone_dash_is_zero() -> None:
    assert tokens(b"- g")[0] == COSInteger.get(0)


def test_leading_dot_real() -> None:
    assert tokens(b".5 g")[0] == COSFloat(".5")


def test_negative_leading_dot_real() -> None:
    assert tokens(b"-.5 g")[0] == COSFloat("-.5")


def test_trailing_dot_real() -> None:
    assert tokens(b"4. g")[0] == COSFloat("4.")


def test_real_number() -> None:
    assert tokens(b"-2.25 g")[0] == COSFloat("-2.25")


def test_double_negative_collapses() -> None:
    # Ignore double negative (consistent with Adobe Reader).
    assert tokens(b"--5 g")[0] == COSInteger.get(-5)


def test_mid_dash_dropped() -> None:
    # PDFBOX-4064: a '-' in the middle of a number is dropped, not split.
    assert tokens(b"5-3 g")[0] == COSInteger.get(53)


def test_second_dot_terminates_number() -> None:
    # The number loop only allows ONE '.', so ``1.2.3`` splits into 1.2 and .3.
    toks = tokens(b"1.2.3 g")
    assert toks[0] == COSFloat("1.2")
    assert toks[1] == COSFloat(".3")
    assert isinstance(toks[2], Operator) and toks[2].name == "g"


# ---------- literal strings ----------


def test_literal_string_simple() -> None:
    toks = tokens(b"(hello) Tj")
    assert toks[0] == COSString(b"hello")
    assert isinstance(toks[1], Operator) and toks[1].name == "Tj"


def test_literal_string_escaped_paren() -> None:
    # ``(a\)b)`` -> the escaped ')' is literal, string is "a)b".
    assert tokens(b"(a\\)b) Tj")[0] == COSString(b"a)b")


def test_literal_string_nested_parens() -> None:
    # Balanced inner parens need no escaping.
    assert tokens(b"(a(b)c) Tj")[0] == COSString(b"a(b)c")


def test_literal_string_octal_escape() -> None:
    assert tokens(b"(\\101) Tj")[0] == COSString(b"A")


# ---------- hex strings ----------


def test_hex_string_basic() -> None:
    toks = tokens(b"<48656C6C6F> Tj")
    assert toks[0] == COSString(b"Hello")
    assert isinstance(toks[1], Operator) and toks[1].name == "Tj"


def test_hex_string_odd_length_zero_padded() -> None:
    # Odd trailing nibble is implicitly padded with '0': <48656C> -> "Hel".
    assert tokens(b"<48656C> Tj")[0] == COSString(b"Hel")


def test_hex_string_internal_whitespace_ignored() -> None:
    assert tokens(b"<48 65 6C> Tj")[0] == COSString(b"Hel")


# ---------- names ----------


def test_name_operand() -> None:
    toks = tokens(b"/F1 12 Tf")
    assert toks[0] == COSName.get_pdf_name("F1")
    assert names(toks) == ["Tf"]


def test_name_hash_escape() -> None:
    # /A#20B -> the '#20' decodes to a space -> name "A B".
    assert tokens(b"/A#20B gs")[0] == COSName.get_pdf_name("A B")


def test_two_names_then_operator() -> None:
    toks = tokens(b"/Name1 /Name2 gs")
    assert toks[0] == COSName.get_pdf_name("Name1")
    assert toks[1] == COSName.get_pdf_name("Name2")
    assert names(toks) == ["gs"]


# ---------- array / dict operands ----------


def test_array_operand() -> None:
    toks = tokens(b"[1 2 3] g")
    arr = toks[0]
    assert isinstance(arr, COSArray)
    assert [e for e in arr] == [
        COSInteger.get(1),
        COSInteger.get(2),
        COSInteger.get(3),
    ]
    assert names(toks) == ["g"]


def test_array_mixed_element_types() -> None:
    toks = tokens(b"[(a) /B 3.5] TJ")
    arr = toks[0]
    assert isinstance(arr, COSArray)
    assert arr.get(0) == COSString(b"a")
    assert arr.get(1) == COSName.get_pdf_name("B")
    assert arr.get(2) == COSFloat("3.5")


def test_nested_array() -> None:
    toks = tokens(b"[[1 2][3 4]] op")
    arr = toks[0]
    assert isinstance(arr, COSArray)
    assert isinstance(arr.get(0), COSArray)
    assert isinstance(arr.get(1), COSArray)


def test_dict_operand() -> None:
    toks = tokens(b"<< /A 1 /B 2 >> BDC")
    d = toks[0]
    assert isinstance(d, COSDictionary)
    assert d.get_int("A") == 1
    assert d.get_int("B") == 2
    assert names(toks) == ["BDC"]


def test_dict_with_nested_array_value() -> None:
    toks = tokens(b"<< /A [1 2] >> op")
    d = toks[0]
    assert isinstance(d, COSDictionary)
    assert isinstance(d.get_dictionary_object("A"), COSArray)


# ---------- booleans / null ----------


def test_true_false_null_operands() -> None:
    toks = tokens(b"true false null op")
    assert toks[0] is COSBoolean.TRUE
    assert toks[1] is COSBoolean.FALSE
    assert toks[2] is COSNull.NULL
    assert names(toks) == ["op"]


# ---------- operators with special forms ----------


def test_star_operators() -> None:
    assert names(tokens(b"W* n f* B*")) == ["W*", "n", "f*", "B*"]


def test_apostrophe_and_quote_text_show_operators() -> None:
    assert names(tokens(b"(line) '")) == ["'"]
    assert names(tokens(b'0 0 (line) "')) == ['"']


def test_type3_d0_d1_operators_keep_the_digit() -> None:
    assert names(tokens(b"0 0 d0")) == ["d0"]
    assert names(tokens(b"1 1 0 0 0 0 d1")) == ["d1"]


def test_unknown_operator_token() -> None:
    # Unknown keywords are still wrapped as Operator (no validation here).
    assert names(tokens(b"foobar")) == ["foobar"]


def test_garbage_bytes_become_operators() -> None:
    # readOperator only stops on whitespace / [ < ( / % / digit, so '@' and
    # '#' are consumed as (bogus) operator keywords.
    toks = tokens(b"1 @ 2 # op")
    assert toks[0] == COSInteger.get(1)
    assert names(toks) == ["@", "#", "op"]


# ---------- comments ----------


def test_comment_midstream_is_skipped() -> None:
    toks = tokens(b"1 % a comment\n2 g")
    assert toks[0] == COSInteger.get(1)
    assert toks[1] == COSInteger.get(2)
    assert names(toks) == ["g"]


def test_comment_to_eof_is_skipped() -> None:
    toks = tokens(b"1 2 % trailing comment with no newline")
    assert toks == [COSInteger.get(1), COSInteger.get(2)]


# ---------- stray close tokens ----------


def test_stray_close_bracket_is_null() -> None:
    # ']' with no matching '[' -> COSNull.NULL (corrupt-but-continue).
    toks = tokens(b"] 1 op")
    assert toks[0] is COSNull.NULL
    assert toks[1] == COSInteger.get(1)
    assert names(toks) == ["op"]


def test_stray_close_dict_becomes_operator() -> None:
    # '>>' isn't special-cased in dispatch -> readOperator reads ">>".
    toks = tokens(b">> 1 op")
    assert names(toks) == [">>", "op"]


# ---------- inline images (BI / ID / EI delegated) ----------


def test_inline_image_basic() -> None:
    raw = b"BI /W 2 /H 2 /BPC 8 ID " + bytes([0x00, 0x11, 0x22, 0x33]) + b" EI Q"
    toks = tokens(raw)
    assert isinstance(toks[0], Operator) and toks[0].name == "BI"
    assert toks[0].image_parameters.get_int("W") == 2
    assert toks[0].image_data is not None
    assert isinstance(toks[1], Operator) and toks[1].name == "Q"


def test_inline_image_embedded_ei_not_premature_terminator() -> None:
    # An 'E' 'I' byte pair embedded in the binary payload (followed by more
    # binary, not a separator) must NOT end the segment early.
    raw = b"BI /W 8 /H 1 ID " + bytes([0x00, 0x45, 0x49, 0x00, 0x99]) + b" EI Q"
    toks = tokens(raw)
    assert isinstance(toks[0], Operator) and toks[0].name == "BI"
    assert isinstance(toks[1], Operator) and toks[1].name == "Q"


def test_bare_id_without_bi_is_inline_data_operator() -> None:
    toks = tokens(b"ID " + bytes([0x01, 0x02]) + b" EI Q")
    assert isinstance(toks[0], Operator) and toks[0].name == "ID"
    assert toks[0].image_data is not None
    assert isinstance(toks[1], Operator) and toks[1].name == "Q"


def test_id_followed_by_nonspace_is_inline_data() -> None:
    # 'ID' terminates the instant two bytes are read; 'x' is the first data byte.
    toks = tokens(b"IDx")
    assert len(toks) == 1
    assert isinstance(toks[0], Operator) and toks[0].name == "ID"


def test_nested_bi_raises() -> None:
    # PDFBOX-6038: a second BI before EI is rejected.
    with pytest.raises(PDFParseError):
        tokens(b"BI /W 1 BI /W 1 ID x EI")


# ---------- uppercase-I non-ID rejection (wave 1574 convergence) ----------


def test_uppercase_i_non_id_throws_and_closes() -> None:
    # case 'I' reads exactly two bytes; anything but "ID" closes + raises.
    parser = PDFStreamParser.from_bytes(b"Ix q")
    with pytest.raises(PDFParseError):
        parser.parse_next_token()
    assert parser.is_closed()


def test_lone_i_at_eof_throws_and_closes() -> None:
    parser = PDFStreamParser.from_bytes(b"I")
    with pytest.raises(PDFParseError):
        parser.parse_next_token()
    assert parser.is_closed()


# ---------- truncated / malformed at EOF ----------


def test_truncated_literal_string_returns_partial() -> None:
    # Unterminated '(' string yields what was gathered (lenient at EOF).
    assert tokens(b"(abc")[0] == COSString(b"abc")


def test_truncated_hex_string_raises_then_none() -> None:
    # Unterminated '<' hex string is the one hard EOF error; the dispatcher
    # surfaces it via the hex reader (no recovery).
    with pytest.raises(PDFParseError):
        tokens(b"<4865")


def test_truncated_array_returns_gathered_elements() -> None:
    # Missing ']' -> lenient: return the elements gathered so far.
    arr = tokens(b"[1 2 3")[0]
    assert isinstance(arr, COSArray)
    assert [e for e in arr] == [
        COSInteger.get(1),
        COSInteger.get(2),
        COSInteger.get(3),
    ]


def test_truncated_dict_returns_gathered_pairs() -> None:
    d = tokens(b"<< /A 1 /B 2")[0]
    assert isinstance(d, COSDictionary)
    assert d.get_int("A") == 1
    assert d.get_int("B") == 2


def test_dangling_operands_at_eof() -> None:
    # Operands with no trailing operator are simply returned as tokens.
    assert tokens(b"1 2 3") == [
        COSInteger.get(1),
        COSInteger.get(2),
        COSInteger.get(3),
    ]


def test_empty_input_yields_nothing() -> None:
    assert tokens(b"") == []


def test_only_whitespace_yields_nothing() -> None:
    assert tokens(b"   \r\n\t ") == []
