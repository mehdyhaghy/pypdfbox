"""Customised ``ttk.Treeview`` used by the debugger.

Ported from ``org.apache.pdfbox.debugger.ui.Tree``.

The Swing version adds a right-click popup with "Copy Tree Path" and a set of
stream-saving actions. We port the same UX: right-click selects the node and
opens a popup menu whose entries are built dynamically based on the selected
node's type.

To stay testable without a real Tk display, the menu-building logic is split
into pure-data helpers (``build_menu_items(node, ...)`` returning a list of
``(label, callback)`` tuples). The widget code only wires those into a real
``tk.Menu`` when shown.
"""

from __future__ import annotations

import os
import tempfile
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk
from typing import Any

from pypdfbox.cos import COSArray, COSName, COSObject, COSStream

from .array_entry import ArrayEntry
from .map_entry import MapEntry
from .xref_entry import XrefEntry

#: A menu entry is a label string plus a zero-arg callback.
MenuItem = tuple[str, Callable[[], None]]


class Tree(ttk.Treeview):
    """A customised tree for PDFDebugger."""

    def __init__(self, master: tk.Misc | None = None, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self._row_height: int | None = None
        self._tree_status: Any = None  # ``TreeStatus`` once attached
        self._node_for_iid: dict[str, Any] = {}
        self._popup: tk.Menu | None = None
        # Right-click binding (Button-2 on macOS, Button-3 elsewhere). We bind
        # both for portability.
        self.bind("<Button-3>", self._on_right_click)
        self.bind("<Button-2>", self._on_right_click)

    # --- two-step construction (Swing parity) -----------------------------

    def init(self, row_height: int | None = None) -> None:
        """Apply configuration that depends on the running display."""
        if row_height is not None:
            self._row_height = int(row_height)
            style = ttk.Style(self)
            style.configure("Treeview", rowheight=self._row_height)

    # --- registration helpers --------------------------------------------

    def register_node(self, iid: str, node: Any) -> None:
        """Remember the Python object corresponding to ``iid``."""
        self._node_for_iid[iid] = node

    def get_node(self, iid: str) -> Any:
        """Return the Python object for ``iid``, or ``None``."""
        return self._node_for_iid.get(iid)

    def set_tree_status(self, tree_status: Any) -> None:
        """Attach a :class:`TreeStatus` instance for path stringification."""
        self._tree_status = tree_status

    # --- popup-menu logic (pure data, used by tests) ----------------------

    def build_menu_items(
        self,
        node: Any,
        tree_path: tuple[Any, ...],
        *,
        save_dialog: Any = None,
        open_handler: Callable[[str], None] | None = None,
    ) -> list[MenuItem]:
        """Return the popup-menu items appropriate for ``node``.

        :param node: the tree-row's Python value.
        :param tree_path: the tuple-of-nodes path used by
            :class:`TreeStatus` to stringify the location.
        :param save_dialog: a :class:`FileOpenSaveDialog`-like object used
            when the user picks a save action. If ``None``, a default one is
            constructed lazily.
        :param open_handler: optional callable invoked with the path of a
            temp file written when the user picks "Open with Default
            Application". If ``None``, no open action is generated.
        """
        items: list[MenuItem] = []
        items.append(("Copy Tree Path", self._make_copy_path(tree_path)))
        unwrapped = self._unwrap(node)
        if not isinstance(unwrapped, COSStream):
            return items
        items.append(("", _separator))
        items.append(
            (
                f"Save Stream As{self._format_extension_suffix(unwrapped, node)}...",
                self._make_save_stream(unwrapped, node, save_dialog),
            )
        )
        filters = self._get_filters_for_stream(unwrapped)
        if filters:
            if len(filters) >= 2:
                items.extend(self._build_partial_decode_items(unwrapped, save_dialog))
            items.append(
                (
                    f"Save Raw Stream ({', '.join(filters)}) As...",
                    self._make_save_raw_stream(unwrapped, save_dialog),
                )
            )
        extension = self._get_file_extension(unwrapped, node)
        if extension is not None and open_handler is not None:
            items.append(("", _separator))
            items.append(
                (
                    "Open with Default Application",
                    self._make_open_with_default(unwrapped, extension, open_handler),
                )
            )
        return items

    # --- helpers ----------------------------------------------------------

    @staticmethod
    def _unwrap(node: Any) -> Any:
        if isinstance(node, MapEntry):
            return node.get_value()
        if isinstance(node, ArrayEntry):
            return node.get_value()
        if isinstance(node, XrefEntry):
            return node.get_object()
        return node

    def _make_copy_path(
        self,
        tree_path: tuple[Any, ...],
    ) -> Callable[[], None]:
        def _copy() -> None:
            if self._tree_status is None:
                return
            path_string = self._tree_status.get_string_for_path(tree_path)
            try:
                self.clipboard_clear()
                self.clipboard_append(path_string)
            except tk.TclError:  # pragma: no cover - no display
                pass

        return _copy

    @staticmethod
    def _get_filters_for_stream(stream: COSStream) -> list[str]:
        """Return the filter-name list for ``stream``."""
        filters = stream.get_filters() if hasattr(stream, "get_filters") else None
        if isinstance(filters, COSName):
            return [filters.get_name()]
        if isinstance(filters, COSArray):
            names: list[str] = []
            for entry in filters:
                if isinstance(entry, COSName):
                    names.append(entry.get_name())
            return names
        return []

    @staticmethod
    def _get_file_extension(stream: COSStream, node: Any) -> str | None:
        """Pick a recommended file extension for ``stream``."""
        if isinstance(node, MapEntry):
            key = node.get_key()
            name = key.get_name() if key is not None else ""
        elif isinstance(node, ArrayEntry):
            name = str(node.get_index())
        else:
            name = str(node)
        if name == "FontFile":
            return "pfb"
        if name == "FontFile2":
            return "ttf"
        if name == "FontFile3":
            try:
                subtype = stream.get_cos_name("Subtype")
            except Exception:  # pragma: no cover - older API surface
                subtype = None
            if subtype is not None and subtype.get_name() == "OpenType":
                return "otf"
            return "cff"
        return None

    def _format_extension_suffix(self, stream: COSStream, node: Any) -> str:
        ext = self._get_file_extension(stream, node)
        return "" if ext is None else " " + ext.upper()

    def _make_save_stream(
        self,
        stream: COSStream,
        node: Any,
        save_dialog: Any,
    ) -> Callable[[], None]:
        extension = self._get_file_extension(stream, node)
        file_filter = _filter_for_extension(extension)

        def _save() -> None:
            data = _read_stream(stream, raw=False)
            self._save_via_dialog(save_dialog, data, file_filter, extension)

        return _save

    def _make_save_raw_stream(
        self,
        stream: COSStream,
        save_dialog: Any,
    ) -> Callable[[], None]:
        def _save() -> None:
            data = _read_stream(stream, raw=True)
            self._save_via_dialog(save_dialog, data, None, None)

        return _save

    def _build_partial_decode_items(
        self,
        stream: COSStream,
        save_dialog: Any,
    ) -> list[MenuItem]:
        filters = self._get_filters_for_stream(stream)
        items: list[MenuItem] = []
        for stop_index in range(len(filters) - 1, 0, -1):
            kept = filters[stop_index:]
            label = "Keep " + " & ".join(kept) + "..."
            items.append((label, self._make_partial(stream, stop_index, save_dialog)))
        return items

    def _make_partial(
        self,
        stream: COSStream,
        stop_index: int,
        save_dialog: Any,
    ) -> Callable[[], None]:
        def _save() -> None:
            data = _read_stream_partial(stream, stop_index)
            self._save_via_dialog(save_dialog, data, None, None)

        return _save

    def _make_open_with_default(
        self,
        stream: COSStream,
        extension: str,
        open_handler: Callable[[str], None],
    ) -> Callable[[], None]:
        def _open() -> None:
            tmp_dir = Path(tempfile.mkdtemp(prefix="pdfbox-"))
            os.chmod(tmp_dir, 0o700)
            tmp_file = tmp_dir / f"stream.{extension}"
            tmp_file.write_bytes(_read_stream(stream, raw=False))
            open_handler(str(tmp_file))

        return _open

    def _save_via_dialog(
        self,
        save_dialog: Any,
        data: bytes,
        file_filter: Any,
        extension: str | None,
    ) -> None:
        if save_dialog is None:
            # Lazy import keeps us decoupled from FileOpenSaveDialog when
            # callers supply their own.
            from .file_open_save_dialog import FileOpenSaveDialog

            save_dialog = FileOpenSaveDialog(self, file_filter)
        save_dialog.save_file(data, extension)

    # --- right-click handler ---------------------------------------------

    def _on_right_click(self, event: tk.Event) -> None:  # pragma: no cover - GUI
        iid = self.identify_row(event.y)
        if not iid:
            return
        self.selection_set(iid)
        node = self.get_node(iid)
        if node is None:
            return
        tree_path = self._compute_tree_path(iid)
        items = self.build_menu_items(node, tree_path)
        if not items:
            return
        if self._popup is not None:
            self._popup.destroy()
        menu = tk.Menu(self, tearoff=0)
        for label, callback in items:
            if label == "":
                menu.add_separator()
                continue
            menu.add_command(label=label, command=callback)
        self._popup = menu
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _compute_tree_path(self, iid: str) -> tuple[Any, ...]:
        chain: list[Any] = []
        current = iid
        while current:
            node = self.get_node(current)
            if node is not None:
                chain.append(node)
            current = self.parent(current)
        chain.reverse()
        return tuple(chain)


# --- helpers -----------------------------------------------------------------


def _separator() -> None:
    """Placeholder callback for separator entries."""


def _filter_for_extension(extension: str | None) -> Any:
    """Return a Tk-style filetypes spec for ``extension``."""
    mapping = {
        "pdb": ("Type 1 Font (*.pfb)", "*.pfb"),
        "ttf": ("TrueType Font (*.ttf)", "*.ttf"),
        "cff": ("Compact Font Format (*.cff)", "*.cff"),
        "otf": ("OpenType Font (*.otf)", "*.otf"),
    }
    if extension is None or extension not in mapping:
        return None
    label, pattern = mapping[extension]
    return [(label, pattern)]


def _read_stream(stream: COSStream, *, raw: bool) -> bytes:
    """Read ``stream`` fully into a ``bytes`` value.

    ``raw=True`` reads the encoded/compressed bytes; ``raw=False`` runs all
    decode filters.
    """
    if raw:
        creator = getattr(stream, "create_raw_input_stream", None)
    else:
        creator = getattr(stream, "create_input_stream", None)
    if creator is None:
        return b""
    with creator() as data:
        if hasattr(data, "read"):
            return data.read()
        return bytes(data)


def _read_stream_partial(stream: COSStream, stop_index: int) -> bytes:
    """Read ``stream`` running filters up to (but not including) ``stop_index``."""
    creator = getattr(stream, "create_input_stream", None)
    if creator is None:
        return b""
    filters = []
    base = getattr(stream, "get_filters", None)
    if base is not None:
        raw = base()
        if isinstance(raw, COSName):
            filters = [raw.get_name()]
        elif isinstance(raw, COSArray):
            filters = [f.get_name() for f in raw if isinstance(f, COSName)]
    stop_filters: list[str] = []
    if 0 <= stop_index < len(filters):
        stop_filters = [filters[stop_index]]
    try:
        data = creator(stop_filters) if stop_filters else creator()
    except TypeError:
        data = creator()
    if hasattr(data, "read"):
        return data.read()
    return bytes(data)


# Backwards-compat sentinel referenced by COSObject.get_key in the renderer.
_ = COSObject  # noqa: B015 - keep the import alive for type checkers
