"""Tests for ``pypdfbox.printing``."""

from __future__ import annotations

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.printing.pdf_pageable import Orientation, PDFPageable
from pypdfbox.printing.pdf_printable import PDFPrintable, Scaling


def _make_doc_with_pages(n: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n):
        doc.add_page(PDPage())
    return doc


def test_pdf_pageable_number_of_pages() -> None:
    doc = _make_doc_with_pages(3)
    pageable = PDFPageable(doc)
    assert pageable.get_number_of_pages() == 3


def test_pdf_pageable_get_page_format() -> None:
    doc = _make_doc_with_pages(1)
    pageable = PDFPageable(doc, orientation=Orientation.LANDSCAPE)
    fmt = pageable.get_page_format(0)
    assert fmt["orientation"] == "LANDSCAPE"
    assert fmt["width"] > 0
    assert fmt["height"] > 0


def test_pdf_pageable_get_printable_returns_per_page_helper() -> None:
    doc = _make_doc_with_pages(2)
    pageable = PDFPageable(doc)
    printable = pageable.get_printable(1)
    assert isinstance(printable, PDFPrintable)
    assert printable._page_index == 1  # type: ignore[attr-defined]


def test_pdf_printable_setters() -> None:
    doc = _make_doc_with_pages(1)
    printable = PDFPrintable(doc)
    printable.set_dpi(200.0)
    printable.set_scaling(Scaling.ACTUAL_SIZE)
    printable.set_subsampling_allowed(True)
    printable.set_rendering_hints({"k": "v"})
    assert printable.get_dpi() == 200.0
    assert printable.get_scaling() is Scaling.ACTUAL_SIZE
    assert printable.is_subsampling_allowed() is True
    assert printable.get_rendering_hints() == {"k": "v"}
