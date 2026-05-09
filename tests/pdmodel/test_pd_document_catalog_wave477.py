from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel import (
    PDDeveloperExtension,
    PDDocument,
    PDPageLabels,
    PDViewerPreferences,
)
from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.pagenavigation import PDThread


def _name(name: str) -> COSName:
    return COSName.get_pdf_name(name)


def test_presence_predicates_validate_shape_without_materialising() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        cos = catalog.get_cos_object()

        cos.set_item(_name("Lang"), COSString("en-US"))
        catalog.set_version("1.7")
        catalog.set_page_labels(PDPageLabels(doc))
        catalog.set_viewer_preferences(PDViewerPreferences())
        catalog.set_open_action(PDActionURI())
        catalog.set_threads([PDThread()])

        assert catalog.has_language() is True
        assert catalog.has_version() is True
        assert catalog.has_page_labels() is True
        assert catalog.has_viewer_preferences() is True
        assert catalog.has_open_action() is True
        assert catalog.has_threads() is True

        cos.set_item(_name("Lang"), _name("NotAString"))
        cos.set_item(_name("Version"), COSArray())
        cos.set_item(_name("PageLabels"), COSString("bad"))
        cos.set_item(_name("ViewerPreferences"), COSString("bad"))
        cos.set_item(_name("OpenAction"), COSString("bad"))
        cos.set_item(_name("Threads"), COSDictionary())

        assert catalog.has_language() is False
        assert catalog.has_version() is False
        assert catalog.has_page_labels() is False
        assert catalog.has_viewer_preferences() is False
        assert catalog.has_open_action() is False
        assert catalog.has_threads() is False


def test_base_uri_shortcut_creates_clears_and_removes_empty_uri_dict() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()

        assert catalog.get_base_uri() is None
        assert catalog.has_base_uri() is False

        catalog.set_base_uri("https://example.test/root/")

        assert catalog.has_uri() is True
        assert catalog.has_base_uri() is True
        assert catalog.get_base_uri() == "https://example.test/root/"

        catalog.clear_base_uri()

        assert catalog.get_base_uri() is None
        assert catalog.has_base_uri() is False
        assert catalog.has_uri() is False


def test_developer_extensions_snapshot_add_remove_and_clear() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        extension = PDDeveloperExtension()
        extension.set_base_version(PDDeveloperExtension.BASE_VERSION_1_7)
        extension.set_extension_level(8)

        catalog.add_developer_extension("ADBE", extension)

        fetched = catalog.get_developer_extensions()
        assert catalog.has_developer_extensions() is True
        assert fetched["ADBE"].get_cos_object() is extension.get_cos_object()

        fetched.clear()
        assert catalog.has_developer_extensions() is True

        catalog.remove_developer_extension("ADBE")
        assert catalog.get_developer_extensions() == {}
        assert catalog.has_developer_extensions() is False

        catalog.set_developer_extensions({"ADBE": extension})
        catalog.clear_developer_extensions()
        assert catalog.has_developer_extensions() is False


@pytest.mark.parametrize(
    ("setter", "getter", "predicate", "clearer", "value"),
    [
        ("set_perms", "get_perms", "has_perms", "clear_perms", COSDictionary()),
        ("set_legal", "get_legal", "has_legal", "clear_legal", COSDictionary()),
        (
            "set_collection",
            "get_collection",
            "has_collection",
            "clear_collection",
            COSDictionary(),
        ),
        (
            "set_piece_info",
            "get_piece_info",
            "has_piece_info",
            "clear_piece_info",
            COSDictionary(),
        ),
    ],
)
def test_raw_catalog_dictionary_entries_round_trip_and_clear(
    setter: str,
    getter: str,
    predicate: str,
    clearer: str,
    value: COSDictionary,
) -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()

        getattr(catalog, setter)(value)

        assert getattr(catalog, getter)() is value
        assert getattr(catalog, predicate)() is True

        getattr(catalog, clearer)()

        assert getattr(catalog, getter)() is None
        assert getattr(catalog, predicate)() is False


def test_raw_catalog_dictionary_setters_reject_wrong_type() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()

        with pytest.raises(TypeError):
            catalog.set_perms("bad")  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            catalog.set_legal("bad")  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            catalog.set_collection("bad")  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            catalog.set_piece_info("bad")  # type: ignore[arg-type]
