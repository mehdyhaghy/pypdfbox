from __future__ import annotations

import logging
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

_LOG = logging.getLogger(__name__)


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
        :class:`PDOutlineItem`. Mirrors upstream
        ``PDOutlineNode#getParent`` (package-private in Java).
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

    def set_parent(self, parent: PDOutlineNode | None) -> None:
        """Set ``/Parent`` to point at ``parent`` (or remove it when
        ``parent`` is ``None``). Mirrors upstream
        ``PDOutlineNode#setParent`` (package-private in Java)."""
        self._dictionary.set_item(
            _PARENT,
            parent.get_cos_object() if parent is not None else None,
        )

    # Internal alias kept for in-tree callers that already use the
    # underscore form.
    _set_parent = set_parent

    # ---------- children: first / last ----------

    def has_children(self) -> bool:
        return isinstance(
            self._dictionary.get_dictionary_object(_FIRST), COSDictionary
        )

    def get_outline_item(self, key: COSName) -> PDOutlineItem | None:
        """Return the typed :class:`PDOutlineItem` wrapper for ``key`` (a
        ``/First``/``/Last``/``/Next``/``/Prev`` name) or ``None`` when
        absent. Mirrors upstream ``PDOutlineNode#getOutlineItem``
        (package-private in Java)."""
        from .pd_outline_item import PDOutlineItem

        value = self._dictionary.get_dictionary_object(key)
        if isinstance(value, COSDictionary):
            return PDOutlineItem(value)
        return None

    # Internal alias kept for in-tree callers that already use the
    # underscore form.
    _get_outline_item = get_outline_item

    def get_first_child(self) -> PDOutlineItem | None:
        return self.get_outline_item(_FIRST)

    def get_last_child(self) -> PDOutlineItem | None:
        return self.get_outline_item(_LAST)

    def set_first_child(self, node: PDOutlineNode) -> None:
        """Set ``/First`` to point at ``node``. Mirrors upstream
        ``PDOutlineNode#setFirstChild`` (package-private in Java)."""
        self._dictionary.set_item(_FIRST, node.get_cos_object())

    def set_last_child(self, node: PDOutlineNode) -> None:
        """Set ``/Last`` to point at ``node``. Mirrors upstream
        ``PDOutlineNode#setLastChild`` (package-private in Java)."""
        self._dictionary.set_item(_LAST, node.get_cos_object())

    # Internal aliases kept for in-tree callers that already use the
    # underscore form.
    _set_first_child = set_first_child
    _set_last_child = set_last_child

    # ---------- count / open / close ----------

    def get_open_count(self) -> int:
        """Return ``/Count``. Positive = node is open and the value is the
        number of visible descendant items; negative = node is closed and
        the absolute value is the would-be visible count; zero = leaf
        without descendants."""
        return self._dictionary.get_int(_COUNT, 0)

    def set_open_count(self, count: int) -> None:
        """Set ``/Count``. Mirrors upstream ``PDOutlineNode#setOpenCount``
        (package-private in Java) — pypdfbox keeps it public so callers can
        pre-seed counts on hand-built fixtures."""
        self._dictionary.set_int(_COUNT, count)

    # Internal alias kept for in-tree callers that already use the
    # underscore form.
    _set_open_count = set_open_count

    def is_node_open(self) -> bool:
        return self.get_open_count() > 0

    def open_node(self) -> None:
        """Open this node. No-op if already open."""
        if not self.is_node_open():
            self.switch_node_count()

    def close_node(self) -> None:
        """Close this node. No-op if already closed."""
        if self.is_node_open():
            self.switch_node_count()

    def switch_node_count(self) -> None:
        """Flip the sign of ``/Count`` and propagate the swing into the
        parent chain. Mirrors upstream ``PDOutlineNode#switchNodeCount``
        (private in Java) — pypdfbox keeps it accessible because subclasses
        such as :class:`PDDocumentOutline` need to override the open/close
        behaviour."""
        open_count = self.get_open_count()
        self.set_open_count(-open_count)
        self.update_parent_open_count(-open_count)

    # Internal alias kept for in-tree callers that already use the
    # underscore form.
    _switch_node_count = switch_node_count

    def update_parent_open_count(self, delta: int) -> None:
        """Propagate a count change up the parent chain. Mirrors upstream
        ``PDOutlineNode#updateParentOpenCount`` (package-private in Java):
        when the parent is open, contributions land directly in the
        parent's count and bubble higher; when closed, the parent's
        (negative) count widens but propagation stops.

        Defends against the self-referencing-parent case fixed in
        PDFBOX-5939 by detecting parent identity equality with this node's
        dictionary and bailing out (logged at WARNING level)."""
        parent = self.get_parent()
        if parent is None:
            return
        if parent.get_cos_object() is self._dictionary:
            # Self-referencing parent — see PDFBOX-5939. Bail rather than recurse.
            _LOG.warning("Outline parent points to itself")
            return
        if parent.is_node_open():
            parent.set_open_count(parent.get_open_count() + delta)
            parent.update_parent_open_count(delta)
        else:
            parent.set_open_count(parent.get_open_count() - delta)

    # Internal alias kept for in-tree callers that already use the
    # underscore form.
    _update_parent_open_count = update_parent_open_count

    # ---------- internal: linked-list mutation ----------

    @staticmethod
    def require_single_node(node: PDOutlineItem) -> None:
        """Assert ``node`` is unattached (no ``/Next`` or ``/Prev``).

        Raises ``ValueError`` (Python's stand-in for upstream's
        ``IllegalArgumentException``) when ``node`` is part of a chain.
        Mirrors upstream ``PDOutlineNode#requireSingleNode``
        (package-private in Java)."""
        if node.get_next_sibling() is not None or node.get_previous_sibling() is not None:
            raise ValueError("A single node with no siblings is required")

    # Internal alias kept for in-tree callers that already use the
    # underscore form.
    _require_single_node = require_single_node

    def append(self, new_child: PDOutlineItem) -> None:
        """Append ``new_child`` to the linked list of children. Mirrors
        upstream ``PDOutlineNode#append`` (private in Java) — adjusts
        ``/First``/``/Last``/``/Next``/``/Prev`` pointers but does **not**
        update the parent chain ``/Count``. Use :meth:`add_last` for the
        full bookkeeping."""
        new_child.set_parent(self)
        if not self.has_children():
            self.set_first_child(new_child)
        else:
            previous_last = self.get_last_child()
            assert previous_last is not None
            previous_last._set_next_sibling(new_child)
            new_child._set_previous_sibling(previous_last)
        self.set_last_child(new_child)

    def prepend(self, new_child: PDOutlineItem) -> None:
        """Prepend ``new_child`` to the linked list of children. Mirrors
        upstream ``PDOutlineNode#prepend`` (private in Java) — adjusts
        ``/First``/``/Last``/``/Next``/``/Prev`` pointers but does **not**
        update the parent chain ``/Count``. Use :meth:`add_first` for the
        full bookkeeping."""
        new_child.set_parent(self)
        if not self.has_children():
            self.set_last_child(new_child)
        else:
            previous_first = self.get_first_child()
            assert previous_first is not None
            new_child._set_next_sibling(previous_first)
            previous_first._set_previous_sibling(new_child)
        self.set_first_child(new_child)

    # Internal aliases kept for in-tree callers that already use the
    # underscore form.
    _append = append
    _prepend = prepend

    def update_parent_open_count_for_added_child(self, new_child: PDOutlineItem) -> None:
        """Bubble the count contribution from a newly attached
        ``new_child`` up the parent chain. Mirrors upstream
        ``PDOutlineNode#updateParentOpenCountForAddedChild``
        (package-private in Java)."""
        delta = 1
        if new_child.is_node_open():
            delta += new_child.get_open_count()
        new_child.update_parent_open_count(delta)

    # Internal alias kept for in-tree callers that already use the
    # underscore form.
    _update_parent_open_count_for_added_child = update_parent_open_count_for_added_child

    def _update_parent_open_count_for_removed_child(self, child: PDOutlineItem) -> None:
        delta = -1
        if child.is_node_open():
            delta -= child.get_open_count()
        if self.is_node_open():
            self.set_open_count(self.get_open_count() + delta)
            self.update_parent_open_count(delta)
        else:
            self.set_open_count(self.get_open_count() - delta)

    # ---------- public mutation ----------

    def add_last(self, new_child: PDOutlineItem) -> None:
        """Append ``new_child`` as the last child. ``new_child`` must be a
        single node (no siblings)."""
        self.require_single_node(new_child)
        self.append(new_child)
        self.update_parent_open_count_for_added_child(new_child)

    def add_first(self, new_child: PDOutlineItem) -> None:
        """Prepend ``new_child`` as the first child. ``new_child`` must be a
        single node (no siblings)."""
        self.require_single_node(new_child)
        self.prepend(new_child)
        self.update_parent_open_count_for_added_child(new_child)

    def append_child(self, new_child: PDOutlineItem) -> None:
        """Upstream-compatibility alias for :meth:`add_last`. Mirrors
        ``PDOutlineNode#appendChild`` from the Java API — appends
        ``new_child`` to the end of the child chain."""
        self.add_last(new_child)

    def remove_child(self, child: PDOutlineItem) -> bool:
        """Remove ``child`` from this node's immediate child chain.

        This is a pypdfbox convenience API; upstream PDFBox exposes child
        mutation through append/prepend and sibling insertion only. Returns
        ``True`` when ``child`` was present and unlinked, otherwise
        ``False``. Malformed cyclic ``/Next`` chains are treated as
        not-found once a node is revisited.
        """
        target = child.get_cos_object()
        current = self.get_first_child()
        previous_in_chain: PDOutlineItem | None = None
        seen: set[int] = set()
        while current is not None:
            current_dict = current.get_cos_object()
            current_id = id(current_dict)
            if current_id in seen:
                return False
            seen.add(current_id)
            if current_dict is target:
                self._unlink_child(current, previous_in_chain)
                return True
            previous_in_chain = current
            current = current.get_next_sibling()
        return False

    def _unlink_child(
        self, child: PDOutlineItem, previous_in_chain: PDOutlineItem | None
    ) -> None:
        child_dict = child.get_cos_object()
        previous_sibling = previous_in_chain
        next_sibling = child.get_next_sibling()

        first_child = self.get_first_child()
        if first_child is not None and first_child.get_cos_object() is child_dict:
            previous_sibling = None
            if next_sibling is None:
                self._dictionary.remove_item(_FIRST)
            else:
                self.set_first_child(next_sibling)

        last_child = self.get_last_child()
        if last_child is not None and last_child.get_cos_object() is child_dict:
            next_sibling = None
            if previous_sibling is None:
                self._dictionary.remove_item(_LAST)
            else:
                self.set_last_child(previous_sibling)

        if previous_sibling is not None:
            if next_sibling is None:
                previous_sibling.get_cos_object().remove_item(_NEXT)
            else:
                previous_sibling._set_next_sibling(next_sibling)
        if next_sibling is not None:
            if previous_sibling is None:
                next_sibling.get_cos_object().remove_item(_PREV)
            else:
                next_sibling._set_previous_sibling(previous_sibling)

        self._update_parent_open_count_for_removed_child(child)
        child_dict.remove_item(_PARENT)
        child_dict.remove_item(_PREV)
        child_dict.remove_item(_NEXT)

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

    def next(self) -> PDOutlineItem:
        """Mirror Java ``Iterator.next()`` — alias for :meth:`__next__`.

        Upstream ``PDOutlineItemIterator`` implements
        ``java.util.Iterator<PDOutlineItem>``; the JVM contract throws
        ``NoSuchElementException`` when the chain is exhausted. In Python
        the protocol is :meth:`__next__` + ``StopIteration``, so we keep
        the existing implementation as the source of truth and surface
        ``next`` as an alias for ported callers."""
        return self.__next__()

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
