from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage


def _build_doc_bytes() -> bytes:
    doc = PDDocument()
    page = PDPage()
    stream = COSStream()
    stream.set_raw_data(b"q Q\n")
    page.set_contents(stream)
    doc.add_page(page)
    sink = io.BytesIO()
    doc.save(sink)
    doc.close()
    return sink.getvalue()


def test_add_source_accepts_memoryview() -> None:
    out = io.BytesIO()
    util = PDFMergerUtility()
    util.add_source(memoryview(_build_doc_bytes()))
    util.set_destination_stream(out)

    util.merge_documents()

    with PDDocument.load(out.getvalue()) as merged:
        assert merged.get_number_of_pages() == 1


def test_add_source_rejects_stream_reading_text() -> None:
    util = PDFMergerUtility()
    util.add_source(io.StringIO("%PDF-1.7"))  # type: ignore[arg-type]
    util.set_destination_stream(io.BytesIO())

    with pytest.raises(TypeError, match=r"read\(\) must return bytes"):
        util.merge_documents()


def test_add_source_rejects_non_callable_read_attribute() -> None:
    class NotAStream:
        read = b"%PDF-1.7"

    util = PDFMergerUtility()
    util.add_source(NotAStream())  # type: ignore[arg-type]
    util.set_destination_stream(io.BytesIO())

    with pytest.raises(TypeError, match="unsupported source type: NotAStream"):
        util.merge_documents()
