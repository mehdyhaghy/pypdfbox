from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDocument,
    COSInteger,
    COSName,
    COSObjectKey,
    COSStream,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError, PDFParser
from pypdfbox.pdfparser.xref_trailer_resolver import XrefType


def _parser(data: bytes = b"") -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


def _xref_stream(widths: list[int | COSBase], raw: bytes = b"") -> COSStream:
    stream = COSStream()
    w = COSArray()
    for width in widths:
        w.add(COSInteger.get(width) if isinstance(width, int) else width)
    stream.set_item("W", w)
    stream.set_raw_data(raw)
    return stream


def test_wave563_xref_stream_requires_integer_width_entries() -> None:
    parser = _parser()
    parser.get_xref_trailer_resolver().begin_section(0)
    stream = _xref_stream([1, COSName.get_pdf_name("BadWidth"), 1])
    stream.set_item("Size", COSInteger.get(1))

    with pytest.raises(PDFParseError, match=r"/W\[1\] is not an integer"):
        parser._decode_xref_stream_entries(stream)  # noqa: SLF001


def test_wave563_xref_stream_requires_size_when_index_is_absent() -> None:
    parser = _parser()
    parser.get_xref_trailer_resolver().begin_section(0)
    stream = _xref_stream([1, 1, 1])

    with pytest.raises(PDFParseError, match="missing /Size and /Index"):
        parser._decode_xref_stream_entries(stream)  # noqa: SLF001


def test_wave563_xref_stream_rejects_zero_and_overwide_records() -> None:
    parser = _parser()
    parser.get_xref_trailer_resolver().begin_section(0)
    zero_width = _xref_stream([0, 0, 0])
    zero_width.set_item("Size", COSInteger.get(1))

    with pytest.raises(PDFParseError, match="widths sum to zero"):
        parser._decode_xref_stream_entries(zero_width)  # noqa: SLF001

    overwide = _xref_stream([7, 7, 7], b"\x00" * 21)
    overwide.set_item("Size", COSInteger.get(1))

    with pytest.raises(PDFParseError, match="entry wider than 20 bytes"):
        parser._decode_xref_stream_entries(overwide)  # noqa: SLF001


def test_wave563_xref_stream_free_and_compressed_entries_are_registered() -> None:
    parser = _parser()
    parser.get_xref_trailer_resolver().begin_section(0)
    stream = _xref_stream([1, 1, 1], b"\x00\x05\x02\x02\x09\x03")
    index = COSArray()
    index.add(COSInteger.get(8))
    index.add(COSInteger.get(2))
    stream.set_item("Index", index)

    parser._decode_xref_stream_entries(stream)  # noqa: SLF001

    table = parser.get_xref_trailer_resolver().get_xref_table()
    free = table[COSObjectKey(8, 2)]
    compressed = table[COSObjectKey(9, 0)]
    assert free.type is XrefType.STREAM
    assert free.offset == 5
    assert free.compressed_index == -1
    assert compressed.type is XrefType.COMPRESSED
    assert compressed.offset == 9
    assert compressed.compressed_index == 3


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"1 0 nope\n<< /Type /XRef >>\n", "expected 'obj'"),
        (b"1 0 obj\n42\nendobj\n", "body is not a dictionary"),
        (
            b"1 0 obj\n<< /Type /Catalog /Size 0 /W [1 1 1] >>\nendobj\n",
            "missing /Type /XRef",
        ),
        (
            b"1 0 obj\n<< /Type /XRef /Size 0 /W [1 1 1] >>\nendobj\n",
            "missing 'stream' keyword",
        ),
    ],
)
def test_wave563_handle_xref_stream_reports_malformed_object_shapes(
    body: bytes, message: str
) -> None:
    parser = _parser(body)
    doc = COSDocument()
    parser._document = doc  # noqa: SLF001
    parser._cos_parser = COSParser(parser._src, document=doc)  # noqa: SLF001

    try:
        with pytest.raises(PDFParseError, match=message):
            parser._handle_xref_stream_at(0)  # noqa: SLF001
    finally:
        doc.close()
