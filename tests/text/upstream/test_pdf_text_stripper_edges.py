"""Upstream-shaped edge-case tests for :class:`PDFTextStripper`.

The upstream JUnit suite ``TestTextStripper.java`` exercises the full
layout pipeline against bundled PDF fixtures and is not portable
verbatim against the lite stripper. This file pins the upstream-named
configuration knobs and writer hooks added for API parity, using
synthetic content streams the lite stripper can drive end-to-end.

Each test below maps to an upstream concern (commented inline) so the
intent stays diff-able against future re-syncs of upstream behaviour.
"""

from __future__ import annotations

import sys

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (
    PDPageFitDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (
    PDOutlineItem,
)
from pypdfbox.text import PDFTextStripper


def _make_page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


# ---------------------------------------------------------------------------
# upstream: ``PDFTextStripper`` defaults (mirrors field initialisers)
# ---------------------------------------------------------------------------


def test_defaults_match_upstream() -> None:
    s = PDFTextStripper()
    # Mirrors the JavaDoc / source defaults of upstream
    # ``PDFTextStripper`` setters/getters that we expose.
    assert s.get_start_page() == 1
    # Upstream uses ``Integer.MAX_VALUE``; pypdfbox uses ``sys.maxsize``
    # — both clamp to ``len(pages)`` in ``getText``.
    assert s.get_end_page() == sys.maxsize
    assert s.get_word_separator() == " "
    assert s.get_line_separator() == "\n"
    assert s.get_page_start() == ""
    assert s.get_page_end() == "\n"
    assert s.get_paragraph_start() == ""
    # See comment in ``pdf_text_stripper.py``: pypdfbox keeps
    # ``"\n"`` here vs upstream's ``""``.
    assert s.get_paragraph_end() == "\n"
    assert s.get_article_start() == ""
    assert s.get_article_end() == ""
    assert s.get_sort_by_position() is False
    assert s.is_sort_by_position() is False
    assert s.get_should_separate_by_beads() is True
    assert s.is_should_separate_by_beads() is True
    assert s.get_suppress_duplicate_overlapping_text() is True
    assert s.get_drop_threshold() == 2.5
    assert s.get_indent_threshold() == 2.0
    assert s.get_spacing_tolerance() == 0.5
    assert s.get_average_char_tolerance() == 0.3
    assert s.get_start_bookmark() is None
    assert s.get_end_bookmark() is None


# ---------------------------------------------------------------------------
# upstream: ``setSortByPosition`` round-trip
# ---------------------------------------------------------------------------


def test_set_sort_by_position_round_trip() -> None:
    s = PDFTextStripper()
    s.set_sort_by_position(True)
    assert s.get_sort_by_position() is True
    s.set_sort_by_position(False)
    assert s.get_sort_by_position() is False


# ---------------------------------------------------------------------------
# upstream: ``setSuppressDuplicateOverlappingText``
# ---------------------------------------------------------------------------


def test_set_suppress_duplicate_overlapping_text_round_trip() -> None:
    s = PDFTextStripper()
    s.set_suppress_duplicate_overlapping_text(False)
    assert s.get_suppress_duplicate_overlapping_text() is False
    s.set_suppress_duplicate_overlapping_text(True)
    assert s.get_suppress_duplicate_overlapping_text() is True


# ---------------------------------------------------------------------------
# upstream: ``setShouldSeparateByBeads``
# ---------------------------------------------------------------------------


def test_set_should_separate_by_beads_round_trip() -> None:
    s = PDFTextStripper()
    s.set_should_separate_by_beads(False)
    assert s.get_should_separate_by_beads() is False
    s.set_should_separate_by_beads(True)
    assert s.get_should_separate_by_beads() is True


# ---------------------------------------------------------------------------
# upstream: line / word / page / paragraph / article separators
# ---------------------------------------------------------------------------


def test_set_line_separator_round_trip() -> None:
    s = PDFTextStripper()
    s.set_line_separator("\r\n")
    assert s.get_line_separator() == "\r\n"


def test_set_word_separator_round_trip() -> None:
    s = PDFTextStripper()
    s.set_word_separator("_")
    assert s.get_word_separator() == "_"


def test_set_page_start_and_end_round_trip() -> None:
    s = PDFTextStripper()
    s.set_page_start("<page>")
    s.set_page_end("</page>")
    assert s.get_page_start() == "<page>"
    assert s.get_page_end() == "</page>"


def test_set_paragraph_start_and_end_round_trip() -> None:
    s = PDFTextStripper()
    s.set_paragraph_start("<p>")
    s.set_paragraph_end("</p>")
    assert s.get_paragraph_start() == "<p>"
    assert s.get_paragraph_end() == "</p>"


def test_set_article_start_and_end_round_trip() -> None:
    s = PDFTextStripper()
    s.set_article_start("<a>")
    s.set_article_end("</a>")
    assert s.get_article_start() == "<a>"
    assert s.get_article_end() == "</a>"


# ---------------------------------------------------------------------------
# upstream: numeric tolerances
# ---------------------------------------------------------------------------


def test_set_spacing_tolerance_round_trip() -> None:
    s = PDFTextStripper()
    s.set_spacing_tolerance(0.4)
    assert s.get_spacing_tolerance() == 0.4


def test_set_average_char_tolerance_round_trip() -> None:
    s = PDFTextStripper()
    s.set_average_char_tolerance(0.5)
    assert s.get_average_char_tolerance() == 0.5


def test_set_indent_threshold_round_trip() -> None:
    s = PDFTextStripper()
    s.set_indent_threshold(4.0)
    assert s.get_indent_threshold() == 4.0


def test_set_drop_threshold_round_trip() -> None:
    s = PDFTextStripper()
    s.set_drop_threshold(3.25)
    assert s.get_drop_threshold() == 3.25


# ---------------------------------------------------------------------------
# upstream: ``setStartBookmark`` / ``setEndBookmark``
# ---------------------------------------------------------------------------


def test_set_start_and_end_bookmark_round_trip() -> None:
    s = PDFTextStripper()
    bm1 = PDOutlineItem()
    bm2 = PDOutlineItem()
    s.set_start_bookmark(bm1)
    s.set_end_bookmark(bm2)
    assert s.get_start_bookmark() is bm1
    assert s.get_end_bookmark() is bm2


def test_bookmarks_clamp_extraction_range() -> None:
    """Mirrors upstream behaviour: when both bookmarks are set the
    extraction is limited to the resolved bookmark page range."""
    doc = PDDocument()
    for label in (b"p1", b"p2", b"p3", b"p4"):
        _make_page_with_stream(
            doc, b"BT /F0 12 Tf 100 700 Td (" + label + b") Tj ET"
        )
    pages = doc.get_pages()

    def bookmark_for(idx: int) -> PDOutlineItem:
        dest = PDPageFitDestination()
        dest.set_page(pages[idx])
        item = PDOutlineItem()
        item.set_destination(dest)
        return item

    s = PDFTextStripper()
    s.set_start_bookmark(bookmark_for(1))  # page 2
    s.set_end_bookmark(bookmark_for(2))  # page 3
    assert s.get_text(doc) == "p2\np3\n"


# ---------------------------------------------------------------------------
# upstream: ``writeString`` / ``writeLineSeparator`` / ``writeWordSeparator``
# subclass overrides flow through to ``getText`` output
# ---------------------------------------------------------------------------


def test_write_hooks_override_emission() -> None:
    """Mirrors upstream subclass pattern (e.g. ``PDFTextStripperByXY``)
    where overriding ``writeString`` etc. transforms the output."""

    class HtmlStripper(PDFTextStripper):
        def write_string(self, text, text_positions, sink) -> None:  # type: ignore[override]
            sink(f"<t>{text}</t>")

        def write_word_separator(self, sink) -> None:  # type: ignore[override]
            sink("&nbsp;")

        def write_line_separator(self, sink) -> None:  # type: ignore[override]
            sink("<br/>")

        def write_page_start(self, sink) -> None:  # type: ignore[override]
            sink("<page>")

        def write_page_end(self, sink) -> None:  # type: ignore[override]
            sink("</page>")

    doc = PDDocument()
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"100 700 Td (foo) Tj "
            b"200 0 Td (bar) Tj "
            b"-200 -14 Td (baz) Tj "
            b"ET"
        ),
    )
    out = HtmlStripper().get_text(doc)
    assert out == "<page><t>foo</t>&nbsp;<t>bar</t><br/><t>baz</t></page>"


# ---------------------------------------------------------------------------
# upstream: ``processTextPosition`` invoked per glyph
# ---------------------------------------------------------------------------


def test_process_text_position_called_for_every_emitted_run() -> None:
    """Upstream's ``PDFStreamEngine.processTextPosition`` fires once
    per glyph; the lite stripper aggregates per-run, so this confirms
    the hook fires once per emitted run rather than zero times."""

    captured: list[str] = []

    class CountingStripper(PDFTextStripper):
        def process_text_position(self, text) -> None:  # type: ignore[override]
            captured.append(text.text)

    doc = PDDocument()
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"100 700 Td (alpha) Tj "
            b"0 -14 Td (beta) Tj "
            b"ET"
        ),
    )
    CountingStripper().get_text(doc)
    assert captured == ["alpha", "beta"]


# ---------------------------------------------------------------------------
# upstream: ``setSuppressDuplicateOverlappingText(true)`` collapses
# coincident-glyph fake-bold pairs.
# ---------------------------------------------------------------------------


def test_duplicate_overlapping_text_collapsed_by_default() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (Z) Tj "
            b"1 0 0 1 100 700 Tm (Z) Tj "
            b"ET"
        ),
    )
    assert PDFTextStripper().get_text(doc) == "Z\n"


def test_duplicate_overlapping_text_kept_when_disabled() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (Z) Tj "
            b"1 0 0 1 100 700 Tm (Z) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_suppress_duplicate_overlapping_text(False)
    assert s.get_text(doc) == "ZZ\n"
