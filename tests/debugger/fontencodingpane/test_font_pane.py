"""Tests for the :class:`FontPane` abstract base."""

from __future__ import annotations

from pypdfbox.debugger.fontencodingpane.font_pane import FontPane


class _ConcreteFontPane(FontPane):
    def get_panel(self):  # pragma: no cover - never called by these tests
        raise NotImplementedError


def test_y_bounds_empty_table_returns_zero_zero():
    pane = _ConcreteFontPane()
    assert pane.get_y_bounds([], 0) == (0.0, 0.0)


def test_y_bounds_skips_string_sentinels():
    pane = _ConcreteFontPane()
    rows = [
        ["code", "name", "u", "No glyph"],
        ["code", "name", "u", ".notdef"],
        ["code", "name", "u", None],
    ]
    assert pane.get_y_bounds(rows, 3) == (0.0, 0.0)


def test_y_bounds_walks_tuple_paths():
    pane = _ConcreteFontPane()
    # Each row's path is a sequence of ("moveTo"/"lineTo"/etc, x, y) entries.
    path1 = [("moveTo", 0.0, -10.0), ("lineTo", 5.0, 20.0)]
    path2 = [("moveTo", 0.0, 15.0), ("lineTo", 5.0, 30.0)]
    rows = [
        ["c", "n", "u", path1],
        ["c", "n", "u", path2],
    ]
    lo, hi = pane.get_y_bounds(rows, 3)
    # Capped at 0 / floored at 0 mirrors upstream behaviour: minY=-10, maxY=30.
    assert lo == -10.0
    assert hi == 30.0


def test_y_bounds_ignores_glyph_index_out_of_range():
    pane = _ConcreteFontPane()
    rows = [["only-one-column"]]
    assert pane.get_y_bounds(rows, 3) == (0.0, 0.0)
