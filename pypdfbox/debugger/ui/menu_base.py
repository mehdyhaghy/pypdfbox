"""Tkinter port of ``MenuBase``.

Mirrors ``org.apache.pdfbox.debugger.ui.MenuBase``. The upstream class
wraps a Swing ``JMenu``; this port wraps a ``tk.Menu`` (configured with
``tearoff=0`` to match menubar semantics).

It also exposes two convenience helpers used by ``ZoomMenu``,
``RotationMenu`` and ``RenderDestinationMenu``:

* :py:meth:`MenuBase.add_menu` — append a simple command entry.
* :py:meth:`MenuBase.add_radio_group` — append a mutually-exclusive radio
  set sharing a single ``StringVar``.

In Swing, listeners were attached via ``ActionListener``. In Tk we model
that with a single ``command`` callable per item — but in order to mirror
upstream's *"replace any previously attached listeners"* semantics, we
keep a list of installed commands and replace them all whenever
:py:meth:`add_menu_listeners` is invoked.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any


class MenuBase:
    """Abstract base for the debugger menubar entries.

    Concrete subclasses (``ZoomMenu``, ``RotationMenu``,
    ``RenderDestinationMenu``, ``ViewMenu`` etc.) build their menu
    structure in ``__init__`` and call :py:meth:`set_menu` with the
    resulting ``tk.Menu``.
    """

    def __init__(self) -> None:
        self._menu: tk.Menu | None = None
        # Tracks the action callbacks the *user* has installed via
        # ``add_menu_listeners`` so subsequent installs cleanly replace
        # the previous set (Swing's add/removeActionListener dance).
        self._installed_listeners: list[Callable[[str], None]] = []

    # ------------------------------------------------------------------
    # Menu accessors
    # ------------------------------------------------------------------

    def set_menu(self, menu: tk.Menu) -> None:
        """Bind the underlying ``tk.Menu`` instance."""
        self._menu = menu

    def get_menu(self) -> tk.Menu:
        """Return the wrapped ``tk.Menu`` instance.

        Mirrors upstream ``getMenu()``.
        """
        if self._menu is None:
            msg = "menu has not been set"
            raise RuntimeError(msg)
        return self._menu

    def set_enable_menu(self, is_enable: bool) -> None:
        """Enable/disable the entire menu cascade.

        Mirrors upstream ``setEnableMenu``.
        """
        if self._menu is None:
            return
        state = "normal" if is_enable else "disabled"
        # ``tk.Menu`` itself has no ``state`` option; menubar cascades
        # carry the state on the *parent* entry. The closest analogue
        # for a standalone ``tk.Menu`` is to grey out every entry it
        # owns, which is what the upstream UI ultimately observes.
        last = self._menu.index("end")
        total = (last + 1) if last is not None else 0
        for index in range(total):
            try:
                self._menu.entryconfigure(index, state=state)
            except tk.TclError:  # pragma: no cover - separators etc.
                continue

    # ------------------------------------------------------------------
    # Listener wiring
    # ------------------------------------------------------------------

    def add_menu_listeners(self, listener: Callable[[str], None]) -> None:
        """Install an action callback for every entry on the menu.

        The callback receives the entry's *label* — the closest Tk
        analogue of Swing's ``ActionEvent.getActionCommand``.

        Calling this method again replaces the previously-installed
        callbacks, matching upstream's "remove all then add" behavior.
        """
        if self._menu is None:
            return
        # Forget previously installed callbacks so they don't fire twice.
        self._installed_listeners = [listener]
        last = self._menu.index("end")
        if last is None:
            return
        for index in range(last + 1):
            try:
                entry_type = self._menu.type(index)
            except tk.TclError:  # pragma: no cover - defensive
                continue
            if entry_type in {"separator", "tearoff"}:
                continue
            try:
                label = self._menu.entrycget(index, "label")
            except tk.TclError:  # pragma: no cover - defensive
                continue
            self._menu.entryconfigure(
                index,
                command=lambda value=label: listener(value),
            )

    # ------------------------------------------------------------------
    # Convenience builders shared by concrete menus
    # ------------------------------------------------------------------

    def add_menu(self, label: str, command: Callable[[], None] | None = None) -> None:
        """Append a simple command entry to the wrapped menu."""
        if self._menu is None:
            msg = "menu has not been set"
            raise RuntimeError(msg)
        self._menu.add_command(label=label, command=command or (lambda: None))

    def add_radio_group(
        self,
        items: list[str],
        current: str | None,
        on_change: Callable[[str], None] | None,
        variable: tk.StringVar | None = None,
    ) -> tk.StringVar:
        """Append a radio group sharing a single ``StringVar``.

        :param items: list of entry labels — also the values stored in
            the variable.
        :param current: initial selection (defaults to the first item).
        :param on_change: callable invoked with the new value whenever
            the selection changes.
        :param variable: optional pre-existing ``StringVar``; created on
            demand otherwise.
        :returns: the ``StringVar`` that backs the group.
        """
        if self._menu is None:
            msg = "menu has not been set"
            raise RuntimeError(msg)
        if variable is None:
            initial = current if current is not None else (items[0] if items else "")
            variable = tk.StringVar(value=initial)
        elif current is not None:
            variable.set(current)

        def _handler(value: str) -> None:
            if on_change is not None:
                on_change(value)

        for item in items:
            self._menu.add_radiobutton(
                label=item,
                value=item,
                variable=variable,
                command=lambda value=item: _handler(value),
            )
        return variable


__all__ = ["MenuBase"]


def _safely_invoke(callback: Callable[..., Any] | None, *args: Any) -> None:
    """Internal helper used by subclasses to swallow ``None`` callbacks."""
    if callback is None:
        return
    callback(*args)
