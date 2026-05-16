"""Convert between a tree path and a slash-separated status string.

Ported from ``org.apache.pdfbox.debugger.treestatus.TreeStatus``.

The original class operated on ``javax.swing.tree.TreePath`` instances. This
port replaces that with a plain ``tuple`` of nodes — Python's natural
representation of a path — so the class works equally well with Tkinter's
``ttk.Treeview`` (which does not have a first-class ``TreePath`` type) and
with pure-logic call sites.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSObject
from pypdfbox.debugger.ui.array_entry import ArrayEntry
from pypdfbox.debugger.ui.map_entry import MapEntry
from pypdfbox.debugger.ui.page_entry import PageEntry
from pypdfbox.debugger.ui.xref_entry import XrefEntry

#: Type alias used internally — a "tree path" is a non-empty tuple of nodes.
TreePath = tuple[Any, ...]


class TreeStatus:
    """Convert a debugger tree path to/from a slash-separated status string."""

    def __init__(self, root_node: Any) -> None:
        """Store the root node used when reconstructing a path from a string.

        :param root_node: the root node of the tree that this status object
            should resolve paths against.
        """
        self._root_node = root_node

    # ---- public API ----------------------------------------------------

    def get_string_for_path(self, path: TreePath) -> str:
        """Return the status string for ``path``.

        :param path: tuple representing a tree path (root first, leaf last).
        :return: the slash-separated status string.
        """
        return self.generate_path_string(path)

    def get_path_for_string(self, status_string: str) -> TreePath | None:
        """Return the tree path for ``status_string``.

        :param status_string: a status string previously produced by
            :meth:`get_string_for_path` (or hand-typed by the user).
        :return: the resolved tree path, or ``None`` when the string cannot
            be resolved against the current tree.
        """
        return self.generate_path(status_string)

    # ---- helpers (upstream-named) --------------------------------------

    def generate_path_string(self, path: TreePath) -> str:
        """Construct a status string from ``path``.

        Mirrors the upstream walk up the parent chain, popping the leaf
        component at each step.
        """
        parts: list[str] = []
        # Walk leaf -> root, ignoring the root itself (matches upstream
        # which stops once ``getParentPath() == null``).
        current: TreePath = tuple(path)
        while len(current) > 1:
            obj = current[-1]
            parts.insert(0, "/" + self.get_object_name(obj))
            current = current[:-1]
        if not parts:
            return ""
        # Upstream deletes the first character (the leading "/").
        joined = "".join(parts)
        return joined[1:]

    def generate_path(self, path_string: str) -> TreePath | None:
        """Construct a tree path from ``path_string`` against the root."""
        nodes = self.parse_path_string(path_string)
        if nodes is None:
            return None
        obj: Any = self._root_node
        tree_path: TreePath = (obj,)
        for node in nodes:
            obj = self.search_node(obj, node)
            if obj is None:
                return None
            tree_path = (*tree_path, obj)
        return tree_path

    @staticmethod
    def get_object_name(tree_node: Any) -> str:
        """Return the textual identifier used for ``tree_node`` in the path."""
        if isinstance(tree_node, MapEntry):
            key = tree_node.get_key()
            if key is None:
                # Upstream relied on the key never being null at this point;
                # in our port we mirror the behavior by treating it as the
                # empty name.
                return ""
            return key.get_name()
        if isinstance(tree_node, ArrayEntry):
            return f"[{tree_node.get_index()}]"
        if isinstance(tree_node, PageEntry):
            return tree_node.get_path()
        if isinstance(tree_node, XrefEntry):
            return tree_node.get_path()
        raise ValueError(
            f"Unknown treeNode type: {type(tree_node).__name__}"
        )

    @staticmethod
    def parse_path_string(path: str) -> list[str] | None:
        """Split the status string into individual node identifiers."""
        nodes: list[str] = []
        for raw in path.split("/"):
            node = raw.strip()
            if node.startswith("["):
                node = node.replace("]", "").replace("[", "").strip()
            if not node:
                return None
            nodes.append(node)
        return nodes

    @staticmethod
    def search_node(obj: Any, search_str: str) -> Any:
        """Resolve one step of the path inside ``obj``."""
        if isinstance(obj, (MapEntry, ArrayEntry)):
            obj = obj.get_value()
        elif isinstance(obj, XrefEntry):
            obj = obj.get_object()

        if isinstance(obj, COSObject):
            obj = obj.get_object()

        if isinstance(obj, COSDictionary):
            if obj.contains_key(search_str):
                entry = MapEntry()
                entry.set_key(COSName.get_pdf_name(search_str))
                entry.set_value(obj.get_dictionary_object(search_str))
                entry.set_item(obj.get_item(search_str))
                return entry
        elif isinstance(obj, COSArray):
            try:
                index = int(search_str)
            except ValueError:
                return None
            if 0 <= index <= obj.size() - 1:
                entry = ArrayEntry()
                entry.set_index(index)
                entry.set_value(obj.get_object(index))
                entry.set_item(obj.get(index))
                return entry
        return None

    # ---- backward-compat private aliases -------------------------------
    # The methods were originally private; keep underscore-prefixed
    # references working for any in-tree callers.
    _generate_path_string = generate_path_string
    _generate_path = generate_path
    _get_object_name = get_object_name
    _parse_path_string = parse_path_string
    _search_node = search_node
