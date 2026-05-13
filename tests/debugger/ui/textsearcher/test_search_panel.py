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


def _make_panel(root: tk.Tk, rec: _Recorder) -> SearchPanel:
    return SearchPanel(
        document_listener=rec,
        change_listener=rec,
        component_listener=rec,
        next_action=lambda: None,
        previous_action=lambda: None,
        parent=root,
    )


def test_component_shown_dispatches_to_listener(tk_root: tk.Tk) -> None:
    rec = _Recorder()
    panel = _make_panel(tk_root, rec)
    # Synthesize a fake event — the listener just records the call.
    panel._on_component_shown(None)  # type: ignore[arg-type]
    panel._on_component_hidden(None)  # type: ignore[arg-type]
    assert rec.shown == 1
    assert rec.hidden == 1


def test_component_callbacks_skip_when_listener_missing_methods(
    tk_root: tk.Tk,
) -> None:
    # ``object()`` has neither ``component_shown`` nor ``component_hidden``;
    # the panel must tolerate that without raising.
    panel = SearchPanel(
        document_listener=_Recorder(),
        change_listener=_Recorder(),
        component_listener=object(),
        next_action=lambda: None,
        previous_action=lambda: None,
        parent=tk_root,
    )
    panel._on_component_shown(None)  # type: ignore[arg-type]
    panel._on_component_hidden(None)  # type: ignore[arg-type]


def test_close_action_hides_panel(tk_root: tk.Tk) -> None:
    rec = _Recorder()
    panel = _make_panel(tk_root, rec)
    panel.get_panel().pack()
    tk_root.update_idletasks()
    assert panel.get_panel().winfo_manager() == "pack"
    panel._close_action()  # type: ignore[attr-defined]
    tk_root.update_idletasks()
    # ``pack_forget`` clears the geometry manager record.
    assert panel.get_panel().winfo_manager() == ""


def test_re_focus_selects_existing_text(tk_root: tk.Tk) -> None:
    rec = _Recorder()
    panel = _make_panel(tk_root, rec)
    panel.get_panel().pack()
    panel._search_var.set("hello")  # type: ignore[attr-defined]
    rec.changed = 0
    panel.re_focus()
    tk_root.update_idletasks()
    # ``re_focus`` re-fires the document listener by re-setting the var.
    assert rec.changed >= 1
    # Search var preserved.
    assert panel.get_search_word() == "hello"


# ---------------------------------------------------------------------
# Menu plumbing (``add_menu_listeners`` / ``remove_menu_listeners``)
# ---------------------------------------------------------------------


class _StubMenuItem:
    """A duck-typed ``tk.Menu`` / menu-item stub for menu wiring tests."""

    def __init__(self) -> None:
        self.config: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        self.config.update(kwargs)


class _StubFrame:
    """A debugger-frame stub exposing the four menu accessors used by the panel."""

    def __init__(
        self,
        find_menu: _StubMenuItem | None,
        find_item: _StubMenuItem | None,
        next_item: _StubMenuItem | None,
        prev_item: _StubMenuItem | None,
    ) -> None:
        self._find_menu = find_menu
        self._find_item = find_item
        self._next_item = next_item
        self._prev_item = prev_item

    def get_find_menu(self) -> _StubMenuItem | None:
        return self._find_menu

    def get_find_menu_item(self) -> _StubMenuItem | None:
        return self._find_item

    def get_find_next_menu_item(self) -> _StubMenuItem | None:
        return self._next_item

    def get_find_previous_menu_item(self) -> _StubMenuItem | None:
        return self._prev_item


def test_add_menu_listeners_with_none_is_noop(tk_root: tk.Tk) -> None:
    rec = _Recorder()
    panel = _make_panel(tk_root, rec)
    # Must tolerate a missing frame without raising.
    panel.add_menu_listeners(None)
    panel.remove_menu_listeners(None)


def test_add_menu_listeners_configures_items(tk_root: tk.Tk) -> None:
    rec = _Recorder()
    panel = _make_panel(tk_root, rec)
    find_menu = _StubMenuItem()
    find_item = _StubMenuItem()
    next_item = _StubMenuItem()
    prev_item = _StubMenuItem()
    frame = _StubFrame(find_menu, find_item, next_item, prev_item)
    panel.add_menu_listeners(frame)

    # The menu is enabled.
    assert find_menu.config.get("state") == "normal"
    # Each item received a callable command.
    assert callable(find_item.config["command"])
    assert callable(next_item.config["command"])
    assert callable(prev_item.config["command"])

    # remove_menu_listeners() disables the menu and clears the commands.
    panel.remove_menu_listeners(frame)
    assert find_menu.config.get("state") == "disabled"
    assert find_item.config["command"] == ""
    assert next_item.config["command"] == ""
    assert prev_item.config["command"] == ""


def test_add_menu_listeners_skips_missing_items(tk_root: tk.Tk) -> None:
    rec = _Recorder()
    panel = _make_panel(tk_root, rec)
    # All accessors return None — the wiring should not raise.
    frame = _StubFrame(None, None, None, None)
    panel.add_menu_listeners(frame)
    panel.remove_menu_listeners(frame)


def test_find_action_packs_when_hidden_then_refocuses(tk_root: tk.Tk) -> None:
    rec = _Recorder()
    panel = _make_panel(tk_root, rec)
    frame = _StubFrame(
        _StubMenuItem(), _StubMenuItem(), _StubMenuItem(), _StubMenuItem()
    )
    panel.add_menu_listeners(frame)
    find_command = frame._find_item.config["command"]  # type: ignore[union-attr]
    assert callable(find_command)
    # First invocation packs the (currently un-mapped) panel.
    find_command()
    tk_root.update_idletasks()
    assert panel.get_panel().winfo_ismapped()
    # Second invocation re-focuses (and re-fires the document listener).
    rec.changed = 0
    panel._search_var.set("xyz")  # type: ignore[attr-defined]
    baseline = rec.changed
    find_command()
    tk_root.update_idletasks()
    # ``re_focus`` resets the var, which re-fires the document listener.
    assert rec.changed > baseline
