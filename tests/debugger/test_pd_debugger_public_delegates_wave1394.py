"""Wave 1394 — public-spelling delegate methods on ``PDFDebugger``.

Covers lines 2131, 2135, 2139, 2143, 2154, 2163, 2167, 2171, 2175,
2179, 2183, 2187, 2191, 2247, 2255, 2279 — the thin public delegates
added for upstream-parity that wrap private underscore-prefixed
callbacks / classmethods.

Each test exercises the public spelling and confirms it threads
through to the underlying private one with the right arguments.
"""

from __future__ import annotations

import contextlib
import os
import tkinter as tk
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from pypdfbox.debugger.pd_debugger import PDFDebugger
from pypdfbox.debugger.ui.image_type_menu import ImageTypeMenu
from pypdfbox.debugger.ui.render_destination_menu import RenderDestinationMenu
from pypdfbox.debugger.ui.rotation_menu import RotationMenu
from pypdfbox.debugger.ui.text_stripper_menu import TextStripperMenu
from pypdfbox.debugger.ui.tree_view_menu import TreeViewMenu
from pypdfbox.debugger.ui.view_menu import ViewMenu
from pypdfbox.debugger.ui.zoom_menu import ZoomMenu


def _reset_menu_singletons() -> None:
    ViewMenu._reset_instance()  # noqa: SLF001
    ZoomMenu._reset_instance()  # noqa: SLF001
    RotationMenu._reset_instance()  # noqa: SLF001
    RenderDestinationMenu._reset_instance()  # noqa: SLF001
    TreeViewMenu._reset_for_testing()  # noqa: SLF001
    ImageTypeMenu._reset_for_testing()  # noqa: SLF001
    TextStripperMenu._reset_for_testing()  # noqa: SLF001


@pytest.fixture()
def tk_root() -> Iterator[tk.Tk]:
    if os.environ.get("PYPDFBOX_SKIP_TK", "") == "1":
        pytest.skip("PYPDFBOX_SKIP_TK=1 -- Tk tests opted out")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no Tk display available: {exc}")
    root.withdraw()
    _reset_menu_singletons()
    try:
        yield root
    finally:
        _reset_menu_singletons()
        with contextlib.suppress(tk.TclError):
            root.destroy()


@pytest.fixture()
def debugger(tk_root: tk.Tk) -> Iterator[PDFDebugger]:
    instance = PDFDebugger(tk_root)
    try:
        yield instance
    finally:
        with contextlib.suppress(tk.TclError):
            instance._main_frame.destroy()  # noqa: SLF001


# ---------- delegate forwards (instance-level) ----------


def test_open_menu_item_action_performed_delegates(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = MagicMock()
    monkeypatch.setattr(debugger, "_open_menu_item_action_performed", spy)
    debugger.open_menu_item_action_performed()
    assert spy.call_count == 1


def test_save_as_menu_item_action_performed_delegates(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = MagicMock()
    monkeypatch.setattr(debugger, "_save_as_menu_item_action_performed", spy)
    debugger.save_as_menu_item_action_performed(event="fake")
    assert spy.call_count == 1


def test_print_menu_item_action_performed_delegates(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = MagicMock()
    monkeypatch.setattr(debugger, "_print_menu_item_action_performed", spy)
    debugger.print_menu_item_action_performed()
    assert spy.call_count == 1


def test_exit_menu_item_action_performed_delegates(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = MagicMock()
    monkeypatch.setattr(debugger, "_exit_menu_item_action_performed", spy)
    debugger.exit_menu_item_action_performed()
    assert spy.call_count == 1


def test_j_tree1_value_changed_delegates(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = MagicMock()
    monkeypatch.setattr(debugger, "_on_tree_selection_changed", spy)
    debugger.j_tree1_value_changed()
    assert spy.call_count == 1


def test_read_pd_furl_delegates_with_url_and_password(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = MagicMock()
    monkeypatch.setattr(debugger, "_read_pdf_url", spy)
    debugger.read_pd_furl("http://example.com/foo.pdf", "secret")
    spy.assert_called_once_with("http://example.com/foo.pdf", "secret")


def test_show_page_delegates(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = MagicMock()
    monkeypatch.setattr(debugger, "_show_page", spy)
    sentinel: Any = object()
    debugger.show_page(sentinel)
    spy.assert_called_once_with(sentinel)


def test_show_color_pane_delegates(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = MagicMock()
    monkeypatch.setattr(debugger, "_show_color_pane", spy)
    sentinel = object()
    debugger.show_color_pane(sentinel)
    spy.assert_called_once_with(sentinel)


def test_show_flag_pane_delegates(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = MagicMock()
    monkeypatch.setattr(debugger, "_show_flag_pane", spy)
    parent = object()
    node = object()
    debugger.show_flag_pane(parent, node)
    spy.assert_called_once_with(parent, node)


def test_show_stream_delegates(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = MagicMock()
    monkeypatch.setattr(debugger, "_show_stream", spy)
    node = object()
    debugger.show_stream(node, "iid-a", "parent-iid")
    spy.assert_called_once_with(node, "iid-a", "parent-iid")


def test_show_font_delegates(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = MagicMock()
    monkeypatch.setattr(debugger, "_show_font", spy)
    node = object()
    debugger.show_font(node, "the-iid")
    spy.assert_called_once_with(node, "the-iid")


def test_show_signature_pane_delegates(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = MagicMock()
    monkeypatch.setattr(debugger, "_show_signature_pane", spy)
    node = object()
    debugger.show_signature_pane(node)
    spy.assert_called_once_with(node)


def test_show_string_delegates(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = MagicMock()
    monkeypatch.setattr(debugger, "_show_string", spy)
    node = object()
    debugger.show_string(node)
    spy.assert_called_once_with(node)


# ---------- classmethod delegates (lines 2247, 2255, 2279) ----------


def test_is_encrypt_classmethod_delegates_to_private() -> None:
    """``PDFDebugger.is_encrypt`` matches ``_is_encrypt`` for the same arg."""
    sentinel = object()
    assert PDFDebugger.is_encrypt(sentinel) == PDFDebugger._is_encrypt(sentinel)  # noqa: SLF001


def test_is_signature_classmethod_delegates_to_private() -> None:
    node, parent = object(), object()
    assert PDFDebugger.is_signature(node, parent) == PDFDebugger._is_signature(  # noqa: SLF001
        node, parent
    )


def test_is_flag_node_classmethod_delegates_to_private() -> None:
    node, parent = object(), object()
    assert PDFDebugger.is_flag_node(node, parent) == PDFDebugger._is_flag_node(  # noqa: SLF001
        node, parent
    )
