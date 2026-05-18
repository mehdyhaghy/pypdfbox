"""Wave 1351 coverage-boost tests for :class:`ZoomMenu`.

Targets the two ``raise RuntimeError`` branches in
:meth:`ZoomMenu.get_zoom_scale` — the ``_instance is None`` guard
(lines 113-114) and the empty / malformed selection guard
(lines 117-118), both mirroring upstream's ``IllegalStateException``.
"""

from __future__ import annotations

import tkinter as tk

import pytest

from pypdfbox.debugger.ui.zoom_menu import ZoomMenu


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    ZoomMenu._reset_instance()
    yield
    ZoomMenu._reset_instance()


def test_get_zoom_scale_without_instance_raises() -> None:
    """No ``get_instance`` call has been made → singleton is ``None``."""
    with pytest.raises(RuntimeError, match="no zoom menu item is selected"):
        ZoomMenu.get_zoom_scale()


def test_get_zoom_scale_with_empty_selection_raises(tk_root: tk.Tk) -> None:
    """An empty ``_zoom_var`` string also raises - mirrors upstream's
    ``IllegalStateException`` for the unselected case."""
    menu = ZoomMenu.get_instance(master=tk_root)
    menu._zoom_var.set("")
    with pytest.raises(RuntimeError, match="no zoom menu item is selected"):
        ZoomMenu.get_zoom_scale()


def test_get_zoom_scale_with_malformed_selection_raises(tk_root: tk.Tk) -> None:
    """A selection that does not end with ``%`` is treated as
    unselected, matching upstream's parser guard."""
    menu = ZoomMenu.get_instance(master=tk_root)
    menu._zoom_var.set("garbage")
    with pytest.raises(RuntimeError, match="no zoom menu item is selected"):
        ZoomMenu.get_zoom_scale()
