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

    with pytest.raises(ValueError, match="requires a loaded document with a source"):
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


def test_wave516_add_signature_without_pages_still_stages_field_tree() -> None:
    doc = PDDocument()
    signature = PDSignature()

    doc.add_signature(signature)

    assert doc.has_pending_signature()
    assert doc.has_signatures()
    assert doc.get_last_signature_dictionary().get_cos_object() is signature.get_cos_object()
    fields = doc.get_signature_fields()
    assert len(fields) == 1
    assert fields[0].get_signature().get_cos_object() is signature.get_cos_object()
    doc.close()


def test_wave516_external_signing_requires_pending_signature() -> None:
    doc = PDDocument()

    with pytest.raises(ValueError, match="requires a prior add_signature"):
        doc.save_incremental_for_external_signing(io.BytesIO())

    doc.close()
