from __future__ import annotations

import pytest

from pypdfbox.cos import COSDocument, COSInteger, COSName, COSObjectKey, COSStream
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


def test_wave633_read_all_bytes_preserves_current_position() -> None:
    parser = _parser(b"0123456789")
    parser.seek(4)

    data = parser._read_all_bytes()  # noqa: SLF001

    assert data == b"0123456789"
    assert parser.position == 4
    assert parser.read_byte() == ord("4")


@pytest.mark.parametrize("eol", [b"\r\n", b"\r"])
def test_wave633_direct_length_stream_accepts_crlf_and_bare_cr_eol(eol: bytes) -> None:
    parser = _parser(
        b"8 0 obj\n<< /Length 4 >>\nstream" + eol + b"DATA\nendstream\nendobj"
    )

    stream = parser.parse_indirect_object_definition().get_object()

    assert isinstance(stream, COSStream)
    assert stream.get_raw_data() == b"DATA"


def test_wave633_parse_object_stream_rejects_offset_at_payload_end() -> None:
    doc = COSDocument()
    try:
        stream = COSStream(scratch_file=doc.scratch_file)
        stream.set_item(COSName.TYPE, COSName.get_pdf_name("ObjStm"))
        stream.set_item("N", COSInteger.get(1))
        stream.set_item("First", COSInteger.get(4))
        stream.set_raw_data(b"9 2\nOK")
        doc.get_object_from_pool(COSObjectKey(7, 0)).set_object(stream)

        with pytest.raises(PDFParseError, match="outside payload length 2"):
            _parser(b"", document=doc).parse_object_stream(7)
    finally:
        doc.close()
