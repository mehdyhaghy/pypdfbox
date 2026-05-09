from __future__ import annotations

import pytest

from pypdfbox.cos import COSStream, COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data))


def test_wave584_parse_cos_string_accepts_literal_and_hex_forms() -> None:
    literal = _parser(b"  (hello)").parse_cos_string()
    hex_string = _parser(b" <4869>").parse_cos_string()

    assert isinstance(literal, COSString)
    assert literal.get_bytes() == b"hello"
    assert not literal.is_force_hex_form()
    assert isinstance(hex_string, COSString)
    assert hex_string.get_bytes() == b"Hi"
    assert hex_string.is_force_hex_form()


def test_wave584_parse_cos_string_rejects_dictionary_start() -> None:
    with pytest.raises(PDFParseError, match="dictionary"):
        _parser(b"<< /A 1 >>").parse_cos_string()


def test_wave584_direct_length_stream_accepts_bare_cr_after_stream_keyword() -> None:
    parser = _parser(b"4 0 obj << /Length 5 >> stream\rABCDE\nendstream endobj")

    body = parser.parse_indirect_object_definition().get_object()

    assert isinstance(body, COSStream)
    assert body.get_raw_data() == b"ABCDE"


def test_wave584_direct_length_stream_accepts_missing_eol_after_stream_keyword() -> None:
    parser = _parser(b"4 0 obj << /Length 6 >> stream ABCDE\nendstream endobj")

    body = parser.parse_indirect_object_definition().get_object()

    assert isinstance(body, COSStream)
    assert body.get_raw_data() == b" ABCDE"


def test_wave584_parse_xref_object_stream_without_stream_body_returns_dict_stream() -> None:
    parser = _parser(b"5 0 obj\n<< /Type /XRef /Size 0 /W [1 1 1] >>\nendobj")

    stream = parser.parse_xref_object_stream(0)

    assert isinstance(stream, COSStream)
    assert stream.get_name("Type") == "XRef"
    assert stream.get_raw_data() == b""
    assert not stream.is_skip_encryption()
