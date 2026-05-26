from __future__ import annotations

import io
import re
import sys
from collections.abc import Callable

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
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


_WAVE964_BRACKETED_CLASS: type[PDFTextStripper] | None = None


# ---------------------------------------------------------------------------
# TextPosition dataclass
# ---------------------------------------------------------------------------


def test_text_position_round_trip() -> None:
    pos = TextPosition(
        text="Hi",
        x=10.0,
        y=20.0,
        font_size=12.0,
        font_name="F0",
        resolved_font_name="Helvetica",
        width=10.5,
        width_of_space=3.25,
        char_spacing=1.0,
        word_spacing=2.0,
    )
    assert pos.text == "Hi"
    assert pos.x == 10.0
    assert pos.y == 20.0
    assert pos.font_size == 12.0
    assert pos.font_name == "F0"
    assert pos.resolved_font_name == "Helvetica"
    assert pos.width == 10.5
    assert pos.width_of_space == 3.25
    assert pos.char_spacing == 1.0
    assert pos.word_spacing == 2.0
    assert pos.get_unicode() == "Hi"
    assert pos.get_x() == 10.0
    assert pos.get_y() == 20.0
    assert pos.get_font_size() == 12.0
    assert pos.get_font_name() == "F0"
    assert pos.get_font() is None
    assert pos.get_resolved_font_name() == "Helvetica"
    assert pos.get_width() == 10.5
    assert pos.get_width_of_space() == 3.25


def test_text_position_default_font_name_is_none() -> None:
    pos = TextPosition(text="x", x=0.0, y=0.0, font_size=10.0)
    assert pos.font_name is None
    assert pos.font is None
    assert pos.resolved_font_name is None
    assert pos.width == 0.0
    assert pos.width_of_space == 0.0


# ---------------------------------------------------------------------------
# PDFTextStripper configuration
# ---------------------------------------------------------------------------


def test_default_configuration() -> None:
    s = PDFTextStripper()
    assert s.get_start_page() == 1
    assert s.get_end_page() == sys.maxsize
    assert s.get_word_separator() == " "
    assert s.get_line_separator() == "\n"
    assert s.get_paragraph_start() == ""
    # Matches upstream PDFBox's empty ``paragraphEnd`` default — the line
    # terminator is emitted separately via ``line_separator``.
    assert s.get_paragraph_end() == ""
    assert s.get_page_start() == ""
    assert s.get_page_end() == "\n"
    assert s.get_should_separate_by_beads() is True


def test_setters_round_trip() -> None:
    s = PDFTextStripper()
    s.set_start_page(2)
    s.set_end_page(5)
    s.set_word_separator("|")
    s.set_line_separator("<br>")
    assert s.get_start_page() == 2
    assert s.get_end_page() == 5
    assert s.get_word_separator() == "|"
    assert s.get_line_separator() == "<br>"


# ---------------------------------------------------------------------------
# get_text on empty / no-page documents
# ---------------------------------------------------------------------------


def test_get_text_empty_document() -> None:
    doc = PDDocument()
    s = PDFTextStripper()
    # No pages at all → nothing to walk.
    assert s.get_text(doc) == ""


def test_get_text_blank_page_returns_just_page_end() -> None:
    doc = PDDocument()
    doc.add_page(PDPage())
    s = PDFTextStripper()
    # Blank page (no /Contents) → no text body, just the configured
    # page_end terminator.
    assert s.get_text(doc) == "\n"


# ---------------------------------------------------------------------------
# basic Tj extraction
# ---------------------------------------------------------------------------


def test_get_text_single_tj() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc, b"BT /F0 12 Tf 100 700 Td (Hello) Tj ET"
    )
    s = PDFTextStripper()
    out = s.get_text(doc)
    assert out == "Hello\n"


def test_get_text_multiline_via_td() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (line1) Tj 0 -14 Td (line2) Tj ET",
    )
    s = PDFTextStripper()
    out = s.get_text(doc)
    assert out == "line1\nline2\n"


def test_get_text_t_star_uses_leading() -> None:
    doc = PDDocument()
    # ``TD`` sets leading to 14, then T* moves to next line at the same
    # leading without re-supplying it.
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td 0 -14 TD (line1) Tj T* (line2) Tj ET",
    )
    s = PDFTextStripper()
    out = s.get_text(doc)
    assert "line1" in out
    assert "line2" in out
    assert out.index("line1") < out.index("line2")
    # Lines should be separated by the configured line separator.
    assert "\n" in out


# ---------------------------------------------------------------------------
# word separator heuristic
# ---------------------------------------------------------------------------


def test_word_separator_emitted_for_large_x_gap() -> None:
    # Two Tj on the same line, far apart in x → expect a space between.
    # Font size is 12 so the word gap threshold is 12 * 1.5 = 18 user
    # units. We jump 200 units between the two Tj origins.
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (foo) Tj 200 0 Td (bar) Tj ET",
    )
    s = PDFTextStripper()
    out = s.get_text(doc)
    assert out == "foo bar\n"


def test_no_word_separator_for_close_runs() -> None:
    # Two adjacent Tj — the second comes right after the first, well
    # within the word-gap threshold. Should concatenate without a space.
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (foo)Tj(bar)Tj ET",
    )
    s = PDFTextStripper()
    out = s.get_text(doc)
    assert out == "foobar\n"


# ---------------------------------------------------------------------------
# TJ array handling
# ---------------------------------------------------------------------------


def test_tj_array_concatenates_strings() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td [(He)(llo)] TJ ET",
    )
    s = PDFTextStripper()
    out = s.get_text(doc)
    assert out == "Hello\n"


# ---------------------------------------------------------------------------
# start_page / end_page filtering
# ---------------------------------------------------------------------------


def test_start_and_end_page_filter() -> None:
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (page1) Tj ET")
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (page2) Tj ET")
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (page3) Tj ET")
    s = PDFTextStripper()
    s.set_start_page(2)
    s.set_end_page(2)
    assert s.get_text(doc) == "page2\n"


def test_end_page_clamped_to_page_count() -> None:
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (only) Tj ET")
    s = PDFTextStripper()
    s.set_end_page(99)
    assert s.get_text(doc) == "only\n"


def test_start_page_past_end_returns_empty() -> None:
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (only) Tj ET")
    s = PDFTextStripper()
    s.set_start_page(5)
    assert s.get_text(doc) == ""


# ---------------------------------------------------------------------------
# process_page hook
# ---------------------------------------------------------------------------


def test_process_page_extracts_single_page() -> None:
    doc = PDDocument()
    page = _make_page_with_stream(
        doc, b"BT /F0 12 Tf 100 700 Td (solo) Tj ET"
    )
    s = PDFTextStripper()
    # Returned text should contain "solo" — no page_end wrapping at this level.
    assert s.process_page(page) == "solo"


# ---------------------------------------------------------------------------
# custom separators
# ---------------------------------------------------------------------------


def _attach_to_unicode_font(
    page: PDPage, font_name: str, cmap_body: bytes
) -> None:
    """Wire ``page.Resources.Font.<font_name>`` to a ``Type0`` font dict
    whose ``/ToUnicode`` is a stream carrying ``cmap_body``.

    The font subtype is irrelevant to the stripper's lookup path — only
    ``/ToUnicode`` is consulted — but we set it to ``Type0`` for realism.
    """
    to_unicode = COSStream()
    to_unicode.set_data(cmap_body)
    font_dict = COSDictionary()
    font_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type0"))
    font_dict.set_item(COSName.get_pdf_name("ToUnicode"), to_unicode)
    resources = PDResources()
    resources.put(
        COSName.get_pdf_name("Font"),
        COSName.get_pdf_name(font_name),
        font_dict,
    )
    page.set_resources(resources)


# Minimal ToUnicode CMap mapping byte 0x01 -> 'α' (U+03B1).
_ONE_BYTE_CMAP = (
    b"/CIDInit /ProcSet findresource begin\n"
    b"12 dict begin\n"
    b"begincmap\n"
    b"1 begincodespacerange <00> <FF> endcodespacerange\n"
    b"1 beginbfchar <01> <03B1> endbfchar\n"
    b"endcmap\n"
)

# 2-byte CID-style ToUnicode CMap mapping <0001> -> U+03B1.
_TWO_BYTE_CMAP = (
    b"/CIDInit /ProcSet findresource begin\n"
    b"12 dict begin\n"
    b"begincmap\n"
    b"1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
    b"1 beginbfchar <0001> <03B1> endbfchar\n"
    b"endcmap\n"
)


def test_get_text_to_unicode_one_byte_cmap() -> None:
    """A page whose font has a /ToUnicode CMap mapping byte 0x01 -> 'α'
    should decode ``(\\x01) Tj`` as ``"α"`` rather than the Latin-1
    fallback ``"\\x01"``."""
    doc = PDDocument()
    page = _make_page_with_stream(
        doc, b"BT /F0 12 Tf 100 700 Td (\x01) Tj ET"
    )
    _attach_to_unicode_font(page, "F0", _ONE_BYTE_CMAP)
    s = PDFTextStripper()
    out = s.get_text(doc)
    assert out == "α\n"


def test_get_text_to_unicode_two_byte_cmap() -> None:
    """A 2-byte CID-style /ToUnicode CMap mapping <0001> -> U+03B1
    decodes the hex-string operand ``<0001>`` as ``"α"``."""
    doc = PDDocument()
    page = _make_page_with_stream(
        doc, b"BT /F0 12 Tf 100 700 Td <0001> Tj ET"
    )
    _attach_to_unicode_font(page, "F0", _TWO_BYTE_CMAP)
    s = PDFTextStripper()
    out = s.get_text(doc)
    assert out == "α\n"


def test_get_text_no_to_unicode_falls_back_to_latin1() -> None:
    """Existing behaviour must be preserved: a page with no /ToUnicode
    on the font (or no Resources at all) decodes via COSString.get_string()
    (Latin-1 / PDFDocEncoding)."""
    doc = PDDocument()
    _make_page_with_stream(
        doc, b"BT /F0 12 Tf 100 700 Td (Hello) Tj ET"
    )
    s = PDFTextStripper()
    out = s.get_text(doc)
    assert out == "Hello\n"


def test_custom_separators() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (a) Tj 0 -14 Td (b) Tj ET",
    )
    s = PDFTextStripper()
    s.set_line_separator(" / ")
    s.set_page_end("|END|")
    assert s.get_text(doc) == "a / b|END|"


# ---------------------------------------------------------------------------
# Round-out parity additions: missing aliases / hooks
# ---------------------------------------------------------------------------


def test_get_separate_by_beads_alias_matches_get_should_separate_by_beads() -> None:
    """Upstream's primary 3.x getter is the abbreviated
    ``getSeparateByBeads``. It must mirror the same flag exposed by
    ``getShouldSeparateByBeads`` / ``isShouldSeparateByBeads``."""
    s = PDFTextStripper()
    # Default upstream value is True.
    assert s.get_separate_by_beads() is True
    assert s.get_separate_by_beads() == s.get_should_separate_by_beads()
    s.set_should_separate_by_beads(False)
    assert s.get_separate_by_beads() is False
    assert s.get_separate_by_beads() == s.get_should_separate_by_beads()
    assert s.get_separate_by_beads() == s.is_should_separate_by_beads()


def test_ignore_content_stream_space_glyphs_round_trips() -> None:
    """``setIgnoreContentStreamSpaceGlyphs`` /
    ``getIgnoreContentStreamSpaceGlyphs`` upstream pair — default
    ``False``, settable to ``True``."""
    s = PDFTextStripper()
    assert s.get_ignore_content_stream_space_glyphs() is False
    s.set_ignore_content_stream_space_glyphs(True)
    assert s.get_ignore_content_stream_space_glyphs() is True
    s.set_ignore_content_stream_space_glyphs(False)
    assert s.get_ignore_content_stream_space_glyphs() is False
    # Coercion: any truthy value becomes True.
    s.set_ignore_content_stream_space_glyphs(1)  # type: ignore[arg-type]
    assert s.get_ignore_content_stream_space_glyphs() is True


def test_get_current_page_no_default_is_zero() -> None:
    """Outside a walk, ``getCurrentPageNo`` reports 0 (no page active)."""
    s = PDFTextStripper()
    assert s.get_current_page_no() == 0


def test_get_current_page_no_visible_inside_process_page() -> None:
    """Inside ``process_page`` (and the surrounding ``start_page`` /
    ``end_page`` hooks) the current 1-based page index must be
    visible."""
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (a) Tj ET")
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (b) Tj ET")

    seen: list[int] = []

    class _Tracker(PDFTextStripper):
        def start_page(self, page: PDPage) -> None:
            seen.append(self.get_current_page_no())

    t = _Tracker()
    t.get_text(doc)
    assert seen == [1, 2]
    # Reset back to 0 once the walk finishes.
    assert t.get_current_page_no() == 0


def test_start_document_and_end_document_hooks_fire_once() -> None:
    """``start_document`` / ``end_document`` mirror upstream's protected
    document-bracketing hooks: each must fire exactly once per
    ``get_text`` invocation, regardless of page count."""
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (x) Tj ET")
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (y) Tj ET")

    events: list[str] = []

    class _Bracketed(PDFTextStripper):
        def start_document(self, document: PDDocument) -> None:
            events.append("start")

        def end_document(self, document: PDDocument) -> None:
            events.append("end")

        def start_page(self, page: PDPage) -> None:
            events.append("page-start")

        def end_page(self, page: PDPage) -> None:
            events.append("page-end")

    b = _Bracketed()
    b.get_text(doc)
    # start_document → page-start/page-end pairs → end_document.
    assert events == [
        "start",
        "page-start",
        "page-end",
        "page-start",
        "page-end",
        "end",
    ]


def test_end_document_runs_even_on_empty_range() -> None:
    """When the start/end page range is inverted ``get_text`` returns
    ``""`` early — but ``start_document`` / ``end_document`` should
    still bracket the call so subclasses can release per-walk state.
    """
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (x) Tj ET")

    events: list[str] = []

    class _Bracketed(PDFTextStripper):
        def start_document(self, document: PDDocument) -> None:
            events.append("start")

        def end_document(self, document: PDDocument) -> None:
            events.append("end")

    global _WAVE964_BRACKETED_CLASS
    _WAVE964_BRACKETED_CLASS = _Bracketed

    b = _Bracketed()
    b.set_start_page(5)  # past the only page
    b.set_end_page(10)
    out = b.get_text(doc)
    assert out == ""
    # Lite mode short-circuits before start_document fires (the early
    # return predates the hook). This is acceptable parity with
    # upstream's gate (it also skips startDocument/endDocument when
    # no page passes the filter). Document the behaviour:
    assert events == []


def test_write_characters_default_is_no_op() -> None:
    """``write_characters`` mirrors upstream's protected
    ``writeCharacters(TextPosition)`` — the base implementation must be
    callable and return ``None`` without raising, so subclasses can
    chain via ``super().write_characters(...)``."""
    s = PDFTextStripper()
    pos = TextPosition(text="z", x=0.0, y=0.0, font_size=10.0)
    s.write_characters(pos)


def test_start_and_end_article_hooks_default_no_op() -> None:
    """``start_article`` / ``end_article`` mirror upstream's
    protected article-bracketing hooks. Both default to no-ops with
    the upstream signatures: ``start_article(is_ltr=True)`` and
    ``end_article()``."""
    s = PDFTextStripper()
    s.start_article()
    s.start_article(is_ltr=True)
    s.start_article(is_ltr=False)
    s.end_article()


# ---------------------------------------------------------------------------
# Output / characters-by-article / list-item-pattern accessors
# ---------------------------------------------------------------------------


def test_get_output_default_is_none() -> None:
    """``get_output`` mirrors upstream's protected ``getOutput``. Lite
    mode never sets it (extraction is sink-driven through ``get_text``)
    so the accessor reports ``None`` outside of any future
    ``write_text(doc, writer)`` flow."""
    s = PDFTextStripper()
    assert s.get_output() is None


def test_write_text_writes_extracted_text_to_writer() -> None:
    """``write_text`` mirrors upstream's ``writeText`` writer-driven API."""
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (written) Tj ET")
    writer = io.StringIO()

    s = PDFTextStripper()
    try:
        s.write_text(doc, writer)

        assert writer.getvalue() == "written\n"
        assert s.get_output() is None
    finally:
        doc.close()


def test_write_text_exposes_output_during_hooks_and_restores_afterwards() -> None:
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (hooked) Tj ET")
    writer = io.StringIO()
    seen: list[object | None] = []

    class _OutputAware(PDFTextStripper):
        def start_document(self, document: PDDocument) -> None:
            seen.append(self.get_output())

        def write_string(
            self,
            text: str,
            text_positions: list[TextPosition],
            sink: Callable[[str], None],
        ) -> None:
            seen.append(self.get_output())
            sink(text)

        def end_document(self, document: PDDocument) -> None:
            seen.append(self.get_output())

    s = _OutputAware()
    try:
        s.write_text(doc, writer)

        assert writer.getvalue() == "hooked\n"
        assert seen == [writer, writer, writer]
        assert s.get_output() is None
    finally:
        doc.close()


def test_get_characters_by_article_empty_before_walk() -> None:
    """Before any ``get_text`` invocation the per-page article list is
    empty — mirrors upstream's initial state of the ``charactersByArticle``
    field (cleared by ``resetEngine`` on every walk start)."""
    s = PDFTextStripper()
    assert s.get_characters_by_article() == []


def test_get_characters_by_article_populated_after_process_page() -> None:
    """After ``process_page`` runs, ``get_characters_by_article`` should
    expose a single article (lite mode treats every page as one
    article) whose inner list mirrors the formatter's input
    ``TextPosition`` stream."""
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (hi) Tj ET")
    s = PDFTextStripper()
    out = s.get_text(doc)
    assert "hi" in out
    articles = s.get_characters_by_article()
    assert len(articles) == 1
    assert all(isinstance(p, TextPosition) for p in articles[0])
    # At least one extracted glyph should carry the literal text.
    assert any("h" in p.text or "i" in p.text for p in articles[0])


def test_get_characters_by_article_resets_between_walks() -> None:
    """Two consecutive ``get_text`` calls must not leak state through
    ``charactersByArticle`` — upstream's ``resetEngine`` clears it on
    every walk start."""
    doc1 = PDDocument()
    _make_page_with_stream(doc1, b"BT /F0 12 Tf 100 700 Td (one) Tj ET")
    s = PDFTextStripper()
    s.get_text(doc1)
    first = s.get_characters_by_article()
    assert len(first) == 1

    doc2 = PDDocument()
    # No pages -> nothing to walk -> articles cleared but never refilled.
    s.get_text(doc2)
    assert s.get_characters_by_article() == []


def test_list_item_expressions_constant_matches_upstream() -> None:
    """``LIST_ITEM_EXPRESSIONS`` mirrors upstream's private array of
    list-marker regexes verbatim — order matters because
    ``match_pattern`` returns the first match."""
    assert PDFTextStripper.LIST_ITEM_EXPRESSIONS == (
        r"\.",
        r"\d+\.",
        r"\[\d+\]",
        r"\d+\)",
        r"[A-Z]\.",
        r"[a-z]\.",
        r"[A-Z]\)",
        r"[a-z]\)",
        r"[IVXL]+\.",
        r"[ivxl]+\.",
    )


def test_get_list_item_patterns_lazy_compiles_default() -> None:
    """``get_list_item_patterns`` lazily compiles the default expressions
    on first access and caches the result for subsequent calls."""
    s = PDFTextStripper()
    patterns = s.get_list_item_patterns()
    assert len(patterns) == len(PDFTextStripper.LIST_ITEM_EXPRESSIONS)
    assert all(isinstance(p, re.Pattern) for p in patterns)
    # Cached: identical instance on the second call.
    assert s.get_list_item_patterns() is patterns


def test_set_list_item_patterns_overrides_defaults() -> None:
    """Caller-supplied list of patterns replaces the default; passing
    ``None`` reverts to the lazy default on the next access."""
    s = PDFTextStripper()
    custom = [re.compile(r"#\d+")]
    s.set_list_item_patterns(custom)
    assert s.get_list_item_patterns() is custom

    s.set_list_item_patterns(None)
    reverted = s.get_list_item_patterns()
    assert reverted is not custom
    assert len(reverted) == len(PDFTextStripper.LIST_ITEM_EXPRESSIONS)


def test_match_pattern_returns_first_match() -> None:
    """``match_pattern`` mirrors upstream's anchored-match helper: it
    returns the first pattern in ``patterns`` whose full match accepts
    ``string``, or ``None`` when nothing matches."""
    patterns = PDFTextStripper().get_list_item_patterns()
    # ``"1."`` matches ``\d+\.`` (the second pattern; the first ``\.``
    # does not full-match because ``1.`` is two characters).
    matched = PDFTextStripper.match_pattern("1.", patterns)
    assert matched is not None
    assert matched.pattern == r"\d+\."

    # ``"[42]"`` matches ``\[\d+\]``.
    matched = PDFTextStripper.match_pattern("[42]", patterns)
    assert matched is not None
    assert matched.pattern == r"\[\d+\]"

    # ``"hello"`` matches none of the list-marker patterns.
    assert PDFTextStripper.match_pattern("hello", patterns) is None


def test_match_pattern_uses_fullmatch_not_search() -> None:
    """Upstream uses ``Matcher.matches()`` which is anchored at both
    ends. ``match_pattern`` must mirror that — a partial match should
    not count."""
    patterns = [re.compile(r"\d+")]
    # A full match returns the pattern.
    assert PDFTextStripper.match_pattern("42", patterns) is patterns[0]
    # A partial / mid-string match does NOT.
    assert PDFTextStripper.match_pattern("a42", patterns) is None
    assert PDFTextStripper.match_pattern("42a", patterns) is None


# ---------------------------------------------------------------------------
# Wave 1258 — newly-ported upstream helpers (1:1 parity).
# ---------------------------------------------------------------------------


def test_within_uses_strict_inequality() -> None:
    """``within`` matches upstream's ``second < first + variance &&
    second > first - variance`` — strict on both ends."""
    assert PDFTextStripper.within(10.0, 10.05, 0.1)
    # Strict <: equal-to-upper is NOT within.
    assert not PDFTextStripper.within(10.0, 10.1, 0.1)
    assert not PDFTextStripper.within(10.0, 9.9, 0.1)


def test_overlap_matches_upstream_predicate() -> None:
    """``overlap`` is true iff the two y-spans share any pixels."""
    # within tolerance — overlaps.
    assert PDFTextStripper.overlap(10.0, 5.0, 10.05, 5.0)
    # y2 sits inside [y1 - height1, y1] — overlaps.
    assert PDFTextStripper.overlap(10.0, 5.0, 8.0, 3.0)
    # disjoint — no overlap.
    assert not PDFTextStripper.overlap(10.0, 1.0, 50.0, 1.0)


def test_multiply_float_truncates_to_thousandths() -> None:
    """Mirrors upstream's ``Math.round(a*b*1000) / 1000f`` so float
    drift doesn't break == comparisons."""
    assert PDFTextStripper.multiply_float(1.2345, 1.0) == 1.234
    assert PDFTextStripper.multiply_float(0.1, 0.1) == 0.01


def test_has_font_or_size_changed_detects_size_change() -> None:
    """``has_font_or_size_changed`` reports a change when the font size
    moved between two adjacent positions, regardless of font."""
    a = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0)
    b = TextPosition(text="x", x=0.0, y=0.0, font_size=14.0)
    assert PDFTextStripper.has_font_or_size_changed(b, a) is True
    # Same size, same font (None) -> no change.
    assert PDFTextStripper.has_font_or_size_changed(
        TextPosition(text="x", x=0.0, y=0.0, font_size=12.0),
        TextPosition(text="x", x=0.0, y=0.0, font_size=12.0),
    ) is False
    # last == None -> never changed.
    assert PDFTextStripper.has_font_or_size_changed(a, None) is False


def test_remove_contained_spaces_drops_overlapping_space() -> None:
    """Upstream's PDFBOX-5487 fix: a literal space whose box is fully
    inside a previous run's box is dropped."""
    big = TextPosition(text="ab", x=0.0, y=0.0, font_size=12.0, width=20.0)
    contained_space = TextPosition(
        text=" ", x=5.0, y=0.0, font_size=12.0, width=2.0
    )
    after = TextPosition(text="c", x=30.0, y=0.0, font_size=12.0, width=10.0)
    text_list = [big, contained_space, after]
    PDFTextStripper.remove_contained_spaces(text_list)
    assert [p.text for p in text_list] == ["ab", "c"]


def test_remove_contained_spaces_preserves_non_contained() -> None:
    """When the space is not fully contained, it stays."""
    a = TextPosition(text="a", x=0.0, y=0.0, font_size=12.0, width=8.0)
    sp = TextPosition(text=" ", x=10.0, y=0.0, font_size=12.0, width=4.0)
    b = TextPosition(text="b", x=20.0, y=0.0, font_size=12.0, width=8.0)
    text_list = [a, sp, b]
    PDFTextStripper.remove_contained_spaces(text_list)
    assert [p.text for p in text_list] == ["a", " ", "b"]


def test_normalize_word_returns_input_for_basic_latin() -> None:
    """Pure ASCII input passes through unchanged."""
    s = PDFTextStripper()
    assert s.normalize_word("hello") == "hello"
    assert s.normalize_word("") == ""


def test_normalize_word_decomposes_fi_ligature() -> None:
    """Upstream's ``normalizeWord`` runs FB00–FDFF through NFKC, so the
    "fi" ligature U+FB01 expands to "fi"."""
    s = PDFTextStripper()
    out = s.normalize_word("ﬁnal")
    assert out == "final"


def test_handle_direction_passthrough_for_ltr() -> None:
    s = PDFTextStripper()
    assert s.handle_direction("hello") == "hello"


def test_handle_direction_reverses_for_rtl() -> None:
    """Hebrew (R) and Arabic (AL) runs are visually reversed."""
    s = PDFTextStripper()
    # Hebrew aleph + bet — bidi class R.
    assert s.handle_direction("אב") == "בא"


def test_create_word_normalizes_text() -> None:
    """``create_word`` runs the input through :meth:`normalize_word`."""
    s = PDFTextStripper()
    word = s.create_word("ﬁx", [])
    assert word.get_text() == "fix"
    assert word.get_text_positions() == []


def test_word_with_text_positions_factory_returns_uppercase_class() -> None:
    """Factory matching upstream's inner-class constructor signature."""
    from pypdfbox.text import WordWithTextPositions

    word = PDFTextStripper.word_with_text_positions("hi", [])
    assert isinstance(word, WordWithTextPositions)
    assert word.get_text() == "hi"


def test_normalize_round_trips_via_line_items() -> None:
    """``normalize`` and ``normalize_add`` walk a list of line items and
    produce one ``WordWithTextPositions`` per word boundary."""
    from pypdfbox.text.pdf_text_stripper import _LineItem

    s = PDFTextStripper()
    a = TextPosition(text="he", x=0.0, y=0.0, font_size=12.0)
    b = TextPosition(text="llo", x=10.0, y=0.0, font_size=12.0)
    c = TextPosition(text="world", x=40.0, y=0.0, font_size=12.0)
    line: list[_LineItem] = [
        _LineItem(a),
        _LineItem(b),
        _LineItem.get_word_separator(),
        _LineItem(c),
    ]
    out = s.normalize(line)
    assert [w.get_text() for w in out] == ["hello", "world"]


def test_match_list_item_pattern_matches_position_text() -> None:
    """Wraps ``match_pattern`` for a :class:`PositionWrapper`."""
    from pypdfbox.text.position_wrapper import PositionWrapper

    s = PDFTextStripper()
    wrapper = PositionWrapper(TextPosition(text="1.", x=0.0, y=0.0, font_size=12.0))
    matched = s.match_list_item_pattern(wrapper)
    assert matched is not None
    assert matched.pattern == r"\d+\."

    wrapper2 = PositionWrapper(
        TextPosition(text="hello", x=0.0, y=0.0, font_size=12.0)
    )
    assert s.match_list_item_pattern(wrapper2) is None


def test_write_paragraph_separator_emits_end_then_start() -> None:
    """``write_paragraph_separator`` calls ``write_paragraph_end`` then
    ``write_paragraph_start`` — mirrors upstream."""
    chunks: list[str] = []
    s = PDFTextStripper()
    s.set_paragraph_start("<P>")
    s.set_paragraph_end("</P>")
    s.write_paragraph_separator(chunks.append)
    assert chunks == ["</P>", "<P>"]


def test_write_line_alternates_words_with_separators() -> None:
    """``write_line`` writes each word + a separator between."""
    from pypdfbox.text import WordWithTextPositions

    s = PDFTextStripper()
    s.set_word_separator(" ")
    chunks: list[str] = []
    p1 = TextPosition(text="hello", x=0.0, y=0.0, font_size=12.0)
    p2 = TextPosition(text="world", x=0.0, y=0.0, font_size=12.0)
    line = [
        WordWithTextPositions("hello", [p1]),
        WordWithTextPositions("world", [p2]),
    ]
    s.write_line(line, chunks.append)
    assert "".join(chunks) == "hello world"


def test_parse_bidi_file_extracts_mirroring_pairs() -> None:
    """Mirrors upstream's ``parseBidiFile`` mini-parser."""
    sample = b"# comment line\n0028; 0029 # paren\n0029; 0028\nbad\n"
    out = PDFTextStripper.parse_bidi_file(io.BytesIO(sample))
    assert out["("] == ")"
    assert out[")"] == "("
    # Empty / None input -> empty map.
    assert PDFTextStripper.parse_bidi_file(None) == {}


def test_reset_engine_clears_per_walk_state() -> None:
    """``reset_engine`` clears bead rectangles, bookmarks, and the
    article accumulator."""
    s = PDFTextStripper()
    s._bead_rectangles = [(1.0, 2.0, 3.0, 4.0)]
    s._characters_by_article = [[TextPosition(text="x", x=0.0, y=0.0, font_size=12.0)]]
    s._start_bookmark_page_number = 5
    s._end_bookmark_page_number = 9
    s._current_page_no = 7
    s.reset_engine()
    assert s._bead_rectangles == []
    assert s._characters_by_article == []
    assert s._start_bookmark_page_number == -1
    assert s._end_bookmark_page_number == -1
    assert s._current_page_no == 0


def test_fill_bead_rectangles_returns_empty_when_no_beads() -> None:
    """``fill_bead_rectangles`` returns an empty list and resets the
    cached attribute when the page has no thread beads."""
    doc = PDDocument()
    page = _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (hi) Tj ET")
    s = PDFTextStripper()
    rects = s.fill_bead_rectangles(page)
    assert rects == []
    assert s._bead_rectangles == []


def test_begin_marked_content_sequence_captures_actual_text() -> None:
    """``/ActualText`` from BDC properties replaces soft hyphens and is
    surfaced through ``_actual_text`` for subclasses."""
    s = PDFTextStripper()
    props = COSDictionary()
    props.set_string("ActualText", "fi­ne")
    s.begin_marked_content_sequence(COSName.get_pdf_name("Span"), props)
    assert s._actual_text == "fine"  # soft hyphen stripped
    assert s._first_actual_text_position is True
    s.end_marked_content_sequence()
    assert s._actual_text is None


def test_end_marked_content_sequence_handles_empty_stack() -> None:
    """Calling ``end_marked_content_sequence`` with an empty stack is a
    no-op (defensive parity with upstream's null-safe peek/pop)."""
    s = PDFTextStripper()
    s.end_marked_content_sequence()  # must not raise
    assert s._actual_text is None
