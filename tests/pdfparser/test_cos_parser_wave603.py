from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
    COSStream,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


def _objstm(
    doc: COSDocument,
    *,
    object_count: int,
    first: int,
    raw: bytes,
) -> COSStream:
    stream = COSStream(scratch_file=doc.scratch_file)
    stream.set_item("Type", COSName.get_pdf_name("ObjStm"))
    stream.set_item("N", COSInteger.get(object_count))
    stream.set_item("First", COSInteger.get(first))
    stream.set_raw_data(raw)
    return stream


def test_wave603_parse_indirect_object_registers_body_in_bound_document() -> None:
    doc = COSDocument()
    try:
        parser = _parser(b"7 2 obj\n<< /Answer 42 >>\nendobj", document=doc)

        parsed = parser.parse_indirect_object_definition()

        assert parsed is doc.get_object_from_pool(COSObjectKey(7, 2))
        body = parsed.get_object()
        assert isinstance(body, COSDictionary)
        assert body.get_dictionary_object("Answer") is COSInteger.get(42)
    finally:
        doc.close()


def test_wave603_parse_object_dynamically_respects_existing_requirement() -> None:
    doc = COSDocument()
    try:
        parser = _parser(b"", document=doc)

        with pytest.raises(PDFParseError, match="object not present"):
            parser.parse_object_dynamically(4, 0, requires_existing_not_compressed=True)

        holder = doc.get_object_from_pool(COSObjectKey(4, 0))
        holder.set_object(COSInteger.get(9))

        assert parser.parse_object_dynamically(4, 0, True) is COSInteger.get(9)
    finally:
        doc.close()


def test_wave603_no_document_dynamic_parse_returns_or_rejects_placeholder() -> None:
    parser = _parser(b"")

    placeholder = parser.parse_object_dynamically(11, 3)

    assert isinstance(placeholder, COSObject)
    assert placeholder.get_object_number() == 11
    assert placeholder.get_generation_number() == 3
    with pytest.raises(PDFParseError, match="no document bound"):
        parser.parse_object_dynamically(11, 3, requires_existing_not_compressed=True)


def test_wave603_leniency_latches_after_initial_parse_done() -> None:
    parser = _parser(b"")

    parser.set_lenient(False)
    parser.set_initial_parse_done(True)

    assert not parser.is_lenient()
    assert parser.is_initial_parse_done()
    with pytest.raises(ValueError, match="Cannot change leniency"):
        parser.set_lenient(True)


def test_wave603_eof_lookup_range_ignores_too_small_values() -> None:
    parser = _parser(b"")

    parser.set_eof_lookup_range(15)
    assert parser.get_eof_lookup_range() == COSParser.DEFAULT_TRAIL_BYTECOUNT

    parser.set_eof_lookup_range(16)
    assert parser.get_eof_lookup_range() == 16


def test_wave603_parse_xref_stream_defaults_index_and_tracks_offsets() -> None:
    xref = COSDictionary()
    w = COSArray()
    w.add(COSInteger.get(1))
    w.add(COSFloat("2.0"))
    xref.set_item("W", w)
    xref.set_item("Size", COSInteger.get(3))

    table = _parser(b"").parse_xref_stream(xref)

    assert table == {
        COSObjectKey(0, 0): 0,
        COSObjectKey(1, 0): 3,
        COSObjectKey(2, 0): 6,
    }


def test_wave603_parse_xref_stream_rejects_bad_index_shapes() -> None:
    xref = COSDictionary()
    w = COSArray()
    w.add(COSInteger.get(1))
    xref.set_item("W", w)
    xref.set_item("Size", COSInteger.get(1))
    xref.set_item("Index", COSArray())

    with pytest.raises(PDFParseError, match="odd or empty"):
        _parser(b"").parse_xref_stream(xref)


def test_wave603_object_stream_header_rejects_offsets_at_payload_end() -> None:
    doc = COSDocument()
    try:
        raw = b"8 4 true"
        stream = _objstm(doc, object_count=1, first=4, raw=raw)
        doc.get_object_from_pool(COSObjectKey(5, 0)).set_object(stream)

        with pytest.raises(PDFParseError, match="outside payload length 4"):
            _parser(b"", document=doc).parse_object_stream(5)
    finally:
        doc.close()

