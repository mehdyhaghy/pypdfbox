from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestinationNameTreeNode,
    PDNamedDestination,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import PDOutlineItem
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary
from pypdfbox.pdmodel.pd_page import PDPage


def test_named_destination_name_tree_value_resolves_without_recoercion() -> None:
    with PDDocument() as document:
        document.add_page(PDPage())
        target_page = PDPage()
        document.add_page(target_page)

        destination = PDPageXYZDestination()
        destination.set_page_number(1)
        tree = PDDestinationNameTreeNode()
        tree.set_names({"chapter": destination})
        names = PDDocumentNameDictionary(document.get_document_catalog())
        names.set_dests(tree)

        item = PDOutlineItem()
        item.set_destination(PDNamedDestination("chapter"))

        assert item.find_destination_page(document) is target_page.get_cos_object()


def test_named_destination_name_tree_precedes_legacy_catalog_dests() -> None:
    with PDDocument() as document:
        document.add_page(PDPage())
        legacy_page = PDPage()
        name_tree_page = PDPage()
        document.add_page(legacy_page)
        document.add_page(name_tree_page)

        name_tree_destination = PDPageXYZDestination()
        name_tree_destination.set_page_number(2)
        tree = PDDestinationNameTreeNode()
        tree.set_names({"chapter": name_tree_destination})
        names = PDDocumentNameDictionary(document.get_document_catalog())
        names.set_dests(tree)

        legacy_destination = PDPageXYZDestination()
        legacy_destination.set_page_number(1)
        legacy_dests = COSDictionary()
        legacy_dests.set_item(
            COSName.get_pdf_name("chapter"),
            legacy_destination.get_cos_object(),
        )
        document.get_document_catalog().get_cos_object().set_item(
            COSName.get_pdf_name("Dests"),
            legacy_dests,
        )

        item = PDOutlineItem()
        item.set_destination(PDNamedDestination("chapter"))

        assert item.find_destination_page(document) is name_tree_page.get_cos_object()


def test_malformed_legacy_named_destination_entry_returns_none() -> None:
    with PDDocument() as document:
        item = PDOutlineItem()
        item.set_destination(PDNamedDestination("broken"))

        legacy_dests = COSDictionary()
        legacy_dests.set_item(
            COSName.get_pdf_name("broken"),
            COSArray([COSInteger.get(0)]),
        )
        document.get_document_catalog().get_cos_object().set_item(
            COSName.get_pdf_name("Dests"),
            legacy_dests,
        )

        assert item.find_destination_page(document) is None
