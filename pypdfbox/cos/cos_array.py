from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from .cos_base import COSBase
from .cos_object import COSObject
from .i_cos_visitor import ICOSVisitor


class COSArray(COSBase):
    """
    PDF array — ordered sequence of ``COSBase`` values. Indirect references
    are stored as ``COSObject`` instances and only dereferenced through
    ``get_object(index)`` (cf. ``get(index)`` which returns the raw entry).
    """

    def __init__(self, items: Iterable[COSBase] | None = None) -> None:
        super().__init__()
        self._items: list[COSBase] = list(items) if items is not None else []

    # ---------- core list operations ----------

    def add(self, item: COSBase) -> None:
        self._items.append(item)

    def add_at(self, index: int, item: COSBase) -> None:
        self._items.insert(index, item)

    def add_all(self, items: Iterable[COSBase]) -> None:
        self._items.extend(items)

    def get(self, index: int) -> COSBase:
        """Raw entry at ``index`` — may be a ``COSObject`` indirect ref."""
        return self._items[index]

    def get_object(self, index: int) -> COSBase | None:
        """Resolved entry — if the entry is a ``COSObject``, returns its
        target; otherwise returns the entry itself."""
        item = self._items[index]
        if isinstance(item, COSObject):
            return item.get_object()
        return item

    def set(self, index: int, item: COSBase) -> None:
        self._items[index] = item

    def remove(self, item: COSBase) -> bool:
        try:
            self._items.remove(item)
            return True
        except ValueError:
            return False

    def remove_at(self, index: int) -> COSBase:
        return self._items.pop(index)

    def clear(self) -> None:
        self._items.clear()

    def size(self) -> int:
        return len(self._items)

    def is_empty(self) -> bool:
        return not self._items

    def contains(self, item: COSBase) -> bool:
        return item in self._items

    def to_list(self) -> list[COSBase]:
        """Return a defensive copy of the underlying list."""
        return list(self._items)

    def index_of(self, item: COSBase) -> int:
        """``index_of`` mirrors PDFBox; returns -1 if not present."""
        try:
            return self._items.index(item)
        except ValueError:
            return -1

    # ---------- visitor / Python protocols ----------

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_array(self)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[COSBase]:
        return iter(self._items)

    def __getitem__(self, index: int) -> COSBase:
        return self._items[index]

    def __contains__(self, item: object) -> bool:
        return item in self._items

    def __repr__(self) -> str:
        return f"COSArray({self._items!r})"
