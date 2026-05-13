"""Tests for the :class:`FlagBitsPaneView` Tkinter widget."""

from __future__ import annotations

from pypdfbox.debugger.flagbitspane.flag_bits_pane_view import FlagBitsPaneView


def test_view_with_no_flag_value_does_not_populate(tk_root):
    view = FlagBitsPaneView(
        tk_root, "header", None, None, ["Bit Position", "Name", "Set"]
    )
    assert view.tree is None
    assert view.get_panel() is view


def test_view_populates_treeview(tk_root):
    rows = [
        [1, "ReadOnly", True],
        [2, "Required", False],
    ]
    view = FlagBitsPaneView(
        tk_root,
        "Field flag",
        "Flag value: 1",
        rows,
        ["Bit Position", "Name", "Set"],
    )
    tree = view.tree
    assert tree is not None
    children = tree.get_children()
    assert len(children) == 2

    # First row: bit position 1, ReadOnly, True
    first = tree.item(children[0])
    assert first["text"] == "1"
    assert [str(v) for v in first["values"]] == ["ReadOnly", "True"]


def test_view_handles_four_column_panose(tk_root):
    rows = [
        [2, "Family Kind", 2, "Latin Text"],
        [3, "Serif Style", 0, "Any"],
    ]
    view = FlagBitsPaneView(
        tk_root,
        "Panose classification",
        "Panose byte :<...>",
        rows,
        ["Byte Position", "Name", "Byte Value", "Value"],
    )
    tree = view.tree
    assert tree is not None
    children = tree.get_children()
    assert len(children) == 2
    first = tree.item(children[0])
    assert first["text"] == "2"
    # Tkinter's Treeview auto-converts decimal-string values to int when
    # round-tripped through ``item()``. Normalize before comparison.
    assert [str(v) for v in first["values"]] == [
        "Family Kind",
        "2",
        "Latin Text",
    ]
