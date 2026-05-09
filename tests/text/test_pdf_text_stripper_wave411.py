from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFTextStripper


def _make_page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


def test_single_quote_operator_moves_to_next_line_and_shows_text() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 14 TL 100 700 Td (first) Tj (second) ' ET",
    )

    assert PDFTextStripper().get_text(doc) == "first\nsecond\n"


def test_double_quote_operator_sets_spacing_moves_line_and_shows_text() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b'BT /F0 12 Tf 14 TL 100 700 Td (first) Tj 9 3 (second) " ET',
    )

    stripper = PDFTextStripper()
    assert stripper.get_text(doc) == "first\nsecond\n"

    positions = stripper.get_characters_by_article()[0]
    assert positions[-1].text == "second"
    assert positions[-1].word_spacing == 9.0
    assert positions[-1].char_spacing == 3.0


def test_tj_numeric_adjustment_can_create_word_separator() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td [(foo) -3000 (bar)] TJ ET",
    )

    assert PDFTextStripper().get_text(doc) == "foo bar\n"


def test_ignore_content_stream_space_glyphs_uses_gap_for_words() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (a    b) Tj ET",
    )

    default = PDFTextStripper()
    assert default.get_text(doc) == "a    b\n"

    stripper = PDFTextStripper()
    stripper.set_ignore_content_stream_space_glyphs(True)
    assert stripper.get_text(doc) == "a b\n"


def test_article_start_and_end_wrap_each_page_body() -> None:
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (one) Tj ET")
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (two) Tj ET")

    stripper = PDFTextStripper()
    stripper.set_page_start("<page>")
    stripper.set_page_end("</page>")
    stripper.set_article_start("<article>")
    stripper.set_article_end("</article>")

    assert (
        stripper.get_text(doc)
        == "<page><article>one</article></page>"
        "<page><article>two</article></page>"
    )


def test_malformed_positioning_operands_are_ignored_without_losing_text() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf (bad) Td (still) Tj /NotANumber 1 2 3 4 5 Tm (ok) Tj ET",
    )

    assert PDFTextStripper().get_text(doc) == "stillok\n"
