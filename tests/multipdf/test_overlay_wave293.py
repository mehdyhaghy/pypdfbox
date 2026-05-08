from __future__ import annotations

import pytest

from pypdfbox.multipdf import Overlay
from pypdfbox.pdmodel import PDDocument, PDPage


def _one_page_document() -> PDDocument:
    doc = PDDocument()
    doc.add_page(PDPage())
    return doc


def test_default_overlay_rejects_empty_overlay_document() -> None:
    base = _one_page_document()
    overlay_doc = PDDocument()
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(overlay_doc)

    with pytest.raises(ValueError, match="at least one page"):
        overlay.overlay({})

    base.close()
    overlay_doc.close()


def test_overlay_documents_rejects_empty_overlay_document() -> None:
    base = _one_page_document()
    overlay_doc = PDDocument()
    overlay = Overlay()
    overlay.set_input_pdf(base)

    with pytest.raises(ValueError, match="at least one page"):
        overlay.overlay_documents({1: overlay_doc})

    base.close()
    overlay_doc.close()

