from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.documentinterchange.markedcontent import PDMarkedContent
from pypdfbox.text import PDFMarkedContentExtractor, TextPosition


def _make_page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


def _text_content(marked_content: PDMarkedContent) -> str:
    return "".join(
        item.get_unicode()
        for item in marked_content.get_contents()
        if isinstance(item, TextPosition)
    )


def test_wave302_duplicate_suppression_cache_resets_per_page() -> None:
    doc = PDDocument()
    body = (
        b"/P <</MCID 0>> BDC\n"
        b"BT /F0 12 Tf 10 20 Td (Same) Tj ET\n"
        b"EMC\n"
    )
    page_1 = _make_page_with_stream(doc, body)
    page_2 = _make_page_with_stream(doc, body)
    extractor = PDFMarkedContentExtractor()

    extractor.process_page(page_1)
    extractor.process_page(page_2)

    contents = extractor.get_marked_contents()
    assert len(contents) == 2
    assert [_text_content(content) for content in contents] == ["Same", "Same"]


def test_wave302_open_marked_content_stack_resets_per_page() -> None:
    doc = PDDocument()
    malformed_page = _make_page_with_stream(
        doc,
        b"/Sect <</MCID 0>> BDC\n"
        b"BT /F0 12 Tf 0 0 Td (Unclosed) Tj ET\n",
    )
    next_page = _make_page_with_stream(
        doc,
        b"/P <</MCID 1>> BDC\n"
        b"BT /F0 12 Tf 0 0 Td (Next) Tj ET\n"
        b"EMC\n",
    )
    extractor = PDFMarkedContentExtractor()

    extractor.process_page(malformed_page)
    extractor.process_page(next_page)

    contents = extractor.get_marked_contents()
    assert len(contents) == 2
    assert contents[0].get_tag() == "Sect"
    assert contents[1].get_tag() == "P"
    assert _text_content(contents[1]) == "Next"
