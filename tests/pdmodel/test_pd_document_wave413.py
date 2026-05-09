from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSDictionary, COSDocument, COSName, COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdmodel import PDDocument, PDDocumentCatalog
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)


def test_set_document_catalog_requires_catalog_and_dictionary_wave413() -> None:
    doc = PDDocument()

    with pytest.raises(TypeError, match="must not be None"):
        doc.set_document_catalog(None)  # type: ignore[arg-type]

    class BadCatalog:
        def get_cos_object(self) -> COSName:
            return COSName.get_pdf_name("Catalog")

    with pytest.raises(TypeError, match="COSDictionary"):
        doc.set_document_catalog(BadCatalog())  # type: ignore[arg-type]


def test_set_document_catalog_creates_missing_trailer_and_invalidates_pages_wave413() -> None:
    cos_doc = COSDocument()
    doc = PDDocument(cos_doc)
    catalog = PDDocumentCatalog(doc, COSDictionary())

    doc.set_document_catalog(catalog)

    trailer = cos_doc.get_trailer()
    assert trailer is not None
    assert trailer.get_dictionary_object(COSName.ROOT) is catalog.get_cos_object()  # type: ignore[attr-defined]
    assert doc.get_document_catalog() is catalog


def test_has_and_clear_trailer_entries_do_not_materialize_wrappers_wave413() -> None:
    doc = PDDocument()
    trailer = doc.get_document().get_trailer()
    assert trailer is not None

    trailer.set_item(COSName.INFO, COSName.get_pdf_name("BadInfo"))  # type: ignore[attr-defined]
    trailer.set_item(COSName.ENCRYPT, COSName.get_pdf_name("BadEncrypt"))  # type: ignore[attr-defined]

    assert doc.has_document_catalog()
    assert not doc.has_document_information()
    assert not doc.has_encryption_dictionary()
    assert doc.is_encrypted()

    doc.clear_document_catalog()
    doc.clear_document_information()
    doc.clear_encryption_dictionary()

    assert not doc.has_document_catalog()
    assert not doc.has_document_information()
    assert not doc.has_encryption_dictionary()
    assert not doc.is_encrypted()


def test_set_encryption_dictionary_accepts_raw_dict_and_clear_wave413() -> None:
    doc = PDDocument()
    encryption = COSDictionary()

    doc.set_encryption_dictionary(encryption)

    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    assert trailer.get_dictionary_object(COSName.ENCRYPT) is encryption  # type: ignore[attr-defined]
    assert doc.has_encryption_dictionary()

    doc.clear_encryption_dictionary()

    assert trailer.get_dictionary_object(COSName.ENCRYPT) is None  # type: ignore[attr-defined]
    assert doc.get_encryption() is None


def test_get_version_ignores_malformed_catalog_version_wave413(
    caplog: pytest.LogCaptureFixture,
) -> None:
    doc = PDDocument()
    doc.get_document_catalog().set_version("not-a-number")

    with caplog.at_level(logging.ERROR, logger="pypdfbox.pdmodel.pd_document"):
        assert doc.get_version() == 1.4

    assert "Can't extract the version number" in caplog.text


def test_set_version_equal_and_lower_are_noops_wave413() -> None:
    cos_doc = COSDocument()
    cos_doc.set_version(1.3)
    cos_doc.set_trailer(COSDictionary())
    doc = PDDocument(cos_doc)

    doc.set_version(1.3)
    doc.set_version(1.2)

    assert doc.get_document().get_version() == 1.3


def test_document_id_seed_validates_type_and_clears_wave413() -> None:
    doc = PDDocument()

    doc.set_document_id(123)
    assert doc.get_document_id() == 123
    doc.set_document_id(None)
    assert doc.get_document_id() is None

    with pytest.raises(TypeError, match="expected int or None"):
        doc.set_document_id("123")  # type: ignore[arg-type]


def test_protect_resets_security_removal_flag_and_stores_policy_wave413(
    caplog: pytest.LogCaptureFixture,
) -> None:
    doc = PDDocument()
    policy = StandardProtectionPolicy("owner", "user", AccessPermission())
    doc.set_all_security_to_be_removed(True)

    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.pd_document"):
        doc.protect(policy)

    assert not doc.is_all_security_to_be_removed()
    assert "set_all_security_to_be_removed(False)" in caplog.text


def test_current_access_permission_caches_unencrypted_owner_permission_wave413() -> None:
    doc = PDDocument()

    first = doc.get_current_access_permission()
    second = doc.get_current_access_permission()

    assert first is second
    assert first.is_owner_permission()


def test_current_access_permission_uses_handler_and_encrypted_no_permission_wave413() -> None:
    class Handler:
        def __init__(self) -> None:
            self.permission = AccessPermission(7)

        def get_current_access_permission(self) -> AccessPermission:
            return self.permission

    doc = PDDocument()
    handler = Handler()
    doc._security_handler = handler  # noqa: SLF001

    assert doc.get_current_access_permission() is handler.permission

    encrypted = PDDocument()
    trailer = encrypted.get_document().get_trailer()
    assert trailer is not None
    trailer.set_item(COSName.ENCRYPT, COSDictionary())  # type: ignore[attr-defined]

    first = encrypted.get_current_access_permission()
    second = encrypted.get_current_access_permission()

    assert first is not second
    assert not first.is_owner_permission()


def test_requires_full_save_reflects_source_and_dirty_objects_wave413() -> None:
    cos_doc = COSDocument(source=RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n"))
    doc = PDDocument(cos_doc)

    assert doc.requires_full_save()

    indirect = cos_doc.get_object_from_pool(COSObjectKey(7, 0))
    indirect.set_needs_to_be_updated(True)

    assert not doc.requires_full_save()


def test_font_close_and_subset_collections_are_live_wave413() -> None:
    doc = PDDocument()
    font = object()
    subset = object()

    doc.register_true_type_font_for_closing(font)
    doc.get_fonts_to_subset().add(subset)

    assert doc.get_fonts_to_close() == [font]
    assert subset in doc.get_fonts_to_subset()
    doc.get_fonts_to_close().clear()
    assert doc.get_fonts_to_close() == []
