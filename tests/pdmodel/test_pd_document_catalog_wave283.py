from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel import PDDocument, PDDocumentCatalog


def _name(name: str) -> COSName:
    return COSName.get_pdf_name(name)


def _dict_with_entry(key: str = "K") -> COSDictionary:
    dictionary = COSDictionary()
    dictionary.set_item(_name(key), COSString("v"))
    return dictionary


def _array_with_dict() -> COSArray:
    array = COSArray()
    array.add(COSDictionary())
    return array


@pytest.mark.parametrize(
    ("clear_name", "key", "value"),
    [
        ("clear_version", _name("Version"), _name("1.7")),
        ("clear_language", _name("Lang"), COSString("en-US")),
        ("clear_page_layout", _name("PageLayout"), _name("OneColumn")),
        ("clear_page_mode", _name("PageMode"), _name("UseOutlines")),
        ("clear_struct_tree_root", _name("StructTreeRoot"), COSDictionary()),
        ("clear_structure_tree_root", _name("StructTreeRoot"), COSDictionary()),
        ("clear_mark_info", _name("MarkInfo"), COSDictionary()),
        ("clear_acro_form", _name("AcroForm"), COSDictionary()),
        ("clear_document_outline", _name("Outlines"), COSDictionary()),
        ("clear_outlines", _name("Outlines"), COSDictionary()),
        ("clear_metadata", _name("Metadata"), COSStream()),
        ("clear_actions", _name("AA"), _dict_with_entry()),
        ("clear_oc_properties", _name("OCProperties"), COSDictionary()),
        ("clear_optional_content_properties", _name("OCProperties"), COSDictionary()),
        ("clear_names", _name("Names"), COSDictionary()),
        ("clear_dests", _name("Dests"), COSDictionary()),
        ("clear_open_action", _name("OpenAction"), COSDictionary()),
        ("clear_viewer_preferences", _name("ViewerPreferences"), COSDictionary()),
        ("clear_view_preferences", _name("ViewerPreferences"), COSDictionary()),
        ("clear_page_labels", _name("PageLabels"), COSDictionary()),
        ("clear_output_intents", _name("OutputIntents"), _array_with_dict()),
        ("clear_threads", _name("Threads"), _array_with_dict()),
        ("clear_perms", _name("Perms"), COSDictionary()),
        ("clear_legal", _name("Legal"), COSDictionary()),
        ("clear_collection", _name("Collection"), COSDictionary()),
        ("clear_developer_extensions", _name("Extensions"), _dict_with_entry("ADBE")),
        ("clear_uri", _name("URI"), COSDictionary()),
        ("clear_requirements", _name("Requirements"), _array_with_dict()),
        ("clear_associated_files", _name("AF"), _array_with_dict()),
        ("clear_piece_info", _name("PieceInfo"), COSDictionary()),
        ("clear_needs_rendering", _name("NeedsRendering"), COSBoolean.TRUE),
    ],
)
def test_clear_helpers_remove_catalog_entries(
    clear_name: str,
    key: COSName,
    value: Any,
) -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        catalog.get_cos_object().set_item(key, value)
        assert key in catalog

        getattr(catalog, clear_name)()

        assert key not in catalog


def test_clear_acro_form_invalidates_cached_wrapper() -> None:
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        catalog.set_acro_form(PDAcroForm(doc))
        assert catalog.get_acro_form() is not None

        catalog.clear_acro_form()

        assert catalog.get_acro_form() is None
        assert catalog.has_acro_form() is False


def test_clear_base_uri_removes_only_base_entry() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        uri = COSDictionary()
        uri.set_item(_name("Base"), COSString("https://example.test/"))
        uri.set_item(_name("Custom"), COSString("keep"))
        catalog.get_cos_object().set_item(_name("URI"), uri)
        assert catalog.has_base_uri() is True

        catalog.clear_base_uri()

        assert catalog.has_uri() is True
        assert catalog.has_base_uri() is False
        assert uri.get_string("Custom") == "keep"


def test_has_actions_is_read_only_and_requires_non_empty_dictionary() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        assert catalog.has_actions() is False
        assert _name("AA") not in catalog

        catalog.get_actions()
        assert _name("AA") in catalog
        assert catalog.has_actions() is False

        catalog.get_cos_object().set_item(_name("AA"), _dict_with_entry())
        assert catalog.has_actions() is True

        catalog.get_cos_object().set_item(_name("AA"), COSString("not-a-dict"))
        assert catalog.has_actions() is False


def test_page_layout_and_mode_predicates_reject_unrecognised_names() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()

        catalog.get_cos_object().set_item(_name("PageLayout"), _name("BogusLayout"))
        catalog.get_cos_object().set_item(_name("PageMode"), COSString("BogusMode"))
        assert catalog.has_page_layout() is False
        assert catalog.has_page_mode() is False

        catalog.set_page_layout("TwoColumnLeft")
        catalog.set_page_mode("UseOutlines")
        assert catalog.has_page_layout() is True
        assert catalog.has_page_mode() is True


def test_has_output_intents_requires_a_dictionary_entry() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        array = COSArray()
        array.add(COSString("not-an-intent"))
        catalog.get_cos_object().set_item(_name("OutputIntents"), array)
        assert catalog.has_output_intents() is False

        array.add(COSDictionary())

        assert catalog.has_output_intents() is True


def test_has_base_uri_and_needs_rendering_validate_presence() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        assert catalog.has_base_uri() is False
        assert catalog.has_needs_rendering() is False

        catalog.get_cos_object().set_item(_name("URI"), COSDictionary())
        assert catalog.has_base_uri() is False

        catalog.set_base_uri("")
        assert catalog.has_base_uri() is True

        catalog.set_needs_rendering(False)
        assert catalog.has_needs_rendering() is True
        assert catalog.is_needs_rendering() is False


def test_catalog_class_docstring_no_longer_mentions_stubbed_accessors() -> None:
    assert PDDocumentCatalog.__doc__ is not None
    assert "stubbed" not in PDDocumentCatalog.__doc__
