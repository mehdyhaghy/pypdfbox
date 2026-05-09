from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_wave578_requirements_skip_bad_entries_and_clear() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        requirement = COSDictionary()
        arr = COSArray()
        arr.add(COSString("bad"))
        arr.add(requirement)
        catalog.get_cos_object().set_item(_name("Requirements"), arr)

        assert catalog.get_requirements() == [requirement]
        assert catalog.has_requirements() is True

        catalog.clear_requirements()
        assert catalog.get_requirements() == []
        assert catalog.has_requirements() is False


def test_wave578_requirements_setters_reject_wrong_types() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()

        with pytest.raises(TypeError, match="set_requirements entries"):
            catalog.set_requirements([COSString("bad")])  # type: ignore[list-item]

        with pytest.raises(TypeError, match="add_requirement expected"):
            catalog.add_requirement(COSString("bad"))  # type: ignore[arg-type]


def test_wave578_base_uri_clear_preserves_non_empty_uri_dictionary() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        uri = COSDictionary()
        uri.set_item(_name("Base"), COSString("https://example.test/root/"))
        uri.set_item(_name("Other"), COSString("kept"))
        catalog.set_uri(uri)

        catalog.clear_base_uri()

        assert catalog.get_base_uri() is None
        assert catalog.has_base_uri() is False
        assert catalog.has_uri() is True
        assert catalog.get_uri().get_cos_object() is uri
        assert uri.get_string(_name("Other")) == "kept"


def test_wave578_set_base_uri_none_does_not_create_uri_dictionary() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()

        catalog.set_base_uri(None)

        assert catalog.get_uri() is None
        assert catalog.has_uri() is False


def test_wave578_names_dictionary_round_trips_and_dests_presence() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        names = PDDocumentNameDictionary(catalog)
        dests = COSDictionary()
        names.get_cos_object().set_item(_name("Dests"), dests)

        catalog.set_names(names)

        assert catalog.get_names().get_cos_object() is names.get_cos_object()
        assert catalog.has_names() is True
        assert catalog.has_dests_name_tree() is True

        catalog.clear_names()
        assert catalog.get_names() is None
        assert catalog.has_names() is False
        assert catalog.has_dests_name_tree() is False
