from __future__ import annotations

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
from pypdfbox.pdfparser import COSParser, PDFParser


def _parser(data: bytes = b"") -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


def test_wave644_trailer_encryption_and_document_id_accessors() -> None:
    parser = _parser()

    assert parser.get_encryption_dictionary() is None
    assert parser.get_document_id() is None

    encrypt = COSDictionary()
    encrypt.set_item("Filter", COSName.get_pdf_name("Standard"))
    ids = COSArray()
    ids.add(COSString(b"primary-id"))
    ids.add(COSString(b"secondary-id"))
    trailer = COSDictionary()
    trailer.set_item(COSName.ENCRYPT, encrypt)
    trailer.set_item("ID", ids)
    parser.get_xref_trailer_resolver().begin_section(0)
    parser.get_xref_trailer_resolver().set_trailer(trailer)

    assert parser.get_encryption_dictionary() is encrypt
    assert parser.get_document_id() == b"primary-id"


def test_wave644_get_root_ignores_missing_or_non_dictionary_root() -> None:
    parser = _parser()
    parser.get_xref_trailer_resolver().begin_section(0)
    parser.get_xref_trailer_resolver().set_trailer(COSDictionary())
    assert parser.get_root() is None

    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, COSInteger.get(7))
    parser.get_xref_trailer_resolver().begin_section(1)
    parser.get_xref_trailer_resolver().set_trailer(trailer)

    assert parser.get_root() is None


def test_wave644_read_stream_body_rewinds_after_resolving_length() -> None:
    data = b"4 0 obj\n3\nendobj\nABC\nendstream\n"
    parser = _parser(data)
    doc = parser._document = COSDocument()  # noqa: SLF001
    parser._cos_parser = COSParser(parser._src, document=doc)  # noqa: SLF001
    try:
        length_ref = doc.get_object_from_pool(COSObjectKey(4, 0))
        length_ref.set_loader(
            lambda obj: parser._load_indirect_object_at(0, obj)  # noqa: SLF001
        )
        stream = COSStream()
        stream.set_item(COSName.LENGTH, length_ref)
        parser._src.seek(data.index(b"\nABC"))  # noqa: SLF001

        parser._read_stream_body(stream)  # noqa: SLF001

        assert stream.get_raw_data() == b"ABC"
        assert parser._src.get_position() > data.index(b"endstream")  # noqa: SLF001
    finally:
        doc.close()


def test_wave644_read_stream_body_recovers_negative_direct_length() -> None:
    """A negative direct /Length fails ``validate_stream_length`` and the body
    is recovered by scanning to ``endstream`` in lenient mode, mirroring
    upstream PDFBox ``parseCOSStream``. (Wave 1517 — formerly pypdfbox raised a
    fail-fast ``PDFParseError`` on a negative length.)"""
    parser = _parser(b"\nABC\nendstream\n")
    stream = COSStream()
    stream.set_item(COSName.LENGTH, COSInteger.get(-1))

    parser._read_stream_body(stream)  # noqa: SLF001
    assert stream.get_raw_data() == b"ABC"
