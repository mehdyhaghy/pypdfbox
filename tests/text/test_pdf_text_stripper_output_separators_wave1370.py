"""Wave 1370 — output separators round-trip through get_text() + write_text().

Pins the configurable text separators against the actual text emitted
by a ``PDFTextStripper`` walk:

  - ``line_separator``     — emitted between lines on the same page.
  - ``word_separator``     — emitted between word-broken runs on the same line.
  - ``page_start`` / ``page_end`` — wrap every page's body.
  - ``paragraph_start`` / ``paragraph_end`` — wrap detected paragraphs.

Also verifies the same separators flow through the ``write_text``
streaming entry point (which streams text into a caller-supplied
writer) without dropping any markers along the way.
"""
from __future__ import annotations

import io

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
# Round-trip: every set_* is observable in get_text()
# ---------------------------------------------------------------------------


def test_round_trip_word_separator_observable() -> None:
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (foo) Tj "
            b"1 0 0 1 400 700 Tm (bar) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_word_separator(" / ")
    out = s.get_text(doc)
    assert "foo / bar" in out


def test_round_trip_line_separator_observable() -> None:
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
    s.set_line_separator("###")
    s.set_paragraph_end("")
    out = s.get_text(doc)
    assert "top###bot" in out


def test_round_trip_page_start_and_end_observable() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (body) Tj ET")
    s = PDFTextStripper()
    s.set_page_start("<PAGE>")
    s.set_page_end("</PAGE>")
    out = s.get_text(doc)
    assert out.startswith("<PAGE>")
    assert out.endswith("</PAGE>")
    assert "body" in out


def test_round_trip_paragraph_end_observable() -> None:
    """``paragraph_end`` fires at every detected paragraph boundary.
    Set up a content stream that triggers one via a big y-drop, then
    confirm the configured marker shows up in the output."""
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (alpha) Tj "
            # Large y-drop -> paragraph separation.
            b"1 0 0 1 100 100 Tm (beta) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_paragraph_end("<PE>")
    out = s.get_text(doc)
    assert "<PE>" in out


def test_round_trip_paragraph_start_observable_on_paragraph_drop() -> None:
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (a) Tj "
            # Massive y-drop -> paragraph separation fires.
            b"1 0 0 1 100 100 Tm (b) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_paragraph_start("<PS>")
    out = s.get_text(doc)
    assert "<PS>" in out


# ---------------------------------------------------------------------------
# Empty-string separators collapse the corresponding break
# ---------------------------------------------------------------------------


def test_empty_word_separator_collapses_word_breaks() -> None:
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (foo) Tj "
            b"1 0 0 1 400 700 Tm (bar) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_word_separator("")
    s.set_page_end("")
    out = s.get_text(doc)
    assert out == "foobar"


def test_empty_line_separator_collapses_line_breaks() -> None:
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
    s.set_line_separator("")
    s.set_paragraph_end("")
    s.set_page_end("")
    out = s.get_text(doc)
    assert out == "topbot"


def test_empty_page_end_concatenates_pages() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (a) Tj ET")
    _page(doc, b"BT /F0 12 Tf 100 700 Td (b) Tj ET")
    s = PDFTextStripper()
    s.set_page_end("")
    out = s.get_text(doc)
    assert out == "ab"


# ---------------------------------------------------------------------------
# write_text streams through the configured separators identically
# ---------------------------------------------------------------------------


def test_write_text_uses_same_separators_as_get_text() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (alpha) Tj ET")
    _page(doc, b"BT /F0 12 Tf 100 700 Td (beta) Tj ET")

    s = PDFTextStripper()
    s.set_page_start("|")
    s.set_page_end("|")
    s.set_word_separator(" ")

    buffer = io.StringIO()
    s.write_text(doc, buffer)
    streamed = buffer.getvalue()
    assert streamed == s.get_text(doc)


def test_write_text_clears_output_handle_after_completion() -> None:
    """``write_text`` installs the writer for the duration of the
    walk and restores ``output`` to its previous (None) state when
    the walk completes — the ``get_output`` accessor should reflect
    that."""
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (one) Tj ET")
    s = PDFTextStripper()
    assert s.get_output() is None
    buffer = io.StringIO()
    s.write_text(doc, buffer)
    # Restored to its previous value.
    assert s.get_output() is None
    # And the writer received the text.
    assert "one" in buffer.getvalue()


# ---------------------------------------------------------------------------
# Default separators round-trip when nothing is configured
# ---------------------------------------------------------------------------


def test_default_line_separator_is_newline_in_output() -> None:
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
    out = s.get_text(doc)
    # Default line separator is "\n"; both lines must appear separated.
    assert "\n" in out
    assert "top" in out and "bot" in out


def test_default_page_end_is_newline_in_output() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (only) Tj ET")
    s = PDFTextStripper()
    out = s.get_text(doc)
    # Default page_end is "\n".
    assert out.endswith("\n")
    assert "only" in out


def test_round_trip_independent_separators_no_cross_talk() -> None:
    """Setting word_separator to a value should not change the line
    separator, and vice versa."""
    s = PDFTextStripper()
    s.set_word_separator("W")
    s.set_line_separator("L")
    assert s.get_word_separator() == "W"
    assert s.get_line_separator() == "L"
    s.set_word_separator("Q")
    assert s.get_line_separator() == "L"  # unchanged


# ---------------------------------------------------------------------------
# Multi-page output respects every configured separator together
# ---------------------------------------------------------------------------


def test_combined_separators_layout_two_pages() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (a) Tj ET")
    _page(doc, b"BT /F0 12 Tf 100 700 Td (b) Tj ET")

    s = PDFTextStripper()
    s.set_page_start("<S>")
    s.set_page_end("<E>")
    out = s.get_text(doc)
    # Each page is wrapped by start + end exactly once.
    assert out.count("<S>") == 2
    assert out.count("<E>") == 2
    # The pair sandwich is preserved in order:  <S>a<E><S>b<E>.
    assert out == "<S>a<E><S>b<E>"
