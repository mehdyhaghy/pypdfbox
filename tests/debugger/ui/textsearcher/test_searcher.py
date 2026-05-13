"""Hand-written tests for :class:`Searcher`.

The class wires a Tk ``Text`` widget to a :class:`SearchPanel`; we need a
live Tk root, so the tests skip when no display is available.
"""

from __future__ import annotations

import tkinter as tk

import pytest

from pypdfbox.debugger.ui.textsearcher.searcher import (
    PAINTER,
    SELECTION_PAINTER,
    Searcher,
)


@pytest.fixture
def tk_root() -> tk.Tk:
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover
        pytest.skip(f"Tk display unavailable: {exc}")
    try:
        yield root
    finally:
        root.destroy()


def _make_text(root: tk.Tk, body: str) -> tk.Text:
    widget = tk.Text(root)
    widget.insert("1.0", body)
    widget.tag_configure(PAINTER)
    widget.tag_configure(SELECTION_PAINTER)
    return widget


def test_init_builds_search_panel(tk_root: tk.Tk) -> None:
    text = _make_text(tk_root, "one two three")
    searcher = Searcher(text)
    searcher.init()
    panel = searcher.get_search_panel()
    assert isinstance(panel, tk.Widget)


def test_search_finds_three_occurrences(tk_root: tk.Tk) -> None:
    text = _make_text(tk_root, "foo bar foo baz foo")
    searcher = Searcher(text)
    searcher.init()
    panel = searcher._search_panel  # type: ignore[attr-defined]
    panel._search_var.set("foo")
    # Allow the StringVar trace to dispatch synchronously.
    tk_root.update_idletasks()
    assert searcher._total_match == 3  # type: ignore[attr-defined]
    assert searcher._current_match == 0  # type: ignore[attr-defined]
    # Match #0 should now carry the selection painter.
    assert searcher._highlights[0].painter == SELECTION_PAINTER  # type: ignore[attr-defined]
    assert searcher._highlights[1].painter == PAINTER  # type: ignore[attr-defined]


def test_next_and_previous_navigation(tk_root: tk.Tk) -> None:
    text = _make_text(tk_root, "x x x x")
    searcher = Searcher(text)
    searcher.init()
    panel = searcher._search_panel  # type: ignore[attr-defined]
    panel._search_var.set("x")
    tk_root.update_idletasks()
    assert searcher._current_match == 0  # type: ignore[attr-defined]

    searcher._next_action()
    assert searcher._current_match == 1  # type: ignore[attr-defined]
    searcher._next_action()
    assert searcher._current_match == 2  # type: ignore[attr-defined]
    searcher._previous_action()
    assert searcher._current_match == 1  # type: ignore[attr-defined]


def test_clearing_search_resets(tk_root: tk.Tk) -> None:
    text = _make_text(tk_root, "abc abc")
    searcher = Searcher(text)
    searcher.init()
    panel = searcher._search_panel  # type: ignore[attr-defined]
    panel._search_var.set("abc")
    tk_root.update_idletasks()
    assert searcher._total_match == 2  # type: ignore[attr-defined]

    panel._search_var.set("")
    tk_root.update_idletasks()
    # No highlights should remain.
    ranges_match = text.tag_ranges(PAINTER)
    ranges_sel = text.tag_ranges(SELECTION_PAINTER)
    assert ranges_match == ()
    assert ranges_sel == ()
