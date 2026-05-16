"""Tests for the promoted ``ASCIIPane.paint_component`` / ``paint_in_selected``.

The upstream Swing class uses ``paintComponent`` and ``paintInSelected`` to
render each line and to highlight the selected character. We exposed these
two methods publicly; the previous ``_render`` private alias is preserved
for back-compat.
"""

from __future__ import annotations

from pypdfbox.debugger.hexviewer.ascii_pane import ASCIIPane
from pypdfbox.debugger.hexviewer.hex_model import HexModel


def test_paint_component_renders_every_line(tk_root) -> None:
    model = HexModel(b"ABCD" + bytes(range(20)))
    pane = ASCIIPane(tk_root, model)
    pane.paint_component()
    # Two lines (16 bytes + 8) -> at least the first line is visible.
    content = pane.get("1.0", "end-1c")
    assert "ABCD" in content


def test_paint_in_selected_highlights_byte(tk_root) -> None:
    model = HexModel(b"hello world!!!!!")  # 16 bytes = one full line
    pane = ASCIIPane(tk_root, model)
    pane.set_selected(2)  # the second 'l'
    # ``selected`` tag has been applied to exactly one character span.
    ranges = pane.tag_ranges("selected")
    assert len(ranges) == 2  # one (start, end) pair


def test_paint_in_selected_clears_when_no_selection(tk_root) -> None:
    model = HexModel(b"abcdefghij")
    pane = ASCIIPane(tk_root, model)
    # Default state: no selection => no highlighted span.
    ranges = pane.tag_ranges("selected")
    assert len(ranges) == 0


def test_render_alias_still_works(tk_root) -> None:
    """The original private ``_render`` is preserved as an alias."""
    model = HexModel(b"xy")
    pane = ASCIIPane(tk_root, model)
    pane._render()  # noqa: SLF001
    assert "xy" in pane.get("1.0", "end-1c")
