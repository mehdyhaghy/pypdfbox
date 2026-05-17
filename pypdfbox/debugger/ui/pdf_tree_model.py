"""Tree-model wrapping a :class:`PDDocument`'s COS tree.

Ported from ``org.apache.pdfbox.debugger.ui.PDFTreeModel``. The Swing
``TreeModelListener`` boilerplate is intentionally omitted: Tkinter's
``ttk.Treeview`` is event-driven from the consumer side, so the upstream
no-op listener registry has no analogue here.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSObject,
)

from .array_entry import ArrayEntry
from .document_entry import DocumentEntry
from .map_entry import MapEntry
from .page_entry import PageEntry
from .xref_entries import XrefEntries
from .xref_entry import XrefEntry

if TYPE_CHECKING:
    from pypdfbox.pdmodel import PDDocument


class PDFTreeModel:
    """Models a PDF document as a tree structure.

    The model is intentionally read-only: ``value_for_path_changed`` is a
    no-op, matching upstream behaviour.
    """

    def __init__(
        self,
        root: PDDocument | DocumentEntry | XrefEntries | None = None,
    ) -> None:
        self._root: Any
        if root is None:
            self._root = None
        elif isinstance(root, (DocumentEntry, XrefEntries)):
            self._root = root
        else:
            # ``root`` is a PDDocument; the upstream API roots at the trailer.
            self._root = root.get_document().get_trailer()
        # Listener fan-out mirrors Swing's ``TreeModelListener`` registry; the
        # Tkinter view does not subscribe today, but the surface is kept for
        # API parity so embedders can hook tree-change events.
        self._tree_model_listeners: list[Callable[[PDFTreeModel], None]] = []

    # --- root --------------------------------------------------------------

    def get_root(self) -> Any:
        """Return the root of the tree."""
        return self._root

    # --- children ----------------------------------------------------------

    def get_child(self, parent: Any, index: int) -> Any:
        """Return the child of ``parent`` at ``index``."""
        if isinstance(parent, COSArray):
            entry = ArrayEntry()
            entry.set_index(index)
            entry.set_value(parent.get_object(index))
            entry.set_item(parent.get(index))
            return entry
        if isinstance(parent, COSDictionary):
            keys = sorted(parent.key_set(), key=lambda k: k.get_name())
            key = keys[index]
            value = parent.get_dictionary_object(key)
            entry = MapEntry()
            entry.set_key(key)
            entry.set_value(value)
            entry.set_item(parent.get_item(key))
            return entry
        if isinstance(parent, MapEntry):
            return self.get_child(parent.get_value(), index)
        if isinstance(parent, ArrayEntry):
            return self.get_child(parent.get_value(), index)
        if isinstance(parent, DocumentEntry):
            return parent.get_page(index)
        if isinstance(parent, XrefEntries):
            return parent.get_xref_entry(index)
        if isinstance(parent, XrefEntry):
            entry = ArrayEntry()
            entry.set_index(index)
            entry.set_value(parent.get_object())
            entry.set_item(parent.get_cos_object())
            return entry
        if isinstance(parent, PageEntry):
            return self.get_child(parent.get_dict(), index)
        if isinstance(parent, COSObject):
            return parent.get_object()
        raise ValueError(f"Unknown COS type {type(parent).__name__}")

    def get_child_count(self, parent: Any) -> int:
        """Return the number of children of ``parent``."""
        if isinstance(parent, COSArray):
            return parent.size()
        if isinstance(parent, COSDictionary):
            return parent.size()
        if isinstance(parent, MapEntry):
            return self.get_child_count(parent.get_value())
        if isinstance(parent, ArrayEntry):
            return self.get_child_count(parent.get_value())
        if isinstance(parent, DocumentEntry):
            return parent.get_page_count()
        if isinstance(parent, XrefEntries):
            return parent.get_xref_entry_count()
        if isinstance(parent, XrefEntry):
            return 1
        if isinstance(parent, PageEntry):
            return self.get_child_count(parent.get_dict())
        if isinstance(parent, COSObject):
            return 1
        return 0

    def get_index_of_child(self, parent: Any, child: Any) -> int:
        """Return the index of ``child`` in ``parent``, or -1."""
        if parent is None or child is None:
            return -1
        if isinstance(parent, COSArray):
            if isinstance(child, ArrayEntry):
                return child.get_index()
            return parent.index_of(child)
        if isinstance(parent, COSDictionary):
            if not isinstance(child, MapEntry):
                return -1
            keys = sorted(parent.key_set(), key=lambda k: k.get_name())
            for i, k in enumerate(keys):
                if k == child.get_key():
                    return i
            return -1
        if isinstance(parent, MapEntry):
            return self.get_index_of_child(parent.get_value(), child)
        if isinstance(parent, ArrayEntry):
            return self.get_index_of_child(parent.get_value(), child)
        if isinstance(parent, DocumentEntry):
            return parent.index_of(child)
        if isinstance(parent, XrefEntries):
            return child.get_index()
        if isinstance(parent, XrefEntry):
            return 0
        if isinstance(parent, PageEntry):
            return self.get_index_of_child(parent.get_dict(), child)
        if isinstance(parent, COSObject):
            return 0
        raise ValueError(f"Unknown COS type {type(parent).__name__}")

    # --- leaves ------------------------------------------------------------

    def is_leaf(self, node: Any) -> bool:
        """Return ``True`` iff ``node`` cannot have children."""
        if isinstance(
            node,
            (
                COSDictionary,
                COSArray,
                COSDocument,
                DocumentEntry,
                XrefEntries,
                PageEntry,
                COSObject,
            ),
        ):
            return False
        if isinstance(node, XrefEntry):
            return self.is_leaf(node.get_cos_object())
        if isinstance(node, MapEntry):
            return self.is_leaf(node.get_value())
        if isinstance(node, ArrayEntry):
            return self.is_leaf(node.get_value())
        return True

    # --- write side (no-op, retained for API parity) -----------------------

    def value_for_path_changed(self, path: Any, new_value: Any) -> None:
        """Required by the upstream interface; intentionally a no-op."""
        # Mirrors the Swing API surface. Tkinter editing is handled directly
        # by the view, not the model.

    # --- listener fan-out --------------------------------------------------

    def add_tree_model_listener(
        self, listener: Callable[[PDFTreeModel], None]
    ) -> None:
        """Register ``listener`` for tree-change notifications.

        Mirrors Swing's ``TreeModel.addTreeModelListener``. The upstream
        implementation is a no-op (the registry exists but is never fired);
        we keep a real list so embedders can opt in to change events via
        :meth:`_fire_tree_changed`.
        """
        if listener not in self._tree_model_listeners:
            self._tree_model_listeners.append(listener)

    def remove_tree_model_listener(
        self, listener: Callable[[PDFTreeModel], None]
    ) -> None:
        """Unregister a previously added ``listener``.

        Mirrors Swing's ``TreeModel.removeTreeModelListener``. Silently
        ignores listeners that were never registered.
        """
        with contextlib.suppress(ValueError):
            self._tree_model_listeners.remove(listener)

    def _fire_tree_changed(self) -> None:
        """Notify all registered listeners that the tree has changed."""
        for listener in list(self._tree_model_listeners):
            listener(self)
