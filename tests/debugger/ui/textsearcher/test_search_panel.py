"""Hand-written tests for :class:`SearchPanel`.

The panel relies on a live Tk root; tests skip cleanly when a display is
unavailable.
"""

from __future__ import annotations

import tkinter as tk

import pytest

from pypdfbox.debugger.ui.textsearcher.search_panel import SearchPanel


class _Recorder:
    """Tiny stub object capturing every listener callback."""

    def __init__(self) -> None:
        self.changed = 0
        self.state_changed_count = 0
        self.shown = 0
        self.hidden = 0

    def insert_update(self, _e: object = None) -> None:  # pragma: no cover
        self.changed += 1

    def remove_update(self, _e: object = None) -> None:  # pragma: no cover
        self.changed += 1

    def changed_update(self, _e: object = None) -> None:
        self.changed += 1

    def state_changed(self, _e: object = None) -> None:
        self.state_changed_count += 1

    def component_shown(self, _e: object = None) -> None:
        self.shown += 1

    def component_hidden(self, _e: object = None) -> None:
        self.hidden += 1


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


def test_panel_initial_state(tk_root: tk.Tk) -> None:
    rec = _Recorder()
    next_calls: list[int] = []
    prev_calls: list[int] = []
    panel = SearchPanel(
        document_listener=rec,
        change_listener=rec,
        component_listener=rec,
        next_action=lambda: next_calls.append(1),
        previous_action=lambda: prev_calls.append(1),
        parent=tk_root,
    )
    assert panel.is_case_sensitive() is False
    assert panel.is_regex() is False
    assert panel.get_search_word() == ""
    assert isinstance(panel.get_panel(), tk.Widget)


def test_document_listener_fires_on_typing(tk_root: tk.Tk) -> None:
    rec = _Recorder()
    panel = SearchPanel(
        document_listener=rec,
        change_listener=rec,
        component_listener=rec,
        next_action=lambda: None,
        previous_action=lambda: None,
        parent=tk_root,
    )
    panel._search_var.set("abc")  # type: ignore[attr-defined]
    assert rec.changed >= 1
    assert panel.get_search_word() == "abc"


def test_state_change_on_checkbox(tk_root: tk.Tk) -> None:
    rec = _Recorder()
    panel = SearchPanel(
        document_listener=rec,
        change_listener=rec,
        component_listener=rec,
        next_action=lambda: None,
        previous_action=lambda: None,
        parent=tk_root,
    )
    panel._case_sensitive_var.set(True)  # type: ignore[attr-defined]
    panel._on_state_change()  # invoke the checkbutton callback explicitly
    assert rec.state_changed_count == 1
    assert panel.is_case_sensitive() is True


def test_update_counter_label_text(tk_root: tk.Tk) -> None:
    rec = _Recorder()
    panel = SearchPanel(
        document_listener=rec,
        change_listener=rec,
        component_listener=rec,
        next_action=lambda: None,
        previous_action=lambda: None,
        parent=tk_root,
    )
    panel.update_counter_label(2, 5)
    assert panel._counter_var.get() == " 2 of 5 "  # type: ignore[attr-defined]
    panel.update_counter_label(0, 0)
    assert panel._counter_var.get() == " No match found "  # type: ignore[attr-defined]


def test_set_button_enabled_state(tk_root: tk.Tk) -> None:
    panel = SearchPanel(
        document_listener=_Recorder(),
        change_listener=_Recorder(),
        component_listener=_Recorder(),
        next_action=lambda: None,
        previous_action=lambda: None,
        parent=tk_root,
    )
    panel.set_next_enabled(False)
    panel.set_previous_enabled(False)
    assert "disabled" in panel._next_button.state()  # type: ignore[attr-defined]
    assert "disabled" in panel._previous_button.state()  # type: ignore[attr-defined]
    panel.set_next_enabled(True)
    panel.set_previous_enabled(True)
    assert "disabled" not in panel._next_button.state()  # type: ignore[attr-defined]
    assert "disabled" not in panel._previous_button.state()  # type: ignore[attr-defined]
