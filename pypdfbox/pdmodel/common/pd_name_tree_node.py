from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSNull, COSString

_LOG = logging.getLogger(__name__)

_KIDS: COSName = COSName.KIDS  # type: ignore[attr-defined]
_NAMES: COSName = COSName.get_pdf_name("Names")
_LIMITS: COSName = COSName.get_pdf_name("Limits")
_MAX_NAMES_IN_LEAF = 64
_MAX_KIDS_IN_NODE = 64


class PDNameTreeNode[T](ABC):
    """
    Generic name-tree node wrapper. Mirrors PDFBox ``PDNameTreeNode<T>``.

    A name tree is the PDF ordered map structure (``/Kids``-vs-``/Names``
    dictionaries with ``/Limits``) used for ``/JavaScript``, ``/Dests``,
    ``/EmbeddedFiles`` and similar catalog name dictionaries. Subclasses
    provide the value type by implementing ``convert_cos_to_value``,
    ``convert_value_to_cos``, and ``create_child_node``.
    """

    def __init__(
        self,
        node: COSDictionary | None = None,
        value_type: type | None = None,
    ) -> None:
        self._node: COSDictionary = node if node is not None else COSDictionary()
        self._parent: PDNameTreeNode[T] | None = None
        # Mirrors PDFBox's ``Class<? extends T> valueType`` constructor
        # parameter. Concrete subclasses already pin ``T``; the field is
        # exposed so dynamic factories that build typed name trees from a
        # raw COSDictionary can inspect/round-trip the leaf value class.
        self._value_type: type | None = value_type

    # ---------- COS plumbing ----------

    def get_cos_object(self) -> COSDictionary:
        return self._node

    # ---------- parent / root ----------

    def get_parent(self) -> PDNameTreeNode[T] | None:
        return self._parent

    def set_parent(self, parent: PDNameTreeNode[T] | None) -> None:
        self._parent = parent
        self._calculate_limits()

    def is_root_node(self) -> bool:
        return self._parent is None

    def is_leaf_node(self) -> bool:
        """``True`` when this node carries ``/Names`` directly (no
        ``/Kids`` array). PDF name trees are required to be either a leaf
        (``/Names`` is the value mapping) or an intermediate node
        (``/Kids`` references child nodes), but never both at the same
        level. Mirrors the upstream-implied predicate used by traversal
        helpers."""
        return self._node.contains_key(_NAMES) and not self._node.contains_key(_KIDS)

    def is_intermediate_node(self) -> bool:
        """``True`` when this node carries ``/Kids`` (no ``/Names``).
        Complement of :meth:`is_leaf_node` for nodes that have been
        populated; an empty (freshly-constructed) node is neither."""
        return self._node.contains_key(_KIDS) and not self._node.contains_key(_NAMES)

    def has_names(self) -> bool:
        """``True`` when this node carries a leaf ``/Names`` entry.

        Unlike :meth:`is_leaf_node`, this predicate does not also require
        the absence of ``/Kids`` — useful for raw-shape inspection of a
        partially-built or malformed dictionary. Mirrors
        :meth:`PDNumberTreeNode.has_numbers`."""
        return isinstance(self._node.get_dictionary_object(_NAMES), COSArray)

    def has_kids(self) -> bool:
        """``True`` when this node carries a ``/Kids`` entry.

        Mirrors :meth:`PDNumberTreeNode.has_kids`."""
        return isinstance(self._node.get_dictionary_object(_KIDS), COSArray)

    def has_limits(self) -> bool:
        """``True`` when this node carries a ``/Limits`` entry.

        A root node never carries ``/Limits`` per PDF Reference 1.7
        §7.9.6; intermediate and leaf nodes do once they have content.
        Mirrors :meth:`PDNumberTreeNode.has_limits`."""
        return isinstance(self._node.get_dictionary_object(_LIMITS), COSArray)

    # ---------- value type plumbing ----------

    def get_value_type(self) -> type | None:
        """The ``Class<? extends T>`` PDFBox stores at construction.

        Concrete subclasses pin ``T`` and may safely return ``None`` here;
        the value is purely informational and is never inspected by the
        base class behaviour.
        """
        return self._value_type

    # ---------- subclass extension points ----------

    @abstractmethod
    def convert_cos_to_value(self, base: COSBase) -> T:
        """Convert a COS leaf value into the subclass's value type."""

    @abstractmethod
    def convert_value_to_cos(self, value: T) -> COSBase:
        """Convert a subclass value into its COS representation."""

    @abstractmethod
    def create_child_node(self, dic: COSDictionary) -> PDNameTreeNode[T]:
        """Create a child node of the same concrete subclass type."""

    # ---------- /Kids ----------

    def get_kids(self) -> list[PDNameTreeNode[T]] | None:
        kids = self._node.get_dictionary_object(_KIDS)
        if not isinstance(kids, COSArray):
            return None
        out: list[PDNameTreeNode[T]] = []
        for i in range(kids.size()):
            base = kids.get_object(i)
            if isinstance(base, COSDictionary):
                child = self.create_child_node(base)
            else:
                _LOG.warning("Bad child node at position %d", i)
                child = self.create_child_node(COSDictionary())
            child._parent = self
            out.append(child)
        return out

    def set_kids(self, kids: list[PDNameTreeNode[T]] | None) -> None:
        if kids:
            for kid in kids:
                kid.set_parent(self)
            arr = COSArray()
            for kid in kids:
                arr.add(kid.get_cos_object())
            self._node.set_item(_KIDS, arr)
            self._node.remove_item(_NAMES)
        else:
            self._node.remove_item(_KIDS)
            self._node.remove_item(_LIMITS)
        self._calculate_limits()
        self._notify_parent_limits_changed()

    # ---------- /Names ----------

    def get_names(self) -> dict[str, T] | None:
        names_array = self._node.get_dictionary_object(_NAMES)
        if isinstance(names_array, COSArray):
            return self._read_names_array(names_array)
        kids = self.get_kids()
        if kids is None:
            return None
        out = {}
        for child in kids:
            child_names = child.get_names()
            if child_names:
                out.update(child_names)
        return out

    def set_names(self, names: dict[str, T] | None) -> None:
        if names is None:
            self._node.remove_item(_NAMES)
            self._node.remove_item(_LIMITS)
            self._notify_parent_limits_changed()
            return
        if len(names) > _MAX_NAMES_IN_LEAF:
            self.set_kids(self._build_balanced_kids(names))
            return
        arr = COSArray()
        for key in sorted(names):
            arr.add(COSString(key))
            arr.add(self.convert_value_to_cos(names[key]))
        self._node.remove_item(_KIDS)
        self._node.set_item(_NAMES, arr)
        self._calculate_limits()
        self._notify_parent_limits_changed()

    # ---------- value lookup (binary descent through /Limits) ----------

    def get_value(self, name: str) -> T | None:
        names_array = self._node.get_dictionary_object(_NAMES)
        if isinstance(names_array, COSArray):
            return self._read_names_array(names_array).get(name)
        kids = self.get_kids()
        if kids is not None:
            for child in kids:
                upper = child.get_upper_limit()
                lower = child.get_lower_limit()
                if upper is None or lower is None or upper < lower:
                    value = child.get_value(name)
                    if value is not None:
                        return value
                    continue
                if lower <= name <= upper:
                    return child.get_value(name)
        else:
            _LOG.warning('NameTreeNode does not have "Names" nor "Kids" objects.')
        return None

    # ---------- /Limits ----------

    def get_lower_limit(self) -> str | None:
        arr = self._node.get_dictionary_object(_LIMITS)
        if isinstance(arr, COSArray) and arr.size() >= 1:
            return arr.get_string(0)
        return None

    def set_lower_limit(self, lower: str | None) -> None:
        arr = self._ensure_limits_array()
        arr.set(0, COSString(lower) if lower is not None else COSNull.NULL)

    def get_upper_limit(self) -> str | None:
        arr = self._node.get_dictionary_object(_LIMITS)
        if isinstance(arr, COSArray) and arr.size() >= 2:
            return arr.get_string(1)
        return None

    def set_upper_limit(self, upper: str | None) -> None:
        arr = self._ensure_limits_array()
        arr.set(1, COSString(upper) if upper is not None else COSNull.NULL)

    # ---------- internal ----------

    def _ensure_limits_array(self) -> COSArray:
        arr = self._node.get_dictionary_object(_LIMITS)
        if not isinstance(arr, COSArray):
            arr = COSArray()
            arr.add(COSNull.NULL)
            arr.add(COSNull.NULL)
            self._node.set_item(_LIMITS, arr)
        return arr

    def _read_names_array(self, names_array: COSArray) -> dict[str, T]:
        size = names_array.size()
        if size % 2 != 0:
            _LOG.warning("Names array has odd size: %d", size)
        out: dict[str, T] = {}
        i = 0
        while i + 1 < size:
            base = names_array.get_object(i)
            if not isinstance(base, COSString):
                raise OSError(
                    f"Expected string, found {base!r} in name tree at index {i}"
                )
            cos_value = names_array.get_object(i + 1)
            if cos_value is None:
                raise OSError(f"Expected COS value in name tree at index {i + 1}")
            out[base.get_string()] = self.convert_cos_to_value(cos_value)
            i += 2
        return out

    def _set_leaf_names(self, names: dict[str, T]) -> None:
        arr = COSArray()
        for key in sorted(names):
            arr.add(COSString(key))
            arr.add(self.convert_value_to_cos(names[key]))
        self._node.remove_item(_KIDS)
        self._node.set_item(_NAMES, arr)
        self._calculate_limits()
        self._notify_parent_limits_changed()

    def _build_balanced_kids(self, names: dict[str, T]) -> list[PDNameTreeNode[T]]:
        sorted_keys = sorted(names)
        level: list[PDNameTreeNode[T]] = []
        for i in range(0, len(sorted_keys), _MAX_NAMES_IN_LEAF):
            chunk_keys = sorted_keys[i : i + _MAX_NAMES_IN_LEAF]
            leaf = self.create_child_node(COSDictionary())
            leaf._set_leaf_names({key: names[key] for key in chunk_keys})
            level.append(leaf)
        while len(level) > _MAX_KIDS_IN_NODE:
            next_level: list[PDNameTreeNode[T]] = []
            for i in range(0, len(level), _MAX_KIDS_IN_NODE):
                child = self.create_child_node(COSDictionary())
                child.set_kids(level[i : i + _MAX_KIDS_IN_NODE])
                next_level.append(child)
            level = next_level
        return level

    # ---------- removal & merge helpers ----------

    def remove_names(self) -> None:
        """Drop the ``/Names`` and ``/Limits`` entries from this node.

        Equivalent to ``set_names(None)``; provided as a verb-shaped helper
        for parity with other PDFBox-style remove_* APIs and for callers
        that want a no-arg cleanup without recomputing the limits walk.
        """
        self._node.remove_item(_NAMES)
        self._node.remove_item(_LIMITS)
        self._notify_parent_limits_changed()

    def clear_names(self) -> None:
        """Clear the ``/Names`` entry.

        Alias for :meth:`remove_names`, matching the local ``clear_*``
        helper naming used by newer PD model wrappers.
        """
        self.remove_names()

    def remove_kids(self) -> None:
        """Drop the ``/Kids`` and ``/Limits`` entries from this node."""
        self._node.remove_item(_KIDS)
        self._node.remove_item(_LIMITS)
        self._notify_parent_limits_changed()

    def clear_kids(self) -> None:
        """Clear the ``/Kids`` entry.

        Alias for :meth:`remove_kids`, matching the local ``clear_*``
        helper naming used by newer PD model wrappers.
        """
        self.remove_kids()

    def clear(self) -> None:
        """Drop ``/Names``, ``/Kids`` and ``/Limits`` from this node.

        Verb-shaped helper for callers that want to reset a node to its
        empty state without inspecting which arm (leaf-vs-intermediate)
        is currently populated. Equivalent to calling :meth:`remove_names`
        and :meth:`remove_kids` back-to-back."""
        self._node.remove_item(_NAMES)
        self._node.remove_item(_KIDS)
        self._node.remove_item(_LIMITS)
        self._notify_parent_limits_changed()

    def merge(self, other: PDNameTreeNode[T] | dict[str, T] | None) -> None:
        """Merge ``other`` into this node, overwriting on key collisions.

        Accepts either another ``PDNameTreeNode`` (whose flattened
        name-to-value mapping is read via ``get_names``) or a plain
        ``dict[str, T]``. The result is rebalanced through ``set_names``,
        which preserves the leaf-vs-kids decision based on cardinality.
        """
        if other is None:
            return
        other_names = (
            other.get_names() or {}
            if isinstance(other, PDNameTreeNode)
            else dict(other)
        )
        if not other_names:
            return
        existing = self.get_names() or {}
        existing.update(other_names)
        self.set_names(existing)

    def get_number_of_values(self) -> int:
        """Total leaf-value count across this subtree.

        Mirrors a common PDFBox idiom of asking "how big is this name
        tree" without materialising every leaf. We still walk children
        because the on-disk format does not record subtree sizes.
        """
        names_array = self._node.get_dictionary_object(_NAMES)
        if isinstance(names_array, COSArray):
            return names_array.size() // 2
        kids = self.get_kids()
        if not kids:
            return 0
        return sum(child.get_number_of_values() for child in kids)

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        return self.get_value(name) is not None

    # ---------- internal ----------

    def _calculate_limits(self) -> None:
        if self.is_root_node():
            self._node.remove_item(_LIMITS)
            return
        kids = self.get_kids()
        if kids:
            first_kid = kids[0]
            last_kid = kids[-1]
            self.set_lower_limit(first_kid.get_lower_limit())
            self.set_upper_limit(last_kid.get_upper_limit())
            return
        try:
            names = self.get_names()
        except OSError:
            self._node.remove_item(_LIMITS)
            _LOG.exception("Error while calculating the Limits of a name tree node")
            return
        if names:
            keys = list(names.keys())
            self.set_lower_limit(keys[0])
            self.set_upper_limit(keys[-1])
        else:
            self._node.remove_item(_LIMITS)

    def _notify_parent_limits_changed(self) -> None:
        parent = self._parent
        while parent is not None:
            parent._calculate_limits()
            parent = parent._parent


__all__ = ["PDNameTreeNode"]
