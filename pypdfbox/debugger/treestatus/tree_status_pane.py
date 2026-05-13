"""Tkinter port of ``org.apache.pdfbox.debugger.treestatus.TreeStatusPane``.

Holds the status entry widget which displays the path to the currently
selected tree node, and lets the user type a path to jump to.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from pypdfbox.debugger.treestatus.tree_status import TreePath, TreeStatus


class TreeStatusPane:
    """A status bar bound to a ``ttk.Treeview``.

    The pane exposes an entry where the path of the currently selected tree
    node is shown. When the user types a path and hits *Return*, the bound
    :class:`TreeStatus` is asked to resolve it and the tree's selection is
    updated accordingly.
    """

    def __init__(
        self,
        tree: ttk.Treeview,
        node_lookup: Callable[[str], Any] | None = None,
    ) -> None:
        """Construct the pane.

        :param tree: the ``ttk.Treeview`` whose selection mirrors the entry.
        :param node_lookup: optional callable that maps a ``ttk.Treeview``
            item id to the underlying domain node — used when ``TreeStatus``
            needs to compute the string for a freshly selected tree row.
            When ``None``, the item id is passed through unchanged.
        """
        self._tree = tree
        self._node_lookup = node_lookup or (lambda item: item)
        self._status_obj: TreeStatus | None = None

        self._panel: ttk.Frame | None = None
        self._status_field: ttk.Entry | None = None
        self._status_var: tk.StringVar | None = None
        self._default_style = "TreeStatusPane.TEntry"
        self._error_style = "TreeStatusPane.Error.TEntry"

    # --- initialisation -------------------------------------------------

    def init(self) -> None:
        """Build the widgets. Must be called immediately after construction."""
        self._panel = ttk.Frame(self._tree.master, relief="raised", borderwidth=2)
        self._status_var = tk.StringVar()
        self._status_field = ttk.Entry(
            self._panel,
            textvariable=self._status_var,
            state="disabled",
        )
        self._status_field.pack(fill="x", expand=True)

        # Two styles are registered so we can flash the entry red on a bad
        # path (mirrors upstream's BevelBorder colour swap).
        style = ttk.Style(self._panel)
        style.configure(self._default_style)
        style.configure(self._error_style, fieldbackground="#ffd0d0")
        self._status_field.configure(style=self._default_style)

        # Trigger lookup on Enter; upstream uses an AbstractAction wired to
        # the JTextField's default action.
        self._status_field.bind("<Return>", self._on_text_input)

        # Tkinter does not have a tree-selection listener interface; we wire
        # the equivalent ``<<TreeviewSelect>>`` virtual event instead.
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select, add="+")

    # --- public API -----------------------------------------------------

    def get_panel(self) -> ttk.Frame:
        """Return the :class:`ttk.Frame` containing the status entry."""
        if self._panel is None:
            raise RuntimeError("init() must be called before get_panel()")
        return self._panel

    def update_tree_status(self, status_obj: TreeStatus) -> None:
        """Bind a fresh :class:`TreeStatus` (e.g. after a document switch)."""
        if self._status_field is None:
            raise RuntimeError("init() must be called before update_tree_status()")
        self._status_field.configure(state="normal")
        self._status_obj = status_obj
        self._update_text(None)

    # --- event handlers -------------------------------------------------

    def value_changed(self, path: TreePath) -> None:
        """Refresh the status text for ``path``.

        Exposed for callers that prefer to push the selection in directly,
        bypassing the ``<<TreeviewSelect>>`` plumbing.
        """
        if self._status_obj is None:
            return
        self._update_text(self._status_obj.get_string_for_path(path))

    # --- internals ------------------------------------------------------

    def _on_tree_select(self, _event: tk.Event[Any]) -> None:
        if self._status_obj is None:
            return
        selection = self._tree.selection()
        if not selection:
            return
        item = selection[0]
        path: TreePath = tuple(self._build_path(item))
        self._update_text(self._status_obj.get_string_for_path(path))

    def _on_text_input(self, _event: tk.Event[Any]) -> str:
        if self._status_obj is None or self._status_var is None or self._status_field is None:
            return "break"
        text = self._status_var.get()
        path = self._status_obj.get_path_for_string(text)
        if path is not None:
            # Walk the path mapping each domain node back to a tree item id.
            # We can only do this if the caller supplied a reverse lookup,
            # so fall back to a no-op when none was provided.
            item = self._locate_item_for_path(path)
            if item is not None:
                self._tree.selection_set(item)
                self._tree.see(item)
                self._tree.focus_set()
            else:
                # Resolution succeeded but we have no way to highlight it —
                # treat it as a soft success: clear the error style.
                self._status_field.configure(style=self._default_style)
        else:
            self._status_field.configure(style=self._error_style)
        return "break"

    def _update_text(self, status_string: str | None) -> None:
        if self._status_var is None or self._status_field is None:
            return
        self._status_var.set(status_string or "")
        self._status_field.configure(style=self._default_style)

    def _build_path(self, item: str) -> list[Any]:
        """Walk from ``item`` up to the tree root, returning a list of nodes."""
        nodes: list[Any] = []
        current = item
        while current:
            nodes.insert(0, self._node_lookup(current))
            current = self._tree.parent(current)
        return nodes

    def _locate_item_for_path(self, path: TreePath) -> str | None:
        """Best-effort reverse lookup from a domain path to a tree item id.

        Subclasses (or callers) may override this by providing a custom
        ``node_lookup`` that exposes the inverse mapping. The default
        implementation simply returns ``None`` so the pane degrades to a
        text-only display when no mapping is available.
        """
        del path  # unused
        return None
