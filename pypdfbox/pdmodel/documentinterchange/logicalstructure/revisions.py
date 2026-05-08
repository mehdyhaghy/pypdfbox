from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

from pypdfbox.cos import COSArray, COSBase, COSInteger


class Revisions[T]:
    """
    Helper that pairs values with PDF revision numbers. Mirrors PDFBox
    ``Revisions<T>`` (used by ``PDStructureElement`` for ``/A`` attribute
    objects and ``/C`` class names).

    Storage: a flat ``COSArray`` of ``[value, revision_int, value,
    revision_int, ...]``. The trailing ``revision_int`` is omitted on the
    PDF side when the revision is ``0``; newly-added entries keep both slots
    populated while existing compact arrays are read in place.
    """

    def __init__(self, array: COSArray | None = None) -> None:
        self._array: COSArray = array if array is not None else COSArray()

    def add_object(self, value: T, revision_number: int = 0) -> None:
        if revision_number < 0:
            raise ValueError("Revision number must be > -1")
        self._array.add(_to_cos(value))
        self._array.add(COSInteger.get(revision_number))

    def get_object_at(self, index: int) -> Any:
        return self._array.get_object(self._entry_offset(index))

    def get_revision_number_at(self, index: int) -> int:
        revision_offset = self._revision_offset(index)
        if revision_offset is None:
            return 0
        entry = self._array.get_object(revision_offset)
        if isinstance(entry, COSInteger):
            return entry.int_value()
        return 0

    def get_revision_number(self, value: Any) -> int:
        """Return the revision number paired with ``value``, or ``-1`` when
        ``value`` is not present.

        pypdfbox addition: companion to upstream's
        ``Revisions.setRevisionNumber(T, int)`` object-based locator.
        Upstream exposes only the index-based ``getRevisionNumber(int)``
        but consumers (``PDStructureElement.attribute_changed``) need to
        find a revision number by object identity. Equality follows
        :meth:`index_of` (identity first, then ``__eq__``).
        """
        idx = self.index_of(value)
        if idx == -1:
            return -1
        return self.get_revision_number_at(idx)

    def set_object_at(self, index: int, value: T) -> None:
        if index < 0 or index >= self.size():
            raise IndexError(index)
        self._array.set(self._entry_offset(index), _to_cos(value))

    def set_revision_number_at(self, index: int, revision_number: int) -> None:
        if index < 0 or index >= self.size():
            raise IndexError(index)
        if revision_number < 0:
            raise ValueError("Revision number must be > -1")
        revision_offset = self._revision_offset(index)
        if revision_offset is None:
            self._array.add_at(
                self._entry_offset(index) + 1, COSInteger.get(revision_number)
            )
            return
        self._array.set(revision_offset, COSInteger.get(revision_number))

    def set_revision_number(self, value: T, revision_number: int) -> None:
        """Update the revision number paired with ``value``.

        Mirrors upstream ``Revisions.setRevisionNumber(T object, int
        revisionNumber)``: when ``value`` is found via :meth:`index_of`
        the paired revision is updated; when it isn't, the call is a
        silent no-op (matching upstream's ``index > -1`` guard). Negative
        revisions are rejected (matches :meth:`set_revision_number_at`).
        """
        if revision_number < 0:
            raise ValueError("Revision number must be > -1")
        idx = self.index_of(value)
        if idx == -1:
            return
        self.set_revision_number_at(idx, revision_number)

    def size(self) -> int:
        return len(self._entry_offsets())

    def is_empty(self) -> bool:
        return self.size() == 0

    def clear(self) -> None:
        self._array.clear()

    def contains(self, value: Any) -> bool:
        return self.index_of(value) != -1

    def index_of(self, value: Any) -> int:
        target = _to_cos(value)
        for i in range(self.size()):
            item = self._array.get_object(self._entry_offset(i))
            if item is target or item == target:
                return i
        return -1

    def remove_at(self, index: int) -> Any:
        if index < 0 or index >= self.size():
            raise IndexError(index)
        object_offset = self._entry_offset(index)
        value = self._array.get_object(object_offset)
        revision_offset = self._revision_offset(index)
        # Remove revision slot first when present (higher index) so the object
        # slot index stays valid for the second removal.
        if revision_offset is not None:
            self._array.remove_at(revision_offset)
        self._array.remove_at(object_offset)
        return value

    def to_cos_array(self) -> COSArray:
        return self._array

    @classmethod
    def from_cos_array(cls, array: COSArray) -> Revisions[Any]:
        return cls(array)

    def iterator(self) -> Iterator[Any]:
        return iter(self)

    def __iter__(self) -> Iterator[Any]:
        for i in range(self.size()):
            yield self.get_object_at(i)

    def __len__(self) -> int:
        return self.size()

    def __repr__(self) -> str:
        parts = [
            f"object={self.get_object_at(i)}, revisionNumber={self.get_revision_number_at(i)}"
            for i in range(self.size())
        ]
        return "{" + "; ".join(parts) + "}"

    def _entry_offsets(self) -> list[int]:
        """Return raw COSArray offsets for objects in compact revision arrays."""
        offsets: list[int] = []
        i = 0
        while i < self._array.size():
            offsets.append(i)
            next_i = i + 1
            if next_i < self._array.size() and isinstance(
                self._array.get_object(next_i), COSInteger
            ):
                i += 2
            else:
                i += 1
        return offsets

    def _entry_offset(self, index: int) -> int:
        offsets = self._entry_offsets()
        if index < 0 or index >= len(offsets):
            raise IndexError(index)
        return offsets[index]

    def _revision_offset(self, index: int) -> int | None:
        object_offset = self._entry_offset(index)
        revision_offset = object_offset + 1
        if revision_offset >= self._array.size():
            return None
        if isinstance(self._array.get_object(revision_offset), COSInteger):
            return revision_offset
        return None


def _to_cos(value: Any) -> COSBase:
    if hasattr(value, "get_cos_object"):
        return cast(COSBase, value.get_cos_object())
    return cast(COSBase, value)


__all__ = ["Revisions"]
