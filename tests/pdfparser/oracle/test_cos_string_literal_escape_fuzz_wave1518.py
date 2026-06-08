"""Live PDFBox differential fuzz for malformed literal escapes (wave 1518)."""

from __future__ import annotations

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import BaseParser, PDFParseError
from tests.oracle.harness import requires_oracle, run_probe_text

_CASES: list[tuple[str, bytes]] = [
    ("empty", b"()"),
    ("named", b"(a\\nb\\rc\\td\\be\\ff\\(g\\)h\\\\i)"),
    ("unknown", b"(a\\zb)"),
    ("octal_one", b"(\\7)"),
    ("octal_two", b"(\\77)"),
    ("octal_three", b"(\\377)"),
    ("octal_overflow", b"(\\777)"),
    ("octal_stops_at_8", b"(\\128)"),
    ("nested", b"(a(b(c)d)e)"),
    ("escaped_close", b"(a\\)b)"),
    ("line_lf", b"(a\\\nb)"),
    ("line_cr", b"(a\\\rb)"),
    ("line_crlf", b"(a\\\r\nb)"),
    ("bare_eols", b"(a\rb\r\nc\nd)"),
    ("backslash_eof", b"(abc\\"),
    ("unterminated", b"(abc"),
    ("nul_byte", b"(a\x00b)"),
]


def _py_dump() -> str:
    lines: list[str] = []
    for name, syntax in _CASES:
        try:
            value = BaseParser(RandomAccessReadBuffer(syntax)).parse_cos_string()
            lines.append(f"CASE {name} bytes={value.get_bytes().hex()}")
        except Exception as exc:
            java_name = "IOException" if isinstance(exc, PDFParseError) else type(exc).__name__
            lines.append(f"CASE {name} ERR:{java_name}")
    return "".join(line + "\n" for line in lines)


@requires_oracle
def test_literal_escape_fuzz_matches_pdfbox() -> None:
    assert _py_dump() == run_probe_text("CosStringLiteralEscapeFuzzProbe")
