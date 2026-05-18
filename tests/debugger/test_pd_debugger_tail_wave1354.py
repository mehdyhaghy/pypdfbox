"""Wave 1354 tail-sweep for ``PDFDebugger._show_font`` success branch.

Covers line 1142 in ``pd_debugger.py`` — the ``_replace_right_component``
call reached when ``FontEncodingPaneController.get_pane()`` returns a
non-``None`` widget.
"""

from __future__ import annotations

import contextlib
import os
import tkinter as tk
from collections.abc import Iterator
from tkinter import ttk
from typing import Any

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.debugger import pd_debugger as _pd_debugger
from pypdfbox.debugger.pd_debugger import PDFDebugger
from pypdfbox.debugger.ui.image_type_menu import ImageTypeMenu
from pypdfbox.debugger.ui.map_entry import MapEntry
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


@pytest.fixture(autouse=True)
def _stub_error_dialog() -> Iterator[None]:
    from pypdfbox.debugger.ui import error_dialog as _ed

    _ed.set_show_error_impl(lambda title, message: None)
    try:
        yield
    finally:
        _ed.set_show_error_impl(None)


@pytest.fixture()
def debugger(tk_root: tk.Tk) -> Iterator[PDFDebugger]:
    instance = PDFDebugger(tk_root)
    try:
        yield instance
    finally:
        with contextlib.suppress(tk.TclError):
            instance._main_frame.destroy()  # noqa: SLF001


def _make_map_entry(key_name: str, value: Any) -> MapEntry:
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name(key_name))
    entry.set_value(value)
    return entry


def _insert(tree: Any, parent_iid: str, text: str, node: Any) -> str:
    iid = tree.insert(parent_iid, "end", text=text)
    tree.register_node(iid, node)
    return iid


class _WidgetPaneController:
    """Stub controller that returns a real widget from ``get_pane``."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        # The third positional arg is the parent frame supplied by
        # the debugger; capture it so the pane has a proper master.
        self._parent = _args[2] if len(_args) >= 3 else None

    def get_pane(self) -> ttk.Frame:
        return ttk.Frame(self._parent)


def test_show_font_replaces_right_component_when_pane_present(
    debugger: PDFDebugger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hit line 1142: ``get_pane()`` returns a non-None widget, so the
    debugger swaps the right pane to the encoding view."""
    monkeypatch.setattr(
        _pd_debugger, "FontEncodingPaneController", _WidgetPaneController
    )
    font_dict = COSDictionary()
    resources_dict = COSDictionary()
    font_container = COSDictionary()
    font_container.set_item(COSName.get_pdf_name("F1"), font_dict)
    resources_dict.set_item(COSName.get_pdf_name("Font"), font_container)

    grand_iid = _insert(
        debugger._tree,  # noqa: SLF001
        "",
        "Resources",
        _make_map_entry("Resources", resources_dict),
    )
    parent_iid = _insert(
        debugger._tree,  # noqa: SLF001
        grand_iid,
        "Font",
        _make_map_entry("Font", font_container),
    )
    font_node = _make_map_entry("F1", font_dict)
    iid = _insert(debugger._tree, parent_iid, "F1", font_node)  # noqa: SLF001
    debugger._show_font(font_node, iid)  # noqa: SLF001
