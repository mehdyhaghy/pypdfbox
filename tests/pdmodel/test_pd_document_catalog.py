from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDDocumentCatalog


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
        cat.get_document_outline,
        cat.get_metadata,
        cat.get_oc_properties,
        cat.get_names,
        cat.get_dests,
        cat.get_open_action,
        cat.get_viewer_preferences,
        cat.get_output_intents,
        cat.get_mark_info,
    ):
        with pytest.raises(NotImplementedError):
            stub()
