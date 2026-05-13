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


def test_get_search_panel_before_init_raises(tk_root: tk.Tk) -> None:
    text = _make_text(tk_root, "abc")
    searcher = Searcher(text)
    with pytest.raises(RuntimeError):
        searcher.get_search_panel()


def test_document_listener_aliases_route_to_search(tk_root: tk.Tk) -> None:
    text = _make_text(tk_root, "alpha beta alpha")
    searcher = Searcher(text)
    searcher.init()
    panel = searcher._search_panel  # type: ignore[attr-defined]
    panel._search_var.set("alpha")
    tk_root.update_idletasks()
    # All three document-listener methods delegate to ``_search_from_widget``.
    searcher.insert_update(None)
    searcher.remove_update(None)
    searcher.changed_update(None)
    assert searcher._total_match == 2  # type: ignore[attr-defined]


def test_search_from_widget_no_panel_is_noop(tk_root: tk.Tk) -> None:
    text = _make_text(tk_root, "anything")
    searcher = Searcher(text)
    # _search_from_widget runs before init() — must early-return silently.
    searcher._search_from_widget()  # type: ignore[attr-defined]


def test_state_changed_without_panel_is_noop(tk_root: tk.Tk) -> None:
    text = _make_text(tk_root, "noop")
    searcher = Searcher(text)
    # Pre-init: must not raise.
    searcher.state_changed(None)


def test_state_changed_runs_a_new_search(tk_root: tk.Tk) -> None:
    text = _make_text(tk_root, "Foo foo FOO")
    searcher = Searcher(text)
    searcher.init()
    panel = searcher._search_panel  # type: ignore[attr-defined]
    panel._search_var.set("foo")
    tk_root.update_idletasks()
    # Case-insensitive baseline: 3 matches.
    assert searcher._total_match == 3  # type: ignore[attr-defined]
    # Flip the case-sensitive flag — the StringVar callback doesn't fire,
    # but ``state_changed`` re-runs the search through the change listener.
    panel._case_sensitive_var.set(True)  # type: ignore[attr-defined]
    searcher.state_changed(None)
    assert searcher._total_match == 1  # type: ignore[attr-defined]


def test_regex_search_path(tk_root: tk.Tk) -> None:
    text = _make_text(tk_root, "a1 b2 c3")
    searcher = Searcher(text)
    searcher.init()
    panel = searcher._search_panel  # type: ignore[attr-defined]
    panel._regex_var.set(True)  # type: ignore[attr-defined]
    panel._search_var.set(r"[a-z]\d")
    tk_root.update_idletasks()
    assert searcher._total_match == 3  # type: ignore[attr-defined]


def test_no_match_path_updates_counter(tk_root: tk.Tk) -> None:
    text = _make_text(tk_root, "hello world")
    searcher = Searcher(text)
    searcher.init()
    panel = searcher._search_panel  # type: ignore[attr-defined]
    panel._search_var.set("zzz-not-present")
    tk_root.update_idletasks()
    assert searcher._total_match == 0  # type: ignore[attr-defined]
    # Counter label should now read "No match found".
    counter = panel._counter_var.get()  # type: ignore[attr-defined]
    assert "No match found" in counter


def test_next_action_disables_next_at_end(tk_root: tk.Tk) -> None:
    text = _make_text(tk_root, "x x")
    searcher = Searcher(text)
    searcher.init()
    panel = searcher._search_panel  # type: ignore[attr-defined]
    panel._search_var.set("x")
    tk_root.update_idletasks()
    assert searcher._total_match == 2  # type: ignore[attr-defined]
    # Walk to the last match.
    searcher._next_action()  # type: ignore[attr-defined]
    assert searcher._current_match == 1  # type: ignore[attr-defined]
    assert searcher._next_enabled is False  # type: ignore[attr-defined]
    assert searcher._previous_enabled is True  # type: ignore[attr-defined]


def test_component_shown_refocuses_panel(tk_root: tk.Tk) -> None:
    text = _make_text(tk_root, "x")
    searcher = Searcher(text)
    searcher.init()
    panel = searcher._search_panel  # type: ignore[attr-defined]
    panel.get_panel().pack()
    panel._search_var.set("x")
    tk_root.update_idletasks()
    # component_shown re-focuses the search field — exercise the code path.
    searcher.component_shown(None)
    tk_root.update_idletasks()


def test_component_hidden_clears_highlights(tk_root: tk.Tk) -> None:
    text = _make_text(tk_root, "abc abc")
    searcher = Searcher(text)
    searcher.init()
    panel = searcher._search_panel  # type: ignore[attr-defined]
    panel._search_var.set("abc")
    tk_root.update_idletasks()
    assert searcher._total_match == 2  # type: ignore[attr-defined]
    searcher.component_hidden(None)
    assert text.tag_ranges(PAINTER) == ()
    assert text.tag_ranges(SELECTION_PAINTER) == ()


class _StubMenuItem:
    def __init__(self) -> None:
        self.config: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        self.config.update(kwargs)


class _StubFrame:
    def __init__(self) -> None:
        self._find_menu = _StubMenuItem()
        self._find_item = _StubMenuItem()
        self._next_item = _StubMenuItem()
        self._prev_item = _StubMenuItem()

    def get_find_menu(self) -> _StubMenuItem:
        return self._find_menu

    def get_find_menu_item(self) -> _StubMenuItem:
        return self._find_item

    def get_find_next_menu_item(self) -> _StubMenuItem:
        return self._next_item

    def get_find_previous_menu_item(self) -> _StubMenuItem:
        return self._prev_item


def test_menu_listeners_delegate_to_panel(tk_root: tk.Tk) -> None:
    text = _make_text(tk_root, "abc")
    searcher = Searcher(text)
    searcher.init()
    frame = _StubFrame()
    searcher.add_menu_listeners(frame)
    assert frame._find_menu.config.get("state") == "normal"
    searcher.remove_menu_listeners(frame)
    assert frame._find_menu.config.get("state") == "disabled"


def test_menu_listeners_without_init_are_noops(tk_root: tk.Tk) -> None:
    text = _make_text(tk_root, "abc")
    searcher = Searcher(text)
    # Calling before init() must short-circuit silently.
    searcher.add_menu_listeners(_StubFrame())
    searcher.remove_menu_listeners(_StubFrame())
