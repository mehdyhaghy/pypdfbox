from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

from pypdfbox.cos import COSDictionary, COSDocument, COSName
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer, RandomAccessWriteBuffer
from pypdfbox.pdmodel import PDDocument, PDDocumentCatalog, PDDocumentInformation
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)


def test_wave596_presence_predicates_ignore_malformed_entries() -> None:
    doc = PDDocument()
    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    trailer.set_item(COSName.ROOT, COSName.get_pdf_name("NotADict"))  # type: ignore[attr-defined]
    trailer.set_item(COSName.INFO, COSName.get_pdf_name("NotADict"))  # type: ignore[attr-defined]
    trailer.set_item(COSName.ENCRYPT, COSName.get_pdf_name("NotADict"))  # type: ignore[attr-defined]

    try:
        assert doc.has_document_catalog() is False
        assert doc.has_document_information() is False
        assert doc.has_encryption_dictionary() is False
    finally:
        doc.close()


def test_wave596_clear_helpers_remove_trailer_entries_and_caches() -> None:
    doc = PDDocument()
    doc.get_document_catalog()
    doc.get_document_information()
    doc.set_encryption_dictionary(COSDictionary())

    try:
        doc.clear_document_catalog()
        doc.clear_document_information()
        doc.clear_encryption_dictionary()

        trailer = doc.get_document().get_trailer()
        assert trailer is not None
        assert trailer.get_dictionary_object(COSName.ROOT) is None  # type: ignore[attr-defined]
        assert trailer.get_dictionary_object(COSName.INFO) is None  # type: ignore[attr-defined]
        assert trailer.get_dictionary_object(COSName.ENCRYPT) is None  # type: ignore[attr-defined]
        assert doc._catalog is None  # noqa: SLF001
        assert doc._pages is None  # noqa: SLF001
        assert doc._document_information is None  # noqa: SLF001
    finally:
        doc.close()


def test_wave596_setters_create_missing_trailer() -> None:
    cos_doc = COSDocument()
    cos_doc.set_trailer(None)
    doc = PDDocument(cos_doc)
    new_catalog = PDDocumentCatalog(doc, COSDictionary())
    info = PDDocumentInformation()
    encryption = COSDictionary()

    try:
        doc.set_document_catalog(new_catalog)
        doc.set_document_information(info)
        doc.set_encryption_dictionary(encryption)

        trailer = cos_doc.get_trailer()
        assert trailer is not None
        assert trailer.get_dictionary_object(COSName.ROOT) is new_catalog.get_cos_object()  # type: ignore[attr-defined]
        assert trailer.get_dictionary_object(COSName.INFO) is info.get_cos_object()  # type: ignore[attr-defined]
        assert trailer.get_dictionary_object(COSName.ENCRYPT) is encryption  # type: ignore[attr-defined]
    finally:
        doc.close()


def test_wave596_save_incremental_marks_requested_objects_and_rejects_non_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writes: list[COSDocument] = []

    class Writer:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> Writer:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

        def write(self, document: COSDocument) -> None:
            writes.append(document)

    import pypdfbox.pdfwriter as pdfwriter

    monkeypatch.setattr(pdfwriter, "COSWriter", Writer)
    cos_doc = COSDocument(source=RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n"))
    doc = PDDocument(cos_doc)
    forced = COSDictionary()

    try:
        doc.save_incremental(io.BytesIO(), {forced})

        assert forced.is_needs_to_be_updated() is True
        assert writes == [cos_doc]
        with pytest.raises(TypeError, match="COSDictionary"):
            doc.save_incremental(io.BytesIO(), {object()})  # type: ignore[arg-type]
    finally:
        doc.close()


def test_wave596_write_bytes_to_random_access_write_buffer() -> None:
    sink = RandomAccessWriteBuffer()

    PDDocument._write_bytes_to_target(b"abc", sink)  # noqa: SLF001

    assert sink.to_bytes() == b"abc"


def test_wave596_signature_dictionary_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    first = object()
    second = object()
    fields = [
        SimpleNamespace(get_signature=lambda: None),
        SimpleNamespace(get_signature=lambda: first),
        SimpleNamespace(get_signature=lambda: second),
    ]
    doc = PDDocument()
    monkeypatch.setattr(doc, "get_signature_fields", lambda: fields)

    try:
        assert doc.get_signature_dictionaries() == [first, second]
        assert doc.has_signatures() is True
        assert doc.get_last_signature_dictionary() is second

        monkeypatch.setattr(
            doc,
            "get_signature_fields",
            lambda: [SimpleNamespace(get_signature=lambda: None)],
        )
        assert doc.has_signatures() is False
        assert doc.get_last_signature_dictionary() is None
    finally:
        doc.close()


def test_wave596_requires_full_save_false_when_object_or_inner_dirty() -> None:
    cos_doc = COSDocument(source=RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n"))
    cos_obj = cos_doc.get_object_from_pool(COSObjectKey(4))
    cos_obj.set_object(COSDictionary())
    doc = PDDocument(cos_doc)

    try:
        cos_obj.set_needs_to_be_updated(True)
        assert doc.requires_full_save() is False
        cos_obj.set_needs_to_be_updated(False)
        inner = cos_obj.get_object()
        assert inner is not None
        inner.set_needs_to_be_updated(True)
        assert doc.requires_full_save() is False
    finally:
        doc.close()


def test_wave596_access_permission_uses_handler_and_caches() -> None:
    permission = object()
    handler = SimpleNamespace(get_current_access_permission=lambda: permission)
    doc = PDDocument()
    doc._security_handler = handler  # noqa: SLF001

    try:
        assert doc.get_current_access_permission() is permission
        doc._security_handler = SimpleNamespace(  # noqa: SLF001
            get_current_access_permission=lambda: object()
        )
        assert doc.get_current_access_permission() is permission
    finally:
        doc.close()


def test_wave596_protect_clears_security_removal_flag() -> None:
    doc = PDDocument()
    policy = StandardProtectionPolicy()
    doc.set_all_security_to_be_removed(True)

    try:
        doc.protect(policy)

        assert doc.is_all_security_to_be_removed() is False
        assert doc._protection_policy is policy  # noqa: SLF001
    finally:
        doc.close()


def test_wave596_closed_split_and_extract_raise() -> None:
    doc = PDDocument()
    doc.close()

    with pytest.raises(OSError, match="PDDocument has been closed"):
        doc.split()
    with pytest.raises(OSError, match="PDDocument has been closed"):
        doc.extract_pages(1, 1)
