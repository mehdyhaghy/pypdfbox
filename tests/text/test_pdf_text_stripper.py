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
    pos = TextPosition(text="Hi", x=10.0, y=20.0, font_size=12.0, font_name="F0")
    assert pos.text == "Hi"
    assert pos.x == 10.0
    assert pos.y == 20.0
    assert pos.font_size == 12.0
    assert pos.font_name == "F0"
    assert pos.get_unicode() == "Hi"
    assert pos.get_x() == 10.0
    assert pos.get_y() == 20.0
    assert pos.get_font_size() == 12.0
    assert pos.get_font_name() == "F0"


def test_text_position_default_font_name_is_none() -> None:
    pos = TextPosition(text="x", x=0.0, y=0.0, font_size=10.0)
    assert pos.font_name is None


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
