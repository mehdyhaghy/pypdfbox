"""Wave 1370 — Splitter destination-handling round-out (agent E).

Covers the splitter's link / destination fix-up post-pass:

- A direct link destination pointing INSIDE the chunk: target rewrites
  to the cloned page dict.
- A direct link destination pointing OUTSIDE the chunk (target page is
  in a *different* chunk): target nulled out (becomes COSNull at [0]).
- Multiple links inside one chunk, both pointing to same target chunk:
  both nulled, no cross-talk between fix-up entries.
- Link with /A GoTo action pointing inside chunk: action's /D rewrites
  to cloned target page.
- Link with no destination at all is tolerated (no exception).
- Splitter does not propagate the source catalog's /Dest legacy flat
  dictionary into chunks.
"""
from __future__ import annotations

from pathlib import Path

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSNull,
    COSStream,
)
from pypdfbox.multipdf import Splitter
from pypdfbox.pdmodel.interactive.action import PDActionGoTo
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationLink
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitDestination,
)


def _make_doc(n_pages: int) -> PDDocument:
    doc = PDDocument()
    for i in range(n_pages):
        page = PDPage()
        s = COSStream()
        s.set_raw_data(b"% page " + str(i).encode("ascii") + b"\n")
        page.set_contents(s)
        doc.add_page(page)
    return doc


def _fit_destination(page: PDPage) -> PDPageFitDestination:
    dest = PDPageFitDestination()
    dest.set_page(page)
    return dest


# ---------- in-chunk target ----------


def test_direct_link_destination_in_same_chunk_rewrites_to_cloned_page() -> None:
    """A link on page 0 pointing at page 1, both in the same chunk, gets
    its destination's first slot rewritten to the cloned target page
    dict."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    link = PDAnnotationLink()
    link.set_destination(_fit_destination(src_pages[1]))
    src_pages[0].set_annotations([link])

    # Single chunk: all 2 pages together.
    chunks = Splitter().set_split_at_page(2).split(src)
    try:
        assert len(chunks) == 1
        imported_pages = list(chunks[0].get_pages())
        imported_link = imported_pages[0].get_annotations()[0]
        assert isinstance(imported_link, PDAnnotationLink)
        imported_dest = imported_link.get_destination()
        assert isinstance(imported_dest, PDPageFitDestination)
        # [0] slot is the cloned target page dict.
        assert imported_dest.get_page() is imported_pages[1].get_cos_object()
    finally:
        for c in chunks:
            c.close()
        src.close()


def test_direct_link_destination_target_in_different_chunk_nulled() -> None:
    """A link on page 0 pointing at page 1; split puts each page in its
    own chunk → target page lives outside chunk[0], so [0] gets nulled."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    link = PDAnnotationLink()
    link.set_destination(_fit_destination(src_pages[1]))
    src_pages[0].set_annotations([link])

    # Default split = 1 page per chunk: chunk[0] = page 0, chunk[1] = page 1.
    chunks = Splitter().split(src)
    try:
        assert len(chunks) == 2
        imported_link = chunks[0].get_page(0).get_annotations()[0]
        imported_dest = imported_link.get_destination()
        assert isinstance(imported_dest, PDPageFitDestination)
        # Target nulled — [0] slot is COSNull, not a page dict.
        assert imported_dest.get_cos_object().get(0) is COSNull.NULL
    finally:
        for c in chunks:
            c.close()
        src.close()


def test_goto_action_destination_in_same_chunk_rewrites() -> None:
    """A /A GoTo action's destination is rewritten the same way /Dest is."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    action = PDActionGoTo()
    action.set_destination(_fit_destination(src_pages[1]))
    link = PDAnnotationLink()
    link.set_action(action)
    src_pages[0].set_annotations([link])

    chunks = Splitter().set_split_at_page(2).split(src)
    try:
        assert len(chunks) == 1
        imported_pages = list(chunks[0].get_pages())
        imported_link = imported_pages[0].get_annotations()[0]
        imported_action = imported_link.get_action()
        assert isinstance(imported_action, PDActionGoTo)
        imported_dest = imported_action.get_destination()
        assert isinstance(imported_dest, PDPageFitDestination)
        assert imported_dest.get_page() is imported_pages[1].get_cos_object()
    finally:
        for c in chunks:
            c.close()
        src.close()


# ---------- multiple links per chunk ----------


def test_multiple_links_each_nulled_when_targets_outside_chunk() -> None:
    """Two links on the same page, both pointing at out-of-chunk pages,
    each get independently nulled."""
    src = _make_doc(3)
    src_pages = list(src.get_pages())
    link_a = PDAnnotationLink()
    link_a.set_destination(_fit_destination(src_pages[1]))
    link_b = PDAnnotationLink()
    link_b.set_destination(_fit_destination(src_pages[2]))
    src_pages[0].set_annotations([link_a, link_b])

    chunks = Splitter().split(src)
    try:
        # Chunk 0 holds page 0; both targets (page 1, page 2) live in
        # chunks 1 and 2 respectively.
        imported_annots = chunks[0].get_page(0).get_annotations()
        assert len(imported_annots) == 2
        for ann in imported_annots:
            dest = ann.get_destination()
            assert isinstance(dest, PDPageFitDestination)
            assert dest.get_cos_object().get(0) is COSNull.NULL
    finally:
        for c in chunks:
            c.close()
        src.close()


def test_link_without_destination_is_tolerated() -> None:
    """A link annotation with no /Dest and no /A action survives the
    split without raising."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    link = PDAnnotationLink()
    src_pages[0].set_annotations([link])
    # No exception expected.
    chunks = Splitter().split(src)
    try:
        annots = chunks[0].get_page(0).get_annotations()
        assert len(annots) == 1
    finally:
        for c in chunks:
            c.close()
        src.close()


def test_link_destination_target_in_chunk_with_offset_start() -> None:
    """Start page 2, end page 4, chunk-size 10 → single chunk holds source
    pages 2-3-4 (1-based). A link on source page 2 → source page 4 must
    land inside that chunk."""
    src = _make_doc(5)
    src_pages = list(src.get_pages())
    link = PDAnnotationLink()
    link.set_destination(_fit_destination(src_pages[4]))
    src_pages[2].set_annotations([link])

    splitter = Splitter()
    splitter.set_start_page(3)  # 1-based source page 3 == src_pages[2]
    splitter.set_end_page(5)
    splitter.set_split_at_page(10)
    chunks = splitter.split(src)
    try:
        assert len(chunks) == 1
        chunk_pages = list(chunks[0].get_pages())
        assert len(chunk_pages) == 3
        # The link lives on the first chunk page (source page 3) → cloned page 0 in chunk.
        annots = chunk_pages[0].get_annotations()
        imported_link = annots[0]
        dest = imported_link.get_destination()
        assert isinstance(dest, PDPageFitDestination)
        # Target is source page 5 (1-based) → chunk's page index 2.
        assert dest.get_page() is chunk_pages[2].get_cos_object()
    finally:
        for c in chunks:
            c.close()
        src.close()


def test_split_chunk_save_with_link_round_trips(tmp_path: Path) -> None:
    """A chunk containing a link with a same-chunk destination saves
    successfully — the destination /D [0] is now a concrete page dict
    on the chunk, so the writer can resolve it."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    link = PDAnnotationLink()
    link.set_destination(_fit_destination(src_pages[1]))
    src_pages[0].set_annotations([link])

    chunks = Splitter().set_split_at_page(2).split(src)
    try:
        out = tmp_path / "chunk.pdf"
        chunks[0].save(out)
    finally:
        for c in chunks:
            c.close()
        src.close()

    with PDDocument.load(out) as reopened:
        assert reopened.get_number_of_pages() == 2
        annots = reopened.get_page(0).get_annotations()
        assert len(annots) == 1


# ---------- legacy /Dests not propagated ----------


def test_splitter_does_not_copy_catalog_dests_flat_dict() -> None:
    """A legacy catalog ``/Dests`` flat dictionary on the source is NOT
    cloned onto chunk catalogs."""
    src = _make_doc(2)
    legacy_dests = COSDictionary()
    page_dest = COSArray()
    page_dest.add(src.get_page(0).get_cos_object())
    page_dest.add(COSName.get_pdf_name("Fit"))
    legacy_dests.set_item(COSName.get_pdf_name("LegacyEntry"), page_dest)
    src.get_document_catalog().get_cos_object().set_item(
        COSName.get_pdf_name("Dests"), legacy_dests
    )

    chunks = Splitter().split(src)
    try:
        for chunk in chunks:
            assert (
                chunk.get_document_catalog().get_cos_object().get_dictionary_object(
                    COSName.get_pdf_name("Dests")
                )
                is None
            )
    finally:
        for c in chunks:
            c.close()
        src.close()
