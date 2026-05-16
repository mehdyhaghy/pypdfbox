"""Hand-written coverage for :class:`PDFDebugger`'s menu-builder methods.

Mirrors the upstream JUnit smoke checks for ``createFileMenu`` /
``createEditMenu`` / ``createFindMenu`` / ``addRecentFileItems``; the
upstream tests inspect the resulting ``JMenu`` widget's child count and
labels, which translates cleanly to ``tk.Menu.index("end")`` here.

``PYPDFBOX_SKIP_TK=1`` opt-out matches the fixture pattern used in
``test_pd_debugger.py``.
"""

from __future__ import annotations

import contextlib
import os
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path

import pytest

from pypdfbox.debugger.pd_debugger import PDFDebugger
from pypdfbox.debugger.ui.tree_view_menu import TreeViewMenu
from pypdfbox.debugger.ui.view_menu import ViewMenu


@pytest.fixture()
def tk_root() -> Iterator[tk.Tk]:
    """Per-test Tk root with menu singletons reset around the test."""
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


def _reset_menu_singletons() -> None:
    """Drop every cached menu singleton so each test starts fresh."""
    from pypdfbox.debugger.ui.image_type_menu import ImageTypeMenu
    from pypdfbox.debugger.ui.render_destination_menu import RenderDestinationMenu
    from pypdfbox.debugger.ui.rotation_menu import RotationMenu
    from pypdfbox.debugger.ui.text_stripper_menu import TextStripperMenu
    from pypdfbox.debugger.ui.zoom_menu import ZoomMenu

    ViewMenu._reset_instance()  # noqa: SLF001
    ZoomMenu._reset_instance()  # noqa: SLF001
    RotationMenu._reset_instance()  # noqa: SLF001
    RenderDestinationMenu._reset_instance()  # noqa: SLF001
    TreeViewMenu._reset_for_testing()  # noqa: SLF001
    ImageTypeMenu._reset_for_testing()  # noqa: SLF001
    TextStripperMenu._reset_for_testing()  # noqa: SLF001


@pytest.fixture()
def debugger(tk_root: tk.Tk) -> Iterator[PDFDebugger]:
    """Per-test :class:`PDFDebugger` rooted at the session :class:`tk.Tk`."""
    dbg = PDFDebugger(tk_root)
    try:
        yield dbg
    finally:
        with contextlib.suppress(tk.TclError):
            dbg._main_frame.destroy()  # noqa: SLF001


# ----------------------------------------------------------------------
# create_file_menu
# ----------------------------------------------------------------------


def test_create_file_menu_returns_menu(debugger: PDFDebugger) -> None:
    parent = tk.Menu(debugger._toplevel)  # noqa: SLF001
    menu = debugger.create_file_menu(parent)
    assert isinstance(menu, tk.Menu)
    # Upstream entries on a non-macOS layout:
    #   Open..., Open URL..., Reopen, Open Recent (cascade), Save as...,
    #   Save Decoded Stream..., Save Raw Stream..., (sep), Print, (sep),
    #   Exit
    # On macOS the Exit + trailing separator are dropped (the system
    # quit menu handles it). The lower bound is 9 entries (mac), upper
    # bound 11 (non-mac).
    last = menu.index("end")
    assert last is not None
    assert last >= 8


def test_create_file_menu_has_open_label(debugger: PDFDebugger) -> None:
    parent = tk.Menu(debugger._toplevel)  # noqa: SLF001
    menu = debugger.create_file_menu(parent)
    assert menu.entrycget(0, "label") == "Open..."


# ----------------------------------------------------------------------
# create_edit_menu
# ----------------------------------------------------------------------


def test_create_edit_menu_returns_menu(debugger: PDFDebugger) -> None:
    parent = tk.Menu(debugger._toplevel)  # noqa: SLF001
    menu = debugger.create_edit_menu(parent)
    assert isinstance(menu, tk.Menu)
    # Cut, Copy, Paste, Delete, sep, Copy Tree Path, sep, Find cascade
    last = menu.index("end")
    assert last is not None
    assert last == 7
    # Verify entries by label (separators throw TclError on entrycget).
    labels: list[str] = []
    for i in range(last + 1):
        with contextlib.suppress(tk.TclError):
            labels.append(menu.entrycget(i, "label"))
    for expected in ("Cut", "Copy", "Paste", "Delete", "Copy Tree Path", "Find"):
        assert expected in labels


# ----------------------------------------------------------------------
# create_find_menu
# ----------------------------------------------------------------------


def test_create_find_menu_three_entries(debugger: PDFDebugger) -> None:
    parent = tk.Menu(debugger._toplevel)  # noqa: SLF001
    menu = debugger.create_find_menu(parent)
    assert isinstance(menu, tk.Menu)
    # Find..., Find Next, Find Previous
    assert menu.index("end") == 2
    labels = [menu.entrycget(i, "label") for i in range(3)]
    assert labels == ["Find...", "Find Next", "Find Previous"]


# ----------------------------------------------------------------------
# create_view_menu
# ----------------------------------------------------------------------


def test_create_view_menu_returns_tk_menu(debugger: PDFDebugger) -> None:
    parent = tk.Menu(debugger._toplevel)  # noqa: SLF001
    menu = debugger.create_view_menu(parent)
    assert isinstance(menu, tk.Menu)
    # ViewMenu wires its own children (Tree View, Zoom, Rotation, etc.);
    # the exact count is governed by ViewMenu and not under test here.
    # Just verify at least one entry was attached.
    last = menu.index("end")
    assert last is not None
    assert last >= 0


# ----------------------------------------------------------------------
# create_window_menu
# ----------------------------------------------------------------------


def test_create_window_menu_returns_empty_menu(debugger: PDFDebugger) -> None:
    parent = tk.Menu(debugger._toplevel)  # noqa: SLF001
    menu = debugger.create_window_menu(parent)
    assert isinstance(menu, tk.Menu)
    # Upstream Swing has no Window menu; pypdfbox keeps a stub cascade.
    assert menu.index("end") is None


# ----------------------------------------------------------------------
# create_help_menu
# ----------------------------------------------------------------------


def test_create_help_menu_has_about(debugger: PDFDebugger) -> None:
    parent = tk.Menu(debugger._toplevel)  # noqa: SLF001
    menu = debugger.create_help_menu(parent)
    assert isinstance(menu, tk.Menu)
    assert menu.index("end") == 0
    assert menu.entrycget(0, "label") == "About PDFBox"


# ----------------------------------------------------------------------
# add_recent_file_items
# ----------------------------------------------------------------------


def test_add_recent_file_items_in_mru_order(
    debugger: PDFDebugger, tmp_path: Path
) -> None:
    # Reset on-disk recent-files state so this test is deterministic.
    debugger._recent_files.remove_all()  # noqa: SLF001
    assert debugger._recent_files_menu is not None  # noqa: SLF001
    debugger._recent_files_menu.delete(0, "end")  # noqa: SLF001

    # Three real files so RecentFiles.get_files() doesn't drop them.
    paths = []
    for i in range(3):
        path = tmp_path / f"sample-{i}.pdf"
        path.write_bytes(b"%PDF-1.4\n%%EOF\n")
        paths.append(str(path))
        debugger._recent_files.add_file(str(path))  # noqa: SLF001

    debugger.add_recent_file_items()

    menu = debugger._recent_files_menu  # noqa: SLF001
    last = menu.index("end")
    assert last == 2
    # Java iterates ``size() - 1`` downwards, so the most recently-added
    # file is at index 0 in the resulting menu.
    labels = [menu.entrycget(i, "label") for i in range(3)]
    assert labels == [Path(paths[2]).name, Path(paths[1]).name, Path(paths[0]).name]


def test_add_recent_file_items_empty_history(debugger: PDFDebugger) -> None:
    # Ensure history starts empty and the cascade is wiped.
    debugger._recent_files.remove_all()  # noqa: SLF001
    assert debugger._recent_files_menu is not None  # noqa: SLF001
    debugger._recent_files_menu.delete(0, "end")  # noqa: SLF001

    debugger.add_recent_file_items()
    # Upstream's ``addRecentFileItems`` early-returns on an empty
    # history without touching the cascade — so the menu stays empty.
    assert debugger._recent_files_menu.index("end") is None  # noqa: SLF001


def test_add_recent_file_items_preserves_menu_when_history_empty(
    debugger: PDFDebugger, tmp_path: Path
) -> None:
    # Seed one item, populate, then clear the history and re-populate.
    debugger._recent_files.remove_all()  # noqa: SLF001
    assert debugger._recent_files_menu is not None  # noqa: SLF001
    debugger._recent_files_menu.delete(0, "end")  # noqa: SLF001
    path = tmp_path / "sample.pdf"
    path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    debugger._recent_files.add_file(str(path))  # noqa: SLF001
    debugger.add_recent_file_items()
    assert debugger._recent_files_menu.index("end") == 0  # noqa: SLF001
    # Upstream's ``addRecentFileItems`` is a no-op when the history is
    # empty (it does NOT wipe the cascade); the cascade therefore
    # retains its prior contents. Mirror that behaviour faithfully.
    debugger._recent_files.remove_all()  # noqa: SLF001
    debugger.add_recent_file_items()
    assert debugger._recent_files_menu.index("end") == 0  # noqa: SLF001
