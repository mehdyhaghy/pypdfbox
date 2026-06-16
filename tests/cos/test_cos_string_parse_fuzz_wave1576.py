"""Wave 1576 — COSString literal/hex parse + serialization + text-decode fuzz.

Hammers ``BaseParser.read_literal_string`` / ``read_hex_string`` /
``parse_cos_string`` and ``COSString.parse_hex`` / ``get_string`` /
``to_hex_string`` against PDFBox 3.0.7 behaviour:

* every literal-string escape (``\\n \\r \\t \\b \\f \\( \\) \\\\``),
* octal ``\\ddd`` (1-3 digits, value mod 256), octal-digit boundaries,
* line continuation ``\\<EOL>`` (LF / CR / CRLF) → backslash+EOL dropped,
* bare CR / LF / CRLF inside a literal kept **verbatim** (PDFBox does NOT
  apply the ISO 32000-1 §7.3.4.2 EOL→LF normalization — verified by the
  live oracle, see ``read_literal_string`` comment),
* balanced nested parens, unknown escape (backslash dropped),
* hex string whitespace skipping, odd-nibble trailing-zero padding,
* empty ``()`` and ``<>``,
* text-string BOM detection (UTF-16BE / UTF-16LE) vs PDFDocEncoding,
* ``to_hex_string`` output and ``COSString.parse_hex`` internal-whitespace
  strictness + FORCE_PARSING substitution.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_string import COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import BaseParser, PDFParseError


def _parser(data: bytes) -> BaseParser:
    return BaseParser(RandomAccessReadBuffer(data))


def _lit(body: bytes) -> bytes:
    """Parse a literal string given its full ``(...)`` byte form."""
    return _parser(body).read_literal_string()


# ---------- single-char escape sequences ----------


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        (rb"(\n)", b"\n"),
        (rb"(\r)", b"\r"),
        (rb"(\t)", b"\t"),
        (rb"(\b)", b"\b"),
        (rb"(\f)", b"\f"),
        (rb"(\()", b"("),
        (rb"(\))", b")"),
        (rb"(\\)", b"\\"),
    ],
    ids=["n", "r", "t", "b", "f", "lparen", "rparen", "backslash"],
)
def test_named_escapes(src: bytes, expected: bytes) -> None:
    assert _lit(src) == expected


def test_all_named_escapes_in_one_string() -> None:
    assert _lit(rb"(\n\r\t\b\f\(\)\\)") == b"\n\r\t\b\f()\\"


# ---------- octal escapes ----------


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        (rb"(\101)", b"A"),  # 0o101 = 65 = 'A'
        (rb"(\0)", b"\x00"),  # 1-digit
        (rb"(\40)", b" "),  # 2-digit -> 0o40 = 32 = space
        (rb"(\101B)", b"AB"),  # 3-digit then literal 'B'
        (rb"(\1011)", b"A1"),  # only 3 octal digits consumed, '1' literal
        (rb"(\7)", b"\x07"),
        (rb"(\377)", b"\xff"),  # 255, max in one byte
    ],
    ids=["A", "nul", "space", "A_then_B", "A_then_1", "bell", "0xFF"],
)
def test_octal_escapes(src: bytes, expected: bytes) -> None:
    assert _lit(src) == expected


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        (rb"(\400)", b"\x00"),  # 0o400 = 256 -> &0xFF = 0
        (rb"(\401)", b"\x01"),  # 257 -> 1
        (rb"(\777)", b"\xff"),  # 511 -> 255
    ],
    ids=["256", "257", "511"],
)
def test_octal_overflow_is_masked_mod_256(src: bytes, expected: bytes) -> None:
    # PDFBox masks the parsed octal value with &0xFF; \400 wraps to NUL.
    assert _lit(src) == expected


def test_octal_stops_at_non_octal_digit() -> None:
    # '8' and '9' are not octal digits, so \18 is octal \1 then literal '8'.
    assert _lit(rb"(\18)") == b"\x018"
    assert _lit(rb"(\19)") == b"\x019"


# ---------- line continuation ----------


def test_line_continuation_lf() -> None:
    assert _lit(b"(a\\\nb)") == b"ab"


def test_line_continuation_cr() -> None:
    assert _lit(b"(a\\\rb)") == b"ab"


def test_line_continuation_crlf() -> None:
    assert _lit(b"(a\\\r\nb)") == b"ab"


def test_trailing_backslash_before_close_is_lenient() -> None:
    # A lone trailing backslash at EOF: PDFBox emits the 0xFF EOF sentinel
    # byte, then returns what it has.
    assert _lit(b"(a\\") == b"a\xff"


# ---------- bare EOL bytes (NOT normalized by PDFBox) ----------


def test_bare_cr_kept_verbatim() -> None:
    assert _lit(b"(a\rb)") == b"a\rb"


def test_bare_lf_kept_verbatim() -> None:
    assert _lit(b"(a\nb)") == b"a\nb"


def test_bare_crlf_kept_verbatim() -> None:
    assert _lit(b"(a\r\nb)") == b"a\r\nb"


def test_mixed_eol_bytes_kept_verbatim() -> None:
    # Mirrors the canonical upstream oracle case: no EOL normalization.
    assert _lit(b"(line1\r\nline2\rline3\nline4)") == b"line1\r\nline2\rline3\nline4"


# ---------- balanced / nested parens ----------


def test_balanced_nested_parens() -> None:
    assert _lit(b"(a(b)c)") == b"a(b)c"


def test_deeply_nested_parens() -> None:
    assert _lit(b"(a(b(c)d)e)") == b"a(b(c)d)e"


def test_escaped_unbalanced_parens() -> None:
    assert _lit(rb"(a\(b)") == b"a(b"
    assert _lit(rb"(a\)b)") == b"a)b"


def test_empty_literal() -> None:
    assert _lit(b"()") == b""


def test_unterminated_literal_returns_partial_at_eof() -> None:
    # PDFBox's lenient loop returns the bytes accumulated so far at EOF.
    assert _lit(b"(abc") == b"abc"


# ---------- unknown escape: backslash dropped, byte kept ----------


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        (rb"(\q)", b"q"),
        (rb"(\z)", b"z"),
        (rb"(\A)", b"A"),
        (rb"(\ )", b" "),
    ],
    ids=["q", "z", "A", "space"],
)
def test_unknown_escape_drops_backslash(src: bytes, expected: bytes) -> None:
    assert _lit(src) == expected


# ---------- hex string parsing (parser path) ----------


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        (b"<4865>", b"He"),
        (b"<48 65>", b"He"),  # whitespace ignored
        (b"<48\n65>", b"He"),  # LF ignored
        (b"<48\t65\r>", b"He"),  # HT / CR ignored
        (b"<>", b""),  # empty
        (b"<F>", b"\xf0"),  # odd: last nibble padded with 0
        (b"<ABC>", b"\xab\xc0"),  # odd 3-digit -> ABC0
        (b"<abcd>", b"\xab\xcd"),  # lowercase accepted
    ],
    ids=["He", "He_ws", "He_lf", "He_tabcr", "empty", "F_pad", "ABC_pad", "lower"],
)
def test_read_hex_string(src: bytes, expected: bytes) -> None:
    assert _parser(src).read_hex_string() == expected


def test_read_hex_string_eof_raises() -> None:
    with pytest.raises(PDFParseError):
        _parser(b"<4865").read_hex_string()


def test_read_hex_string_recovers_from_garbage() -> None:
    # Non-hex non-whitespace: discard dangling half-pair, skip to '>'.
    assert _parser(b"<48G65>").read_hex_string() == b"H"


# ---------- parse_cos_string dispatch ----------


def test_parse_cos_string_literal() -> None:
    assert _parser(b"(Hi)").parse_cos_string().get_bytes() == b"Hi"


def test_parse_cos_string_hex() -> None:
    assert _parser(b"<4869>").parse_cos_string().get_bytes() == b"Hi"


def test_parse_cos_string_rejects_non_string_start() -> None:
    with pytest.raises(PDFParseError):
        _parser(b"[1]").parse_cos_string()


# ---------- COSString.parse_hex strictness ----------


def test_parse_hex_trims_only_outer_whitespace() -> None:
    assert COSString.parse_hex("  4865  ").get_bytes() == b"He"


def test_parse_hex_internal_whitespace_raises() -> None:
    # Only outer whitespace is trimmed; internal ws is a malformed digit.
    with pytest.raises(OSError):
        COSString.parse_hex("48 65")


def test_parse_hex_odd_length_pads_trailing_zero() -> None:
    assert COSString.parse_hex("F").get_bytes() == b"\xf0"
    assert COSString.parse_hex("ABC").get_bytes() == b"\xab\xc0"


def test_parse_hex_empty() -> None:
    assert COSString.parse_hex("").get_bytes() == b""


def test_parse_hex_force_parsing_substitutes_question_mark() -> None:
    original = COSString.FORCE_PARSING
    COSString.FORCE_PARSING = True
    try:
        # '4G' is a malformed pair -> '?' (0x3F) under FORCE_PARSING.
        assert COSString.parse_hex("4G").get_bytes() == b"?"
    finally:
        COSString.FORCE_PARSING = original


def test_parse_hex_returns_literal_form() -> None:
    # Upstream returns a string NOT marked hex-form so the writer may choose.
    assert COSString.parse_hex("4865").is_force_hex_form() is False


# ---------- to_hex_string ----------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"\x01\xab", "01AB"),
        (b"", ""),
        (b"\x00\xff", "00FF"),
        (b"Hi", "4869"),
    ],
    ids=["01AB", "empty", "00FF", "Hi"],
)
def test_to_hex_string(raw: bytes, expected: str) -> None:
    assert COSString(raw).to_hex_string() == expected


# ---------- text-string decode (BOM detection) ----------


def test_get_string_utf16be_bom() -> None:
    assert COSString(b"\xfe\xff\x00A\x00B").get_string() == "AB"


def test_get_string_utf16le_bom() -> None:
    assert COSString(b"\xff\xfeA\x00B\x00").get_string() == "AB"


def test_get_string_pdfdocencoding_default() -> None:
    # No BOM -> PDFDocEncoding; ASCII range is identity.
    assert COSString(b"Hello").get_string() == "Hello"


def test_get_string_utf16be_supplementary() -> None:
    # U+1F600 GRINNING FACE = surrogate pair D83D DE00.
    raw = b"\xfe\xff\xd8\x3d\xde\x00"
    assert COSString(raw).get_string() == "\U0001f600"


def test_get_string_empty() -> None:
    assert COSString(b"").get_string() == ""


# ---------- round-trip: parse then re-decode ----------


def test_roundtrip_utf16be_literal_then_text() -> None:
    # A literal string holding a UTF-16BE BOM payload decodes as text.
    parsed = _parser(b"(\xfe\xff\x00A)").parse_cos_string()
    assert parsed.get_string() == "A"


def test_roundtrip_hex_to_text() -> None:
    parsed = _parser(b"<FEFF0041>").parse_cos_string()
    assert parsed.get_string() == "A"
