from __future__ import annotations

import pytest

from pypdfbox.cos import COSDocument, COSInteger, COSName, COSObjectKey, COSStream
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


def _objstm(doc: COSDocument, raw: bytes = b"") -> COSStream:
    stream = COSStream(scratch_file=doc.scratch_file)
    stream.set_item("Type", COSName.get_pdf_name("ObjStm"))
    stream.set_item("N", COSInteger.get(1))
    stream.set_item("First", COSInteger.get(4))
    stream.set_raw_data(raw or b"8 0\ntrue")
    return stream


def test_wave613_parse_xref_object_stream_non_standalone_allows_missing_type() -> None:
    parser = _parser(
        b"5 0 obj\n<< /Size 0 /W [1 1 1] /Length 0 >>\n"
        b"stream\n\nendstream\nendobj"
    )

    stream = parser.parse_xref_object_stream(0, is_standalone=False)

    assert isinstance(stream, COSStream)
    assert stream.get_raw_data() == b""
    assert stream.is_skip_encryption()


def test_wave613_direct_length_stream_rejects_negative_length() -> None:
    parser = _parser(b"4 0 obj << /Length -1 >> stream\nABC\nendstream endobj")

    with pytest.raises(PDFParseError, match="negative"):
        parser.parse_indirect_object_definition()


def test_wave613_direct_length_stream_reports_truncated_body() -> None:
    parser = _parser(b"4 0 obj << /Length 8 >> stream\nABC")

    with pytest.raises(PDFParseError, match="stream body truncated"):
        parser.parse_indirect_object_definition()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda stream: stream.remove_item("Type"), "missing /Type /ObjStm"),
        (lambda stream: stream.remove_item("N"), "missing /N or /First"),
        (lambda stream: stream.set_item("N", COSInteger.get(-1)), "negative /N"),
        (
            lambda stream: stream.set_item("First", COSInteger.get(-1)),
            "negative /First",
        ),
        (lambda stream: stream.set_raw_data(b"-8 0\ntrue"), "negative object number"),
    ],
)
def test_wave613_object_stream_metadata_validation(
    mutate, message: str
) -> None:
    doc = COSDocument()
    try:
        stream = _objstm(doc)
        mutate(stream)
        doc.get_object_from_pool(COSObjectKey(7, 0)).set_object(stream)

        with pytest.raises(PDFParseError, match=message):
            _parser(b"", document=doc).parse_object_stream(7)
    finally:
        doc.close()
