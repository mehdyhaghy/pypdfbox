"""Tests for ``pypdfbox.examples.printing.opaque_pdf_renderer``."""
from __future__ import annotations

import pytest

from pypdfbox.examples.printing.opaque_pdf_renderer import OpaquePDFRenderer
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.rendering.page_drawer import PageDrawer
from pypdfbox.rendering.page_drawer_parameters import PageDrawerParameters
from pypdfbox.rendering.pdf_renderer import PDFRenderer
from pypdfbox.rendering.render_destination import RenderDestination


def test_subclasses_pdf_renderer() -> None:
    assert issubclass(OpaquePDFRenderer, PDFRenderer)


def test_main_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        OpaquePDFRenderer.main([])


def test_create_page_drawer_exists() -> None:
    assert callable(OpaquePDFRenderer.create_page_drawer)


def test_constructor_initialises_document() -> None:
    """Exercise the explicit ``super().__init__(document)`` call (line 27)."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        renderer = OpaquePDFRenderer(doc)
        assert isinstance(renderer, PDFRenderer)


def test_create_page_drawer_returns_opaque_drawer() -> None:
    """Drive ``create_page_drawer`` end-to-end so both line 45 (factory
    return) and lines 52-55 (inner-class constructor + operator
    additions) execute. The inner class is private so we verify shape
    via ``isinstance(PageDrawer)`` rather than the underscored name."""
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        renderer = OpaquePDFRenderer(doc)
        params = PageDrawerParameters(
            renderer,
            page,
            False,
            RenderDestination.PRINT,
            None,
            0.5,
        )
        drawer = renderer.create_page_drawer(params)
        assert isinstance(drawer, PageDrawer)
