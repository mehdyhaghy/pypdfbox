"""Tkinter port of ``SearchPanel``.

The panel hosts the search entry, the match counter, the prev/next
buttons and the *Match case* / *Regex* check-boxes. Event wiring is
delegated to its owning :class:`Searcher` via the listener objects passed
into the constructor — the Swing equivalents of ``DocumentListener``,
``ChangeListener`` and ``ComponentListener``.

The *Regex* check-box is a project-level extension over upstream (see
``CHANGES.md``).
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any


class SearchPanel:
    """A search bar with prev/next, match-case and regex toggles."""

    def __init__(
        self,
        document_listener: Any,
        change_listener: Any,
        component_listener: Any,
        next_action: Callable[[], None],
        previous_action: Callable[[], None],
        parent: tk.Misc | None = None,
    ) -> None:
        """Build the search panel.

        :param document_listener: object exposing ``insert_update`` /
            ``remove_update`` / ``changed_update`` callbacks.
        :param change_listener: object exposing ``state_changed``.
        :param component_listener: object exposing ``component_shown`` /
            ``component_hidden``.
        :param next_action: callable invoked when the user activates "Next".
        :param previous_action: callable invoked for "Previous".
        :param parent: optional parent widget; when ``None`` a hidden root
            window is implicitly created by Tk.
        """
        self._document_listener = document_listener
        self._change_listener = change_listener
        self._component_listener = component_listener
        self._next_action = next_action
        self._previous_action = previous_action

        self._search_var = tk.StringVar()
        self._case_sensitive_var = tk.BooleanVar(value=False)
        self._regex_var = tk.BooleanVar(value=False)
        self._counter_var = tk.StringVar(value="")

        self._panel = ttk.Frame(parent)
        self._init_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        self._search_field = ttk.Entry(self._panel, textvariable=self._search_var)
        self._counter_label = ttk.Label(self._panel, textvariable=self._counter_var)
        self._previous_button = ttk.Button(
            self._panel, text="Previous", command=self._previous_action
        )
        self._next_button = ttk.Button(
            self._panel, text="Next", command=self._next_action
        )
        self._case_sensitive = ttk.Checkbutton(
            self._panel,
            text="Match case",
            variable=self._case_sensitive_var,
            command=self._on_state_change,
        )
        self._regex_checkbox = ttk.Checkbutton(
            self._panel,
            text="Regex",
            variable=self._regex_var,
            command=self._on_state_change,
        )
        self._cross_button = ttk.Button(
            self._panel, text="Done", command=self._close_action
        )

        # Layout — packed horizontally to match Swing's BoxLayout(X_AXIS).
        self._search_field.pack(side="left", fill="x", expand=True, padx=2)
        self._counter_label.pack(side="left", padx=2)
        self._previous_button.pack(side="left", padx=2)
        self._next_button.pack(side="left", padx=2)
        self._case_sensitive.pack(side="left", padx=2)
        self._regex_checkbox.pack(side="left", padx=2)
        self._cross_button.pack(side="left", padx=(5, 2))

        # Document-listener wiring: a ``StringVar`` trace fires on any
        # update, mirroring insert/remove/changed updates from Swing.
        self._search_var.trace_add("write", self._on_document_event)

        # Component listener wiring — Tk's <<Visibility>> doesn't quite map
        # one-to-one, but <Map>/<Unmap> match componentShown/componentHidden.
        self._panel.bind("<Map>", self._on_component_shown, add="+")
        self._panel.bind("<Unmap>", self._on_component_hidden, add="+")

        # Esc inside the search field closes the panel (upstream KeyEvent).
        self._search_field.bind("<Escape>", lambda _e: self._close_action())

        # Counter starts hidden until update_counter_label() is called.
        self._counter_label.pack_forget()
        self._counter_visible = False

    # ------------------------------------------------------------------
    # Listener dispatch helpers
    # ------------------------------------------------------------------

    def _on_document_event(self, *_args: Any) -> None:
        # ``trace_add("write")`` cannot distinguish insert/remove/change, so
        # we route every change through changed_update — the upstream
        # ``Searcher`` does the same work for all three callbacks anyway.
        if hasattr(self._document_listener, "changed_update"):
            self._document_listener.changed_update(None)

    def _on_state_change(self) -> None:
        if hasattr(self._change_listener, "state_changed"):
            self._change_listener.state_changed(None)

    def _on_component_shown(self, _event: tk.Event[Any]) -> None:
        if hasattr(self._component_listener, "component_shown"):
            self._component_listener.component_shown(_event)

    def _on_component_hidden(self, _event: tk.Event[Any]) -> None:
        if hasattr(self._component_listener, "component_hidden"):
            self._component_listener.component_hidden(_event)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _close_action(self) -> None:
        self._panel.pack_forget()

    # ------------------------------------------------------------------
    # Public API mirrored from upstream
    # ------------------------------------------------------------------

    def is_case_sensitive(self) -> bool:
        return bool(self._case_sensitive_var.get())

    def is_regex(self) -> bool:
        """Project extension — returns the *Regex* checkbox state."""
        return bool(self._regex_var.get())

    def get_search_word(self) -> str:
        return self._search_var.get()

    def reset(self) -> None:
        if self._counter_visible:
            self._counter_label.pack_forget()
            self._counter_visible = False
        self._counter_var.set("")

    def update_counter_label(self, now: int, total: int) -> None:
        if not self._counter_visible:
            self._counter_label.pack(side="left", padx=2, before=self._previous_button)
            self._counter_visible = True
        if total == 0:
            self._counter_var.set(" No match found ")
            self.set_next_enabled(False)
            return
        self._counter_var.set(f" {now} of {total} ")

    def get_panel(self) -> ttk.Frame:
        return self._panel

    def re_focus(self) -> None:
        self._search_field.focus_set()
        text = self._search_var.get()
        # Re-select the whole search key, mirroring the upstream behavior.
        self._search_field.icursor("end")
        self._search_field.select_range(0, "end")
        # Setting the variable again is the upstream's way of forcing a
        # re-fire of any document listeners — we do the same here.
        self._search_var.set(text)

    # ------------------------------------------------------------------
    # Enable/disable wiring for the surrounding Searcher
    # ------------------------------------------------------------------

    def set_next_enabled(self, enabled: bool) -> None:
        self._next_button.state(["!disabled"] if enabled else ["disabled"])

    def set_previous_enabled(self, enabled: bool) -> None:
        self._previous_button.state(["!disabled"] if enabled else ["disabled"])

    # ------------------------------------------------------------------
    # Menu plumbing
    # ------------------------------------------------------------------

    def add_menu_listeners(self, frame: Any) -> None:
        """Wire the panel into a debugger frame's *Find* menu.

        The shape of ``frame`` mirrors the upstream ``PDFDebugger`` —
        a duck-typed object exposing ``get_find_menu``,
        ``get_find_menu_item``, ``get_find_next_menu_item`` and
        ``get_find_previous_menu_item``. Each menu item is expected to
        expose ``configure(command=...)``.
        """
        if frame is None:
            return
        find_menu = getattr(frame, "get_find_menu", lambda: None)()
        if find_menu is not None and hasattr(find_menu, "configure"):
            with contextlib.suppress(tk.TclError):  # pragma: no cover
                find_menu.configure(state="normal")
        for accessor, command in (
            ("get_find_menu_item", self._find_action),
            ("get_find_next_menu_item", self._next_action),
            ("get_find_previous_menu_item", self._previous_action),
        ):
            item = getattr(frame, accessor, lambda: None)()
            if item is not None and hasattr(item, "configure"):
                item.configure(command=command)

    def remove_menu_listeners(self, frame: Any) -> None:
        if frame is None:
            return
        find_menu = getattr(frame, "get_find_menu", lambda: None)()
        if find_menu is not None and hasattr(find_menu, "configure"):
            with contextlib.suppress(tk.TclError):  # pragma: no cover
                find_menu.configure(state="disabled")
        for accessor in (
            "get_find_menu_item",
            "get_find_next_menu_item",
            "get_find_previous_menu_item",
        ):
            item = getattr(frame, accessor, lambda: None)()
            if item is not None and hasattr(item, "configure"):
                item.configure(command="")

    def _find_action(self) -> None:
        # Toggle visibility: pack if hidden, re-focus otherwise.
        if not self._panel.winfo_ismapped():
            self._panel.pack(fill="x")
        else:
            self.re_focus()
