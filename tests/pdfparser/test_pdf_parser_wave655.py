from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObjectKey,
    COSStream,
    COSString,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError, PDFParser
from pypdfbox.pdfparser.xref_trailer_resolver import XrefEntry, XrefType


def _parser(data: bytes = b"") -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


def _ready_parser(data: bytes) -> tuple[PDFParser, COSDocument]:
    parser = _parser(data)
    doc = parser._document = COSDocument()  # noqa: SLF001
    parser._cos_parser = COSParser(parser._src, document=doc)  # noqa: SLF001
    return parser, doc


def test_wave655_linearization_detection_ignores_bad_indirect_headers() -> None:
    parser = _parser(b"%PDF-1.7\n1 nope")
    parser.parse_header()
    parser._detect_linearization()  # noqa: SLF001
    assert parser.get_linearization_dictionary() is None

    parser = _parser(b"%PDF-1.7\n1 0 nope")
    parser.parse_header()
    parser._detect_linearization()  # noqa: SLF001
    assert parser.get_linearization_dictionary() is None


def test_wave655_document_id_rejects_empty_or_non_string_id_arrays() -> None:
    parser = _parser()
    resolver = parser.get_xref_trailer_resolver()

    trailer = COSDictionary()
    trailer.set_item("ID", COSArray())
    resolver.begin_section(0)
    resolver.set_trailer(trailer)
    assert parser.get_document_id() is None

    ids = COSArray()
    ids.add(COSInteger.get(3))
    trailer = COSDictionary()
    trailer.set_item("ID", ids)
    resolver.begin_section(1)
    resolver.set_trailer(trailer)
    assert parser.get_document_id() is None


def test_wave655_security_handler_short_circuits_cached_and_missing_trailer() -> None:
    parser = _parser()
    handler = object()
    parser._security_handler = handler  # noqa: SLF001
    assert parser._prepare_security_handler_if_needed() is handler  # noqa: SLF001

    parser = _parser()
    parser.set_password(b"secret")
    assert parser._prepare_security_handler_if_needed() is None  # noqa: SLF001


def test_wave655_resolve_dict_entry_returns_none_for_unknown_indirect_object() -> None:
    parser, doc = _ready_parser(b"")
    try:
        container = COSDictionary()
        missing = doc.get_object_from_pool(COSObjectKey(9, 0))
        container.set_item(COSName.ENCRYPT, missing)

        assert parser._resolve_dict_entry(container, COSName.ENCRYPT) is None  # noqa: SLF001
    finally:
        doc.close()


def test_wave655_recover_xref_offset_keeps_original_when_search_misses() -> None:
    class Searcher:
        def bf_search_for_xref(self, offset: int) -> int:
            assert offset == 0
            return 2

    parser = _parser(b"not xref")
    parser._cos_parser = Searcher()  # type: ignore[assignment]  # noqa: SLF001

    assert parser._recover_xref_offset_if_needed(0) == 0  # noqa: SLF001


def test_wave655_xref_shape_check_rejects_indirect_without_obj_keyword() -> None:
    parser, doc = _ready_parser(b"1 0 nope")
    try:
        assert parser._xref_section_starts_at(0) is False  # noqa: SLF001
    finally:
        doc.close()


def test_wave655_xref_stream_rejects_stream_like_wrong_keyword() -> None:
    parser, doc = _ready_parser(b"1 0 obj << /Type /XRef /Length 0 >> stuff")
    try:
        with pytest.raises(PDFParseError, match="expected 'stream'"):
            parser._handle_xref_stream_at(0)  # noqa: SLF001
    finally:
        doc.close()


def test_wave655_decode_xref_stream_rejects_missing_w_and_bad_index_entries() -> None:
    parser = _parser()
    with pytest.raises(PDFParseError, match="/W"):
        parser._decode_xref_stream_entries(COSStream())  # noqa: SLF001

    stream = COSStream()
    stream.set_item("W", COSArray([COSInteger.get(1), COSInteger.get(1), COSInteger.get(1)]))
    stream.set_item("Index", COSArray([COSInteger.get(0), COSString("bad")]))
    stream.set_raw_data(b"\x01\x00\x00")

    with pytest.raises(PDFParseError, match="/Index entries"):
        parser._decode_xref_stream_entries(stream)  # noqa: SLF001


def test_wave655_traditional_xref_rejects_bad_keywords_and_eof() -> None:
    parser = _parser(b"notxref")
    with pytest.raises(PDFParseError, match="expected 'xref'"):
        parser._parse_traditional_xref_section()  # noqa: SLF001

    parser = _parser(b"xref\n")
    with pytest.raises(PDFParseError, match="unexpected EOF"):
        parser._parse_traditional_xref_section()  # noqa: SLF001

    parser, doc = _ready_parser(b"xref\ntrailerish")
    try:
        with pytest.raises(PDFParseError, match="expected 'trailer'"):
            parser._parse_traditional_xref_section()  # noqa: SLF001
    finally:
        doc.close()


def test_wave655_compressed_loader_rejects_non_stream_object_stream() -> None:
    parser, doc = _ready_parser(b"")
    try:
        objstm = doc.get_object_from_pool(COSObjectKey(7, 0))
        objstm.set_object(COSDictionary())
        target = doc.get_object_from_pool(COSObjectKey(8, 0))

        with pytest.raises(PDFParseError, match="not a stream"):
            parser._load_compressed_object(7, 0, target)  # noqa: SLF001
    finally:
        doc.close()


def test_wave655_indirect_loader_rejects_bad_object_and_end_markers() -> None:
    parser, doc = _ready_parser(b"1 0 nope")
    try:
        obj = doc.get_object_from_pool(COSObjectKey(1, 0))
        with pytest.raises(PDFParseError, match="expected 'obj'"):
            parser._load_indirect_object_at(0, obj)  # noqa: SLF001
    finally:
        doc.close()

    parser, doc = _ready_parser(b"1 0 obj 42 stuff")
    try:
        obj = doc.get_object_from_pool(COSObjectKey(1, 0))
        with pytest.raises(PDFParseError, match="expected 'endobj'"):
            parser._load_indirect_object_at(0, obj)  # noqa: SLF001
    finally:
        doc.close()

    parser, doc = _ready_parser(b"1 0 obj 42 nope")
    try:
        obj = doc.get_object_from_pool(COSObjectKey(1, 0))
        with pytest.raises(PDFParseError, match="expected 'endobj'"):
            parser._load_indirect_object_at(0, obj)  # noqa: SLF001
    finally:
        doc.close()


def test_wave655_read_stream_body_rejects_truncated_body() -> None:
    parser = _parser(b"\nAB")
    stream = COSStream()
    stream.set_item(COSName.LENGTH, COSInteger.get(3))

    with pytest.raises(PDFParseError, match="stream body truncated"):
        parser._read_stream_body(stream)  # noqa: SLF001


def test_wave655_populate_document_skips_free_xref_entries() -> None:
    parser = _parser()
    doc = parser._document = COSDocument()  # noqa: SLF001
    try:
        resolver = parser.get_xref_trailer_resolver()
        resolver.begin_section(0)
        resolver.set_entry(
            COSObjectKey(10, 0),
            XrefEntry(type=XrefType.TABLE, offset=0, compressed_index=-1),
        )

        parser.populate_document()

        assert doc.get_object(COSObjectKey(10, 0)) is None
    finally:
        doc.close()
