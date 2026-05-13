"""Tests for :class:`PagePane`.

The widget needs a Tk root (``tk_root`` fixture from conftest) and is
exercised against a single synthetic PDF page.
"""

from __future__ import annotations

import tkinter as tk

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.debugger.pagepane.page_pane import (
    PagePane,
    _resolve_rotation,
    _resolve_zoom_scale,
    _safe_call,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle


def _make_one_page_doc(content: bytes | None = b"BT /F0 12 Tf 10 50 Td (x) Tj ET") -> PDDocument:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 60.0, 60.0))
    if content is not None:
        stream = COSStream()
        stream.set_data(content)
        page.set_contents(stream)
    doc.add_page(page)
    return doc


def test_page_pane_constructs_and_returns_frame(tk_root: tk.Tk) -> None:
    doc = _make_one_page_doc(content=None)
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        assert pane.get_panel() is not None
        assert pane._initialized is True  # noqa: SLF001 — internal flag
        # Page label widget mentions the 1-based page number.
        assert pane._page_label_widget is not None  # noqa: SLF001
        assert "Page 1" in pane._page_label_widget.cget("text")  # noqa: SLF001
    finally:
        doc.close()


def test_page_pane_orphan_page_label(tk_root: tk.Tk) -> None:
    """A page whose dictionary isn't in the document tree shows the orphan label."""
    doc = _make_one_page_doc(content=None)
    try:
        orphan = PDPage(PDRectangle(0.0, 0.0, 50.0, 50.0))
        pane = PagePane(tk_root, doc, orphan.get_cos_object(), statuslabel=None)
        pane.init()
        label = pane._page_label_widget  # noqa: SLF001
        assert label is not None
        assert "orphan" in label.cget("text")
    finally:
        doc.close()


def test_page_pane_render_places_image_on_canvas(tk_root: tk.Tk) -> None:
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        # After init() ran, the canvas should have one image item with
        # tag "rendered_page".
        canvas = pane._canvas  # noqa: SLF001
        assert canvas is not None
        items = canvas.find_withtag("rendered_page")
        assert items, "expected at least one rendered page image on the canvas"
        assert pane.get_image() is not None
    finally:
        doc.close()


def test_page_pane_set_page_swaps_rendered_image(tk_root: tk.Tk) -> None:
    doc = _make_one_page_doc()
    second = PDPage(PDRectangle(0.0, 0.0, 80.0, 40.0))
    stream = COSStream()
    stream.set_data(b"BT /F0 10 Tf 5 20 Td (y) Tj ET")
    second.set_contents(stream)
    doc.add_page(second)
    try:
        first_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, first_dict, statuslabel=None)
        pane.init()
        before = pane.get_image()
        pane.set_page(doc.get_page(1))
        after = pane.get_image()
        assert after is not None
        # Image size after the swap should reflect the second page.
        assert after.size == (80, 40)
        # And the image instance should have changed.
        assert before is not after
    finally:
        doc.close()


def test_page_pane_status_label_updates_on_mouse_motion(tk_root: tk.Tk) -> None:
    """Sanity check that the mouse handler writes to the status widget."""
    from tkinter import ttk

    doc = _make_one_page_doc()
    try:
        status = ttk.Label(tk_root, text="")
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=status)
        pane.init()
        # Synthesize a motion event by directly invoking the handler.
        event = tk.Event()
        event.x = 10
        event.y = 10
        pane._on_mouse_moved(event)  # noqa: SLF001
        assert status.cget("text").startswith("x: ")
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Helper-function tests (no Tk required)
# ---------------------------------------------------------------------------


def test_resolve_zoom_scale_returns_float() -> None:
    value = _resolve_zoom_scale()
    assert isinstance(value, float)
    assert value > 0


def test_resolve_rotation_returns_int() -> None:
    value = _resolve_rotation()
    assert isinstance(value, int)


def test_safe_call_returns_default_when_target_is_none() -> None:
    assert _safe_call(None, "missing", default=42) == 42


def test_safe_call_returns_method_result() -> None:
    class _T:
        def value(self) -> int:
            return 7

    assert _safe_call(_T(), "value", default=0) == 7


def test_safe_call_returns_default_when_method_missing() -> None:
    assert _safe_call(object(), "no_such", default="fallback") == "fallback"


def test_safe_call_returns_default_when_method_raises() -> None:
    class _T:
        def boom(self) -> None:
            raise RuntimeError("nope")

    assert _safe_call(_T(), "boom", default="ok") == "ok"


@pytest.mark.parametrize(
    "label, expected_uri",
    [("URI: https://example.com", "https://example.com"), ("Field name: foo, value: bar", "")],
)
def test_page_pane_currrent_uri_after_motion_over_rect(
    tk_root: tk.Tk, label: str, expected_uri: str
) -> None:
    """When the cursor sits over a URI rect, ``_current_uri`` is populated."""
    doc = _make_one_page_doc(content=None)
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        # Inject a fake rectangle that contains any point.
        class _AlwaysContains:
            def contains(self, _x: float, _y: float) -> bool:
                return True

        pane._rect_map[_AlwaysContains()] = label  # noqa: SLF001
        event = tk.Event()
        event.x = 5
        event.y = 5
        pane._on_mouse_moved(event)  # noqa: SLF001
        assert pane._current_uri == expected_uri  # noqa: SLF001
    finally:
        doc.close()
