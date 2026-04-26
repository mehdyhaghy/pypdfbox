from __future__ import annotations

from typing import Any, Generic, TypeVar

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

    def size(self) -> int:
        return self._array.size() // 2

    def to_cos_array(self) -> COSArray:
        return self._array

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
