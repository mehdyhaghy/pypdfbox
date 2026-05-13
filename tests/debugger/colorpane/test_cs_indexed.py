"""Tests for :class:`CSIndexed`."""

from __future__ import annotations

from tkinter import ttk

from pypdfbox.cos import COSArray, COSInteger, COSName, COSString
from pypdfbox.debugger.colorpane.cs_indexed import CSIndexed
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB


def _indexed_array(hival: int, palette: bytes) -> COSArray:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(hival))
    arr.add(COSString(palette))
    return arr


def test_cs_indexed_three_color_palette_builds_panel(tk_root) -> None:
    # Palette: black, red, green — 3 colors × 3 bytes RGB.
    palette = b"\x00\x00\x00\xff\x00\x00\x00\xff\x00"
    pane = CSIndexed(_indexed_array(2, palette), master=tk_root)
    panel = pane.get_panel()
    assert isinstance(panel, ttk.Frame)
    # color_count = hival + 1.
    assert pane.color_count == 3
    # Treeview should be populated with three rows.
    tree = pane.tree
    assert tree is not None
    assert len(tree.get_children()) == 3


def test_cs_indexed_table_model_round_trip(tk_root) -> None:
    palette = b"\x00\x00\x00\xff\x00\x00"
    pane = CSIndexed(_indexed_array(1, palette), master=tk_root)
    model = pane.table_model
    assert model.get_row_count() == 2
    assert model.get_columns() == ["Index", "RGB value", "Color"]
    # Index 0 is black; index 1 is red.
    assert model.get_value_at(0, 0) == 0
    assert model.get_value_at(1, 0) == 1


def test_cs_indexed_clamps_hival_to_255(tk_root) -> None:
    # Pass hival=300 — must be clamped to 255 ⇒ color_count = 256.
    # Provide a 256-entry RGB palette so the lookup walks the
    # full table without index-out-of-range.
    palette = bytes(range(256)) * 3  # 768 bytes
    pane = CSIndexed(_indexed_array(300, palette), master=tk_root)
    assert pane.color_count == 256
