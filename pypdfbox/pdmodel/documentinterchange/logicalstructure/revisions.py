from __future__ import annotations

from typing import Any, Generic, Iterator, TypeVar

from pypdfbox.cos import COSArray, COSBase, COSInteger

T = TypeVar("T")


class Revisions(Generic[T]):
    """
    Helper that pairs values with PDF revision numbers. Mirrors PDFBox
    ``Revisions<T>`` (used by ``PDStructureElement`` for ``/A`` attribute
    objects and ``/C`` class names).

    Storage: a flat ``COSArray`` of ``[value, revision_int, value,
    revision_int, ...]``. The trailing ``revision_int`` is omitted on the
    PDF side when the revision is ``0``, but for in-memory simplicity the
    helper keeps both slots populated.
    """

    def __init__(self, array: COSArray | None = None) -> None:
        self._array: COSArray = array if array is not None else COSArray()

    def add_object(self, value: T, revision_number: int = 0) -> None:
        self._array.add(_to_cos(value))
        self._array.add(COSInteger.get(revision_number))

    def get_object_at(self, index: int) -> Any:
        return self._array.get_object(index * 2)

    def get_revision_number_at(self, index: int) -> int:
        entry = self._array.get_object(index * 2 + 1)
        if isinstance(entry, COSInteger):
            return entry.int_value()
        return 0

    def set_object_at(self, index: int, value: T) -> None:
        if index < 0 or index >= self.size():
            raise IndexError(index)
        self._array.set(index * 2, _to_cos(value))

    def set_revision_number_at(self, index: int, revision_number: int) -> None:
        if index < 0 or index >= self.size():
            raise IndexError(index)
        if revision_number < 0:
            raise ValueError("Revision number must be > -1")
        self._array.set(index * 2 + 1, COSInteger.get(revision_number))

    def size(self) -> int:
        return self._array.size() // 2

    def is_empty(self) -> bool:
        return self.size() == 0

    def clear(self) -> None:
        self._array.clear()

    def contains(self, value: Any) -> bool:
        return self.index_of(value) != -1

    def index_of(self, value: Any) -> int:
        target = _to_cos(value)
        for i in range(self.size()):
            if self._array.get_object(i * 2) is target or self._array.get_object(i * 2) == target:
                return i
        return -1

    def remove_at(self, index: int) -> Any:
        if index < 0 or index >= self.size():
            raise IndexError(index)
        value = self._array.get_object(index * 2)
        # Remove revision slot first (higher index) so the object slot index
        # stays valid for the second removal.
        self._array.remove_at(index * 2 + 1)
        self._array.remove_at(index * 2)
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


def _to_cos(value: Any) -> COSBase:
    if hasattr(value, "get_cos_object"):
        return value.get_cos_object()
    return value


__all__ = ["Revisions"]
