"""PDFBOX-6145 — no ``hasContents()`` gate in the text-stripper page loops.

JIRA title: *"Extremely slow text extraction of single page of large
PDF"*. ``PDPage.hasContents()`` resolves ``/Contents`` — an indirect
reference, sometimes an array of them — for **every** page in the tree, so
gating the loop on it made the "extract page 900 of 1000" case pay for all
1000 pages. Upstream 3.0.9 deletes the gate from
``PDFTextStripper.processPages`` and ``PDFTextStripperByArea.extractRegions``;
``PDFStreamEngine.processPage`` keeps its own guard, so a contentless page
simply yields no glyphs while the per-page hooks still fire.
"""

from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFTextStripper, PDFTextStripperByArea


def _page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


def _blank_page(doc: PDDocument) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    doc.add_page(page)
    return page


# ---------------------------------------------------------------------------
# PDFTextStripper.process_pages
# ---------------------------------------------------------------------------


def test_process_pages_visits_contentless_pages() -> None:
    doc = PDDocument()
    try:
        blank_a = _blank_page(doc)
        with_text = _page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (hi) Tj ET")
        blank_b = _blank_page(doc)
        assert blank_a.has_contents() is False

        stripper = PDFTextStripper()
        stripper._active_document = doc
        visited: list[PDPage] = []
        original = stripper.process_page

        def spy(page: PDPage) -> str:
            visited.append(page)
            return original(page)

        stripper.process_page = spy  # type: ignore[method-assign]
        stripper.process_pages([blank_a, with_text, blank_b])

        assert visited == [blank_a, with_text, blank_b]
    finally:
        doc.close()


def test_process_pages_does_not_resolve_contents_itself() -> None:
    """The loop must not probe ``/Contents`` — that probe was the cost
    PDFBOX-6145 removed."""
    doc = PDDocument()
    try:
        page = _page_with_stream(doc, b"BT /F0 12 Tf 10 10 Td (a) Tj ET")
        probes: list[int] = []
        real_has_contents = page.has_contents

        def counting_has_contents() -> bool:
            probes.append(1)
            return real_has_contents()

        page.has_contents = counting_has_contents  # type: ignore[method-assign]

        stripper = PDFTextStripper()
        stripper._active_document = doc
        stripper.process_pages([page])

        assert probes == []
    finally:
        doc.close()


def test_page_counter_still_advances_over_contentless_pages() -> None:
    doc = PDDocument()
    try:
        pages = [_blank_page(doc), _blank_page(doc), _blank_page(doc)]
        stripper = PDFTextStripper()
        stripper._active_document = doc
        seen: list[int] = []

        original = stripper.process_page

        def spy(page: PDPage) -> str:
            seen.append(stripper.get_current_page_no())
            return original(page)

        stripper.process_page = spy  # type: ignore[method-assign]
        stripper.process_pages(pages)

        assert seen == [0, 1, 2]
    finally:
        doc.close()


def test_get_text_emits_a_page_terminator_for_a_contentless_page() -> None:
    """``get_text`` already ran the per-page hooks unconditionally; this
    pins the shape ``process_pages`` now agrees with."""
    doc = PDDocument()
    try:
        _page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (hi) Tj ET")
        _blank_page(doc)
        stripper = PDFTextStripper()
        text = stripper.get_text(doc)
        assert text.count(stripper.get_line_separator()) >= 2
    finally:
        doc.close()


def test_start_and_end_page_hooks_fire_for_contentless_pages() -> None:
    doc = PDDocument()
    try:
        blank = _blank_page(doc)
        _page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (hi) Tj ET")

        started: list[PDPage] = []
        ended: list[PDPage] = []

        class _HookStripper(PDFTextStripper):
            def start_page(self, page: PDPage) -> None:
                started.append(page)

            def end_page(self, page: PDPage) -> None:
                ended.append(page)

        _HookStripper().get_text(doc)
        assert blank in started
        assert blank in ended
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# PDFTextStripperByArea.extract_regions
# ---------------------------------------------------------------------------


def test_extract_regions_walks_a_contentless_page() -> None:
    doc = PDDocument()
    try:
        blank = _blank_page(doc)
        stripper = PDFTextStripperByArea()
        stripper.add_region("r", (0.0, 0.0, 612.0, 792.0))
        stripper.extract_regions(blank)
        # The region captured nothing, but the per-region writePage still
        # emitted the page terminator — same as an in-range empty region.
        assert stripper.get_text_for_region("r") == stripper.get_line_separator()
    finally:
        doc.close()


def test_extract_regions_contentless_matches_empty_region_shape() -> None:
    """A contentless page and a page whose text misses every region must
    now produce identical region output."""
    doc = PDDocument()
    try:
        blank = _blank_page(doc)
        far = _page_with_stream(doc, b"BT /F0 12 Tf 500 700 Td (hi) Tj ET")

        stripper = PDFTextStripperByArea()
        stripper.add_region("r", (0.0, 0.0, 10.0, 10.0))

        stripper.extract_regions(far)
        far_text = stripper.get_text_for_region("r")
        stripper.extract_regions(blank)
        blank_text = stripper.get_text_for_region("r")

        assert blank_text == far_text
    finally:
        doc.close()


def test_extract_regions_contentless_page_clears_prior_text() -> None:
    doc = PDDocument()
    try:
        page = _page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (hello) Tj ET")
        blank = _blank_page(doc)

        stripper = PDFTextStripperByArea()
        stripper.add_region("r", (50.0, 690.0, 500.0, 20.0))
        stripper.extract_regions(page)
        assert stripper.get_text_for_region("r").strip() == "hello"

        stripper.extract_regions(blank)
        assert stripper.get_text_for_region("r").strip() == ""
    finally:
        doc.close()
