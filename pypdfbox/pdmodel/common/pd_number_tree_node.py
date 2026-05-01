from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
)

_LOG = logging.getLogger(__name__)

_KIDS: COSName = COSName.KIDS  # type: ignore[attr-defined]
_NUMS: COSName = COSName.get_pdf_name("Nums")
_LIMITS: COSName = COSName.get_pdf_name("Limits")
_MAX_NUMS = 64


class PDNumberTreeNode[T](ABC):
    """
    Generic number-tree node wrapper. Mirrors PDFBox ``PDNumberTreeNode``.

    A number tree (PDF Reference 1.7 section 7.9.7) is the integer-keyed
    cousin of the name tree, used for ``/PageLabels`` and the structure
    tree's ``/ParentTree``. The on-disk layout is the same nested
    ``/Kids`` / ``/Nums`` / ``/Limits`` shape but keys are integers.

    Subclasses provide the value type by implementing
    ``convert_cos_to_value``, ``convert_value_to_cos``, and
    ``create_child_node``.
    """

    def __init__(self, node: COSDictionary | None = None) -> None:
        self._node: COSDictionary = node if node is not None else COSDictionary()
        self._parent: PDNumberTreeNode[T] | None = None

    # ---------- COS plumbing ----------

    def get_cos_object(self) -> COSDictionary:
        return self._node

    # ---------- parent / root ----------

    def get_parent(self) -> PDNumberTreeNode[T] | None:
        return self._parent

    def set_parent(self, parent: PDNumberTreeNode[T] | None) -> None:
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
    def create_child_node(self, dic: COSDictionary) -> PDNumberTreeNode[T]:
        """Create a child node of the same concrete subclass type."""

    # ---------- /Kids ----------

    def get_kids(self) -> list[PDNumberTreeNode[T]] | None:
        kids = self._node.get_dictionary_object(_KIDS)
        if not isinstance(kids, COSArray):
            return None
        out: list[PDNumberTreeNode[T]] = []
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

    def set_kids(self, kids: list[PDNumberTreeNode[T]] | None) -> None:
        if kids:
            for kid in kids:
                kid.set_parent(self)
            arr = COSArray()
            for kid in kids:
                arr.add(kid.get_cos_object())
            self._node.set_item(_KIDS, arr)
            # root nodes with kids do not have Nums
            if self.is_root_node():
                self._node.remove_item(_NUMS)
        else:
            self._node.remove_item(_KIDS)
            self._node.remove_item(_LIMITS)
        self._calculate_limits()

    # ---------- /Nums ----------

    def get_numbers(self) -> dict[int, T] | None:
        numbers_array = self._node.get_dictionary_object(_NUMS)
        if isinstance(numbers_array, COSArray):
            return self._read_numbers_array(numbers_array)

        kids = self.get_kids()
        if kids is None:
            return None
        out: dict[int, T] = {}
        for child in kids:
            child_numbers = child.get_numbers()
            if child_numbers is None:
                continue
            out.update(child_numbers)
        return dict(sorted(out.items()))

    def set_numbers(self, numbers: dict[int, T] | None) -> None:
        if numbers is None:
            self._node.remove_item(_NUMS)
            self._node.remove_item(_LIMITS)
            self._notify_parent_limits_changed()
            return

        if self.is_root_node() and len(numbers) > _MAX_NUMS:
            keys = sorted(numbers)
            kids: list[PDNumberTreeNode[T]] = []
            for i in range(0, len(keys), _MAX_NUMS):
                child = self.create_child_node(COSDictionary())
                child._set_numbers_leaf({key: numbers[key] for key in keys[i : i + _MAX_NUMS]})
                kids.append(child)
            self.set_kids(kids)
            return

        self._node.remove_item(_KIDS)
        self._set_numbers_leaf(numbers)

    def _set_numbers_leaf(self, numbers: dict[int, T]) -> None:
        arr = COSArray()
        keys = sorted(numbers)
        for key in keys:
            arr.add(COSInteger.get(key))
            value = numbers[key]
            if value is None:
                arr.add(COSNull.NULL)
            else:
                arr.add(self.convert_value_to_cos(value))
        self._node.set_item(_NUMS, arr)
        self._calculate_limits()
        self._notify_parent_limits_changed()

    # ---------- value lookup (descent through /Limits) ----------

    def get_value(self, index: int) -> T | None:
        numbers = self.get_numbers()
        if numbers is not None:
            return numbers.get(index)
        kids = self.get_kids()
        if kids is not None:
            for child in kids:
                lower = child.get_lower_limit()
                upper = child.get_upper_limit()
                if lower is not None and upper is not None and lower <= index <= upper:
                    return child.get_value(index)
        else:
            _LOG.warning('NumberTreeNode does not have "nums" nor "kids" objects.')
        return None

    def get_number(self, index: int) -> T | None:
        """Alias for :meth:`get_value` matching the PDFBox accessor name."""
        return self.get_value(index)

    def get_number_of_values(self) -> int:
        """Total leaf-value count across this subtree.

        Counterpart of :meth:`PDNameTreeNode.get_number_of_values` — the
        on-disk format does not record subtree sizes, so we recurse through
        ``/Kids``.
        """
        numbers_array = self._node.get_dictionary_object(_NUMS)
        if isinstance(numbers_array, COSArray):
            return numbers_array.size() // 2
        kids = self.get_kids()
        if not kids:
            return 0
        return sum(child.get_number_of_values() for child in kids)

    def __contains__(self, index: object) -> bool:
        if not isinstance(index, int) or isinstance(index, bool):
            # ``bool`` is a subclass of ``int`` in Python; PDF number-tree
            # keys are integers, not booleans, so reject the surprising
            # ``True in tree`` case explicitly.
            return False
        return self.get_value(index) is not None

    # ---------- /Limits ----------

    def get_lower_limit(self) -> int | None:
        arr = self._node.get_dictionary_object(_LIMITS)
        if isinstance(arr, COSArray) and arr.size() >= 1:
            entry = arr.get_object(0)
            if isinstance(entry, COSInteger):
                return int(entry.value)
        return None

    def set_lower_limit(self, lower: int | None) -> None:
        arr = self._ensure_limits_array()
        if lower is not None:
            arr.set_int(0, lower)
        else:
            arr.set(0, COSNull.NULL)

    def get_upper_limit(self) -> int | None:
        arr = self._node.get_dictionary_object(_LIMITS)
        if isinstance(arr, COSArray) and arr.size() >= 2:
            entry = arr.get_object(1)
            if isinstance(entry, COSInteger):
                return int(entry.value)
        return None

    def set_upper_limit(self, upper: int | None) -> None:
        arr = self._ensure_limits_array()
        if upper is not None:
            arr.set_int(1, upper)
        else:
            arr.set(1, COSNull.NULL)

    # ---------- internal ----------

    def _ensure_limits_array(self) -> COSArray:
        arr = self._node.get_dictionary_object(_LIMITS)
        if not isinstance(arr, COSArray):
            arr = COSArray()
            arr.add(COSNull.NULL)
            arr.add(COSNull.NULL)
            self._node.set_item(_LIMITS, arr)
        return arr

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
        numbers_array = self._node.get_dictionary_object(_NUMS)
        numbers = (
            self._read_numbers_array(numbers_array)
            if isinstance(numbers_array, COSArray)
            else None
        )
        if numbers:
            keys = sorted(numbers.keys())
            self.set_lower_limit(keys[0])
            self.set_upper_limit(keys[-1])
        else:
            self._node.remove_item(_LIMITS)

    def _read_numbers_array(self, numbers_array: COSArray) -> dict[int, T] | None:
        size = numbers_array.size()
        if size % 2 != 0:
            _LOG.warning("Numbers array has odd size: %d", size)
        out: dict[int, T] = {}
        i = 0
        while i + 1 < size:
            base = numbers_array.get_object(i)
            if not isinstance(base, COSInteger):
                _LOG.error(
                    "page labels ignored, index %d should be a number, but is %r",
                    i,
                    base,
                )
                return None
            cos_value = numbers_array.get_object(i + 1)
            out[int(base.value)] = self.convert_cos_to_value(cos_value)  # type: ignore[arg-type]
            i += 2
        return out

    def _notify_parent_limits_changed(self) -> None:
        parent = self._parent
        while parent is not None:
            parent._calculate_limits()
            parent = parent._parent


__all__ = ["PDNumberTreeNode"]
