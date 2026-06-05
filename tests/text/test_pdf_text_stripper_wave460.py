from __future__ import annotations

import re

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFTextStripper, TextPosition


def _make_page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


_WAVE963_HOOK_STRIPPER_CLASS: type[PDFTextStripper] | None = None


def test_wave460_list_item_patterns_are_cached_customizable_and_fullmatch_only() -> None:
    stripper = PDFTextStripper()

    defaults = stripper.get_list_item_patterns()
    assert stripper.get_list_item_patterns() is defaults
    assert PDFTextStripper.match_pattern("12.", defaults) is not None
    assert PDFTextStripper.match_pattern("item 12.", defaults) is None

    custom = [re.compile(r"Item-\d+")]
    stripper.set_list_item_patterns(custom)
    assert stripper.get_list_item_patterns() is custom
    assert PDFTextStripper.match_pattern("Item-7", custom) is custom[0]

    stripper.set_list_item_patterns(None)
    assert stripper.get_list_item_patterns() is not custom


def test_wave460_get_text_empty_range_does_not_call_document_hooks() -> None:
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (ignored) Tj ET")
    events: list[str] = []

    class HookStripper(PDFTextStripper):
        def start_document(self, document: PDDocument) -> None:
            events.append("start")

        def end_document(self, document: PDDocument) -> None:
            events.append("end")

    global _WAVE963_HOOK_STRIPPER_CLASS
    _WAVE963_HOOK_STRIPPER_CLASS = HookStripper

    stripper = HookStripper()
    stripper.set_start_page(3)
    stripper.set_end_page(1)

    assert stripper.get_text(doc) == ""
    assert events == []
    assert stripper.get_current_page_no() == 0


def test_wave460_duplicate_overlap_suppression_can_be_disabled() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (bold) Tj 1 0 Td (bold) Tj ET",
    )

    default = PDFTextStripper()
    assert default.get_text(doc) == "bold\n"

    unsuppressed = PDFTextStripper()
    unsuppressed.set_suppress_duplicate_overlapping_text(False)
    assert unsuppressed.get_text(doc) == "boldbold\n"
    assert unsuppressed.get_suppress_duplicate_overlapping_text() is False
    assert unsuppressed.is_suppress_duplicate_overlapping_text() is False


def test_wave460_paragraph_drop_emits_paragraph_markers_between_lines() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 10 Tf 100 700 Td (first) Tj 0 -40 Td (second) Tj ET",
    )

    stripper = PDFTextStripper()
    stripper.set_paragraph_start("<p>")
    stripper.set_paragraph_end("</p>")
    stripper.set_line_separator("|")

    # Upstream ``writePage`` brackets the page body in a paragraph: a leading
    # ``writeParagraphStart`` on the first glyph (``<p>``) and a trailing
    # ``writeParagraphEnd`` after the last line (``</p>``). The mid-page break
    # emits the line separator first, then the paragraph separator
    # (``writeParagraphEnd`` + ``writeParagraphStart``): ``writeLineSeparator →
    # writeParagraphEnd → writeParagraphStart`` (PDFTextStripper.java:700-724,
    # 1578-1579, 1697-1700). page_end adds the trailing newline.
    assert stripper.get_text(doc) == "<p>first|</p><p>second</p>\n"


def test_wave460_text_matrix_tracks_tm_scale_and_translation_on_positions() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 0 1 -1 0 25 50 Tm (rotated) Tj ET",
    )

    stripper = PDFTextStripper()
    assert stripper.get_text(doc) == "rotated\n"

    pos = stripper.get_characters_by_article()[0][0]
    assert pos.text_matrix == [0.0, 1.0, -1.0, 0.0, 25.0, 50.0]
    assert pos.x == 25.0
    assert pos.y == 50.0


def test_wave460_direct_formatting_helpers_respect_flip_axes_indent() -> None:
    prev = TextPosition(
        text="left",
        x=100.0,
        y=20.0,
        font_size=10.0,
        width=20.0,
        width_of_space=4.0,
    )
    pos = TextPosition(
        text="right",
        x=106.0,
        y=60.0,
        font_size=10.0,
        width=25.0,
        width_of_space=4.0,
    )
    stripper = PDFTextStripper()
    stripper.set_should_flip_axes(True)
    stripper.set_indent_threshold(2.0)

    assert stripper.is_para_break_indented(pos, prev) is True
    assert stripper.start_of_paragraph(pos, prev) is True
    assert stripper._is_line_break(pos, prev) is True
    assert stripper._is_word_break(pos, prev) is True


def test_wave460_write_character_and_article_hooks_are_noops_by_default() -> None:
    stripper = PDFTextStripper()
    pos = TextPosition(text="x", x=0.0, y=0.0, font_size=1.0)

    assert stripper.write_characters(pos) is None
    assert stripper.start_article(False) is None
    assert stripper.end_article() is None
