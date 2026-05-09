from __future__ import annotations

from pypdfbox.cos import COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser
from tests.pdfparser.test_xref_stream_decoder import _build_xref_stream_pdf, _pack_record


def test_wave1158_xref_stream_builder_appends_extra_dict_entries() -> None:
    obj1 = b"1 0 obj\n42\nendobj"
    obj1_off = len(b"%PDF-1.5\n")
    records = (
        _pack_record(0, 0, 65535, w2=4)
        + _pack_record(1, obj1_off, 0, w2=4)
        + _pack_record(1, 0, 0, w2=4)
    )

    pdf = _build_xref_stream_pdf([obj1], records, extra_dict_entries=b"/Root 1 0 R")

    assert b"/Root 1 0 R" in pdf
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    try:
        assert doc.has_object(COSObjectKey(1, 0))
    finally:
        doc.close()
