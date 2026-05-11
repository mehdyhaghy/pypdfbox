"""Tests for ``pypdfbox.examples.printing.opaque_pdf_renderer``."""
from __future__ import annotations

import pytest

from pypdfbox.examples.printing.opaque_pdf_renderer import OpaquePDFRenderer
from pypdfbox.rendering.pdf_renderer import PDFRenderer


def test_subclasses_pdf_renderer() -> None:
    assert issubclass(OpaquePDFRenderer, PDFRenderer)


def test_main_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        OpaquePDFRenderer.main([])


def test_create_page_drawer_exists() -> None:
    assert callable(OpaquePDFRenderer.create_page_drawer)
