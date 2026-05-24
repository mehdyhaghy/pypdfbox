"""Wave 1394 — ``PagePane`` listener-shaped public method early-exits.

Covers lines 575, 609-611, 638-640, 657-659 — the upstream-parity
public wrappers that thread through to the Tk-bound private callbacks
(``_on_mouse_clicked`` / ``_on_mouse_exited`` / ``_on_mouse_moved``)
when an event is supplied, or return immediately when called with
``None`` for parity-tool invocation.

The ``action_performed`` public method (line 575) re-fires
``start_rendering``; the existing ``test_page_pane_dispatch.py`` covers
the success path of ``start_rendering`` itself, so we just assert
``action_performed`` actually invokes it.
"""

from __future__ import annotations

import tkinter as tk
from unittest.mock import MagicMock

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.debugger.pagepane.page_pane import PagePane
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle


def _make_one_page_doc() -> PDDocument:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 60.0, 60.0))
    stream = COSStream()
    stream.set_data(b"BT /F0 12 Tf 5 10 Td (x) Tj ET")
    page.set_contents(stream)
    doc.add_page(page)
    return doc


def test_action_performed_invokes_start_rendering(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``action_performed`` should call :meth:`start_rendering` (line 575)."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        spy = MagicMock()
        monkeypatch.setattr(pane, "start_rendering", spy)
        pane.action_performed()
        assert spy.call_count == 1
        # Also accept the optional event arg.
        pane.action_performed(event="fake")
        assert spy.call_count == 2
    finally:
        doc.close()


def test_mouse_clicked_none_event_is_noop(tk_root: tk.Tk) -> None:
    """``mouse_clicked(None)`` should return immediately (lines 609-610)."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        # Should not raise.
        pane.mouse_clicked(None)
    finally:
        doc.close()


def test_mouse_clicked_with_event_delegates(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``mouse_clicked(event)`` should delegate to ``_on_mouse_clicked``
    (line 611)."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        spy = MagicMock()
        monkeypatch.setattr(pane, "_on_mouse_clicked", spy)
        event = tk.Event()
        pane.mouse_clicked(event)
        spy.assert_called_once_with(event)
    finally:
        doc.close()


def test_mouse_exited_none_event_is_noop(tk_root: tk.Tk) -> None:
    """``mouse_exited(None)`` should return immediately (lines 638-639)."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        pane.mouse_exited(None)
    finally:
        doc.close()


def test_mouse_exited_with_event_delegates(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``mouse_exited(event)`` delegates to ``_on_mouse_exited`` (line 640)."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        spy = MagicMock()
        monkeypatch.setattr(pane, "_on_mouse_exited", spy)
        event = tk.Event()
        pane.mouse_exited(event)
        spy.assert_called_once_with(event)
    finally:
        doc.close()


def test_mouse_moved_none_event_is_noop(tk_root: tk.Tk) -> None:
    """``mouse_moved(None)`` should return immediately (lines 657-658)."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        pane.mouse_moved(None)
    finally:
        doc.close()


def test_mouse_moved_with_event_delegates(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``mouse_moved(event)`` delegates to ``_on_mouse_moved`` (line 659)."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        spy = MagicMock()
        monkeypatch.setattr(pane, "_on_mouse_moved", spy)
        event = tk.Event()
        pane.mouse_moved(event)
        spy.assert_called_once_with(event)
    finally:
        doc.close()
