"""Link-annotation remap tests for ``pypdfbox merge``.

After Wave 13's ``PDDocument.import_page`` landed, the merge tool now
deep-copies pages and rewires intra-source link destinations to point at
the imported page set. These tests exercise that contract end-to-end.
"""
from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationLink
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitDestination,
)
from pypdfbox.tools import cli

_ANNOTS = COSName.get_pdf_name("Annots")
_DEST = COSName.get_pdf_name("Dest")
_SUBTYPE = COSName.get_pdf_name("Subtype")


def _build_pdf_with_link(
    path: Path,
    *,
    page_count: int,
    link_from_index: int,
    link_to_index: int | None,
) -> Path:
    """Build a PDF with ``page_count`` blank pages and a Link annotation
    on page ``link_from_index`` whose ``/Dest`` is an explicit Fit array
    pointing at page ``link_to_index`` (or at a foreign dictionary if
    ``link_to_index is None``, simulating a dangling cross-doc ref)."""
    doc = PDDocument()
    pages: list[PDPage] = []
    try:
        for _ in range(page_count):
            page = PDPage()
            doc.add_page(page)
            pages.append(page)

        link = PDAnnotationLink()
        if link_to_index is not None:
            target_page_dict = pages[link_to_index].get_cos_object()
        else:
            # Unrelated dictionary the merger can never have imported —
            # exercises the "leave dangling" branch.
            target_page_dict = COSDictionary()
            target_page_dict.set_item(
                COSName.get_pdf_name("Type"), COSName.get_pdf_name("Page")
            )
        dest = PDPageFitDestination()
        dest.set_page(target_page_dict)
        link.set_destination(dest)

        pages[link_from_index].set_annotations([link])
        doc.save(path)
    finally:
        doc.close()
    return path


def _link_dest_target(page_dict: COSDictionary) -> COSDictionary | None:
    """Return the ``/D[0]`` dictionary of the first Link annotation on
    ``page_dict``, or ``None`` if no link with an explicit-array dest is
    present."""
    annots = page_dict.get_dictionary_object(_ANNOTS)
    if not isinstance(annots, COSArray):
        return None
    for i in range(annots.size()):
        annot = annots.get_object(i)
        if not isinstance(annot, COSDictionary):
            continue
        if annot.get_name(_SUBTYPE) != "Link":
            continue
        dest = annot.get_dictionary_object(_DEST)
        if not isinstance(dest, COSArray) or dest.size() < 1:
            continue
        target = dest.get_object(0)
        if isinstance(target, COSDictionary):
            return target
    return None


def test_merge_remaps_intra_source_link(tmp_path: Path, make_pdf) -> None:
    """Source A page 1 → page 3 of A. After merging A into a fresh
    target with a second filler input, the link must point at the
    imported page-3 in the target — NOT at A's original page-3 dict."""
    a = _build_pdf_with_link(
        tmp_path / "a.pdf",
        page_count=3,
        link_from_index=0,
        link_to_index=2,
    )
    b = make_pdf("b.pdf", page_count=1)
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(["merge", "-i", str(a), str(b), "-o", str(out)])
    assert rc == 0

    with PDDocument.load(out) as merged:
        assert merged.get_number_of_pages() == 4
        merged_pages = list(merged.get_pages())
        link_target = _link_dest_target(merged_pages[0].get_cos_object())
        assert link_target is not None
        # The remapped target must be the imported page-3 (merged index 2).
        assert link_target is merged_pages[2].get_cos_object()

    # And it must NOT be the original A's page-3 dict — re-load A to
    # confirm identity is independent of the source object graph.
    with PDDocument.load(a) as src_a:
        src_pages = list(src_a.get_pages())
        with PDDocument.load(out) as merged:
            merged_pages = list(merged.get_pages())
            link_target = _link_dest_target(merged_pages[0].get_cos_object())
            assert link_target is not src_pages[2].get_cos_object()


def test_merge_remaps_each_source_independently(
    tmp_path: Path, make_pdf
) -> None:
    """A and B each carry an intra-source link; both must remap to their
    new positions in the merged output."""
    a = _build_pdf_with_link(
        tmp_path / "a.pdf",
        page_count=3,
        link_from_index=0,
        link_to_index=2,
    )
    b = _build_pdf_with_link(
        tmp_path / "b.pdf",
        page_count=2,
        link_from_index=0,
        link_to_index=1,
    )
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(["merge", "-i", str(a), str(b), "-o", str(out)])
    assert rc == 0

    with PDDocument.load(out) as merged:
        assert merged.get_number_of_pages() == 5
        merged_pages = list(merged.get_pages())
        # A's link: page 0 → page 2 (unchanged offset, A came first).
        a_link = _link_dest_target(merged_pages[0].get_cos_object())
        assert a_link is merged_pages[2].get_cos_object()
        # B's link: page 3 → page 4 (B's pages 0,1 → merged 3,4).
        b_link = _link_dest_target(merged_pages[3].get_cos_object())
        assert b_link is merged_pages[4].get_cos_object()


def test_merge_leaves_dangling_cross_doc_link_alone(
    tmp_path: Path, make_pdf
) -> None:
    """When a Link's /Dest[0] points at a page that wasn't imported
    (foreign dict), the merger must leave the entry as-is — the link
    will dangle, but mutating it to a wrong target is worse."""
    a = _build_pdf_with_link(
        tmp_path / "a.pdf",
        page_count=2,
        link_from_index=0,
        link_to_index=None,  # foreign target dict
    )
    b = make_pdf("b.pdf", page_count=1)
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(["merge", "-i", str(a), str(b), "-o", str(out)])
    assert rc == 0

    with PDDocument.load(out) as merged:
        assert merged.get_number_of_pages() == 3
        merged_pages = list(merged.get_pages())
        link_target = _link_dest_target(merged_pages[0].get_cos_object())
        assert link_target is not None
        # The dangling target dict must NOT be one of the merged pages.
        page_ids = {id(p.get_cos_object()) for p in merged_pages}
        assert id(link_target) not in page_ids


def test_merge_remaps_goto_action_dest(tmp_path: Path, make_pdf) -> None:
    """A Link whose target is set via ``/A`` (GoTo action with ``/D``
    array) is also remapped, not just ``/Dest``."""
    from pypdfbox.pdmodel.interactive.action import PDActionGoTo

    a_path = tmp_path / "a.pdf"
    doc = PDDocument()
    pages: list[PDPage] = []
    try:
        for _ in range(3):
            page = PDPage()
            doc.add_page(page)
            pages.append(page)
        link = PDAnnotationLink()
        action = PDActionGoTo()
        dest = PDPageFitDestination()
        dest.set_page(pages[2].get_cos_object())
        action.set_destination(dest)
        link.set_action(action)
        pages[0].set_annotations([link])
        doc.save(a_path)
    finally:
        doc.close()

    b = make_pdf("b.pdf", page_count=1)
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(["merge", "-i", str(a_path), str(b), "-o", str(out)])
    assert rc == 0

    with PDDocument.load(out) as merged:
        merged_pages = list(merged.get_pages())
        annots = merged_pages[0].get_cos_object().get_dictionary_object(_ANNOTS)
        assert isinstance(annots, COSArray)
        annot = annots.get_object(0)
        assert isinstance(annot, COSDictionary)
        action_dict = annot.get_dictionary_object(COSName.get_pdf_name("A"))
        assert isinstance(action_dict, COSDictionary)
        d = action_dict.get_dictionary_object(COSName.get_pdf_name("D"))
        assert isinstance(d, COSArray)
        target = d.get_object(0)
        assert target is merged_pages[2].get_cos_object()


def test_merged_pdf_reparses_clean(tmp_path: Path, make_pdf) -> None:
    """End-to-end: the merged output must round-trip through the
    parser with the expected page count and intact annotations."""
    a = _build_pdf_with_link(
        tmp_path / "a.pdf",
        page_count=2,
        link_from_index=0,
        link_to_index=1,
    )
    b = make_pdf("b.pdf", page_count=2)
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(["merge", "-i", str(a), str(b), "-o", str(out)])
    assert rc == 0
    assert out.is_file()

    # Re-load via the public Loader-backed entrypoint and confirm the
    # page count and that page-0's link annotation survived the round
    # trip (still parseable as a Link with an explicit-array dest).
    with PDDocument.load(out) as merged:
        assert merged.get_number_of_pages() == 4
        page0 = next(iter(merged.get_pages()))
        link_target = _link_dest_target(page0.get_cos_object())
        assert link_target is not None
