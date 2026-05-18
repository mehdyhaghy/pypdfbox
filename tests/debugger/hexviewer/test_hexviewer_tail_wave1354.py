"""Wave 1354 tail-sweep for the debugger hexviewer subpackage.

Covers four short branches that the existing test files miss:

* ``AddressPane.set_selected`` early-return when the index does not
  change (line 56 in ``address_pane.py``).
* ``ASCIIPane.hex_model_changed`` listener fan-out (line 54 in
  ``ascii_pane.py``).
* ``HexEditor`` jump-dialog commit with empty input (line 194 in
  ``hex_editor.py``).
* ``HexModel(None)`` empty-data branch (line 26 in ``hex_model.py``).
"""

from __future__ import annotations

import contextlib
import tkinter as tk

from pypdfbox.debugger.hexviewer.address_pane import AddressPane
from pypdfbox.debugger.hexviewer.ascii_pane import ASCIIPane
from pypdfbox.debugger.hexviewer.hex_editor import HexEditor
from pypdfbox.debugger.hexviewer.hex_model import HexModel
from pypdfbox.debugger.hexviewer.hex_model_changed_event import HexModelChangedEvent


def test_address_pane_set_selected_same_index_is_noop(tk_root: tk.Tk) -> None:
    pane = AddressPane(tk_root, total=3)
    pane.set_selected(5)
    # Calling again with the same index hits the early-return branch.
    pane.set_selected(5)
    ranges = pane.tag_ranges("selected")
    assert ranges  # selection still present


def test_ascii_pane_hex_model_changed_repaints(tk_root: tk.Tk) -> None:
    model = HexModel(bytes(range(16)))
    pane = ASCIIPane(tk_root, model)
    # Fire the listener directly to cover line 54.
    pane.hex_model_changed(HexModelChangedEvent(0, HexModelChangedEvent.BULK_CHANGE))
    body = pane.get("1.0", "end-1c")
    assert body  # repaint produced text


def test_hex_editor_jump_dialog_empty_input_is_ignored(tk_root: tk.Tk) -> None:
    model = HexModel(bytes(range(8)))
    editor = HexEditor(tk_root, model)
    dialog = editor.create_jump_dialog()
    try:
        commit = dialog._pypdfbox_commit  # type: ignore[attr-defined]
        # Entry left blank — ``commit`` must early-return without raising.
        commit()
        assert dialog.winfo_exists()
    finally:
        with contextlib.suppress(tk.TclError):
            dialog.destroy()


def test_hex_model_none_input_yields_empty_data() -> None:
    model = HexModel(None)
    assert model.size() == 0
