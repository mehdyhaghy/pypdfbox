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

    def __init__(self, node: COSDictionary | None = None) -> None:
        self._node: COSDictionary = node if node is not None else COSDictionary()
        self._parent: PDNameTreeNode[T] | None = None

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
                if (
                    upper is None
                    or lower is None
                    or upper < lower
                    or (lower <= name <= upper)
                ):
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
            out[base.get_string()] = self.convert_cos_to_value(cos_value)  # type: ignore[arg-type]
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


__all__ = ["PDNameTreeNode"]
