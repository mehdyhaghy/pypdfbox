"""Edge-case round-out for the content-stream parser.

The PDFBox class that tokenizes a content stream is
``org.apache.pdfbox.pdfparser.PDFStreamParser`` (PDFBox 3.0 keeps it under
``pdfparser``; 4.0-era code sometimes refers to it as
``PDFContentStreamParser``). In pypdfbox the implementation lives at
:mod:`pypdfbox.pdfparser.pdf_stream_parser` and is consumed from
:mod:`pypdfbox.contentstream.pdf_stream_engine`. These tests exercise the
ISO 32000-1 §7.3.4 string conventions and the §8.9.7 inline-image
tokenizer in a content-stream context (operands feeding operators), so
they live under ``tests/contentstream/`` rather than ``tests/pdfparser/``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSFloat, COSInteger, COSName, COSNull, COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser


def _parse(data: bytes) -> list[object]:
    p = PDFStreamParser(RandomAccessReadBuffer(data))
    return list(p.tokens())


# ---------- §7.3.4.2 literal-string escape sequences ----------


@pytest.mark.parametrize(
    "raw,expected",
    [
        (b"(\\n) Tj", b"\n"),
        (b"(\\r) Tj", b"\r"),
        (b"(\\t) Tj", b"\t"),
        (b"(\\b) Tj", b"\x08"),
        (b"(\\f) Tj", b"\x0c"),
        (b"(\\() Tj", b"("),
        (b"(\\)) Tj", b")"),
        (b"(\\\\) Tj", b"\\"),
        # Unknown escape: per §7.3.4.2 the backslash is dropped, byte kept.
        (b"(\\z) Tj", b"z"),
    ],
)
def test_literal_string_simple_escapes(raw: bytes, expected: bytes) -> None:
    toks = _parse(raw)
    assert isinstance(toks[0], COSString)
    assert toks[0].get_bytes() == expected
    assert isinstance(toks[1], Operator) and toks[1].name == "Tj"


@pytest.mark.parametrize(
    "raw,expected",
    [
        # 1-digit, 2-digit, 3-digit octal forms.
        (b"(\\1) Tj", bytes([0o1])),
        (b"(\\12) Tj", bytes([0o12])),
        (b"(\\101) Tj", b"A"),
        (b"(\\101\\102\\103) Tj", b"ABC"),
        # Octal of value > 0xFF gets masked to low 8 bits — but \777 == 0x1FF
        # is the canonical edge case mentioned in the spec.
        (b"(\\377) Tj", bytes([0xFF])),
        # Non-octal digit terminates the escape.
        (b"(\\18) Tj", bytes([0o1]) + b"8"),
    ],
)
def test_literal_string_octal_escapes(raw: bytes, expected: bytes) -> None:
    toks = _parse(raw)
    assert isinstance(toks[0], COSString)
    assert toks[0].get_bytes() == expected


def test_literal_string_line_continuation_lf() -> None:
    # Backslash + LF is a line continuation: both bytes are dropped.
    toks = _parse(b"(line1\\\nline2) Tj")
    assert isinstance(toks[0], COSString)
    assert toks[0].get_bytes() == b"line1line2"


def test_literal_string_line_continuation_cr() -> None:
    toks = _parse(b"(line1\\\rline2) Tj")
    assert isinstance(toks[0], COSString)
    assert toks[0].get_bytes() == b"line1line2"


def test_literal_string_line_continuation_crlf() -> None:
    toks = _parse(b"(line1\\\r\nline2) Tj")
    assert isinstance(toks[0], COSString)
    assert toks[0].get_bytes() == b"line1line2"


def test_literal_string_raw_eol_bytes_preserved() -> None:
    # PDFBox 3.0.7 writes unescaped EOL bytes verbatim inside a literal
    # string — bare CR / CRLF are NOT normalized to LF (verified by the live
    # oracle, ParseLiteralNameProbe). Keep the raw bytes for byte parity.
    toks_cr = _parse(b"(a\rb) Tj")
    assert isinstance(toks_cr[0], COSString)
    assert toks_cr[0].get_bytes() == b"a\rb"
    toks_crlf = _parse(b"(a\r\nb) Tj")
    assert isinstance(toks_crlf[0], COSString)
    assert toks_crlf[0].get_bytes() == b"a\r\nb"
    # Bare LF stays as LF.
    toks_lf = _parse(b"(a\nb) Tj")
    assert isinstance(toks_lf[0], COSString)
    assert toks_lf[0].get_bytes() == b"a\nb"


# ---------- balanced parens within literal strings ----------


def test_balanced_parens_simple() -> None:
    toks = _parse(b"(a(b)c) Tj")
    assert isinstance(toks[0], COSString)
    assert toks[0].get_bytes() == b"a(b)c"


def test_balanced_parens_nested_deeply() -> None:
    toks = _parse(b"(a(b(c(d)e)f)g) Tj")
    assert isinstance(toks[0], COSString)
    assert toks[0].get_bytes() == b"a(b(c(d)e)f)g"


def test_unbalanced_paren_with_escape() -> None:
    # An escaped paren is NOT counted in the balance — the string here
    # really does end at the unescaped ')'.
    toks = _parse(b"(a\\(b) Tj")
    assert isinstance(toks[0], COSString)
    assert toks[0].get_bytes() == b"a(b"


def test_literal_string_with_only_escaped_parens() -> None:
    toks = _parse(b"(\\(\\)) Tj")
    assert isinstance(toks[0], COSString)
    assert toks[0].get_bytes() == b"()"


# ---------- §7.3.4.3 hex strings ----------


def test_hex_string_basic() -> None:
    toks = _parse(b"<48656C6C6F> Tj")
    assert isinstance(toks[0], COSString)
    assert toks[0].get_bytes() == b"Hello"


def test_hex_string_lowercase_digits() -> None:
    toks = _parse(b"<48656c6c6f> Tj")
    assert isinstance(toks[0], COSString)
    assert toks[0].get_bytes() == b"Hello"


def test_hex_string_whitespace_ignored() -> None:
    # ISO 32000-1 §7.3.4.3: ASCII whitespace inside <...> is ignored.
    toks = _parse(b"<48 65\n6C\t6C\r6F> Tj")
    assert isinstance(toks[0], COSString)
    assert toks[0].get_bytes() == b"Hello"


def test_hex_string_odd_length_pads_with_zero() -> None:
    # Odd-trailing-digit case: '2' is treated as '20' (= space).
    toks = _parse(b"<48656C6C6F2> Tj")
    assert isinstance(toks[0], COSString)
    assert toks[0].get_bytes() == b"Hello "


def test_hex_string_empty() -> None:
    toks = _parse(b"<> Tj")
    assert isinstance(toks[0], COSString)
    assert toks[0].get_bytes() == b""


# ---------- comment handling ----------


def test_comment_to_end_of_line() -> None:
    # '%' to next EOL is a comment; everything after % on that line is
    # discarded.
    toks = _parse(b"100 % first coord\n200 % second\nm")
    assert len(toks) == 3
    assert isinstance(toks[0], COSInteger) and toks[0].value == 100
    assert isinstance(toks[1], COSInteger) and toks[1].value == 200
    assert isinstance(toks[2], Operator) and toks[2].name == "m"


def test_comment_terminated_by_cr_only() -> None:
    toks = _parse(b"100 % cr-terminated\r200 m")
    assert isinstance(toks[0], COSInteger) and toks[0].value == 100
    assert isinstance(toks[1], COSInteger) and toks[1].value == 200
    assert isinstance(toks[2], Operator) and toks[2].name == "m"


def test_comment_terminated_by_crlf() -> None:
    toks = _parse(b"100 % crlf\r\n200 m")
    assert isinstance(toks[0], COSInteger) and toks[0].value == 100
    assert isinstance(toks[1], COSInteger) and toks[1].value == 200
    assert isinstance(toks[2], Operator) and toks[2].name == "m"


def test_comment_at_end_of_stream() -> None:
    # No trailing newline: comment runs to EOF, no tokens after.
    toks = _parse(b"100 m % trailing")
    assert len(toks) == 2
    assert isinstance(toks[0], COSInteger) and toks[0].value == 100
    assert isinstance(toks[1], Operator) and toks[1].name == "m"


def test_comment_with_percent_inside_literal_string_is_kept() -> None:
    # A '%' inside a literal string is content, not a comment marker.
    toks = _parse(b"(50% off) Tj")
    assert isinstance(toks[0], COSString)
    assert toks[0].get_bytes() == b"50% off"


# ---------- inline image (BI / ID / EI) edge cases ----------


def test_inline_image_ei_followed_by_whitespace() -> None:
    # The minimal valid terminator: 'EI' then a single whitespace byte.
    # The space between the payload and EI is itself part of the image
    # bytes (only the LF after 'ID' is consumed as the data separator).
    toks = _parse(b"BI /W 1 ID\nABCEI Q")
    assert isinstance(toks[0], Operator) and toks[0].name == "BI"
    assert toks[0].image_data == b"ABC"
    assert isinstance(toks[1], Operator) and toks[1].name == "Q"


def test_inline_image_ei_at_end_of_stream() -> None:
    # 'EI' at EOF (no trailing whitespace) still terminates the segment.
    toks = _parse(b"BI /W 1 ID\nABC EI")
    assert isinstance(toks[0], Operator) and toks[0].name == "BI"
    # 'ABC ' — the space before EI is data; EI itself is the terminator.
    assert toks[0].image_data == b"ABC "


def test_inline_image_ei_bytes_in_payload_not_terminator() -> None:
    # 'EI' embedded inside binary image data (not followed by an
    # operator-shaped token) must NOT terminate the segment.
    toks = _parse(b"BI /W 1 ID\n12EI5EI Q")
    assert isinstance(toks[0], Operator) and toks[0].name == "BI"
    assert toks[0].image_data == b"12EI5"


def test_inline_image_id_separator_can_be_single_whitespace() -> None:
    # Per upstream: after 'ID' we consume one EOL OR a single whitespace
    # byte. A space separator is acceptable; the byte after that is data.
    # The trailing space before EI is itself part of the image bytes.
    toks = _parse(b"BI /W 1 ID XYZEI Q")
    assert isinstance(toks[0], Operator) and toks[0].name == "BI"
    assert toks[0].image_data == b"XYZ"


# ---------- numeric token edge cases ----------


def test_trailing_decimal_dot_is_real_number() -> None:
    # '3.' is a valid PDF real number (§7.3.3).
    toks = _parse(b"3. Tj")
    assert isinstance(toks[0], COSFloat)
    assert toks[0].value == 3.0
    assert isinstance(toks[1], Operator) and toks[1].name == "Tj"


def test_leading_decimal_dot_is_real_number() -> None:
    # '.5' parses as 0.5.
    toks = _parse(b".5 Tj")
    assert isinstance(toks[0], COSFloat)
    assert toks[0].value == 0.5


def test_leading_plus_sign_on_number() -> None:
    # '+3' is parsed as 3 (per ISO 32000-1 §7.3.3 — sign optional).
    toks = _parse(b"+3 Tj")
    assert isinstance(toks[0], COSInteger)
    assert toks[0].value == 3


def test_leading_minus_sign_on_number() -> None:
    toks = _parse(b"-3 Tj")
    assert isinstance(toks[0], COSInteger)
    assert toks[0].value == -3


def test_isolated_plus_yields_cosnull() -> None:
    # PDFBOX-5906 — isolated '+' becomes COSNull.
    toks = _parse(b"+ Tj")
    assert toks[0] is COSNull.NULL


def test_negative_real_with_trailing_dot() -> None:
    toks = _parse(b"-3. m")
    assert isinstance(toks[0], COSFloat)
    assert toks[0].value == -3.0


# ---------- mixed whole-stream smoke test ----------


def test_mixed_content_stream_smoke() -> None:
    # Drives every edge case at once: comments, escapes, balanced parens,
    # hex string, names, and operators.
    raw = (
        b"q % save state\n"
        b"BT\n"
        b"/F1 12 Tf\n"
        b"(line\\\n one\\(parens\\)) Tj\n"
        b"<48 69> Tj\n"
        b"ET\n"
        b"Q"
    )
    toks = _parse(raw)
    op_names = [t.name for t in toks if isinstance(t, Operator)]
    assert op_names == ["q", "BT", "Tf", "Tj", "Tj", "ET", "Q"]
    # First Tj operand: line + " one" + "(parens)"
    strings = [t for t in toks if isinstance(t, COSString)]
    assert strings[0].get_bytes() == b"line one(parens)"
    assert strings[1].get_bytes() == b"Hi"
    # /F1 made it through.
    names = [t for t in toks if isinstance(t, COSName)]
    assert any(n.get_name() == "F1" for n in names)


# ---------- error path: unterminated literal string ----------


def test_unterminated_literal_string_raises() -> None:
    with pytest.raises(PDFParseError):
        _parse(b"(unterminated Tj")


def test_unterminated_hex_string_raises() -> None:
    with pytest.raises(PDFParseError):
        _parse(b"<4865 Tj")
