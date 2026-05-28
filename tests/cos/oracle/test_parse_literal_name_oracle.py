"""Live PDFBox differential parity for the literal-string + name PARSE/DECODE
direction of ``BaseParser`` — the inverse of the COSWriter escape direction
(covered by ``test_cos_escape_oracle``) and of the ``getString()`` text decode
(covered by ``test_cos_string_text_oracle``).

One Java probe (``ParseLiteralNameProbe``) feeds raw PDF syntax bytes through
``PDFStreamParser.parseNextToken()`` (which dispatches to
``BaseParser.parseCOSString()`` / ``parseCOSName()``) and emits the DECODED raw
byte sequence the parser produced. pypdfbox runs the same input through
``PDFStreamParser.from_bytes(...).parse_next_token()`` and we compare the
decoded bytes hex-for-hex.

Covered decode decisions:

* literal ``(...)``: octal escapes (``\\0``, ``\\12``, ``\\123``, ``\\053``),
  octal-overflow byte wrap (``\\400`` -> 0x00), the named escapes
  (``\\n \\r \\t \\b \\f \\( \\) \\\\``), unknown-escape drop-the-backslash,
  line continuation (``\\<LF>``, ``\\<CR>``, ``\\<CRLF>``), bare EOL
  normalisation (CR / CRLF / LF -> LF), and balanced nested parens kept as
  data;
* name ``/Foo``: ``#XX`` hex-escape decoding, a ``#`` followed by fewer than
  two hex digits kept literally, and high bytes via ``#XX``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_string import COSString
from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------------- #
# Each case is (id, raw PDF syntax bytes for ONE object). The oracle supplies
# the expected decoded byte sequence.
# --------------------------------------------------------------------------- #

_CASES: tuple[tuple[str, bytes], ...] = (
    # ---- literal-string named escapes ----
    ("lit_plain", b"(Hello)"),
    ("lit_empty", b"()"),
    ("esc_n", b"(a\\nb)"),
    ("esc_r", b"(a\\rb)"),
    ("esc_t", b"(a\\tb)"),
    ("esc_b", b"(a\\bb)"),
    ("esc_f", b"(a\\fb)"),
    ("esc_open_paren", b"(a\\(b)"),
    ("esc_close_paren", b"(a\\)b)"),
    ("esc_backslash", b"(a\\\\b)"),
    # unknown escape -> drop the backslash, keep the byte (§7.3.4.2)
    ("esc_unknown_q", b"(a\\qb)"),
    ("esc_unknown_z", b"(\\z)"),
    # ---- octal escapes (1-3 digits) ----
    ("oct_1digit", b"(\\0)"),
    ("oct_2digit", b"(\\12)"),
    ("oct_3digit", b"(\\123)"),
    ("oct_053", b"(\\053)"),  # '+' (0x2B)
    ("oct_101", b"(\\101)"),  # 'A'
    ("oct_followed_by_digit", b"(\\0053)"),  # \005 then literal '3'
    ("oct_max_377", b"(\\377)"),  # 0xFF
    ("oct_overflow_400", b"(\\400)"),  # wraps: 0400 & 0xFF == 0x00
    ("oct_overflow_777", b"(\\777)"),  # 0777 & 0xFF == 0xFF
    ("oct_two_then_nonoctal", b"(\\47x)"),  # \47 = 0x27 then 'x'
    # ---- line continuation (backslash + EOL) ----
    ("cont_lf", b"(a\\\nb)"),
    ("cont_cr", b"(a\\\rb)"),
    ("cont_crlf", b"(a\\\r\nb)"),
    # ---- bare EOL normalisation (CR / CRLF / LF -> LF) ----
    ("eol_bare_cr", b"(a\rb)"),
    ("eol_bare_crlf", b"(a\r\nb)"),
    ("eol_bare_lf", b"(a\nb)"),
    # ---- balanced nested parens kept as data ----
    ("nested_balanced", b"(a(b)c)"),
    ("nested_deep", b"(a(b(c)d)e)"),
    ("nested_empty", b"(())"),
    # ---- name #XX hex-escape decoding ----
    ("name_plain", b"/Type"),
    ("name_space_escape", b"/A#20B"),  # '#20' -> space
    ("name_hash_escape", b"/A#23B"),  # '#23' -> '#'
    ("name_slash_escape", b"/A#2FB"),  # '#2F' -> '/'
    ("name_paren_escape", b"/A#28B"),  # '#28' -> '('
    ("name_high_byte", b"/A#C3#A9"),  # e-acute UTF-8 bytes
    ("name_lowercase_hex", b"/A#e9B"),  # lowercase hex digits
    ("name_mixed_hex", b"/A#aFB"),  # mixed-case hex
    # malformed: '#' with fewer than two hex digits kept literally
    ("name_hash_no_hex", b"/A#GB"),  # '#G' not hex
    ("name_hash_one_hex", b"/A#2 "),  # '#2' then space terminator
    ("name_hash_at_end", b"/AB#"),  # trailing '#' then terminator
    ("name_empty", b"/ "),  # empty name (slash then terminator)
)


def _py_render(syntax: bytes) -> str:
    """pypdfbox PDFStreamParser.parse_next_token() rendered like the probe."""
    tok = PDFStreamParser.from_bytes(syntax).parse_next_token()
    if tok is None:
        return "NULL"
    if isinstance(tok, COSString):
        return "STR:" + tok.get_bytes().hex()
    if isinstance(tok, COSName):
        return "NAME:" + tok.get_name().encode("utf-8").hex()
    return "OTHER:" + type(tok).__name__


@requires_oracle
@pytest.mark.parametrize(
    ("case_id", "syntax"), _CASES, ids=[c[0] for c in _CASES]
)
def test_parse_literal_name_matches_pdfbox(case_id: str, syntax: bytes) -> None:
    java = run_probe_text("ParseLiteralNameProbe", syntax.hex())
    py = _py_render(syntax)
    assert py == java
