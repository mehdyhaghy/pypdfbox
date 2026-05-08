"""Wave 284 coverage for PDDocument trailer helpers and malformed COS values."""

from __future__ import annotations

from pypdfbox import PDDocument
from pypdfbox.cos import COSDictionary, COSDocument, COSName


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_has_document_catalog_is_read_only_for_malformed_root_wave284() -> None:
    bad_root = _name("NotACatalog")
    trailer = COSDictionary()
    trailer.set_item(_name("Root"), bad_root)
    cos_doc = COSDocument()
    cos_doc.set_trailer(trailer)
    doc = PDDocument(cos_doc)

    assert doc.has_document_catalog() is False
    assert trailer.get_item(_name("Root")) is bad_root

    catalog = doc.get_document_catalog()

    assert doc.has_document_catalog() is True
    assert trailer.get_item(_name("Root")) is catalog.get_cos_object()
    doc.close()


def test_clear_document_catalog_removes_root_and_invalidates_caches_wave284() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    pages = doc.get_pages()

    doc.clear_document_catalog()

    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    assert trailer.get_item(_name("Root")) is None
    assert doc.has_document_catalog() is False

    assert doc.get_document_catalog() is not catalog
    assert doc.get_pages() is not pages
    assert doc.has_document_catalog() is True
    doc.close()


def test_has_document_information_treats_malformed_info_as_absent_wave284() -> None:
    doc = PDDocument()
    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    bad_info = _name("NotInfo")
    trailer.set_item(_name("Info"), bad_info)

    assert doc.has_document_information() is False
    assert trailer.get_item(_name("Info")) is bad_info

    info = doc.get_document_information()

    assert doc.has_document_information() is True
    assert trailer.get_item(_name("Info")) is info.get_cos_object()
    doc.close()


def test_clear_document_information_removes_info_and_cached_wrapper_wave284() -> None:
    doc = PDDocument()
    info = doc.get_document_information()

    assert doc.has_document_information() is True

    doc.clear_document_information()

    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    assert trailer.get_item(_name("Info")) is None
    assert doc.has_document_information() is False
    assert doc.get_document_information() is not info
    doc.close()


def test_encryption_dictionary_helpers_distinguish_malformed_entry_wave284() -> None:
    doc = PDDocument()
    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    trailer.set_item(_name("Encrypt"), _name("BadEncrypt"))

    assert doc.is_encrypted() is True
    assert doc.has_encryption_dictionary() is False
    assert doc.get_encryption() is None

    enc = COSDictionary()
    doc.set_encryption_dictionary(enc)

    assert doc.is_encrypted() is True
    assert doc.has_encryption_dictionary() is True

    doc.clear_encryption_dictionary()

    assert doc.is_encrypted() is False
    assert doc.has_encryption_dictionary() is False
    assert trailer.get_item(_name("Encrypt")) is None
    doc.close()
