from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature
from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation


def test_wave485_document_information_replaces_malformed_info_and_clears_cache() -> None:
    doc = PDDocument()
    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    trailer.set_item(COSName.INFO, COSName.get_pdf_name("BadInfo"))  # type: ignore[attr-defined]

    info = doc.get_document_information()

    assert isinstance(info, PDDocumentInformation)
    assert doc.has_document_information()
    assert trailer.get_dictionary_object(COSName.INFO) is info.get_cos_object()  # type: ignore[attr-defined]
    assert doc.get_document_information() is info

    doc.clear_document_information()

    assert not doc.has_document_information()
    assert doc.get_document_information() is not info
    doc.close()


def test_wave485_add_signature_wires_form_field_and_page_annotation() -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        signature = PDSignature()
        options = object()

        doc.add_signature(signature, options=options)

        assert doc.has_pending_signature()
        assert doc.get_pending_signature() is signature
        assert doc.get_signature_options() is options
        assert doc.is_signature_added()
        assert signature.get_filter() == "Adobe.PPKLite"
        assert signature.get_sub_filter() == "adbe.pkcs7.detached"
        assert doc.has_signatures()
        signatures = doc.get_signature_dictionaries()
        assert len(signatures) == 1
        assert signatures[0].get_cos_object() is signature.get_cos_object()
        assert (
            doc.get_last_signature_dictionary().get_cos_object()
            is signature.get_cos_object()
        )

        page_dict = doc.get_page(0).get_cos_object()
        annots = page_dict.get_dictionary_object(COSName.get_pdf_name("Annots"))
        assert isinstance(annots, COSArray)
        assert annots.size() == 1
        field_dict = annots.get_object(0)
        assert isinstance(field_dict, COSDictionary)
        assert field_dict.get_name("FT") == "Sig"
        assert field_dict.get_dictionary_object("V") is signature.get_cos_object()

        with pytest.raises(ValueError, match="Only one signature"):
            doc.add_signature(PDSignature())
    finally:
        doc.close()


def test_wave485_add_signature_rejects_non_signature() -> None:
    doc = PDDocument()

    with pytest.raises(TypeError, match="PDSignature"):
        doc.add_signature(object())  # type: ignore[arg-type]
    doc.close()


def test_wave485_import_page_deep_copies_page_dictionary_and_stream_data() -> None:
    source = PDDocument()
    page = PDPage()
    stream = COSStream()
    stream.set_raw_data(b"page bytes")
    page_dict = page.get_cos_object()
    page_dict.set_item(COSName.CONTENTS, stream)  # type: ignore[attr-defined]
    source.add_page(page)

    target = PDDocument()
    imported = target.import_page(page)
    imported_dict = imported.get_cos_object()
    imported_stream = imported_dict.get_dictionary_object(COSName.CONTENTS)  # type: ignore[attr-defined]

    assert imported_dict is not page_dict
    imported_parent = imported_dict.get_dictionary_object(COSName.PARENT)  # type: ignore[attr-defined]
    source_parent = page_dict.get_dictionary_object(COSName.PARENT)  # type: ignore[attr-defined]
    assert imported_parent is not None
    assert imported_parent is not source_parent
    assert isinstance(imported_stream, COSStream)
    assert imported_stream is not stream
    assert imported_stream.get_raw_data() == b"page bytes"
    assert target.get_number_of_pages() == 1

    source.close()
    target.close()


def test_wave485_closed_document_guards_page_convenience_helpers() -> None:
    doc = PDDocument()
    doc.close()

    with pytest.raises(ValueError, match="closed PDDocument"):
        doc.split()
    with pytest.raises(ValueError, match="closed PDDocument"):
        doc.extract_pages(1, 1)


def test_wave485_merge_without_documents_returns_empty_document() -> None:
    merged = PDDocument.merge()

    assert isinstance(merged, PDDocument)
    assert merged.get_number_of_pages() == 0
    merged.close()
