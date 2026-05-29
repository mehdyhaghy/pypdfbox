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
    COSString,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError, PDFParser
from pypdfbox.pdfparser.xref_trailer_resolver import XrefType


def _parser(data: bytes = b"") -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


def _ready_parser(data: bytes) -> tuple[PDFParser, COSDocument]:
    parser = _parser(data)
    doc = parser._document = COSDocument()  # noqa: SLF001
    parser._cos_parser = COSParser(parser._src, document=doc)  # noqa: SLF001
    return parser, doc


def test_wave664_prepare_security_handler_accepts_bytes_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pypdfbox.pdmodel.encryption.pd_encryption as pd_encryption_module
    import pypdfbox.pdmodel.encryption.standard_security_handler as handler_module

    captured: dict[str, object] = {}

    class FakePDEncryption:
        def __init__(self, dictionary: COSDictionary) -> None:
            captured["dictionary"] = dictionary

    class FakeMaterial:
        def __init__(self, password: bytes) -> None:
            captured["password"] = password

    class FakeHandler:
        def __init__(self, encryption: FakePDEncryption) -> None:
            captured["handler_encryption"] = encryption

        def prepare_for_decryption(
            self,
            encryption: FakePDEncryption,
            document_id: bytes,
            material: FakeMaterial,
        ) -> None:
            captured["prepared"] = (encryption, document_id, material)

    monkeypatch.setattr(pd_encryption_module, "PDEncryption", FakePDEncryption)
    monkeypatch.setattr(handler_module, "StandardDecryptionMaterial", FakeMaterial)
    monkeypatch.setattr(handler_module, "StandardSecurityHandler", FakeHandler)

    parser = _parser()
    parser.set_password(b"secret")
    trailer = COSDictionary()
    encrypt = COSDictionary()
    trailer.set_item(COSName.ENCRYPT, encrypt)
    ids = COSArray()
    ids.add(COSString(b"file-id"))
    trailer.set_item("ID", ids)
    resolver = parser.get_xref_trailer_resolver()
    resolver.begin_section(0)
    resolver.set_trailer(trailer)

    handler = parser._prepare_security_handler_if_needed()  # noqa: SLF001

    assert isinstance(handler, FakeHandler)
    assert captured["dictionary"] is encrypt
    assert captured["password"] == b"secret"
    assert captured["prepared"][1] == b"file-id"  # type: ignore[index]


def test_wave664_resolve_document_id_rejects_empty_or_non_string_arrays() -> None:
    parser = _parser()
    trailer = COSDictionary()
    trailer.set_item("ID", COSArray())
    assert parser._resolve_document_id(trailer) is None  # noqa: SLF001

    ids = COSArray()
    ids.add(COSInteger.get(42))
    trailer.set_item("ID", ids)
    assert parser._resolve_document_id(trailer) is None  # noqa: SLF001


def test_wave664_xref_shape_check_rejects_scalar_indirect_body() -> None:
    parser, doc = _ready_parser(b"1 0 obj\n42\nendobj")
    try:
        assert parser._xref_section_starts_at(0) is False  # noqa: SLF001
    finally:
        doc.close()


def test_wave664_decode_xref_stream_records_unknown_type_as_free_entry() -> None:
    parser = _parser()
    stream = COSStream()
    stream.set_item("W", COSArray([COSInteger.get(1), COSInteger.get(1), COSInteger.get(1)]))
    stream.set_item("Size", COSInteger.get(1))
    stream.set_raw_data(b"\x03\x63\x04")
    parser.get_xref_trailer_resolver().begin_section(0)

    parser._decode_xref_stream_entries(stream)  # noqa: SLF001

    entry = parser.get_xref_trailer_resolver().get_xref_table()[COSObjectKey(0, 0)]
    assert entry.type is XrefType.STREAM
    assert entry.offset == 0
    assert entry.compressed_index == -1


def test_wave664_load_compressed_object_tolerates_header_object_number_mismatch() -> None:
    parser, doc = _ready_parser(b"")
    try:
        objstm = COSStream()
        objstm.set_item(COSName.TYPE, COSName.get_pdf_name("ObjStm"))
        objstm.set_item("N", COSInteger.get(1))
        objstm.set_item("First", COSInteger.get(4))
        objstm.set_raw_data(b"9 0 42")
        doc.get_object_from_pool(COSObjectKey(7, 0)).set_object(objstm)

        loaded = parser._load_compressed_object(7, 0, COSObject(8, 0))  # noqa: SLF001

        assert isinstance(loaded, COSInteger)
        assert loaded.value == 42
    finally:
        doc.close()


def test_wave664_indirect_loader_stream_strict_rejects_wrong_endobj_keyword() -> None:
    # Strict mode mirrors upstream parseFileObject (Java line 691): a stream
    # object whose closing keyword is not 'endobj' is an IOError.
    parser, doc = _ready_parser(b"1 0 obj\n<< /Length 0 >>\nstream\nendstream\nwrong")
    parser.set_lenient(False)
    try:
        obj = doc.get_object_from_pool(COSObjectKey(1, 0))
        with pytest.raises(PDFParseError, match="does not end with 'endobj'"):
            parser._load_indirect_object_at(0, obj)  # noqa: SLF001
    finally:
        doc.close()


def test_wave664_indirect_loader_stream_lenient_warns_on_wrong_endobj() -> None:
    # Lenient mode (the default, matching upstream isLenient=true) only warns
    # and keeps the recovered stream when the closing keyword is not 'endobj'
    # (Java lines 682-688) — the embedded-endstream recovery path relies on
    # this, since the scan can leave the cursor mid-body.
    parser, doc = _ready_parser(b"1 0 obj\n<< /Length 0 >>\nstream\nendstream\nwrong")
    try:
        obj = doc.get_object_from_pool(COSObjectKey(1, 0))
        result = parser._load_indirect_object_at(0, obj)  # noqa: SLF001
        assert isinstance(result, COSStream)
    finally:
        doc.close()
