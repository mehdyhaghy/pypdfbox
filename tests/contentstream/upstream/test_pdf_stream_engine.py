"""Upstream parity tests for ``PDFStreamEngine``.

There is no standalone JUnit test for ``PDFStreamEngine`` in PDFBox 3.0.x
(``find /tmp/pdfbox -name 'PDFStreamEngineTest*'`` returns nothing). The
class is exercised through downstream integration tests — chiefly
``PDFTextStripperTest``, ``PDPageContentStreamTest``,
``TestPDFToImage`` — that walk full PDFs through the engine. The hand-
written suite in ``tests/contentstream/test_pdf_stream_engine.py``
covers the public/protected API surface directly; this file documents
the absence of a standalone upstream test and pins a small set of
behaviour-mirroring smoke tests that complement the round-trip suite.
"""
from __future__ import annotations

import pytest

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.pdmodel import PDPage, PDResources


def test_init_page_rejects_null_page_like_upstream() -> None:
    """Mirrors upstream ``initPage(PDPage)`` which throws
    ``IllegalArgumentException("Page cannot be null")``. Our snake_case
    port surfaces ``ValueError`` (the closest Pythonic mapping per the
    porting conventions in CLAUDE.md)."""
    engine = PDFStreamEngine()
    with pytest.raises(ValueError, match="cannot be null"):
        engine.init_page(None)  # type: ignore[arg-type]


def test_show_form_requires_current_page_like_upstream() -> None:
    """Upstream ``showForm`` raises ``IllegalStateException`` when no
    current page is set. We surface ``RuntimeError`` (mapping in
    CLAUDE.md)."""
    from pypdfbox.cos import COSStream  # noqa: PLC0415
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (  # noqa: PLC0415
        PDFormXObject,
    )

    engine = PDFStreamEngine()
    cos = COSStream()
    cos.set_raw_data(b"")
    form = PDFormXObject(cos)
    with pytest.raises(RuntimeError, match="process_child_stream"):
        engine.show_form(form)


def test_get_graphics_stack_size_starts_at_zero() -> None:
    """Mirrors upstream ``getGraphicsStackSize()`` returning 0 before
    any ``processPage`` / ``saveGraphicsState`` push."""
    engine = PDFStreamEngine()
    assert engine.get_graphics_stack_size() == 0


def test_increase_decrease_level_mirrors_upstream() -> None:
    """Mirrors upstream ``increaseLevel`` / ``decreaseLevel`` /
    ``getLevel``. The base value is 0 and the helpers are inverse-pair."""
    engine = PDFStreamEngine()
    assert engine.get_level() == 0
    engine.increase_level()
    engine.increase_level()
    assert engine.get_level() == 2
    engine.decrease_level()
    engine.decrease_level()
    assert engine.get_level() == 0


def test_is_should_process_color_operators_default_true() -> None:
    """Upstream initialises ``shouldProcessColorOperators`` to ``true``
    in the default constructor; flipped only inside the Type3 ``d1``
    first-operator path and uncoloured tiling pattern path."""
    engine = PDFStreamEngine()
    assert engine.is_should_process_color_operators() is True


def test_get_resources_default_is_none() -> None:
    """Upstream ``getResources()`` returns ``null`` until a stream is
    in flight — matches the cluster #2 default."""
    engine = PDFStreamEngine()
    assert engine.get_resources() is None


def test_get_current_page_default_is_none() -> None:
    """Upstream ``getCurrentPage()`` returns ``null`` outside of
    ``processPage`` / ``processChildStream``."""
    engine = PDFStreamEngine()
    assert engine.get_current_page() is None


def test_init_page_resets_state() -> None:
    """``initPage`` resets the graphics stack and seeds resources from
    the page — mirrors upstream's ``initPage(PDPage)`` body."""
    engine = PDFStreamEngine()
    page = PDPage()
    page.set_resources(PDResources())
    engine._graphics_stack.append("stale")
    engine.init_page(page)
    assert engine.get_graphics_stack_size() == 0
    assert engine.get_current_page() is page
