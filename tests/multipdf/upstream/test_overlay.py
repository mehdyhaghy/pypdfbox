"""Ported from
``pdfbox/src/test/java/org/apache/pdfbox/multipdf/OverlayTest.java``
(PDFBox 3.0).

Upstream's tests rely on a bundle of pre-rendered fixtures
(``OverlayTestBaseRot0.pdf``, ``rot0.pdf`` … ``rot270.pdf``,
``Overlayed-with-rot*.pdf``, ``PDFBOX-6049-*.pdf``) that compare a
just-overlaid output against a pre-rendered model image. We don't ship
those fixtures, and rendering parity isn't part of the io/cos cluster
either, so the rotation/render-comparison tests are skipped here. The
constructable subset — argument validation and the no-fixture path —
translates directly.
"""

from __future__ import annotations

import pytest

from pypdfbox.multipdf import Overlay, Position
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


def _make_simple_doc(width: float = 595.0, height: float = 842.0) -> PDDocument:
    doc = PDDocument()
    page = PDPage(PDRectangle.from_width_height(width, height))
    doc.add_page(page)
    with PDPageContentStream(doc, page) as cs:
        cs.add_rect(10.0, 10.0, 30.0, 30.0)
        cs.stroke()
    return doc


# ---------------------------------------------------------------------------
# testRotatedOverlays / testRotatedOverlaysMap / testOverlayOnRotatedSourcePages
# ---------------------------------------------------------------------------
# Skipped: each of these tests calls ``checkIdenticalRendering`` against
# pre-rendered model PDFs that we don't carry as fixtures. Rendering
# parity also requires the rendering cluster (PRD §6.12) which isn't
# available in this slice.


@pytest.mark.skip(reason="upstream fixture bundle (OverlayTestBaseRot0.pdf etc.) not ported")
def test_rotated_overlays() -> None:
    pass


@pytest.mark.skip(reason="upstream fixture bundle (rot{0,90,180,270}.pdf) not ported")
def test_rotated_overlays_map() -> None:
    pass


@pytest.mark.skip(reason="upstream fixture bundle (PDFBOX-6049-*.pdf) not ported")
def test_overlay_on_rotated_source_pages() -> None:
    pass


# ---------------------------------------------------------------------------
# Constructable subset of testRotatedOverlaysMap:
# ``Assertions.assertThrows(IllegalArgumentException.class,
#    () -> overlay.overlay(specificPageOverlayMap));``
# fires when ``setInputPDF`` was never called. We translate that single
# assertion since it has no fixture dependency.
# ---------------------------------------------------------------------------


def test_overlay_throws_when_no_input_set() -> None:
    """Translated from the ``assertThrows`` inside
    ``testRotatedOverlaysMap``: calling ``overlay`` on a fresh ``Overlay``
    instance with no input document must raise — upstream uses
    ``IllegalArgumentException``; we surface :class:`ValueError`."""
    with Overlay() as overlay, pytest.raises(ValueError):
        overlay.overlay({})


# ---------------------------------------------------------------------------
# Side-line: exercise the public API surface that has no fixture dep.
# ---------------------------------------------------------------------------


def test_overlay_setters_round_trip() -> None:
    """Smoke-test every setter on the upstream ``Overlay`` API surface so
    a regression in any one of them shows up here even when the heavier
    rendering tests are skipped."""
    base = _make_simple_doc()
    extra = _make_simple_doc(200.0, 200.0)
    with Overlay() as overlay:
        overlay.set_input_pdf(base)
        overlay.set_default_overlay_pdf(extra)
        overlay.set_first_page_overlay_pdf(extra)
        overlay.set_last_page_overlay_pdf(extra)
        overlay.set_odd_page_overlay_pdf(extra)
        overlay.set_even_page_overlay_pdf(extra)
        overlay.set_specific_page_overlay_pdf({1: extra})
        overlay.set_overlay_position(Position.BACKGROUND)
        overlay.set_adjust_rotation(True)
        # Exercises the per-bucket selection logic without crashing.
        result = overlay.overlay({})
        assert result is base
