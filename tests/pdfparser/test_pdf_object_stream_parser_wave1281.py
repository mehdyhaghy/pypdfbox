"""Wave 1281: PDFObjectStreamParser port."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDocument, COSInteger, COSName, COSStream
from pypdfbox.pdfparser import PDFObjectStreamParser
from pypdfbox.pdfparser.parse_error import PDFParseError


def _make_stream(payload: bytes, *, n: int, first: int) -> COSStream:
    stream = COSStream()
    stream.set_item(COSName.N, COSInteger.get(n))
    stream.set_item(COSName.FIRST, COSInteger.get(first))
    out = stream.create_raw_output_stream()
    try:
        out.write(payload)
    finally:
        out.close()
    return stream


def _empty_stream() -> COSStream:
    stream = COSStream()
    out = stream.create_raw_output_stream()
    out.close()
    return stream


def test_constructor_requires_n_entry() -> None:
    stream = _empty_stream()
    stream.set_item(COSName.FIRST, COSInteger.get(0))
    with pytest.raises(PDFParseError):
        PDFObjectStreamParser(stream, COSDocument())


def test_constructor_requires_first_entry() -> None:
    stream = _empty_stream()
    stream.set_item(COSName.N, COSInteger.get(0))
    with pytest.raises(PDFParseError):
        PDFObjectStreamParser(stream, COSDocument())


def test_constructor_rejects_negative_n() -> None:
    stream = _empty_stream()
    stream.set_item(COSName.N, COSInteger.get(-1))
    stream.set_item(COSName.FIRST, COSInteger.get(0))
    with pytest.raises(PDFParseError):
        PDFObjectStreamParser(stream, COSDocument())


def test_constructor_rejects_negative_first() -> None:
    stream = _empty_stream()
    stream.set_item(COSName.N, COSInteger.get(0))
    stream.set_item(COSName.FIRST, COSInteger.get(-1))
    with pytest.raises(PDFParseError):
        PDFObjectStreamParser(stream, COSDocument())


def test_read_object_numbers_empty() -> None:
    # Zero objects → parsing the offset table returns empty map.
    stream = _make_stream(b"", n=0, first=0)
    parser = PDFObjectStreamParser(stream, COSDocument())
    assert parser.read_object_numbers() == {}
