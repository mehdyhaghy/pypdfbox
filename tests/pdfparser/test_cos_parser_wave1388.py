"""Wave 1388 — parity tests for `COSParser` upstream-named methods.

Targets the three protected methods surfaced for subclass / advanced
callers: `get_security_handler`, `read_object_marker`, and
`parse_cos_literal_string`. These mirror upstream
`org.apache.pdfbox.pdfparser.COSParser` (Java lines 1543, 1820, 1903).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(payload: bytes) -> COSParser:
    return COSParser(RandomAccessReadBuffer(payload))


def test_get_security_handler_none_when_no_handler_bound() -> None:
    p = _parser(b"%PDF-1.7\n")
    assert p.get_security_handler() is None


def test_get_security_handler_returns_bound_handler() -> None:
    p = _parser(b"%PDF-1.7\n")
    sentinel = object()
    p._security_handler = sentinel
    assert p.get_security_handler() is sentinel


def test_read_object_marker_consumes_obj_keyword() -> None:
    p = _parser(b"obj\n123")
    p.read_object_marker()
    # Cursor is now past 'obj' + newline-skip; reading more should land on '1'.
    p.skip_whitespace()
    assert p._src.peek() == ord("1")


def test_read_object_marker_raises_when_marker_missing() -> None:
    p = _parser(b"xyz\n")
    with pytest.raises(PDFParseError):
        p.read_object_marker()


def test_parse_cos_literal_string_returns_cos_string() -> None:
    p = _parser(b"(hello world)")
    out = p.parse_cos_literal_string()
    assert isinstance(out, COSString)
    assert out.get_string() == "hello world"


def test_parse_cos_literal_string_handles_escapes() -> None:
    p = _parser(b"(a\\nb)")
    out = p.parse_cos_literal_string()
    assert isinstance(out, COSString)
    assert out.get_string() == "a\nb"
