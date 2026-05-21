"""Wave 1373 — pin the three Splitter audit-item closures.

1. ``Splitter.fix_destinations`` retargets cross-page link destinations to
   the cloned chunk pages (PDFBOX-5762 fixture). Verifies that the
   page-identity match uses the source-side snapshot captured at staging
   time, not the deep-copied cloned-array entry that would lose source
   identity.
2. ``Splitter`` ``/RoleMap`` narrowing on PDFBOX-5792-240045.pdf matches
   upstream's expected per-chunk sizes (3, 3, 4, 4, 6, 7) — including
   role names introduced via discarded-annotation back-refs.
3. ``Splitter`` popup ``/P`` / ``/Parent`` back-pointer identity holds
   across cloned pages of the same chunk — a markup annotation on chunk
   page A whose popup lives on chunk page B has its ``/Popup`` rewritten
   to the cloned popup dict (not the deep-copied source clone) and the
   popup's ``/Parent`` rewritten to the cloned markup dict.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.multipdf import Splitter
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_popup import (
    PDAnnotationPopup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text import (
    PDAnnotationText,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (  # noqa: E501
    PDPageDestination,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage

_FIXTURE_DIR = "tests/fixtures/multipdf"


# ---------- helpers ----------


def _annot(subtype: str) -> COSDictionary:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("Type"), "Annot")
    d.set_name(COSName.get_pdf_name("Subtype"), subtype)
    rect = COSArray()
    rect.add(COSFloat(0))
    rect.add(COSFloat(0))
    rect.add(COSFloat(100))
    rect.add(COSFloat(100))
    d.set_item(COSName.get_pdf_name("Rect"), rect)
    return d


# ---------- item 1: fix_destinations identity match ----------


def test_wave1373_fix_destinations_retargets_in_chunk_pages() -> None:
    """``fix_destinations`` rewrites ``/D[0]`` to the cloned chunk-page
    dict for link destinations whose source target is inside the chunk
    (PDFBOX-5762 — fixture annotations 0/1 retarget to chunk pages 0/1).

    Pins the closure of audit item *fix_destinations identity match*:
    pre-wave-1294, comparing against the deep-copied cloned-array entry
    instead of the source-page snapshot nulled pages 0/1 along with the
    cross-chunk pages 2/3/4.
    """
    with PDDocument.load(f"{_FIXTURE_DIR}/PDFBOX-5762-722238.pdf") as doc:
        splitter = Splitter()
        splitter.set_start_page(1)
        splitter.set_end_page(2)
        splitter.set_split_at_page(2)
        chunks = splitter.split(doc)
        assert len(chunks) == 1
        with chunks[0] as chunk:
            annotations = chunk.get_page(0).get_annotations()
            assert len(annotations) == 5
            actions = []
            for ann in annotations:
                assert isinstance(ann, PDAnnotationLink)
                action = ann.get_action()
                assert isinstance(action, PDActionGoTo)
                actions.append(action)
            destinations = [a.get_destination() for a in actions]
            for dest in destinations:
                assert isinstance(dest, PDPageDestination)
            page_tree = chunk.get_pages()
            # Pages 0/1 retarget to the chunk's pages 0/1 — identity
            # match resolved through the source-page snapshot.
            assert page_tree.index_of(destinations[0].get_page()) == 0
            assert page_tree.index_of(destinations[1].get_page()) == 1
            # Pages 2/3/4 are outside the chunk → /D[0] nulled out.
            assert destinations[2].get_page() is None
            assert destinations[3].get_page() is None
            assert destinations[4].get_page() is None


# ---------- item 2: role-map narrowing via discarded annot back-refs ----------


def test_wave1373_role_map_narrowing_matches_upstream_5792() -> None:
    """Per-chunk ``/RoleMap`` sizes on PDFBOX-5792-240045.pdf match
    upstream's expected ``[3, 3, 4, 4, 6, 7]``.

    Pins the closure of audit item *role-map narrowing* — pre-wave-1295
    the first chunk dropped one mapping ("Strong" or similar) because
    ``_role_set`` reset per chunk discarded role names contributed by
    discarded-annotation back-refs walked through the page resources.
    """
    expected_role_map_sizes = [3, 3, 4, 4, 6, 7]
    expected_parent_tree_sizes = [6, 6, 6, 5, 1, 1]
    with PDDocument.load(f"{_FIXTURE_DIR}/PDFBOX-5792-240045.pdf") as doc:
        splitter = Splitter()
        splitter.set_split_at_page(1)
        chunks = splitter.split(doc)
        assert len(chunks) == 6
        try:
            for index, chunk in enumerate(chunks):
                struct_root = (
                    chunk.get_document_catalog().get_structure_tree_root()
                )
                assert struct_root is not None
                role_map = struct_root.get_role_map()
                assert (
                    len(role_map) == expected_role_map_sizes[index]
                ), f"chunk {index} role-map size mismatch (got {role_map})"
                from pypdfbox.multipdf.pdf_merger_utility import (
                    PDFMergerUtility,
                )

                parent_tree = struct_root.get_parent_tree()
                pt_map = PDFMergerUtility.get_number_tree_as_map(parent_tree)
                assert (
                    len(pt_map) == expected_parent_tree_sizes[index]
                ), f"chunk {index} parent-tree size mismatch"
        finally:
            for chunk in chunks:
                chunk.close()


# ---------- item 3: popup back-pointer identity across cloned pages ----------


def _build_cross_page_popup_doc() -> bytes:
    """Synthesise a 2-page PDF where the markup lives on page 0 and its
    popup lives on page 1. Both pages belong to the same chunk after a
    ``split_at_page(2)`` split."""
    doc = PDDocument()
    p0 = PDPage(PDRectangle.A4)
    p1 = PDPage(PDRectangle.A4)
    doc.add_page(p0)
    doc.add_page(p1)

    markup = _annot("Text")
    popup = _annot("Popup")
    markup.set_item(COSName.get_pdf_name("Popup"), popup)
    popup.set_item(COSName.get_pdf_name("Parent"), markup)
    # /P back-pointers
    popup.set_item(COSName.get_pdf_name("P"), p1.get_cos_object())
    markup.set_item(COSName.get_pdf_name("P"), p0.get_cos_object())

    a0 = COSArray()
    a0.add(markup)
    p0.get_cos_object().set_item(COSName.get_pdf_name("Annots"), a0)
    a1 = COSArray()
    a1.add(popup)
    p1.get_cos_object().set_item(COSName.get_pdf_name("Annots"), a1)

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def test_wave1373_popup_back_pointer_identity_across_chunk_pages() -> None:
    """A markup on chunk page A whose popup lives on chunk page B keeps
    cross-annotation back-pointer identity after the chunk is built:

    * markup's ``/Popup`` is the cloned popup dict (not a deep-copy
      clone of the source popup);
    * popup's ``/Parent`` is the cloned markup dict;
    * each annotation's ``/P`` matches the chunk's corresponding page
      dict.

    Pre-wave-1373 the per-page second pass ran before the next page's
    first pass populated ``_annot_dict_map``, so the markup's ``/Popup``
    lookup missed and left the deep-copied source popup in place.
    """
    pdf_bytes = _build_cross_page_popup_doc()
    with PDDocument.load(pdf_bytes) as loaded:
        splitter = Splitter()
        splitter.set_split_at_page(2)
        chunks = splitter.split(loaded)
        assert len(chunks) == 1
        with chunks[0] as chunk:
            assert chunk.get_number_of_pages() == 2
            page0_annots = chunk.get_page(0).get_annotations()
            page1_annots = chunk.get_page(1).get_annotations()
            assert len(page0_annots) == 1
            assert len(page1_annots) == 1
            markup_clone = page0_annots[0]
            popup_clone = page1_annots[0]
            assert isinstance(markup_clone, PDAnnotationText)
            assert isinstance(popup_clone, PDAnnotationPopup)
            # Cross-page popup ↔ markup identity restored.
            assert (
                markup_clone.get_cos_object().get_dictionary_object("Popup")
                is popup_clone.get_cos_object()
            )
            assert (
                popup_clone.get_cos_object().get_dictionary_object("Parent")
                is markup_clone.get_cos_object()
            )
            # /P back-pointers match their host page dicts.
            assert (
                markup_clone.get_cos_object().get_dictionary_object("P")
                is chunk.get_page(0).get_cos_object()
            )
            assert (
                popup_clone.get_cos_object().get_dictionary_object("P")
                is chunk.get_page(1).get_cos_object()
            )


def test_wave1373_same_page_popup_identity_holds_after_refactor() -> None:
    """The existing single-page popup-on-same-page case (PDFBOX-5809
    fixture) still works after the second-pass move. Mirror of the
    upstream parity assertions in
    ``test_split_with_popup_annotations`` so a future refactor that
    drains the queue too early gets caught here as well."""
    with PDDocument.load(f"{_FIXTURE_DIR}/PDFBOX-5809-509329.pdf") as doc:
        splitter = Splitter()
        splitter.set_start_page(3)
        splitter.set_end_page(3)
        splitter.set_split_at_page(1)
        chunks = splitter.split(doc)
        assert len(chunks) == 1
        with chunks[0] as chunk:
            annots = chunk.get_page(0).get_annotations()
            assert len(annots) == 5
            text3 = annots[3]
            popup4 = annots[4]
            assert isinstance(text3, PDAnnotationText)
            assert isinstance(popup4, PDAnnotationPopup)
            assert text3.get_popup() == popup4
            assert popup4.get_parent_markup() == text3
            assert text3.get_page() is chunk.get_page(0).get_cos_object()


def test_wave1373_orphan_popup_clone_remains_linked() -> None:
    """A markup whose popup isn't in any page's ``/Annots`` still gets
    a cloned popup dict re-linked via ``/Popup`` ↔ ``/Parent``. Pins
    that the deferred chunk-finalize doesn't skip the orphan branch."""
    with PDDocument.load(
        f"{_FIXTURE_DIR}/PDFBOX-6018-099267-p9-OrphanPopups.pdf"
    ) as doc:
        splitter = Splitter()
        chunks = splitter.split(doc)
        assert len(chunks) == 1
        with chunks[0] as chunk:
            page = chunk.get_page(0)
            annots = page.get_annotations()
            assert len(annots) == 2
            for ann in annots:
                assert ann.get_page() is page.get_cos_object()
                popup = ann.get_popup()
                assert isinstance(popup, PDAnnotationPopup)
                assert popup.get_parent_markup() == ann


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-q", "--no-cov"])
