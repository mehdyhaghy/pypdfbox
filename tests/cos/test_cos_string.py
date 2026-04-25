from __future__ import annotations

import pytest

from pypdfbox.cos import COSString


def test_construct_from_bytes() -> None:
    s = COSString(b"hello")
    assert s.get_bytes() == b"hello"
    assert not s.is_force_hex_form()


def test_construct_from_str_uses_latin1() -> None:
    s = COSString("hello")
    assert s.get_bytes() == b"hello"


def test_force_hex_form_flag() -> None:
    s = COSString(b"\x01\x02")
    s.set_force_hex_form(True)
    assert s.is_force_hex_form()


def test_parse_hex_basic() -> None:
    s = COSString.parse_hex("48656C6C6F")
    assert s.get_bytes() == b"Hello"
    assert s.is_force_hex_form()


def test_parse_hex_ignores_whitespace() -> None:
    s = COSString.parse_hex("48 65\t6C\n6C 6F")
    assert s.get_bytes() == b"Hello"


def test_parse_hex_pads_odd_digits() -> None:
    # Per ISO 32000-1 §7.3.4.3 — trailing odd digit gets a "0".
    s = COSString.parse_hex("4")
    assert s.get_bytes() == b"\x40"


def test_parse_hex_invalid_raises() -> None:
    # parse_hex raises OSError to mirror PDFBox's IOException contract
    # (translated to OSError in pypdfbox per the test-porting conventions).
    with pytest.raises(OSError):
        COSString.parse_hex("zz")


def test_get_string_utf16_be_bom() -> None:
    raw = b"\xfe\xff" + "Héllo".encode("utf-16-be")
    assert COSString(raw).get_string() == "Héllo"


def test_get_string_utf16_le_bom() -> None:
    raw = b"\xff\xfe" + "Héllo".encode("utf-16-le")
    assert COSString(raw).get_string() == "Héllo"


def test_get_string_utf8_bom_pdf_2_0() -> None:
    raw = b"\xef\xbb\xbf" + "naïve".encode("utf-8")
    assert COSString(raw).get_string() == "naïve"


def test_get_string_default_pdfdocencoding_fallback() -> None:
    # No BOM → latin-1 (approximation of PDFDocEncoding).
    assert COSString(b"plain").get_string() == "plain"


def test_equality_includes_hex_flag() -> None:
    a = COSString(b"abc")
    b = COSString(b"abc")
    assert a == b
    b.set_force_hex_form(True)
    assert a != b


def test_visitor_dispatch() -> None:
    from tests.cos.helpers import RecordingVisitor

    v = RecordingVisitor()
    s = COSString(b"x")
    s.accept(v)
    assert v.calls == [("string", s)]
