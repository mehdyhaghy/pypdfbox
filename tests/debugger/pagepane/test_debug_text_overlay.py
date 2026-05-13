"""Tests for :class:`DebugTextOverlay`.

The overlay subclasses :class:`PDFTextStripper` and walks a synthetic
single-page PDF — we then assert that the per-glyph ``writeString`` hook
produced at least one rectangle when the corresponding overlay flag is
enabled.

These tests intentionally don't bring in Tk: the overlay is decoupled
from the PIL draw context so a headless run can inspect the rectangle
list.
"""

from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.debugger.pagepane.debug_text_overlay import (
    DebugRectangle,
    DebugTextOverlay,
    _normalize_rect,
    displacement_or_one,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle


def _make_one_page_doc_with_text() -> PDDocument:
    """Build a minimal 1-page PDF whose content stream paints one text run."""
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    content = COSStream()
    content.set_data(b"BT /F0 12 Tf 50 100 Td (hi) Tj ET")
    page.set_contents(content)
    doc.add_page(page)
    return doc


def test_overlay_all_flags_disabled_emits_no_rectangles() -> None:
    doc = _make_one_page_doc_with_text()
    try:
        overlay = DebugTextOverlay(
            doc,
            page_index=0,
            scale=1.0,
            show_text_stripper=False,
            show_text_stripper_beads=False,
            show_font_bbox=False,
            show_glyph_bounds=False,
        )
        rects = overlay.render_to(draw=None)
        assert rects == []
    finally:
        doc.close()


def test_overlay_text_stripper_flag_produces_red_rectangles() -> None:
    doc = _make_one_page_doc_with_text()
    try:
        overlay = DebugTextOverlay(
            doc,
            page_index=0,
            scale=1.0,
            show_text_stripper=True,
            show_text_stripper_beads=False,
            show_font_bbox=False,
            show_glyph_bounds=False,
        )
        rects = overlay.render_to(draw=None)
        assert len(rects) >= 1
        assert all(r.color == "red" for r in rects)
        # Each rectangle is well-ordered after _normalize_rect.
        for r in rects:
            x0, y0, x1, y1 = r.coords
            assert x0 <= x1
            assert y0 <= y1
    finally:
        doc.close()


def test_overlay_render_to_draw_paints_rectangles() -> None:
    from PIL import Image, ImageDraw

    doc = _make_one_page_doc_with_text()
    try:
        image = Image.new("RGB", (200, 200), "white")
        draw = ImageDraw.Draw(image)
        overlay = DebugTextOverlay(
            doc,
            page_index=0,
            scale=1.0,
            show_text_stripper=True,
            show_text_stripper_beads=False,
            show_font_bbox=False,
            show_glyph_bounds=False,
        )
        rects = overlay.render_to(draw=draw)
        assert rects, "expected at least one rectangle"
        # The painted image should have at least one non-white pixel
        # where the rectangle was drawn.
        if hasattr(image, "get_flattened_data"):
            flat = image.get_flattened_data()
        else:
            flat = list(image.getdata())
        # ``get_flattened_data`` yields a flat tuple of channels; chunk back.
        if flat and isinstance(flat[0], int):
            pixels = list(zip(flat[0::3], flat[1::3], flat[2::3], strict=False))
        else:
            pixels = list(flat)
        non_white = any(p != (255, 255, 255) for p in pixels)
        assert non_white
    finally:
        doc.close()


def test_overlay_inspection_properties_round_trip() -> None:
    doc = _make_one_page_doc_with_text()
    try:
        overlay = DebugTextOverlay(
            doc,
            page_index=0,
            scale=2.0,
            show_text_stripper=True,
            show_text_stripper_beads=True,
            show_font_bbox=False,
            show_glyph_bounds=True,
        )
        assert overlay.show_text_stripper is True
        assert overlay.show_text_stripper_beads is True
        assert overlay.show_font_bbox is False
        assert overlay.show_glyph_bounds is True
    finally:
        doc.close()


def test_normalize_rect_orders_corners() -> None:
    assert _normalize_rect(10, 20, 30, 40) == (10, 20, 30, 40)
    assert _normalize_rect(30, 40, 10, 20) == (10, 20, 30, 40)
    assert _normalize_rect(30, 20, 10, 40) == (10, 20, 30, 40)


def test_displacement_or_one_handles_missing_get_x() -> None:
    assert displacement_or_one(None) == 1.0
    assert displacement_or_one(object()) == 1.0

    class _D:
        def get_x(self) -> float:
            return 2.5

    assert displacement_or_one(_D()) == 2.5


def test_debug_rectangle_has_default_width() -> None:
    rect = DebugRectangle(coords=(0, 0, 10, 10), color="red")
    assert rect.width == 0.5
    assert rect.color == "red"
