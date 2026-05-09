from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
    COSStream,
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


def test_wave674_linearization_detection_ignores_bad_object_keyword() -> None:
    parser = _parser(b"%PDF-1.7\n1 0 @")
    parser.parse_header()
    saved = parser._src.get_position()  # noqa: SLF001

    parser._detect_linearization()  # noqa: SLF001

    assert parser.get_linearization_dictionary() is None
    assert parser._src.get_position() == saved  # noqa: SLF001


def test_wave674_resolve_dict_entry_skips_compressed_reference() -> None:
    parser, doc = _ready_parser(b"")
    try:
        target = doc.get_object_from_pool(COSObjectKey(4, 0))
        container = COSDictionary()
        container.set_item(COSName.ENCRYPT, target)
        parser.get_xref_trailer_resolver().begin_section(0)
        parser.get_xref_trailer_resolver().set_entry(
            COSObjectKey(4, 0),
            XrefEntry(type=XrefType.COMPRESSED, offset=9, compressed_index=0),
        )

        assert parser._resolve_dict_entry(container, COSName.ENCRYPT) is None  # noqa: SLF001
    finally:
        doc.close()


def test_wave674_recover_xref_offset_returns_original_for_non_section_recovery() -> None:
    class Searcher:
        def bf_search_for_xref(self, offset: int) -> int:
            return 3

    parser = _parser(b"abcnotxref")
    parser._cos_parser = Searcher()  # type: ignore[assignment]  # noqa: SLF001

    assert parser._recover_xref_offset_if_needed(0) == 0  # noqa: SLF001


def test_wave674_xref_shape_check_rejects_dictionary_without_xref_type() -> None:
    parser, doc = _ready_parser(b"1 0 obj\n<< /Type /Catalog >>\nendobj")
    try:
        assert parser._xref_section_starts_at(0) is False  # noqa: SLF001
    finally:
        doc.close()


def test_wave674_handle_xref_stream_rejects_non_dictionary_body() -> None:
    parser, doc = _ready_parser(b"1 0 obj\n42\nstream\nendstream")
    try:
        with pytest.raises(PDFParseError, match="not a dictionary"):
            parser._handle_xref_stream_at(0)  # noqa: SLF001
    finally:
        doc.close()


def test_wave674_decode_xref_stream_rejects_non_integer_width() -> None:
    parser = _parser()
    stream = COSStream()
    stream.set_item("W", COSArray([COSInteger.get(1), COSName.FILTER, COSInteger.get(1)]))  # type: ignore[attr-defined]
    stream.set_item("Size", COSInteger.get(1))
    stream.set_raw_data(b"\x01\x00\x00")

    with pytest.raises(PDFParseError, match=r"/W\[1\]"):
        parser._decode_xref_stream_entries(stream)  # noqa: SLF001


def test_wave674_decode_xref_stream_rejects_odd_index_length() -> None:
    parser = _parser()
    stream = COSStream()
    stream.set_item("W", COSArray([COSInteger.get(1), COSInteger.get(1), COSInteger.get(1)]))
    stream.set_item("Index", COSArray([COSInteger.get(0)]))
    stream.set_raw_data(b"\x01\x00\x00")

    with pytest.raises(PDFParseError, match="odd length"):
        parser._decode_xref_stream_entries(stream)  # noqa: SLF001


def test_wave674_indirect_loader_rejects_stream_body_without_dictionary() -> None:
    parser, doc = _ready_parser(b"1 0 obj\n42\nstream\nendstream\nendobj")
    try:
        obj = doc.get_object_from_pool(COSObjectKey(1, 0))
        with pytest.raises(PDFParseError, match="not a dictionary"):
            parser._load_indirect_object_at(0, obj)  # noqa: SLF001
    finally:
        doc.close()


def test_wave674_compressed_object_index_bounds_are_checked() -> None:
    parser, doc = _ready_parser(b"")
    try:
        objstm = COSStream()
        objstm.set_item(COSName.TYPE, COSName.get_pdf_name("ObjStm"))
        objstm.set_item("N", COSInteger.get(1))
        objstm.set_item("First", COSInteger.get(4))
        objstm.set_raw_data(b"8 0 42")
        doc.get_object_from_pool(COSObjectKey(7, 0)).set_object(objstm)

        with pytest.raises(PDFParseError, match="out of range"):
            parser._load_compressed_object(7, 1, COSObject(8, 0))  # noqa: SLF001
    finally:
        doc.close()
