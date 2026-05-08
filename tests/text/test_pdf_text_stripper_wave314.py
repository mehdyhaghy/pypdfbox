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


def test_wave314_ignore_content_stream_space_glyphs_removes_literal_spaces() -> None:
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (A B C) Tj ET")

    stripper = PDFTextStripper()
    stripper.set_ignore_content_stream_space_glyphs(True)

    try:
        assert stripper.get_text(doc) == "ABC\n"
    finally:
        doc.close()


def test_wave314_ignored_space_glyphs_still_advance_text_cursor() -> None:
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (A ) Tj (B) Tj ET")

    stripper = PDFTextStripper()
    stripper.set_ignore_content_stream_space_glyphs(True)

    try:
        assert stripper.get_text(doc) == "AB\n"
        positions = stripper.get_characters_by_article()[0]
        assert [position.get_unicode() for position in positions] == ["A", "B"]
        assert [position.get_x() for position in positions] == [100.0, 112.0]
    finally:
        doc.close()
