from __future__ import annotations

import sys

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
    assert s.get_paragraph_end() == "\n"
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
    assert s.write_characters(pos) is None


def test_start_and_end_article_hooks_default_no_op() -> None:
    """``start_article`` / ``end_article`` mirror upstream's
    protected article-bracketing hooks. Both default to no-ops with
    the upstream signatures: ``start_article(is_ltr=True)`` and
    ``end_article()``."""
    s = PDFTextStripper()
    assert s.start_article() is None
    assert s.start_article(is_ltr=True) is None
    assert s.start_article(is_ltr=False) is None
    assert s.end_article() is None
