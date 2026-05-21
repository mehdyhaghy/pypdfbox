"""Port of upstream ``TestPDFText2HTML`` from
``tools/src/test/java/org/apache/pdfbox/tools/TestPDFText2HTML.java``.

Builds a synthetic single-page PDF with a title and a Standard 14
Helvetica text run, then asserts that :class:`PDFText2HTML`:

1. HTML-escapes the title (``<script>`` + a non-ASCII codepoint → the
   numeric character reference ``&#12354;``) and the body text
   (``<foo>`` → ``&lt;foo&gt;``).
2. Wraps bold-styled text in ``<b>`` tags inside a ``<p>`` paragraph.
"""

from __future__ import annotations

import re

from pypdfbox import PDDocument, PDPage
from pypdfbox.pdmodel.font import PDFontFactory, Standard14Fonts
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.tools.pdf_text2_html import PDFText2HTML


def _create_document(
    title: str, font_name: Standard14Fonts.FontName, text: str
) -> PDDocument:
    """Build a one-page PDF with ``title`` in the metadata and ``text``
    rendered with ``font_name`` at 12pt at position (100, 700).

    Mirrors upstream ``TestPDFText2HTML.createDocument``.
    """
    doc = PDDocument()
    doc.get_document_information().set_title(title)
    page = PDPage()
    doc.add_page(page)
    font = PDFontFactory.create_default_font(font_name.value)
    content_stream = PDPageContentStream(doc, page)
    try:
        content_stream.begin_text()
        content_stream.set_font(font, 12)
        content_stream.new_line_at_offset(100, 700)
        content_stream.show_text(text)
        content_stream.end_text()
    finally:
        content_stream.close()
    return doc


def test_escape_title() -> None:
    """Ported from ``TestPDFText2HTML#testEscapeTitle``."""
    stripper = PDFText2HTML()
    doc = _create_document(
        "<script>あ", Standard14Fonts.FontName.HELVETICA, "<foo>"
    )
    try:
        text = stripper.get_text(doc)

        match = re.search(r"<title>(.*?)</title>", text)
        assert match is not None
        assert match.group(1) == "&lt;script&gt;&#12354;"
        assert "&lt;foo&gt;" in text
    finally:
        doc.close()


def test_style() -> None:
    """Ported from ``TestPDFText2HTML#testStyle``."""
    stripper = PDFText2HTML()
    doc = _create_document(
        "t", Standard14Fonts.FontName.HELVETICA_BOLD, "<bold>"
    )
    try:
        text = stripper.get_text(doc)

        body_match = re.search(r"<p>(.*?)</p>", text)
        assert body_match is not None, "body p exists"
        assert body_match.group(1) == "<b>&lt;bold&gt;</b>", "body p"
    finally:
        doc.close()
