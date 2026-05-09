from __future__ import annotations

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSNull
from pypdfbox.multipdf import Splitter
from pypdfbox.pdmodel.interactive.action import PDActionGoTo
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationLink
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitDestination,
)


def _make_doc(page_count: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(page_count):
        doc.add_page(PDPage())
    return doc


def _fit_destination(page: PDPage) -> PDPageFitDestination:
    dest = PDPageFitDestination()
    dest.set_page(page)
    return dest


def test_wave533_direct_link_destination_rewrites_to_cloned_page_in_same_chunk() -> None:
    source = _make_doc(2)
    source_pages = list(source.get_pages())
    source_dest = _fit_destination(source_pages[1])
    link = PDAnnotationLink()
    link.set_destination(source_dest)
    source_pages[0].set_annotations([link])

    splitter = Splitter().set_split_at_page(2)
    chunks = splitter.split(source)

    try:
        assert len(chunks) == 1
        imported_pages = list(chunks[0].get_pages())
        imported_link = imported_pages[0].get_annotations()[0]
        imported_dest = imported_link.get_destination()

        assert isinstance(imported_link, PDAnnotationLink)
        assert isinstance(imported_dest, PDPageFitDestination)
        assert imported_dest.get_page() is imported_pages[1].get_cos_object()
        assert source_dest.get_page() is source_pages[1].get_cos_object()
    finally:
        for chunk in chunks:
            chunk.close()
        source.close()


def test_wave533_goto_action_destination_outside_chunk_is_nulled() -> None:
    source = _make_doc(2)
    source_pages = list(source.get_pages())
    source_dest = _fit_destination(source_pages[1])
    action = PDActionGoTo()
    action.set_destination(source_dest)
    link = PDAnnotationLink()
    link.set_action(action)
    source_pages[0].set_annotations([link])

    chunks = Splitter().split(source)

    try:
        assert [chunk.get_number_of_pages() for chunk in chunks] == [1, 1]
        imported_link = chunks[0].get_page(0).get_annotations()[0]
        imported_action = imported_link.get_action()

        assert isinstance(imported_link, PDAnnotationLink)
        assert isinstance(imported_action, PDActionGoTo)
        imported_dest = imported_action.get_destination()
        assert isinstance(imported_dest, PDPageFitDestination)
        assert imported_dest.get_cos_object().get(0) is COSNull.NULL
        assert source_dest.get_page() is source_pages[1].get_cos_object()
    finally:
        for chunk in chunks:
            chunk.close()
        source.close()
