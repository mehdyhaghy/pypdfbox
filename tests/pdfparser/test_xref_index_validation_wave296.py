from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParser
from pypdfbox.pdfparser.parse_error import PDFParseError


def _xref_dict(*, index: list[int] | None = None, size: int = 2) -> COSDictionary:
    dictionary = COSDictionary()
    dictionary.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XRef"))
    dictionary.set_item(
        COSName.get_pdf_name("W"),
        COSArray([COSInteger.get(1), COSInteger.get(1), COSInteger.get(1)]),
    )
    dictionary.set_item(COSName.get_pdf_name("Size"), COSInteger.get(size))
    if index is not None:
        dictionary.set_item(
            COSName.get_pdf_name("Index"),
            COSArray([COSInteger.get(value) for value in index]),
        )
    return dictionary


def _xref_stream_pdf(index: bytes, body: bytes = b"") -> bytes:
    out = bytearray(b"%PDF-1.5\n")
    startxref = len(out)
    out += (
        b"1 0 obj\n"
        b"<< /Type /XRef /Size 2 /Index "
        + index
        + b" /W [ 1 1 1 ] /Length "
        + str(len(body)).encode("ascii")
        + b" >>\nstream\n"
        + body
        + b"\nendstream\nendobj\n"
        b"startxref\n"
        + str(startxref).encode("ascii")
        + b"\n%%EOF"
    )
    return bytes(out)


@pytest.mark.parametrize("index", [[-1, 1], [0, -1]])
def test_cos_parser_rejects_negative_xref_index_values(index: list[int]) -> None:
    parser = COSParser(RandomAccessReadBuffer(b""))

    with pytest.raises(PDFParseError, match="xref stream /Index"):
        parser.parse_xref_stream(_xref_dict(index=index))


def test_cos_parser_rejects_negative_default_xref_size() -> None:
    parser = COSParser(RandomAccessReadBuffer(b""))

    with pytest.raises(PDFParseError, match="xref stream /Index count"):
        parser.parse_xref_stream(_xref_dict(size=-1))


@pytest.mark.parametrize("index", [b"[ -1 1 ]", b"[ 0 -1 ]"])
def test_pdf_parser_rejects_negative_xref_index_values(index: bytes) -> None:
    pdf = _xref_stream_pdf(index, body=b"\x00\x00\x00")

    with pytest.raises(PDFParseError, match="xref stream /Index"):
        PDFParser(RandomAccessReadBuffer(pdf)).parse()
