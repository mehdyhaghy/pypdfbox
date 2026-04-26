"""Ported from
``pdfbox/src/test/java/org/apache/pdfbox/pdfwriter/ContentStreamWriterTest.java``
(PDFBox 3.0).

The single upstream test (``testPDFBox4750``) parses a content stream,
re-emits it via ``ContentStreamWriter``, then renders both the original
and rewritten pages and compares the resulting PNGs via
``TestPDFToImage`` to confirm the rewrite is visually identical.

That harness depends on:
- ``PDFRenderer`` (rendering cluster — not yet ported)
- ``TestPDFToImage`` (test harness using ``BufferedImage`` — Java AWT)
- ``PDPageContentStream`` / ``PDStream.createOutputStream(FlateDecode)``

All three land with the rendering and pdmodel-content-stream clusters,
so the test is skipped until then. Hand-written round-trip coverage in
``../test_content_stream_writer.py`` exercises the same parse → write →
reparse pipeline at the token level (which is what ``ContentStreamWriter``
itself can be tested for without a renderer).
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason=(
        "needs PDFRenderer + TestPDFToImage + PDStream.createOutputStream — "
        "lands with the rendering / pdmodel-content-stream clusters."
    )
)
def test_pdf_box_4750() -> None:  # pragma: no cover - skipped
    pass
