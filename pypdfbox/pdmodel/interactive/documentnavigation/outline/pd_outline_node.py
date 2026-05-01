from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

if TYPE_CHECKING:
    from .pd_outline_item import PDOutlineItem


_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_PARENT: COSName = COSName.PARENT  # type: ignore[attr-defined]
_COUNT: COSName = COSName.COUNT  # type: ignore[attr-defined]
_FIRST: COSName = COSName.get_pdf_name("First")
_LAST: COSName = COSName.get_pdf_name("Last")
_NEXT: COSName = COSName.get_pdf_name("Next")
_PREV: COSName = COSName.PREV  # type: ignore[attr-defined]
_OUTLINES: COSName = COSName.get_pdf_name("Outlines")


class PDOutlineNode:
    """
    Base class for nodes in the document outline tree. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineNode``.

    The outline is a doubly-linked list of items chained via ``/First``,
    ``/Last``, ``/Next``, ``/Prev`` and ``/Parent``, with an aggregate
    ``/Count`` whose **sign** encodes whether the node is open (positive)
    or closed (negative). See PDF 32000-1:2008 table 152.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dictionary = dictionary if dictionary is not None else COSDictionary()

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    # ---------- equality / hashing (PDDictionaryWrapper parity) ----------

    def __eq__(self, other: object) -> bool:
        """Equality by underlying ``COSDictionary`` identity, mirroring
        upstream ``PDDictionaryWrapper#equals``. Two outline wrappers
        compare equal when (and only when) they wrap the same
        ``COSDictionary`` instance — fresh wrappers returned by accessors
        such as ``get_next_sibling`` therefore compare equal across
        calls.
        """
        if self is other:
            return True
        if isinstance(other, PDOutlineNode):
            return self._dictionary is other._dictionary
        return NotImplemented

    def __hash__(self) -> int:
        """Hash by ``id`` of the wrapped dictionary, paired with
        :meth:`__eq__`. Mirrors upstream ``PDDictionaryWrapper#hashCode``,
        which delegates to the dictionary's hash."""
        return id(self._dictionary)

    # ---------- parent ----------

    def get_parent(self) -> PDOutlineNode | None:
        """Return the parent node, or ``None`` for the root.

        Outline roots carry ``/Type /Outlines`` and become
        :class:`PDDocumentOutline` wrappers; everything else is a
        :class:`PDOutlineItem`.
        """
        from .pd_document_outline import PDDocumentOutline
        from .pd_outline_item import PDOutlineItem

        parent = self._dictionary.get_dictionary_object(_PARENT)
        if not isinstance(parent, COSDictionary):
            return None
        type_name = parent.get_dictionary_object(_TYPE)
        if isinstance(type_name, COSName) and type_name == _OUTLINES:
            return PDDocumentOutline(parent)
        return PDOutlineItem(parent)

    def _set_parent(self, parent: PDOutlineNode) -> None:
        self._dictionary.set_item(_PARENT, parent.get_cos_object())

    # ---------- children: first / last ----------

    def has_children(self) -> bool:
        return isinstance(
            self._dictionary.get_dictionary_object(_FIRST), COSDictionary
        )

    def _get_outline_item(self, key: COSName) -> PDOutlineItem | None:
        from .pd_outline_item import PDOutlineItem

        value = self._dictionary.get_dictionary_object(key)
        if isinstance(value, COSDictionary):
            return PDOutlineItem(value)
        return None

    def get_first_child(self) -> PDOutlineItem | None:
        return self._get_outline_item(_FIRST)

    def get_last_child(self) -> PDOutlineItem | None:
        return self._get_outline_item(_LAST)

    def _set_first_child(self, node: PDOutlineNode) -> None:
        self._dictionary.set_item(_FIRST, node.get_cos_object())

    def _set_last_child(self, node: PDOutlineNode) -> None:
        self._dictionary.set_item(_LAST, node.get_cos_object())

    # ---------- count / open / close ----------

    def get_open_count(self) -> int:
        """Return ``/Count``. Positive = node is open and the value is the
        number of visible descendant items; negative = node is closed and
        the absolute value is the would-be visible count; zero = leaf
        without descendants."""
        return self._dictionary.get_int(_COUNT, 0)

    def set_open_count(self, count: int) -> None:
        """Public setter for ``/Count``. Mirrors upstream
        ``PDOutlineNode#setOpenCount``."""
        self._dictionary.set_int(_COUNT, count)

    def _set_open_count(self, count: int) -> None:
        self._dictionary.set_int(_COUNT, count)

    def is_node_open(self) -> bool:
        return self.get_open_count() > 0

    def open_node(self) -> None:
        """Open this node. No-op if already open."""
        if not self.is_node_open():
            self._switch_node_count()

    def close_node(self) -> None:
        """Close this node. No-op if already closed."""
        if self.is_node_open():
            self._switch_node_count()

    def _switch_node_count(self) -> None:
        open_count = self.get_open_count()
        self._set_open_count(-open_count)
        self._update_parent_open_count(-open_count)

    def _update_parent_open_count(self, delta: int) -> None:
        """Propagate a count change up the parent chain. Mirrors upstream:
        when the parent is open, contributions land directly in the
        parent's count and bubble higher; when closed, the parent's
        (negative) count widens but propagation stops."""
        parent = self.get_parent()
        if parent is None:
            return
        if parent.get_cos_object() is self._dictionary:
            # Self-referencing parent — see PDFBOX-5939. Bail rather than recurse.
            return
        if parent.is_node_open():
            parent._set_open_count(parent.get_open_count() + delta)
            parent._update_parent_open_count(delta)
        else:
            parent._set_open_count(parent.get_open_count() - delta)

    # ---------- internal: linked-list mutation ----------

    @staticmethod
    def _require_single_node(node: PDOutlineItem) -> None:
        if node.get_next_sibling() is not None or node.get_previous_sibling() is not None:
            raise ValueError("A single node with no siblings is required")

    def _append(self, new_child: PDOutlineItem) -> None:
        new_child._set_parent(self)
        if not self.has_children():
            self._set_first_child(new_child)
        else:
            previous_last = self.get_last_child()
            assert previous_last is not None
            previous_last._set_next_sibling(new_child)
            new_child._set_previous_sibling(previous_last)
        self._set_last_child(new_child)

    def _prepend(self, new_child: PDOutlineItem) -> None:
        new_child._set_parent(self)
        if not self.has_children():
            self._set_last_child(new_child)
        else:
            previous_first = self.get_first_child()
            assert previous_first is not None
            new_child._set_next_sibling(previous_first)
            previous_first._set_previous_sibling(new_child)
        self._set_first_child(new_child)

    def _update_parent_open_count_for_added_child(self, new_child: PDOutlineItem) -> None:
        delta = 1
        if new_child.is_node_open():
            delta += new_child.get_open_count()
        new_child._update_parent_open_count(delta)

    # ---------- public mutation ----------

    def add_last(self, new_child: PDOutlineItem) -> None:
        """Append ``new_child`` as the last child. ``new_child`` must be a
        single node (no siblings)."""
        self._require_single_node(new_child)
        self._append(new_child)
        self._update_parent_open_count_for_added_child(new_child)

    def add_first(self, new_child: PDOutlineItem) -> None:
        """Prepend ``new_child`` as the first child. ``new_child`` must be a
        single node (no siblings)."""
        self._require_single_node(new_child)
        self._prepend(new_child)
        self._update_parent_open_count_for_added_child(new_child)

    def append_child(self, new_child: PDOutlineItem) -> None:
        """Upstream-compatibility alias for :meth:`add_last`. Mirrors
        ``PDOutlineNode#appendChild`` from the Java API — appends
        ``new_child`` to the end of the child chain."""
        self.add_last(new_child)

    # ---------- iteration ----------

    def children(self) -> _OutlineChildren:
        """Iterate children left-to-right via the ``/Next`` chain.

        Returns an iterable that can be consumed multiple times — each
        ``iter()`` call walks from ``/First`` again."""
        return _OutlineChildren(self)

    def iterator(self) -> PDOutlineItemIterator:
        """Return a forward iterator over children in ``/First`` →
        ``/Next`` chain order. Mirrors upstream
        ``PDOutlineNode#iterator``."""
        return PDOutlineItemIterator(self.get_first_child())

    def nodes(self) -> _OutlineChildren:
        """Alias for :meth:`children`. Mirrors upstream
        ``PDOutlineNode#nodes``."""
        return _OutlineChildren(self)

    def __iter__(self) -> Iterator[PDOutlineItem]:
        return iter(self.children())


class PDOutlineItemIterator:
    """Forward iterator over a chain of ``/Next``-linked outline items.

    Mirrors Java ``Iterator<PDOutlineItem>`` semantics — exposes
    ``has_next()``/``__next__`` for parity with upstream tests, and is
    also usable as a Python iterable."""

    def __init__(self, start: PDOutlineItem | None) -> None:
        self._cursor = start
        self._seen: set[int] = set()

    def has_next(self) -> bool:
        """``True`` when a subsequent :meth:`__next__` call would yield an
        item, mirroring upstream ``PDOutlineItemIterator#hasNext``: the
        cursor must be non-``None`` *and* not already in the visited set
        (so a cycle in ``/Next`` doesn't dangle a phantom ``True``)."""
        if self._cursor is None:
            return False
        return id(self._cursor.get_cos_object()) not in self._seen

    def __iter__(self) -> Iterator[PDOutlineItem]:
        return self

    def __next__(self) -> PDOutlineItem:
        if self._cursor is None:
            raise StopIteration
        current = self._cursor
        cid = id(current.get_cos_object())
        if cid in self._seen:
            # Cycle guard — PDF spec requires acyclic; bail safely.
            self._cursor = None
            raise StopIteration
        self._seen.add(cid)
        self._cursor = current.get_next_sibling()
        return current

    def remove(self) -> None:
        """Java ``Iterator.remove()`` parity — unsupported."""
        raise NotImplementedError("remove is not supported by PDOutlineItemIterator")


class _OutlineChildren:
    """Re-iterable view returned by :meth:`PDOutlineNode.children`. Each
    ``iter()`` call starts a fresh walk from the current ``/First`` child."""

    def __init__(self, owner: PDOutlineNode) -> None:
        self._owner = owner

    def __iter__(self) -> PDOutlineItemIterator:
        return PDOutlineItemIterator(self._owner.get_first_child())


__all__ = ["PDOutlineNode", "PDOutlineItemIterator"]
