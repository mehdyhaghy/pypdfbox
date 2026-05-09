"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/pdfparser/TestBaseParser.java

Upstream targets ``COSParser.parseCOSString`` / ``parseCOSName``. We don't
ship every fixture needed by the upstream class, so:

* ``parseCOSString`` string-end recovery is executed against the ported
  ``COSParser.parse_cos_string``.
* ``parseCOSName`` tests are translated to exercise our ``BaseParser.read_name``,
  which mirrors the upstream name-parsing logic byte-for-byte.
* The PDF-fixture-driven stack-overflow test is skipped pending the fixture pass.
* The two ``COSName`` canonicalization / UTF-8 tests are executed directly
  against the COSName API, matching the upstream assertions' target.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import BaseParser, COSParser


def _parser(data: bytes) -> BaseParser:
    return BaseParser(RandomAccessReadBuffer(data))


def test_check_for_end_of_string() -> None:
    assert COSParser(RandomAccessReadBuffer(b"(Test)")).parse_cos_string().get_string() == "Test"
    assert (
        COSParser(RandomAccessReadBuffer(b"((Test)\n/ "))
        .parse_cos_string()
        .get_string()
        == "(Test"
    )
    assert (
        COSParser(RandomAccessReadBuffer(b"((Test)\r/ "))
        .parse_cos_string()
        .get_string()
        == "(Test"
    )
    assert (
        COSParser(RandomAccessReadBuffer(b"((Test)\r\n>"))
        .parse_cos_string()
        .get_string()
        == "(Test"
    )


# Upstream: testBaseParserStackOverflow — needs sample PDF
# pdfbox/src/test/resources/org/apache/pdfbox/pdfparser/PDFBOX-6041-example.pdf
@pytest.mark.skip(reason="needs fixture PDFBOX-6041-example.pdf — handle in fixture pass")
def test_base_parser_stack_overflow() -> None:
    pass


# COSName parsing tests based on examples from PDF 32000-1:2008, Table 4, §7.3.5.
# Upstream uses parseCOSName; ours uses read_name (which returns the decoded str).


def test_table4_example_name1() -> None:
    # /Name1 → "Name1"
    assert _parser(b"/Name1 ").read_name() == "Name1"


def test_table4_example_a_somewhat_longer_name() -> None:
    # /ASomewhatLongerName → "ASomewhatLongerName"
    assert _parser(b"/ASomewhatLongerName ").read_name() == "ASomewhatLongerName"


def test_table4_example_with_special_characters() -> None:
    # /A;Name_With-Various***Characters? → "A;Name_With-Various***Characters?"
    assert (
        _parser(b"/A;Name_With-Various***Characters? ").read_name()
        == "A;Name_With-Various***Characters?"
    )


def test_table4_example_numeric() -> None:
    # /1.2 → "1.2"
    assert _parser(b"/1.2 ").read_name() == "1.2"


def test_table4_example_dollar_signs() -> None:
    # /$$ → "$$"
    assert _parser(b"/$$ ").read_name() == "$$"


def test_table4_example_at_pattern() -> None:
    # /@pattern → "@pattern"
    assert _parser(b"/@pattern ").read_name() == "@pattern"


def test_table4_example_dot_notdef() -> None:
    # /#2Enotdef → ".notdef"
    assert _parser(b"/#2Enotdef ").read_name() == ".notdef"


def test_table4_example_hex_encoded_space() -> None:
    # /lime#20Green → "lime Green"
    assert _parser(b"/lime#20Green ").read_name() == "lime Green"


def test_table4_example_hex_encoded_parentheses() -> None:
    # /paired#28#29parentheses → "paired()parentheses"
    assert _parser(b"/paired#28#29parentheses ").read_name() == "paired()parentheses"


def test_table4_example_hex_encoded_number_sign() -> None:
    # /The_Key_of_F#23_Minor → "The_Key_of_F#_Minor"
    assert _parser(b"/The_Key_of_F#23_Minor ").read_name() == "The_Key_of_F#_Minor"


def test_table4_example_hex_encoded_letter() -> None:
    # /A#42 → "AB"
    assert _parser(b"/A#42 ").read_name() == "AB"


def test_table4_example_empty_name() -> None:
    # / → ""
    assert _parser(b"/ ").read_name() == ""


def test_null_character_termination() -> None:
    # /Name\0Extra parses as "Name" — null is whitespace per PDF spec.
    data = bytes([ord("/"), ord("N"), ord("a"), ord("m"), ord("e"), 0,
                  ord("E"), ord("x"), ord("t"), ord("r"), ord("a"), ord(" ")])
    assert _parser(data).read_name() == "Name"


def test_invalid_hex_sequence() -> None:
    # /Name#GG — '#' not followed by two hex digits is kept literally.
    assert _parser(b"/Name#GG ").read_name() == "Name#GG"


def test_hex_escape_lowercase() -> None:
    # /Name#2fTest (lowercase #2f = '/')
    assert _parser(b"/Name#2fTest ").read_name() == "Name/Test"


def test_hex_escape_uppercase() -> None:
    # /Name#2FTest (uppercase #2F = '/')
    assert _parser(b"/Name#2FTest ").read_name() == "Name/Test"


def test_name_termination_by_delimiters() -> None:
    # Upstream loops over '>', '<', '[', ']', '(', ')', '/', '%'.
    cases: list[tuple[bytes, str]] = [
        (b"/Name1>", "Name1"),
        (b"/Name2<", "Name2"),
        (b"/Name3[", "Name3"),
        (b"/Name4]", "Name4"),
        (b"/Name5(", "Name5"),
        (b"/Name6)", "Name6"),
        (b"/Name7/", "Name7"),
        (b"/Name8%", "Name8"),
    ]
    for data, expected in cases:
        assert _parser(data).read_name() == expected


def test_ascii_regular_characters() -> None:
    # Range of non-delimiter ASCII chars is preserved verbatim.
    assert (
        _parser(b"/!\"$'*+-._:;=@~^`|\\").read_name()
        == "!\"$'*+-._:;=@~^`|\\"
    )


def test_utf8_in_names() -> None:
    special = "中国你好!"
    name = COSName.get_pdf_name(special)

    assert name.get_name() == special
    assert name.get_bytes() == special.encode("utf-8")


def test_name_canonicalization() -> None:
    assert COSName.get_pdf_name("Test") is COSName.get_pdf_name("Test")
    assert COSName.get_pdf_name(b"Test") is COSName.get_pdf_name(bytearray(b"Test"))
    assert COSName.get_pdf_name("ä") is not COSName.get_pdf_name(b"\xe4")
