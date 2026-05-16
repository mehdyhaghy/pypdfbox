"""Tk radio-group menu for picking the debugger's tree-view style.

Ported from ``org.apache.pdfbox.debugger.ui.TreeViewMenu``. Upstream offers
three views — page-oriented, internal-structure, and cross-reference table.
Selection is exposed via ``get_tree_view_selection`` / ``set_tree_view_selection``.
"""

from __future__ import annotations

from typing import ClassVar

from .menu_base import MenuBase

try:  # pragma: no cover - tkinter is stdlib but might be missing in slim images.
    import tkinter as tk
except ImportError:  # pragma: no cover
    tk = None  # type: ignore[assignment]


class TreeViewMenu(MenuBase):
    """Singleton menubar entry for picking the debugger's tree view."""

    VIEW_PAGES: ClassVar[str] = "Show pages"
    VIEW_STRUCTURE: ClassVar[str] = "Internal structure"
    VIEW_CROSS_REF_TABLE: ClassVar[str] = "Cross reference table"

    _VALID_MODES: ClassVar[tuple[str, ...]] = (
        VIEW_PAGES,
        VIEW_STRUCTURE,
        VIEW_CROSS_REF_TABLE,
    )

    _instance: ClassVar[TreeViewMenu | None] = None

    def __init__(self, master: tk.Misc | None = None) -> None:  # type: ignore[name-defined]
        super().__init__()
        if tk is None:  # pragma: no cover - defensive
            msg = "tkinter is not available"
            raise RuntimeError(msg)
        self._master = master
        self.set_menu(self.create_tree_view_menu())

    def create_tree_view_menu(self) -> tk.Menu:  # type: ignore[name-defined]
        """Build and return the tree-view radio-group menu.

        Mirrors upstream ``TreeViewMenu.createTreeViewMenu``. The three
        labels share a single :class:`tk.StringVar` so the menu acts as a
        Tk-equivalent ``ButtonGroup`` with ``VIEW_PAGES`` pre-selected.
        """
        menu = tk.Menu(self._master, tearoff=0)
        self._var = tk.StringVar(master=self._master, value=self.VIEW_PAGES)
        for label in self._VALID_MODES:
            menu.add_radiobutton(label=label, value=label, variable=self._var)
        return menu

    # Back-compat alias for the previously-private builder.
    _create_tree_view_menu = create_tree_view_menu

    # --- singleton --------------------------------------------------------

    @classmethod
    def get_instance(cls, master: tk.Misc | None = None) -> TreeViewMenu:  # type: ignore[name-defined]
        if cls._instance is None:
            cls._instance = cls(master=master)
        return cls._instance

    @classmethod
    def _reset_for_testing(cls) -> None:
        cls._instance = None

    # --- selection --------------------------------------------------------

    def set_tree_view_selection(self, selection: str) -> None:
        """Mark ``selection`` as the active tree-view label.

        :raises ValueError: when ``selection`` is not a recognised view.
        """
        if selection not in self._VALID_MODES:
            raise ValueError(f"Invalid tree view selection: {selection}")
        self._var.set(selection)

    def get_tree_view_selection(self) -> str:
        """Return the currently selected tree view label.

        :raises RuntimeError: when nothing is selected (matches upstream's
            ``IllegalStateException``).
        """
        value = self._var.get()
        if value not in self._VALID_MODES:
            raise RuntimeError("No tree view selection")
        return value

    @staticmethod
    def is_valid_view_mode(view_mode: str) -> bool:
        """Return ``True`` iff ``view_mode`` is a valid view label."""
        return view_mode in TreeViewMenu._VALID_MODES


__all__ = ["TreeViewMenu"]
