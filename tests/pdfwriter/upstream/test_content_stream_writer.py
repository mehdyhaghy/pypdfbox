"""Ported from
``pdfbox/src/test/java/org/apache/pdfbox/pdfwriter/ContentStreamWriterTest.java``
(PDFBox 3.0).

The single upstream test (``testPDFBox4750``) parses a content stream,
re-emits it via ``ContentStreamWriter``, then renders both the original
and rewritten pages and compares the resulting PNGs via
``TestPDFToImage`` to confirm the rewrite is visually identical.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdfparser import PDFStreamParser
from pypdfbox.pdfwriter import ContentStreamWriter
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.rendering import PDFRenderer


def test_pdf_box_4750() -> None:
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 50, 50))
        doc.add_page(page)

        stream = PDStream(doc)
        with stream.create_output_stream(COSName.FLATE_DECODE) as out:
            out.write(b"0 0 0 rg\n5 5 20 20 re\nf\n")
        page.set_contents(stream)

        before = PDFRenderer(doc).render_image(0)
        tokens = PDFStreamParser.from_content_stream(page).parse()

        new_content = PDStream(doc)
        with new_content.create_output_stream(COSName.FLATE_DECODE) as out:
            ContentStreamWriter(out).write_tokens(tokens)
        page.set_contents(new_content)

        after = PDFRenderer(doc).render_image(0)
        assert before.mode == after.mode
        assert before.size == after.size
        assert before.tobytes() == after.tobytes()
    finally:
        doc.close()
