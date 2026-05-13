"""Tests for :class:`ColorBarCellRenderer`."""

from __future__ import annotations

import tkinter as tk

from pypdfbox.debugger.colorpane.color_bar_cell_renderer import (
    ColorBarCellRenderer,
)


def test_to_hex_quantises_to_byte_range() -> None:
    assert ColorBarCellRenderer.to_hex((0.0, 0.0, 0.0)) == "#000000"
    assert ColorBarCellRenderer.to_hex((1.0, 1.0, 1.0)) == "#FFFFFF"
    assert ColorBarCellRenderer.to_hex((1.0, 0.5, 0.0)) == "#FF8000"


def test_to_hex_none_maps_to_white() -> None:
    assert ColorBarCellRenderer.to_hex(None) == "#FFFFFF"


def test_to_hex_clamps_out_of_range_inputs() -> None:
    assert ColorBarCellRenderer.to_hex((2.0, -1.0, 0.5)) == "#FF0080"


def test_render_swatch_creates_canvas_with_background(tk_root) -> None:
    renderer = ColorBarCellRenderer()
    canvas = renderer.render_swatch(tk_root, (1.0, 0.0, 0.0))
    assert isinstance(canvas, tk.Canvas)
    # Canvas background reflects the requested color (hex form).
    assert canvas.cget("background").upper() in ("#FF0000", "RED")


def test_get_table_cell_renderer_component_returns_canvas(tk_root) -> None:
    renderer = ColorBarCellRenderer()
    canvas = renderer.get_table_cell_renderer_component(
        tk_root, (0.0, 1.0, 0.0)
    )
    assert isinstance(canvas, tk.Canvas)
    # Background should encode the green color.
    assert canvas.cget("background").upper() in ("#00FF00", "GREEN")
