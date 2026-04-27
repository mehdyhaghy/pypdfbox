"""Configuration-option coverage for :class:`PDFTextStripper`.

These tests pin the upstream-shaped option setters/getters added for
PDFBox API parity. Most of the options are inert holders today (the
lite extraction loop doesn't consume them); the round-trip tests guard
against accidental drift in defaults or accessor names so callers can
configure a stripper exactly as they would in Java PDFBox.

A handful are wired through the extraction loop and get behavioural
tests on top of the round-trip checks:

  - ``start_page`` / ``end_page`` gate ``process_page`` calls.
  - ``page_start`` is emitted before each page's body.
  - ``sort_by_position`` re-orders positions before formatting so an
    out-of-order content stream still emits in geometric reading order.
"""

from __future__ import annotations

import sys

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFTextStripper


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_default_sort_by_position_is_false() -> None:
    s = PDFTextStripper()
    assert s.is_sort_by_position() is False


def test_default_should_separate_by_beads_is_true() -> None:
    s = PDFTextStripper()
    assert s.is_should_separate_by_beads() is True
    # And the legacy ``get_*`` alias still resolves to the same value.
    assert s.get_should_separate_by_beads() is True


def test_default_suppress_duplicate_overlapping_text_is_true() -> None:
    s = PDFTextStripper()
    assert s.is_suppress_duplicate_overlapping_text() is True


def test_default_start_page_is_one() -> None:
    s = PDFTextStripper()
    assert s.get_start_page() == 1


def test_default_end_page_is_max_int() -> None:
    s = PDFTextStripper()
    # pypdfbox keeps ``sys.maxsize`` as the sentinel (vs upstream's
    # ``Integer.MAX_VALUE``); both clamp to ``len(pages)`` in practice.
    assert s.get_end_page() == sys.maxsize


def test_default_word_separator_is_space() -> None:
    s = PDFTextStripper()
    assert s.get_word_separator() == " "


def test_default_line_separator_is_newline() -> None:
    s = PDFTextStripper()
    assert s.get_line_separator() == "\n"


def test_default_paragraph_start_is_empty() -> None:
    s = PDFTextStripper()
    assert s.get_paragraph_start() == ""


def test_default_paragraph_end_is_newline() -> None:
    # See pypdfbox/text/pdf_text_stripper.py: the lite stripper keeps
    # ``"\n"`` here (vs upstream ``""``) so the existing extraction
    # contract stays stable until real paragraph detection lands.
    s = PDFTextStripper()
    assert s.get_paragraph_end() == "\n"


def test_default_page_start_is_empty() -> None:
    s = PDFTextStripper()
    assert s.get_page_start() == ""


def test_default_page_end_is_newline() -> None:
    s = PDFTextStripper()
    assert s.get_page_end() == "\n"


def test_default_drop_threshold() -> None:
    s = PDFTextStripper()
    assert s.get_drop_threshold() == 2.5


def test_default_indent_threshold() -> None:
    s = PDFTextStripper()
    assert s.get_indent_threshold() == 2.0


def test_default_spacing_tolerance() -> None:
    s = PDFTextStripper()
    assert s.get_spacing_tolerance() == 0.5


def test_default_average_char_tolerance() -> None:
    s = PDFTextStripper()
    assert s.get_average_char_tolerance() == 0.3


def test_default_add_more_formatting_is_false() -> None:
    s = PDFTextStripper()
    assert s.get_add_more_formatting() is False


def test_default_lenient_stream_parsing_is_true() -> None:
    s = PDFTextStripper()
    assert s.is_lenient_stream_parsing() is True


# ---------------------------------------------------------------------------
# Round-trip set/get for each option
# ---------------------------------------------------------------------------


def test_round_trip_sort_by_position() -> None:
    s = PDFTextStripper()
    s.set_sort_by_position(True)
    assert s.is_sort_by_position() is True
    s.set_sort_by_position(False)
    assert s.is_sort_by_position() is False


def test_round_trip_should_separate_by_beads() -> None:
    s = PDFTextStripper()
    s.set_should_separate_by_beads(False)
    assert s.is_should_separate_by_beads() is False
    assert s.get_should_separate_by_beads() is False


def test_round_trip_suppress_duplicate_overlapping_text() -> None:
    s = PDFTextStripper()
    s.set_suppress_duplicate_overlapping_text(False)
    assert s.is_suppress_duplicate_overlapping_text() is False


def test_round_trip_start_page() -> None:
    s = PDFTextStripper()
    s.set_start_page(7)
    assert s.get_start_page() == 7


def test_round_trip_end_page() -> None:
    s = PDFTextStripper()
    s.set_end_page(42)
    assert s.get_end_page() == 42


def test_round_trip_line_separator() -> None:
    s = PDFTextStripper()
    s.set_line_separator("\r\n")
    assert s.get_line_separator() == "\r\n"


def test_round_trip_word_separator() -> None:
    s = PDFTextStripper()
    s.set_word_separator("\t")
    assert s.get_word_separator() == "\t"


def test_round_trip_paragraph_start() -> None:
    s = PDFTextStripper()
    s.set_paragraph_start("<p>")
    assert s.get_paragraph_start() == "<p>"


def test_round_trip_paragraph_end() -> None:
    s = PDFTextStripper()
    s.set_paragraph_end("</p>")
    assert s.get_paragraph_end() == "</p>"


def test_round_trip_page_start() -> None:
    s = PDFTextStripper()
    s.set_page_start("<page>")
    assert s.get_page_start() == "<page>"


def test_round_trip_page_end() -> None:
    s = PDFTextStripper()
    s.set_page_end("</page>")
    assert s.get_page_end() == "</page>"


def test_round_trip_drop_threshold() -> None:
    s = PDFTextStripper()
    s.set_drop_threshold(1.25)
    assert s.get_drop_threshold() == 1.25


def test_round_trip_indent_threshold() -> None:
    s = PDFTextStripper()
    s.set_indent_threshold(3.0)
    assert s.get_indent_threshold() == 3.0


def test_round_trip_spacing_tolerance() -> None:
    s = PDFTextStripper()
    s.set_spacing_tolerance(0.9)
    assert s.get_spacing_tolerance() == 0.9


def test_round_trip_average_char_tolerance() -> None:
    s = PDFTextStripper()
    s.set_average_char_tolerance(0.7)
    assert s.get_average_char_tolerance() == 0.7


def test_round_trip_add_more_formatting() -> None:
    s = PDFTextStripper()
    s.set_add_more_formatting(True)
    assert s.get_add_more_formatting() is True


def test_round_trip_lenient_stream_parsing() -> None:
    s = PDFTextStripper()
    s.set_lenient_stream_parsing(False)
    assert s.is_lenient_stream_parsing() is False


# ---------------------------------------------------------------------------
# Behavioural tests for the wired-up options
# ---------------------------------------------------------------------------


def test_start_page_and_end_page_extract_only_middle_page() -> None:
    """A 3-page synthetic doc + ``start_page=2``/``end_page=2`` should
    yield only page 2's body, wrapped in the configured ``page_end``."""
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (page1) Tj ET")
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (page2) Tj ET")
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (page3) Tj ET")
    s = PDFTextStripper()
    s.set_start_page(2)
    s.set_end_page(2)
    assert s.get_text(doc) == "page2\n"


def test_page_start_marker_emitted_before_each_page() -> None:
    """Setting ``page_start`` should prepend the marker before the
    body of every page in the extracted range."""
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (a) Tj ET")
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (b) Tj ET")
    s = PDFTextStripper()
    s.set_page_start(">>>")
    out = s.get_text(doc)
    # Two pages, each prefixed by the marker, each terminated by the
    # default ``"\n"`` page_end.
    assert out == ">>>a\n>>>b\n"
    # And the marker count matches the page count.
    assert out.count(">>>") == 2


def test_sort_by_position_reorders_out_of_order_stream() -> None:
    """A content stream that paints "second" above "first" in the
    page (higher ``y``) but emits "first" first should, with
    ``sort_by_position=True``, come out in geometric top-to-bottom
    order."""
    doc = PDDocument()
    # Two Tj at very different y. Stream order: lower-y first.
    # ``Tm`` resets the text matrix so each Tj sits at an absolute
    # ``(x, y)`` regardless of prior advances.
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 100 Tm (lower) Tj "
            b"1 0 0 1 100 700 Tm (upper) Tj "
            b"ET"
        ),
    )

    # Without sort_by_position, the emit order matches the stream order
    # — the ``y`` jump is large, so a line separator is inserted.
    unsorted = PDFTextStripper()
    unsorted_out = unsorted.get_text(doc)
    assert unsorted_out.index("lower") < unsorted_out.index("upper")

    # With sort_by_position, the higher ``y`` (geometrically the top
    # of the page) comes first.
    sorted_stripper = PDFTextStripper()
    sorted_stripper.set_sort_by_position(True)
    sorted_out = sorted_stripper.get_text(doc)
    assert sorted_out.index("upper") < sorted_out.index("lower")


def test_sort_by_position_default_off_preserves_stream_order() -> None:
    """Sanity check: with the default (off), emission order tracks
    the content stream even when ``y`` would put runs out of order."""
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 100 Tm (alpha) Tj "
            b"1 0 0 1 100 700 Tm (beta) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    out = s.get_text(doc)
    assert out.index("alpha") < out.index("beta")


def test_sort_by_position_reorders_same_line_x() -> None:
    """Mirrors upstream ``TextPositionComparator`` X-tie-break: when two
    runs share a line (same ``y``) but are emitted out of left-to-right
    order, ``set_sort_by_position(True)`` should reorder them ascending
    by ``x``."""
    doc = PDDocument()
    # Same y (700). Stream order paints right-of-page first, then
    # left-of-page. Without sort, "right" emits before "left".
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 400 700 Tm (right) Tj "
            b"1 0 0 1 100 700 Tm (left) Tj "
            b"ET"
        ),
    )

    unsorted = PDFTextStripper()
    unsorted_out = unsorted.get_text(doc)
    assert unsorted_out.index("right") < unsorted_out.index("left")

    sorted_stripper = PDFTextStripper()
    sorted_stripper.set_sort_by_position(True)
    sorted_out = sorted_stripper.get_text(doc)
    assert sorted_out.index("left") < sorted_out.index("right")


def test_sort_by_position_full_reading_order_grid() -> None:
    """Multi-line, multi-column synthesis: stream order is scrambled,
    but with sort enabled the output should walk top-to-bottom, then
    left-to-right within each line — i.e. canonical reading order."""
    doc = PDDocument()
    # Stream order (intentionally scrambled):
    #   bottom-right (100,100) "D"
    #   top-left     (100,700) "A"
    #   bottom-left  (50,100)  "C"
    #   top-right    (400,700) "B"
    # Geometric reading order (top→bottom, left→right): A, B, C, D.
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 100 Tm (D) Tj "
            b"1 0 0 1 100 700 Tm (A) Tj "
            b"1 0 0 1 50 100 Tm (C) Tj "
            b"1 0 0 1 400 700 Tm (B) Tj "
            b"ET"
        ),
    )

    s = PDFTextStripper()
    s.set_sort_by_position(True)
    out = s.get_text(doc)
    # Each glyph appears exactly once; their relative order matches the
    # canonical reading order.
    assert out.index("A") < out.index("B") < out.index("C") < out.index("D")


def test_sort_by_position_is_stable_for_equal_y_equal_x() -> None:
    """When two positions share both ``y`` and ``x``, Python's
    ``sorted`` is stable so they should retain their emission order
    even with sort enabled. This pins the upstream behaviour where
    ``TextPositionComparator`` returns 0 for equal keys and the
    surrounding sort preserves insertion order."""
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (one) Tj "
            b"1 0 0 1 100 700 Tm (two) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_sort_by_position(True)
    out = s.get_text(doc)
    assert out.index("one") < out.index("two")
