from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.common.filespecification import PDSimpleFileSpecification
from pypdfbox.pdmodel.interactive.annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDNamedDestination,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.pd_developer_extension import PDDeveloperExtension
from pypdfbox.pdmodel.pd_document_name_destination_dictionary import (
    PDDocumentNameDestinationDictionary,
)
from pypdfbox.pdmodel.pd_page_tree import PDPageTree


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_wave606_catalog_basic_setters_aliases_and_clear_helpers() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        pages = PDPageTree(document=doc)

        catalog.set_pages(pages)
        catalog.set_version("1.7")
        catalog.set_language("en-US")
        catalog.clear_version()
        catalog.clear_language()

        assert catalog.get_cos_object().get_dictionary_object(_name("Pages")) is (
            pages.get_cos_object()
        )
        assert catalog.get_version() is None
        assert catalog.get_language() is None
        assert catalog.has_version() is False
        assert catalog.has_language() is False


def test_wave606_catalog_acro_form_or_create_caches_and_clear_invalidates() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()

        created = catalog.get_acro_form_or_create()
        again = catalog.get_acro_form_or_create()

        assert created is again
        assert catalog.has_acro_form() is True

        catalog.clear_acro_form()

        assert catalog.get_acro_form() is None
        assert catalog.has_acro_form() is False


def test_wave606_catalog_legacy_named_destination_lookup_and_empty_inputs() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        destination = PDPageXYZDestination()
        legacy = PDDocumentNameDestinationDictionary()
        legacy.set_destination("Chapter1", destination)
        catalog.set_dests(legacy)

        assert catalog.find_named_destination_page(None) is None
        assert catalog.find_named_destination_page(object()) is None
        assert catalog.find_named_destination_page(PDNamedDestination()) is None
        resolved = catalog.find_named_destination_page(
            PDNamedDestination("Chapter1")
        )

        assert resolved is not None
        assert resolved.get_cos_object() is destination.get_cos_object()

        catalog.clear_dests()
        assert catalog.has_dests() is False


def test_wave606_catalog_developer_extensions_snapshot_add_remove_and_clear() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        extension = PDDeveloperExtension()
        extension.set_base_version(PDDeveloperExtension.BASE_VERSION_1_7)
        extension.set_extension_level(8)

        catalog.add_developer_extension(PDDeveloperExtension.ADBE, extension)

        fetched = catalog.get_developer_extensions()
        assert fetched[PDDeveloperExtension.ADBE].get_cos_object() is (
            extension.get_cos_object()
        )
        assert catalog.has_developer_extensions() is True

        catalog.remove_developer_extension(PDDeveloperExtension.ADBE)
        assert catalog.has_developer_extensions() is False

        catalog.set_developer_extensions({"TEST": extension})
        catalog.clear_developer_extensions()
        assert catalog.get_developer_extensions() == {}


def test_wave606_catalog_dictionary_setters_reject_wrong_types_and_clear() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        for setter_name, clear_name in (
            ("set_perms", "clear_perms"),
            ("set_legal", "clear_legal"),
            ("set_collection", "clear_collection"),
            ("set_piece_info", "clear_piece_info"),
        ):
            setter = getattr(catalog, setter_name)
            clear = getattr(catalog, clear_name)
            entry = COSDictionary()

            setter(entry)
            with pytest.raises(TypeError, match="expected COSDictionary"):
                setter(COSString("bad"))
            clear()


def test_wave606_catalog_associated_files_valid_setter_and_type_error() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        spec = PDSimpleFileSpecification()
        spec.set_file("readme.txt")

        catalog.set_associated_files([spec])

        files = catalog.get_associated_files()
        assert len(files) == 1
        assert files[0].get_file() == "readme.txt"
        assert catalog.has_associated_files() is True

        with pytest.raises(TypeError, match="set_associated_files entries"):
            catalog.set_associated_files([COSDictionary()])  # type: ignore[list-item]

        catalog.clear_associated_files()
        assert catalog.get_associated_files() == []


def test_wave606_page_constructor_parent_resources_and_bbox_aliases() -> None:
    with pytest.raises(TypeError, match="PDPage requires"):
        PDPage("bad")  # type: ignore[arg-type]

    page_dict = COSDictionary()
    parent = COSDictionary()
    resources = COSDictionary()
    parent.set_item(_name("Resources"), resources)
    page_dict.set_item(_name("P"), parent)
    page = PDPage(page_dict)

    assert page.get_cos_parent() is parent
    assert page.get_inheritable_attribute("Resources") is resources
    assert page.get_resources().get_cos_object() is resources
    assert page.get_b_box() == page.get_bbox()


def test_wave606_page_direct_setters_and_clear_paths() -> None:
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 200.0))
    stream_array = COSArray()
    thumb = COSDictionary()

    class Thumb:
        def get_cos_object(self) -> COSDictionary:
            return thumb

    class Actions:
        def get_cos_object(self) -> COSDictionary:
            return COSDictionary()

    page.set_contents(stream_array)
    page.set_thumb(Thumb())
    page.set_actions(Actions())
    page.set_struct_parents(4)

    assert page.has_contents() is False
    assert page.has_thumb() is True
    assert page.has_actions() is True
    assert page.get_struct_parents() == 4

    page.clear_contents()
    page.set_thumb(None)
    page.set_actions(None)

    assert page.has_contents() is False
    assert page.has_thumb() is False
    assert page.has_actions() is False


def test_wave606_page_annotations_filter_and_empty_slots() -> None:
    page = PDPage()
    wanted = COSDictionary()
    wanted.set_name(_name("Subtype"), "Text")
    skipped = COSDictionary()
    skipped.set_name(_name("Subtype"), "Link")
    annots = COSArray([None, wanted, skipped])
    page.get_cos_object().set_item(_name("Annots"), annots)

    filtered = page.get_annotations(
        lambda annotation: annotation.get_subtype() == "Text"
    )

    assert len(filtered) == 1
    assert filtered[0].get_cos_object() is wanted

    annotation = PDAnnotation.create(wanted)
    page.set_annotations([annotation])
    assert page.get_cos_object().get_dictionary_object(_name("Annots")).size() == 1
