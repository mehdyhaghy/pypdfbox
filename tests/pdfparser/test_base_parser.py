from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import BaseParser, PDFParseError


def parser(data: bytes) -> BaseParser:
    return BaseParser(RandomAccessReadBuffer(data))


# ---------- character classification ----------


def test_is_whitespace_covers_all_pdf_whitespace_bytes() -> None:
    for b in (0x00, 0x09, 0x0A, 0x0C, 0x0D, 0x20):
        assert BaseParser.is_whitespace(b)
    for b in (0x01, 0x40, 0x7F):
        assert not BaseParser.is_whitespace(b)


def test_is_eol_only_lf_and_cr() -> None:
    assert BaseParser.is_eol(0x0A)
    assert BaseParser.is_eol(0x0D)
    assert not BaseParser.is_eol(0x20)


def test_is_delimiter_covers_pdf_delimiter_set() -> None:
    for ch in b"()<>[]{}/%":
        assert BaseParser.is_delimiter(ch)
    assert not BaseParser.is_delimiter(ord("A"))


def test_is_digit_and_hex_digit() -> None:
    for ch in b"0123456789":
        assert BaseParser.is_digit(ch)
        assert BaseParser.is_hex_digit(ch)
    for ch in b"abcdefABCDEF":
        assert not BaseParser.is_digit(ch)
        assert BaseParser.is_hex_digit(ch)
    assert not BaseParser.is_hex_digit(ord("g"))


def test_is_regular_excludes_whitespace_and_delimiters() -> None:
    assert BaseParser.is_regular(ord("A"))
    assert not BaseParser.is_regular(0x20)
    assert not BaseParser.is_regular(ord("("))
    assert not BaseParser.is_regular(-1)


# ---------- low-level byte ops ----------


def test_read_byte_and_position_advances() -> None:
    p = parser(b"abc")
    assert p.read_byte() == ord("a")
    assert p.position == 1
    assert p.peek_byte() == ord("b")
    assert p.position == 1
    assert p.read_byte() == ord("b")
    assert p.read_byte() == ord("c")
    assert p.read_byte() == -1


def test_unread_byte_steps_back() -> None:
    p = parser(b"ab")
    p.read_byte()
    p.unread_byte()
    assert p.read_byte() == ord("a")


def test_require_byte_raises_at_eof() -> None:
    p = parser(b"")
    with pytest.raises(PDFParseError):
        p.require_byte()


# ---------- whitespace / comments / EOL ----------


def test_skip_whitespace_simple() -> None:
    p = parser(b"   \t\n abc")
    p.skip_whitespace()
    assert p.read_byte() == ord("a")


def test_skip_whitespace_skips_comments() -> None:
    p = parser(b"  % comment to EOL\nrest")
    p.skip_whitespace()
    assert p.read_byte() == ord("r")


def test_skip_whitespace_consumes_crlf_after_comment() -> None:
    p = parser(b"% comment\r\nrest")
    p.skip_whitespace()
    assert p.read_byte() == ord("r")


def test_skip_whitespace_at_eof_is_noop() -> None:
    p = parser(b"   ")
    p.skip_whitespace()
    assert p.is_eof()


def test_skip_eol_handles_cr_lf_crlf() -> None:
    for marker, after in [(b"\r", 1), (b"\n", 1), (b"\r\n", 2)]:
        p = parser(marker + b"x")
        p.skip_eol()
        assert p.position == after
        assert p.read_byte() == ord("x")


def test_read_until_eol() -> None:
    p = parser(b"hello\nworld")
    assert p.read_until_eol() == b"hello"
    p.skip_eol()
    assert p.read_until_eol() == b"world"


# ---------- numbers ----------


def test_read_int_basic() -> None:
    assert parser(b"123").read_int() == 123
    assert parser(b"+42").read_int() == 42
    assert parser(b"-7 rest").read_int() == -7


def test_read_int_stops_at_non_digit() -> None:
    p = parser(b"123abc")
    assert p.read_int() == 123
    assert p.read_byte() == ord("a")


def test_read_int_invalid_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"abc").read_int()
    with pytest.raises(PDFParseError):
        parser(b"+").read_int()


def test_read_number_int_form() -> None:
    assert parser(b"42").read_number() == 42
    assert parser(b"-7").read_number() == -7
    assert isinstance(parser(b"42").read_number(), int)


def test_read_number_real_form() -> None:
    assert parser(b"1.5").read_number() == 1.5
    assert parser(b"-0.25").read_number() == -0.25
    # Trailing decimal point per spec.
    assert parser(b"3.").read_number() == 3.0
    # Leading decimal point per spec.
    assert parser(b".5").read_number() == 0.5


def test_read_number_lone_dot_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b".").read_number()


def test_read_number_stops_at_delimiter() -> None:
    p = parser(b"1.5/Foo")
    assert p.read_number() == 1.5
    assert p.read_byte() == ord("/")


# ---------- names ----------


def test_read_name_basic() -> None:
    p = parser(b"/Type")
    assert p.read_name() == "Type"


def test_read_name_terminates_at_whitespace_or_delimiter() -> None:
    p = parser(b"/Pages /Kids")
    assert p.read_name() == "Pages"
    p.skip_whitespace()
    assert p.read_name() == "Kids"


def test_read_name_hex_escape() -> None:
    p = parser(b"/Name#20with#20spaces")
    assert p.read_name() == "Name with spaces"


def test_read_name_utf8_via_hex_escapes() -> None:
    # /naïve → /na#C3#AFve  (PDF 1.2+ encodes name bytes as UTF-8)
    p = parser(b"/na#C3#AFve")
    assert p.read_name() == "naïve"


def test_read_name_invalid_hex_escape_keeps_hash_literally() -> None:
    # Match upstream PDFBox: a '#' not followed by two hex digits is kept
    # literally rather than raising.
    assert parser(b"/Bad#ZZ ").read_name() == "Bad#ZZ"


def test_read_name_missing_slash_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"NotAName").read_name()


def test_read_name_empty_after_slash_returns_empty_string() -> None:
    p = parser(b"/ rest")
    assert p.read_name() == ""


# ---------- literal strings ----------


def test_literal_string_simple() -> None:
    p = parser(b"(hello)")
    assert p.read_literal_string() == b"hello"


def test_literal_string_empty() -> None:
    assert parser(b"()").read_literal_string() == b""


def test_literal_string_balanced_parens() -> None:
    p = parser(b"(this (is (nested)) ok)")
    assert p.read_literal_string() == b"this (is (nested)) ok"


def test_literal_string_basic_escapes() -> None:
    p = parser(b"(line1\\nline2\\tend)")
    assert p.read_literal_string() == b"line1\nline2\tend"


def test_literal_string_paren_and_backslash_escapes() -> None:
    p = parser(b"(a\\(b\\)c\\\\d)")
    assert p.read_literal_string() == b"a(b)c\\d"


def test_literal_string_octal_escapes() -> None:
    # \101 = 0x41 = 'A', \12 = 0x0A = LF, \7 = 0x07
    p = parser(b"(\\101\\12\\7)")
    assert p.read_literal_string() == b"A\n\x07"


def test_literal_string_octal_overflow_truncates_to_byte() -> None:
    # \777 = 0o777 = 511; truncated to byte = 0xFF
    p = parser(b"(\\777)")
    assert p.read_literal_string() == b"\xff"


def test_literal_string_eol_normalization() -> None:
    p = parser(b"(line1\r\nline2\rline3\nline4)")
    assert p.read_literal_string() == b"line1\nline2\nline3\nline4"


def test_literal_string_line_continuation_with_backslash_eol() -> None:
    p = parser(b"(joined\\\nstring)")
    assert p.read_literal_string() == b"joinedstring"


def test_literal_string_unknown_escape_drops_backslash() -> None:
    p = parser(b"(\\zfoo)")
    assert p.read_literal_string() == b"zfoo"


def test_literal_string_unterminated_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"(unterminated").read_literal_string()


def test_literal_string_missing_open_paren_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"hello)").read_literal_string()


# ---------- hex strings ----------


def test_hex_string_basic() -> None:
    p = parser(b"<48656C6C6F>")
    assert p.read_hex_string() == b"Hello"


def test_hex_string_lowercase_and_mixed() -> None:
    p = parser(b"<deadBEEF>")
    assert p.read_hex_string() == b"\xde\xad\xbe\xef"


def test_hex_string_ignores_whitespace() -> None:
    p = parser(b"<48 65\n6C\t6C 6F>")
    assert p.read_hex_string() == b"Hello"


def test_hex_string_odd_digit_padded_with_zero() -> None:
    # Per ISO 32000-1 §7.3.4.3: trailing odd digit is padded with '0'.
    assert parser(b"<4>").read_hex_string() == b"\x40"


def test_hex_string_empty() -> None:
    assert parser(b"<>").read_hex_string() == b""


def test_hex_string_invalid_digit_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"<4G>").read_hex_string()


def test_hex_string_unterminated_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"<4848").read_hex_string()


def test_hex_string_missing_open_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"4848>").read_hex_string()


# ---------- keywords ----------


def test_read_keyword_basic() -> None:
    assert parser(b"true").read_keyword() == b"true"
    assert parser(b"false rest").read_keyword() == b"false"


def test_read_keyword_terminates_at_non_alpha() -> None:
    p = parser(b"obj 7")
    assert p.read_keyword() == b"obj"
    p.skip_whitespace()
    assert p.read_int() == 7


def test_wave330_read_keyword_keeps_regular_suffix_inside_token() -> None:
    p = parser(b"true1 /Next")
    assert p.read_keyword() == b"true1"
    p.skip_whitespace()
    assert p.read_name() == "Next"


def test_read_keyword_at_eof_raises_on_empty() -> None:
    with pytest.raises(PDFParseError):
        parser(b"").read_keyword()
    with pytest.raises(PDFParseError):
        parser(b"123").read_keyword()


def test_read_expected_match() -> None:
    p = parser(b"%PDF-1.7")
    p.read_expected(b"%PDF-")
    assert p.read_byte() == ord("1")


def test_read_expected_mismatch_raises() -> None:
    p = parser(b"%PSF-1.7")
    with pytest.raises(PDFParseError):
        p.read_expected(b"%PDF-")
