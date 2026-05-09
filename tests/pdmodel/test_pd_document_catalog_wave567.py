from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSDocument, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDDocumentCatalog
from pypdfbox.pdmodel.graphics.color import PDOutputIntent
from pypdfbox.pdmodel.interactive.pagenavigation import PDThread


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_wave567_catalog_constructor_synthesizes_missing_root_and_type() -> None:
    cos_doc = COSDocument()
    doc = PDDocument(cos_doc)

    catalog = doc.get_document_catalog()

    trailer = cos_doc.get_trailer()
    assert trailer is not None
    assert trailer.get_dictionary_object(COSName.ROOT) is catalog.get_cos_object()  # type: ignore[attr-defined]
    assert catalog.get_cos_object().get_name(COSName.TYPE) == "Catalog"  # type: ignore[attr-defined]


def test_wave567_explicit_catalog_gets_type_and_replaces_bad_pages() -> None:
    with PDDocument() as doc:
        raw_catalog = COSDictionary()
        raw_catalog.set_item(_name("Pages"), COSArray())
        catalog = PDDocumentCatalog(doc, raw_catalog)

        pages = catalog.get_pages()

        assert raw_catalog.get_name(COSName.TYPE) == "Catalog"  # type: ignore[attr-defined]
        assert raw_catalog.get_dictionary_object(_name("Pages")) is pages.get_cos_object()


def test_wave567_metadata_raw_stream_round_trips_and_clears() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        metadata = COSStream()

        catalog.set_metadata(metadata)

        assert catalog.has_metadata() is True
        assert catalog.get_metadata().get_cos_object() is metadata

        catalog.clear_metadata()
        assert catalog.get_metadata() is None
        assert catalog.has_metadata() is False


def test_wave567_actions_accept_raw_dictionary_and_has_actions_is_read_only() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        raw_actions = COSDictionary()

        catalog.set_actions(raw_actions)
        assert catalog.get_actions().get_cos_object() is raw_actions
        assert catalog.has_actions() is False

        raw_actions.set_item(_name("WC"), COSDictionary())
        assert catalog.has_actions() is True

        catalog.clear_actions()
        assert catalog.has_actions() is False
        assert catalog.get_cos_object().get_dictionary_object(_name("AA")) is None


def test_wave567_optional_content_alias_accepts_raw_dictionary_and_bumps_version() -> None:
    with PDDocument() as doc:
        doc.set_version(1.4)
        catalog = doc.get_document_catalog()
        raw_oc = COSDictionary()

        catalog.set_optional_content_properties(raw_oc)

        assert catalog.get_optional_content_properties().get_cos_object() is raw_oc
        assert catalog.has_oc_properties() is True
        assert doc.get_version() == 1.5

        catalog.clear_optional_content_properties()
        assert catalog.get_optional_content_properties() is None


def test_wave567_output_intents_skip_bad_entries_and_reject_bad_setter_input() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        good = PDOutputIntent()
        arr = COSArray()
        arr.add(COSName.get_pdf_name("bad"))
        arr.add(good.get_cos_object())
        catalog.get_cos_object().set_item(_name("OutputIntents"), arr)

        fetched = catalog.get_output_intents()

        assert len(fetched) == 1
        assert fetched[0].get_cos_object() is good.get_cos_object()
        assert catalog.has_output_intents() is True

        with pytest.raises(TypeError, match="PDOutputIntent"):
            catalog.set_output_intents([COSDictionary()])  # type: ignore[list-item]


def test_wave567_threads_auto_create_skip_bad_entries_and_reject_bad_setter_input() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()

        assert catalog.get_threads() == []
        threads_entry = catalog.get_cos_object().get_dictionary_object(
            _name("Threads")
        )
        assert isinstance(threads_entry, COSArray)

        thread = PDThread()
        arr = COSArray()
        arr.add(COSName.get_pdf_name("bad"))
        arr.add(thread.get_cos_object())
        catalog.get_cos_object().set_item(_name("Threads"), arr)

        fetched = catalog.get_threads()

        assert len(fetched) == 1
        assert fetched[0].get_cos_object() is thread.get_cos_object()
        assert catalog.has_threads() is True

        with pytest.raises(TypeError, match="PDThread"):
            catalog.set_threads([COSDictionary()])  # type: ignore[list-item]
