"""Smoke test for :class:`PDFHighlighter`."""

from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

from pypdfbox.examples.util.pdf_highlighter import PDFHighlighter
from pypdfbox.pdmodel.pd_document import PDDocument


def test_generate_xml_highlight_emits_wrapper(make_pdf: Callable[..., Path]) -> None:
    src = make_pdf("highlight.pdf")
    out = io.StringIO()
    with PDDocument.load(str(src)) as doc:
        PDFHighlighter().generate_xml_highlight(doc, "anything", out)
    text = out.getvalue()
    assert "<XML>" in text
    assert "</XML>" in text
