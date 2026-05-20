"""Edge-case round-out for :class:`PDFTextStripper`.

Covers the upstream-shaped knobs and hooks added on top of the basic
single-page extractor:

  - ``article_start`` / ``article_end`` markers around the page body.
  - ``start_bookmark`` / ``end_bookmark`` clamping the page range.
  - subclass override hooks: ``write_string``, ``write_word_separator``,
    ``write_line_separator``, ``write_paragraph_start`` / ``_end``,
    ``write_page_start`` / ``_end``, ``write_article_start`` / ``_end``,
    and ``process_text_position``.
  - ``suppress_duplicate_overlapping_text`` removing fake-bold double
    glyphs before formatting.
  - getter aliases: ``get_sort_by_position`` /
    ``get_suppress_duplicate_overlapping_text``.
"""

from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (
    PDPageFitDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (
    PDOutlineItem,
)
from pypdfbox.text import PDFTextStripper, TextPosition

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


def _bookmark_for_page(doc: PDDocument, page_index: int) -> PDOutlineItem:
    """Build a ``PDOutlineItem`` whose destination resolves to the
    page at the supplied 0-based ``page_index`` of ``doc``."""
    pages = doc.get_pages()
    dest = PDPageFitDestination()
    dest.set_page(pages[page_index])
    item = PDOutlineItem()
    item.set_destination(dest)
    return item


# ---------------------------------------------------------------------------
# alias getters
# ---------------------------------------------------------------------------


def test_get_sort_by_position_alias_matches_is_sort_by_position() -> None:
    s = PDFTextStripper()
    assert s.get_sort_by_position() is s.is_sort_by_position()
    s.set_sort_by_position(True)
    assert s.get_sort_by_position() is True
    assert s.is_sort_by_position() is True


def test_get_suppress_duplicate_overlapping_text_alias() -> None:
    s = PDFTextStripper()
    assert s.get_suppress_duplicate_overlapping_text() is True
    s.set_suppress_duplicate_overlapping_text(False)
    assert s.get_suppress_duplicate_overlapping_text() is False
    assert s.is_suppress_duplicate_overlapping_text() is False


# ---------------------------------------------------------------------------
# article_start / article_end
# ---------------------------------------------------------------------------


def test_default_article_start_and_end_are_empty() -> None:
    s = PDFTextStripper()
    assert s.get_article_start() == ""
    assert s.get_article_end() == ""


def test_round_trip_article_start_and_end() -> None:
    s = PDFTextStripper()
    s.set_article_start("[A]")
    s.set_article_end("[/A]")
    assert s.get_article_start() == "[A]"
    assert s.get_article_end() == "[/A]"


def test_article_markers_wrap_page_body() -> None:
    """Setting ``article_start`` / ``article_end`` should wrap the
    whole page body, between ``page_start`` and ``page_end``."""
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (body) Tj ET")
    s = PDFTextStripper()
    s.set_article_start("<art>")
    s.set_article_end("</art>")
    out = s.get_text(doc)
    assert out == "<art>body</art>\n"


def test_empty_article_markers_emit_nothing() -> None:
    """When both article markers are the empty default string, no
    extra characters appear in the output."""
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (body) Tj ET")
    s = PDFTextStripper()
    out = s.get_text(doc)
    assert out == "body\n"


# ---------------------------------------------------------------------------
# start_bookmark / end_bookmark
# ---------------------------------------------------------------------------


def test_default_start_bookmark_and_end_bookmark_are_none() -> None:
    s = PDFTextStripper()
    assert s.get_start_bookmark() is None
    assert s.get_end_bookmark() is None


def test_start_bookmark_clamps_first_page() -> None:
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (one) Tj ET")
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (two) Tj ET")
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (three) Tj ET")
    s = PDFTextStripper()
    s.set_start_bookmark(_bookmark_for_page(doc, 1))  # page 2
    assert s.get_text(doc) == "two\nthree\n"


def test_end_bookmark_clamps_last_page() -> None:
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (one) Tj ET")
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (two) Tj ET")
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (three) Tj ET")
    s = PDFTextStripper()
    s.set_end_bookmark(_bookmark_for_page(doc, 1))  # page 2
    assert s.get_text(doc) == "one\ntwo\n"


def test_both_bookmarks_form_inclusive_range() -> None:
    doc = PDDocument()
    for label in (b"a", b"b", b"c", b"d"):
        _make_page_with_stream(
            doc, b"BT /F0 12 Tf 100 700 Td (" + label + b") Tj ET"
        )
    s = PDFTextStripper()
    s.set_start_bookmark(_bookmark_for_page(doc, 1))
    s.set_end_bookmark(_bookmark_for_page(doc, 2))
    assert s.get_text(doc) == "b\nc\n"


def test_bookmark_only_narrows_explicit_page_range() -> None:
    """If the explicit page range is already tighter than the bookmark
    range, the explicit range wins — bookmarks never widen."""
    doc = PDDocument()
    for label in (b"a", b"b", b"c", b"d"):
        _make_page_with_stream(
            doc, b"BT /F0 12 Tf 100 700 Td (" + label + b") Tj ET"
        )
    s = PDFTextStripper()
    s.set_start_page(3)
    s.set_end_page(3)
    # Bookmark covers pages 1..4, but explicit page range is 3..3.
    s.set_start_bookmark(_bookmark_for_page(doc, 0))
    s.set_end_bookmark(_bookmark_for_page(doc, 3))
    assert s.get_text(doc) == "c\n"


def test_unresolvable_bookmark_is_ignored() -> None:
    """A bookmark with no destination at all paired with itself yields
    empty text — mirrors upstream's "same-orphan bookmark clamps to
    empty range" branch (see ``PDFTextStripper.processPages``). Two
    different orphan bookmarks would leave the page range untouched.
    """
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (only) Tj ET")
    bookmark = PDOutlineItem()  # no dest, no action
    s = PDFTextStripper()
    s.set_start_bookmark(bookmark)
    s.set_end_bookmark(bookmark)
    # Per upstream PDFTextStripper, same-bookmark-on-both-ends with no
    # destination clamps to empty.
    assert s.get_text(doc) == ""

    # Different orphan bookmarks (no destination either, but distinct
    # instances): the clamp doesn't trigger, fall back to the unbounded
    # page range and extract everything.
    s = PDFTextStripper()
    s.set_start_bookmark(PDOutlineItem())
    s.set_end_bookmark(PDOutlineItem())
    assert s.get_text(doc) == "only\n"


# ---------------------------------------------------------------------------
# write_* hooks
# ---------------------------------------------------------------------------


def test_write_string_override_can_transform_text() -> None:
    """A subclass that overrides ``write_string`` to upper-case the
    text should affect the final output."""

    class UpperStripper(PDFTextStripper):
        def write_string(self, text, text_positions, sink) -> None:  # type: ignore[override]
            sink(text.upper())

    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (hello) Tj ET")
    out = UpperStripper().get_text(doc)
    assert out == "HELLO\n"


def test_write_string_receives_positions_for_run() -> None:
    """``write_string`` should be passed a list with a ``TextPosition``
    for every run it's asked to write."""

    seen: list[list[TextPosition]] = []

    class CapturingStripper(PDFTextStripper):
        def write_string(self, text, text_positions, sink) -> None:  # type: ignore[override]
            seen.append(list(text_positions))
            sink(text)

    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (foo) Tj 200 0 Td (bar) Tj ET",
    )
    CapturingStripper().get_text(doc)
    # Two emitted runs: "foo" and "bar".
    assert len(seen) == 2
    assert all(len(group) == 1 for group in seen)
    assert seen[0][0].text == "foo"
    assert seen[1][0].text == "bar"


def test_write_word_separator_override_replaces_space() -> None:
    class TabStripper(PDFTextStripper):
        def write_word_separator(self, sink) -> None:  # type: ignore[override]
            sink("|WS|")

    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (foo) Tj 200 0 Td (bar) Tj ET",
    )
    out = TabStripper().get_text(doc)
    assert "foo|WS|bar" in out


def test_write_line_separator_override_replaces_newline() -> None:
    class HtmlStripper(PDFTextStripper):
        def write_line_separator(self, sink) -> None:  # type: ignore[override]
            sink("<br>")

    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (a) Tj 0 -14 Td (b) Tj ET",
    )
    out = HtmlStripper().get_text(doc)
    assert "a<br>b" in out


def test_write_page_start_and_end_overrides_emit_around_body() -> None:
    class FramingStripper(PDFTextStripper):
        def write_page_start(self, sink) -> None:  # type: ignore[override]
            sink("[PS]")

        def write_page_end(self, sink) -> None:  # type: ignore[override]
            sink("[PE]")

    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (body) Tj ET")
    assert FramingStripper().get_text(doc) == "[PS]body[PE]"


def test_write_article_start_and_end_overrides_invoked_when_marker_set() -> None:
    """Even when ``article_start`` / ``article_end`` are at their
    empty defaults, an explicit override only fires when at least one
    marker string is non-empty (matches upstream's ``writeArticle*``
    gating)."""

    calls: list[str] = []

    class ArticleStripper(PDFTextStripper):
        def write_article_start(self, sink) -> None:  # type: ignore[override]
            calls.append("start")
            sink("<a>")

        def write_article_end(self, sink) -> None:  # type: ignore[override]
            calls.append("end")
            sink("</a>")

    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (body) Tj ET")
    s = ArticleStripper()
    # Without setting any article marker, the gate keeps the hook
    # silent — output equals the bare body + page_end.
    assert s.get_text(doc) == "body\n"
    assert calls == []
    # Setting the marker turns the hook on.
    s.set_article_start("<a>")
    s.set_article_end("</a>")
    out = s.get_text(doc)
    assert "<a>" in out and "</a>" in out
    assert calls == ["start", "end"]


def test_process_text_position_default_is_noop() -> None:
    """Default ``process_text_position`` returns ``None`` and does
    nothing observable."""
    s = PDFTextStripper()
    pos = TextPosition(text="x", x=0.0, y=0.0, font_size=10.0)
    assert s.process_text_position(pos) is None


def test_process_text_position_invoked_for_each_run() -> None:
    """Subclasses can collect every emitted ``TextPosition`` via
    ``process_text_position``. The base ``write_string`` calls it
    once per position in its ``text_positions`` list."""

    seen: list[TextPosition] = []

    class CollectingStripper(PDFTextStripper):
        def process_text_position(self, text) -> None:  # type: ignore[override]
            seen.append(text)

    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (foo) Tj 200 0 Td (bar) Tj ET",
    )
    CollectingStripper().get_text(doc)
    assert [p.text for p in seen] == ["foo", "bar"]


# ---------------------------------------------------------------------------
# suppress_duplicate_overlapping_text
# ---------------------------------------------------------------------------


def test_duplicate_overlapping_text_suppressed_by_default() -> None:
    """Two ``Tj`` calls that paint the same glyph at the same origin
    (the fake-bold trick) should collapse into a single output run."""
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (X) Tj "
            b"1 0 0 1 100 700 Tm (X) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    out = s.get_text(doc)
    assert out == "X\n"


def test_duplicate_overlapping_text_kept_when_suppression_off() -> None:
    """When ``suppress_duplicate_overlapping_text`` is disabled, both
    of the overlapping glyphs are emitted — they share ``y`` so the
    line-separator branch doesn't fire and they concatenate."""
    doc = PDDocument()
    _make_page_with_stream(
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
    assert out == "XX\n"


def test_duplicate_suppression_does_not_drop_distinct_glyphs() -> None:
    """Same text but at a different origin (well beyond the
    quarter-em tolerance) is *not* a duplicate and must be kept."""
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (X) Tj "
            b"1 0 0 1 400 700 Tm (X) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    out = s.get_text(doc)
    # Both X's preserved, with a word separator between them (the
    # 300-unit x gap exceeds the word-gap threshold of 12 * 1.5 = 18).
    assert out == "X X\n"
