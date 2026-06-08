from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.pd_document_name_destination_dictionary import (
    PDDocumentNameDestinationDictionary,
)


def test_open_action_round_trip_with_action_uri() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()

    action = PDActionURI()
    action.set_uri("https://parity.example/")
    catalog.set_open_action(action)

    resolved = catalog.get_open_action()
    assert isinstance(resolved, PDActionURI)
    assert resolved.get_uri() == "https://parity.example/"

    catalog.set_open_action(None)
    assert catalog.get_open_action() is None


def test_perms_round_trip() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    assert catalog.get_perms() is None

    perms = COSDictionary()
    catalog.set_perms(perms)

    resolved = catalog.get_perms()
    assert isinstance(resolved, COSDictionary)
    assert resolved is perms

    catalog.set_perms(None)
    assert catalog.get_perms() is None


def test_legal_round_trip() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    assert catalog.get_legal() is None

    legal = COSDictionary()
    catalog.set_legal(legal)
    assert catalog.get_legal() is legal

    catalog.set_legal(None)
    assert catalog.get_legal() is None


def test_collection_round_trip() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    assert catalog.get_collection() is None

    coll = COSDictionary()
    catalog.set_collection(coll)
    assert catalog.get_collection() is coll

    catalog.set_collection(None)
    assert catalog.get_collection() is None


def test_get_threads_returns_empty_list() -> None:
    doc = PDDocument()
    threads = doc.get_document_catalog().get_threads()
    assert threads == []
    assert isinstance(threads, list)


def test_get_view_preferences_alias_matches_get_viewer_preferences() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()

    # Both absent: both return None.
    assert catalog.get_view_preferences() is None
    assert catalog.get_viewer_preferences() is None

    # Set via the upstream-named alias and observe via the original.
    from pypdfbox.pdmodel import PDViewerPreferences

    prefs = PDViewerPreferences()
    catalog.set_view_preferences(prefs)

    via_alias = catalog.get_view_preferences()
    via_original = catalog.get_viewer_preferences()
    assert via_alias is not None
    assert via_original is not None
    assert via_alias.get_cos_object() is prefs.get_cos_object()
    assert via_original.get_cos_object() is prefs.get_cos_object()

    # Unset via alias, original sees the removal.
    catalog.set_view_preferences(None)
    assert catalog.get_view_preferences() is None
    assert catalog.get_viewer_preferences() is None


def test_get_outlines_alias_matches_get_document_outline() -> None:
    from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
        PDDocumentOutline,
    )

    doc = PDDocument()
    catalog = doc.get_document_catalog()

    assert catalog.get_outlines() is None
    assert catalog.get_document_outline() is None

    outline = PDDocumentOutline()
    catalog.set_outlines(outline)

    via_alias = catalog.get_outlines()
    via_original = catalog.get_document_outline()
    assert isinstance(via_alias, PDDocumentOutline)
    assert isinstance(via_original, PDDocumentOutline)
    assert via_alias.get_cos_object() is outline.get_cos_object()
    assert via_original.get_cos_object() is outline.get_cos_object()


def test_set_dests_round_trip_legacy_catalog_entry() -> None:
    # Upstream PDDocumentCatalog.getDests wraps the flat (PDF 1.1) /Dests
    # catalog entry in PDDocumentNameDestinationDictionary (not the name-tree
    # node form). Set a flat-dict entry and read it back through the same
    # wrapper type.
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    dests = PDDocumentNameDestinationDictionary()
    dest = PDPageXYZDestination()
    dest.set_page_number(3)
    dests.set_destination("chapter", dest)

    catalog.set_dests(dests)

    resolved = catalog.get_dests()
    assert isinstance(resolved, PDDocumentNameDestinationDictionary)
    assert resolved.get_cos_object() is dests.get_cos_object()
    fetched = resolved.get_destination("chapter")
    assert isinstance(fetched, PDPageXYZDestination)
    assert fetched.get_page_number() == 3


def test_set_dests_none_clears_legacy_catalog_entry() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    catalog.set_dests(PDDocumentNameDestinationDictionary())

    catalog.set_dests(None)

    assert catalog.get_dests() is None
