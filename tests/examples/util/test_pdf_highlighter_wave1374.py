"""Wave 1374 audit verification — item 4: confirm that
``PDFHighlighter`` emits ``<loc>`` entries against a real PDF.

The audit flagged this as a latent integration gap (CHANGES.md line
3215). Wave 1340 closed it by making ``PDFTextStripper.write_text``
stream each page's text into ``self._output`` via the per-page
``_sink`` callable so the highlighter's ``end_page`` hook sees the
populated buffer. This wave pins that contract with an end-to-end
test against a freshly-generated PDF.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox.examples.util.pdf_highlighter import PDFHighlighter
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


def _build_pdf_with_text(path: Path, text: str) -> Path:
    """Render ``text`` onto a single Helvetica-rendered page."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        with PDPageContentStream(doc, page) as cs:
            cs.begin_text()
            cs.set_font(PDType1Font(), 12)
            cs.new_line_at_offset(50, 700)
            cs.show_text(text)
            cs.end_text()
        doc.save(path)
    finally:
        doc.close()
    return path


def test_highlighter_emits_loc_line_for_real_pdf(tmp_path: Path) -> None:
    """End-to-end regression — without per-page streaming
    (closed in wave 1340) ``end_page`` would see an empty buffer and
    no ``<loc>`` line would be emitted."""
    src = _build_pdf_with_text(tmp_path / "doc.pdf", "Hello World")
    out = io.StringIO()
    with PDDocument.load(str(src)) as doc:
        PDFHighlighter().generate_xml_highlight(doc, "Hello", out)
    text = out.getvalue()
    assert "<loc" in text
    assert "pg=" in text
    assert "len=5" in text  # len("Hello")


def test_highlighter_emits_loc_for_multiple_words(tmp_path: Path) -> None:
    """Multi-word search still hits each word independently when the
    per-page buffer is populated correctly."""
    src = _build_pdf_with_text(tmp_path / "doc.pdf", "Apple Banana Cherry")
    out = io.StringIO()
    with PDDocument.load(str(src)) as doc:
        PDFHighlighter().generate_xml_highlight(doc, ["Apple", "Cherry"], out)
    text = out.getvalue()
    # Each searched word should produce at least one <loc> entry.
    assert text.count("<loc") >= 2
