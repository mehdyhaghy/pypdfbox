from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary, COSDocument, COSName
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature


def test_wave516_context_manager_closes_owned_cos_document_once() -> None:
    cos_doc = COSDocument()

    with PDDocument(cos_doc) as doc:
        assert not doc.is_closed()
        assert not cos_doc.is_closed()

    assert doc.is_closed()
    assert cos_doc.is_closed()

    doc.close()
    assert doc.is_closed()


def test_wave516_save_incremental_requires_loaded_source_before_writing() -> None:
    doc = PDDocument()

    with pytest.raises(
        RuntimeError, match="document was not loaded from a file or a stream"
    ):
        doc.save_incremental(io.BytesIO())

    doc.close()


def test_wave516_set_encryption_dictionary_accepts_wrapper_and_creates_trailer() -> None:
    class EncryptionWrapper:
        def __init__(self) -> None:
            self.cos = COSDictionary()

        def get_cos_object(self) -> COSDictionary:
            return self.cos

    cos_doc = COSDocument()
    doc = PDDocument(cos_doc)
    wrapper = EncryptionWrapper()

    doc.set_encryption_dictionary(wrapper)

    trailer = cos_doc.get_trailer()
    assert trailer is not None
    assert trailer.get_dictionary_object(COSName.ENCRYPT) is wrapper.cos  # type: ignore[attr-defined]
    assert doc.get_encryption() is wrapper


def test_wave516_get_encryption_wraps_raw_trailer_dictionary_once() -> None:
    doc = PDDocument()
    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    trailer.set_item(COSName.ENCRYPT, COSDictionary())  # type: ignore[attr-defined]

    first = doc.get_encryption()
    second = doc.get_encryption()

    assert first is second
    assert first.get_cos_object() is trailer.get_dictionary_object(COSName.ENCRYPT)  # type: ignore[attr-defined]
    doc.close()


def test_wave516_add_signature_stages_field_tree() -> None:
    from pypdfbox.pdmodel import PDPage

    doc = PDDocument()
    # Upstream refuses to sign a page-less document ("Cannot sign an empty
    # document", PDDocument.java line 345), so a page is required before
    # add_signature can wire the field tree.
    doc.add_page(PDPage())
    signature = PDSignature()

    doc.add_signature(signature)

    assert doc.has_pending_signature()
    assert doc.has_signatures()
    assert doc.get_last_signature_dictionary().get_cos_object() is signature.get_cos_object()
    fields = doc.get_signature_fields()
    assert len(fields) == 1
    assert fields[0].get_signature().get_cos_object() is signature.get_cos_object()
    doc.close()


def test_wave516_external_signing_requires_source() -> None:
    # A created (no-source) document hits the source check first, matching
    # upstream order (PDDocument.java line 1174 before 1190). Upstream raises
    # IllegalStateException → RuntimeError with the upstream-exact message
    # (oracle-confirmed against PDFBox 3.0.7, PDDocumentSignStateProbe).
    doc = PDDocument()

    with pytest.raises(
        RuntimeError, match="document was not loaded from a file or a stream"
    ):
        doc.save_incremental_for_external_signing(io.BytesIO())

    doc.close()
