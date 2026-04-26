from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDDocumentCatalog
from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestinationNameTreeNode,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import PDDocumentOutline


def test_catalog_attached_to_fresh_document() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert isinstance(cat, PDDocumentCatalog)
    assert cat.get_cos_object().get_name(COSName.TYPE) == "Catalog"  # type: ignore[attr-defined]


def test_get_pages_returns_tree_rooted_at_pages() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    tree = cat.get_pages()
    pages_dict = cat.get_cos_object().get_dictionary_object(COSName.PAGES)  # type: ignore[attr-defined]
    assert tree.get_cos_object() is pages_dict


def test_language_round_trip() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_language("en-US")
    assert cat.get_language() == "en-US"
    cat.set_language(None)
    assert cat.get_language() is None


def test_page_layout_round_trip() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_page_layout("OneColumn")
    assert cat.get_page_layout() == "OneColumn"
    cat.set_page_layout(None)
    assert cat.get_page_layout() is None


def test_page_mode_round_trip() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_page_mode("UseOutlines")
    assert cat.get_page_mode() == "UseOutlines"


def test_version_round_trip() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_version("1.7")
    assert cat.get_version() == "1.7"


def test_stubbed_accessors_raise() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    for stub in (
        cat.get_struct_tree_root,
        cat.get_acro_form,
        cat.get_metadata,
        cat.get_oc_properties,
        cat.get_names,
        cat.get_output_intents,
        cat.get_mark_info,
    ):
        with pytest.raises(NotImplementedError):
            stub()


def test_get_viewer_preferences_absent_returns_none() -> None:
    doc = PDDocument()
    assert doc.get_document_catalog().get_viewer_preferences() is None


def test_get_page_labels_absent_returns_none() -> None:
    doc = PDDocument()
    assert doc.get_document_catalog().get_page_labels() is None


def test_document_outline_round_trip() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    outline = PDDocumentOutline()

    catalog.set_document_outline(outline)
    resolved = catalog.get_document_outline()

    assert isinstance(resolved, PDDocumentOutline)
    assert resolved.get_cos_object() is outline.get_cos_object()


def test_open_action_accepts_action_or_destination() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    action = PDActionURI()
    action.set_uri("https://example.test")

    catalog.set_open_action(action)
    resolved_action = catalog.get_open_action()
    assert isinstance(resolved_action, PDActionURI)
    assert resolved_action.get_uri() == "https://example.test"

    dest = PDPageXYZDestination()
    dest.set_page_number(0)
    catalog.set_open_action(dest)
    resolved_dest = catalog.get_open_action()
    assert isinstance(resolved_dest, PDPageXYZDestination)
    assert resolved_dest.get_page_number() == 0


def test_get_dests_wraps_destination_name_tree() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    dests_dict = COSDictionary()
    catalog.get_cos_object().set_item(COSName.get_pdf_name("Dests"), dests_dict)

    dests = catalog.get_dests()
    assert isinstance(dests, PDDestinationNameTreeNode)
    assert dests.get_cos_object() is dests_dict

    dest = PDPageXYZDestination()
    dest.set_page_number(1)
    dests.set_value("Chapter1", dest)

    resolved = catalog.get_dests()
    assert isinstance(resolved, PDDestinationNameTreeNode)
    fetched = resolved.get_value("Chapter1")
    assert isinstance(fetched, PDPageXYZDestination)
    assert fetched.get_page_number() == 1
