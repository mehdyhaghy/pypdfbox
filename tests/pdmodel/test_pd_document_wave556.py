from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary, COSDocument, COSName
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdmodel import PDDocument, PDDocumentCatalog, PDPage
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature
from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation


def test_wave556_get_pdf_source_reflects_constructor_source_override() -> None:
    source = RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n")
    doc = PDDocument(source=source)

    try:
        assert doc.get_pdf_source() is source
    finally:
        doc.close()


def test_wave556_set_document_information_creates_missing_trailer() -> None:
    cos_doc = COSDocument()
    info = PDDocumentInformation(COSDictionary())
    doc = PDDocument(cos_doc)

    try:
        doc.set_document_information(info)

        trailer = cos_doc.get_trailer()
        assert trailer is not None
        assert trailer.get_dictionary_object(COSName.INFO) is info.get_cos_object()  # type: ignore[attr-defined]
        assert doc.get_document_information() is info
    finally:
        doc.close()


def test_wave556_set_version_uses_catalog_when_header_supports_override() -> None:
    doc = PDDocument()

    try:
        doc.set_version(1.7)

        assert doc.get_document().get_version() == pytest.approx(1.4)
        assert doc.get_document_catalog().get_version() == "1.7"
        assert doc.get_version() == pytest.approx(1.7)
    finally:
        doc.close()


def test_wave556_save_incremental_marks_extra_objects_and_rejects_non_dict(
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
    extra = COSDictionary()

    try:
        doc.save_incremental(io.BytesIO(), {extra})

        assert extra.is_needs_to_be_updated() is True
        assert writes == [cos_doc]

        with pytest.raises(TypeError, match="COSDictionary"):
            doc.save_incremental(io.BytesIO(), {COSName.get_pdf_name("Bad")})  # type: ignore[arg-type]
    finally:
        doc.close()


def test_wave556_add_signature_preserves_existing_filter_values() -> None:
    doc = PDDocument()
    # add_signature refuses a page-less document upstream.
    doc.add_page(PDPage())
    signature = PDSignature()
    signature.set_filter("Custom.Filter")
    signature.set_sub_filter("custom.subfilter")

    try:
        doc.add_signature(signature)

        assert signature.get_filter() == "Custom.Filter"
        assert signature.get_sub_filter() == "custom.subfilter"
    finally:
        doc.close()


def test_wave556_save_and_external_signing_reject_closed_document() -> None:
    doc = PDDocument()
    doc.close()

    with pytest.raises(OSError, match="Cannot save a document which has been closed"):
        doc.save(io.BytesIO())
    with pytest.raises(OSError, match="Cannot save a document which has been closed"):
        doc.save_incremental_for_external_signing(io.BytesIO())


def test_wave556_page_removal_by_index_and_repr_after_close() -> None:
    doc = PDDocument()
    doc.add_page(PDPage())
    doc.add_page(PDPage())

    assert "pages=2" in repr(doc)

    doc.remove_page(0)

    assert doc.get_number_of_pages() == 1

    doc.close()

    assert "pages=?" in repr(doc)


def test_wave556_set_document_catalog_accepts_fresh_catalog_after_clear() -> None:
    doc = PDDocument()
    doc.clear_document_catalog()
    catalog = PDDocumentCatalog(doc, COSDictionary())

    try:
        doc.set_document_catalog(catalog)

        assert doc.has_document_catalog() is True
        assert doc.get_document_catalog() is catalog
    finally:
        doc.close()
