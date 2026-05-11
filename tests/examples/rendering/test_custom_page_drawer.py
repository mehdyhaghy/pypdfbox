"""Tests for ``pypdfbox.examples.rendering.custom_page_drawer``."""
from __future__ import annotations

from pypdfbox.examples.rendering.custom_page_drawer import (
    CustomPageDrawer,
    MyPageDrawer,
    MyPDFRenderer,
)
from pypdfbox.rendering.page_drawer import PageDrawer
from pypdfbox.rendering.pdf_renderer import PDFRenderer


def test_my_pdf_renderer_is_pdf_renderer_subclass() -> None:
    assert issubclass(MyPDFRenderer, PDFRenderer)


def test_my_page_drawer_is_page_drawer_subclass() -> None:
    assert issubclass(MyPageDrawer, PageDrawer)


def test_outer_class_main_is_static() -> None:
    # Must be a callable that does not require an instance.
    assert callable(CustomPageDrawer.main)


def test_main_raises_when_demo_pdf_missing() -> None:
    # The demo PDF is not bundled in the repository, so main() should
    # surface an OSError-style failure rather than silently succeeding.
    import pytest

    with pytest.raises((OSError, FileNotFoundError, RuntimeError)):
        CustomPageDrawer.main([])
