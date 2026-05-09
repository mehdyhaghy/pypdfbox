from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel import PDDocument


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_wave587_cos_dictionary_alias_contains_and_repr_reflect_catalog() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        catalog.set_version("1.7")

        assert catalog.get_cos_dictionary() is catalog.get_cos_object()
        assert _name("Version") in catalog
        assert "Version" in catalog
        assert repr(catalog) == "PDDocumentCatalog(version='1.7')"


def test_wave587_set_pages_none_removes_entry_and_get_pages_recreates_tree() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        original_pages = catalog.get_pages().get_cos_object()

        catalog.set_pages(None)

        assert catalog.get_cos_object().get_dictionary_object(_name("Pages")) is None

        recreated = catalog.get_pages()

        assert recreated.get_cos_object() is not original_pages
        assert catalog.get_cos_object().get_dictionary_object(
            _name("Pages")
        ) is recreated.get_cos_object()


def test_wave587_mark_info_shortcuts_create_update_and_clear_flags() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()

        assert catalog.has_mark_info() is False
        assert catalog.is_document_marked() is False
        assert catalog.has_user_properties() is False
        assert catalog.has_suspects() is False
        assert catalog.is_tagged() is False

        catalog.set_document_marked(True)
        catalog.set_user_properties(True)
        catalog.set_suspects(True)

        assert catalog.has_mark_info() is True
        assert catalog.is_document_marked() is True
        assert catalog.has_user_properties() is True
        assert catalog.has_suspects() is True
        assert catalog.is_tagged() is True

        catalog.clear_mark_info()

        assert catalog.has_mark_info() is False
        assert catalog.is_document_marked() is False
        assert catalog.has_user_properties() is False
        assert catalog.has_suspects() is False
        assert catalog.is_tagged() is False


def test_wave587_raw_shape_predicates_ignore_malformed_values() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        cos = catalog.get_cos_object()

        cos.set_item(_name("Perms"), COSString("bad"))
        cos.set_item(_name("Legal"), COSString("bad"))
        cos.set_item(_name("Collection"), COSString("bad"))
        cos.set_item(_name("PieceInfo"), COSString("bad"))
        cos.set_item(_name("MarkInfo"), COSString("bad"))

        assert catalog.get_perms() is None
        assert catalog.get_legal() is None
        assert catalog.get_collection() is None
        assert catalog.get_piece_info() is None
        assert catalog.get_mark_info() is None
        assert catalog.has_perms() is False
        assert catalog.has_legal() is False
        assert catalog.has_collection() is False
        assert catalog.is_collection() is False
        assert catalog.has_piece_info() is False
        assert catalog.has_mark_info() is False

        collection = COSDictionary()
        catalog.set_collection(collection)

        assert catalog.get_collection() is collection
        assert catalog.has_collection() is True
        assert catalog.is_collection() is True
