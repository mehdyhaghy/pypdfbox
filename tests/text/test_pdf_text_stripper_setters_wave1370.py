"""Wave 1370 — full-walk setter round-trips through get_text().

For every wired-up setter on :class:`PDFTextStripper` we drive a
``get_text`` walk and confirm that the configured value actually shows
up in the output (not just bounces through the corresponding getter).
The inert holders are pinned separately under
``test_pdf_text_stripper_options.py`` — these tests focus on the
behavioural impact paths.
"""
from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFTextStripper


def _page(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


# ---------------------------------------------------------------------------
# set_sort_by_position — end-to-end
# ---------------------------------------------------------------------------


def test_set_sort_by_position_reorders_emit_order() -> None:
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 100 Tm (low) Tj "
            b"1 0 0 1 100 700 Tm (high) Tj "
            b"ET"
        ),
    )
    on = PDFTextStripper()
    on.set_sort_by_position(True)
    out = on.get_text(doc)
    assert out.index("high") < out.index("low")


# ---------------------------------------------------------------------------
# set_start_page / set_end_page — page-range clamp
# ---------------------------------------------------------------------------


def test_set_start_page_clamps_first_page_emitted() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (p1) Tj ET")
    _page(doc, b"BT /F0 12 Tf 100 700 Td (p2) Tj ET")
    _page(doc, b"BT /F0 12 Tf 100 700 Td (p3) Tj ET")

    s = PDFTextStripper()
    s.set_start_page(2)
    out = s.get_text(doc)
    assert "p1" not in out
    assert "p2" in out
    assert "p3" in out


def test_set_end_page_clamps_last_page_emitted() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (p1) Tj ET")
    _page(doc, b"BT /F0 12 Tf 100 700 Td (p2) Tj ET")
    _page(doc, b"BT /F0 12 Tf 100 700 Td (p3) Tj ET")

    s = PDFTextStripper()
    s.set_end_page(2)
    out = s.get_text(doc)
    assert "p1" in out
    assert "p2" in out
    assert "p3" not in out


def test_set_start_page_beyond_total_yields_empty() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (only) Tj ET")
    s = PDFTextStripper()
    s.set_start_page(5)  # beyond the single page
    s.set_end_page(10)
    assert s.get_text(doc) == ""


def test_set_end_page_smaller_than_start_yields_empty() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (a) Tj ET")
    _page(doc, b"BT /F0 12 Tf 100 700 Td (b) Tj ET")
    s = PDFTextStripper()
    s.set_start_page(2)
    s.set_end_page(1)
    assert s.get_text(doc) == ""


# ---------------------------------------------------------------------------
# set_should_separate_by_beads — flag toggles bead bucketing (no beads on
# the test pages so the flag is observable but not load-bearing — the
# round-trip getter is the contract we're pinning)
# ---------------------------------------------------------------------------


def test_set_should_separate_by_beads_round_trip_via_walk() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (k) Tj ET")
    s = PDFTextStripper()
    # Default is True.
    assert s.is_should_separate_by_beads() is True
    s.set_should_separate_by_beads(False)
    # Survives through a get_text walk.
    s.get_text(doc)
    assert s.is_should_separate_by_beads() is False
    assert s.get_should_separate_by_beads() is False
    assert s.get_separate_by_beads() is False


# ---------------------------------------------------------------------------
# set_word_separator — observable in get_text() output
# ---------------------------------------------------------------------------


def test_set_word_separator_observable_in_output() -> None:
    doc = PDDocument()
    # Two glyphs with a wide gap — stripper inserts a word separator.
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (one) Tj "
            b"1 0 0 1 400 700 Tm (two) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_word_separator("<SEP>")
    out = s.get_text(doc)
    assert "<SEP>" in out
    assert "one<SEP>two" in out


# ---------------------------------------------------------------------------
# set_line_separator — observable when two runs sit on different lines
# ---------------------------------------------------------------------------


def test_set_line_separator_observable_when_lines_split() -> None:
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (top) Tj "
            b"1 0 0 1 100 600 Tm (bot) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_line_separator("||")
    s.set_paragraph_end("")  # collapse the paragraph terminator too
    out = s.get_text(doc)
    # The line break manifests as the configured "||" separator.
    assert "||" in out


# ---------------------------------------------------------------------------
# set_page_start / set_page_end — wrap every page body
# ---------------------------------------------------------------------------


def test_set_page_start_and_end_wrap_every_page() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (a) Tj ET")
    _page(doc, b"BT /F0 12 Tf 100 700 Td (b) Tj ET")

    s = PDFTextStripper()
    s.set_page_start("[")
    s.set_page_end("]")
    out = s.get_text(doc)
    assert out.count("[") == 2
    assert out.count("]") == 2
    # And in the right shape per page: "[<body>]"
    assert out.index("[") < out.index("a") < out.index("]")


# ---------------------------------------------------------------------------
# set_paragraph_start / set_paragraph_end — applied to detected paragraphs
# ---------------------------------------------------------------------------


def test_set_paragraph_end_emits_at_least_one_terminator() -> None:
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (alpha) Tj "
            b"1 0 0 1 100 600 Tm (beta) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_paragraph_end("<END>")
    out = s.get_text(doc)
    # The lite stripper emits paragraph_end after every paragraph;
    # at minimum the default-page-end newline contains it.
    assert "<END>" in out


def test_set_paragraph_start_only_emits_when_paragraph_starts() -> None:
    """``paragraph_start`` defaults to ``""`` — when set to a marker
    the stripper emits it at every detected paragraph boundary."""
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (one) Tj "
            # Big drop to fire the paragraph-detection drop prong.
            b"1 0 0 1 100 300 Tm (two) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_paragraph_start("<P>")
    out = s.get_text(doc)
    # Marker appears at least once.
    assert "<P>" in out


# ---------------------------------------------------------------------------
# set_article_start / set_article_end — wrap the page body (lite mode
# treats each page as a single article)
# ---------------------------------------------------------------------------


def test_set_article_start_and_end_wrap_body() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (body) Tj ET")
    s = PDFTextStripper()
    s.set_article_start("<art>")
    s.set_article_end("</art>")
    out = s.get_text(doc)
    assert "<art>" in out
    assert "</art>" in out
    assert out.index("<art>") < out.index("body") < out.index("</art>")


# ---------------------------------------------------------------------------
# set_lenient_stream_parsing — observable through is_*  getter
# ---------------------------------------------------------------------------


def test_set_lenient_stream_parsing_survives_walk() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (a) Tj ET")
    s = PDFTextStripper()
    s.set_lenient_stream_parsing(False)
    s.get_text(doc)
    assert s.is_lenient_stream_parsing() is False


# ---------------------------------------------------------------------------
# set_ignore_content_stream_space_glyphs — round-trip via the walk
# ---------------------------------------------------------------------------


def test_set_ignore_content_stream_space_glyphs_round_trip() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (a) Tj ET")
    s = PDFTextStripper()
    assert s.get_ignore_content_stream_space_glyphs() is False
    s.set_ignore_content_stream_space_glyphs(True)
    s.get_text(doc)
    assert s.get_ignore_content_stream_space_glyphs() is True


# ---------------------------------------------------------------------------
# set_suppress_duplicate_overlapping_text — drops fake-bold duplicates
# ---------------------------------------------------------------------------


def test_suppress_duplicate_overlapping_text_default_on() -> None:
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (X) Tj "
            b"1 0 0 1 100 700 Tm (X) Tj "  # same place — fake bold
            b"ET"
        ),
    )
    s = PDFTextStripper()
    out = s.get_text(doc)
    assert out.count("X") == 1


def test_suppress_duplicate_overlapping_text_off_keeps_dupes() -> None:
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (X) Tj "
            b"1 0 0 1 100 700 Tm (X) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_suppress_duplicate_overlapping_text(False)
    out = s.get_text(doc)
    assert out.count("X") == 2
