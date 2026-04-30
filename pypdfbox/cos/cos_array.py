from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from .cos_base import COSBase
from .cos_float import COSFloat
from .cos_integer import COSInteger
from .cos_name import COSName
from .cos_null import COSNull
from .cos_object import COSObject
from .cos_string import COSString
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
            item = item.get_object()
        if item is COSNull.NULL:
            return None
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

    def index_of_object(self, item: COSBase) -> int:
        """Return the index of ``item``, resolving indirect object entries."""
        for index, candidate in enumerate(self._items):
            if candidate == item:
                return index
            if isinstance(candidate, COSObject) and candidate.get_object() == item:
                return index
        return -1

    def remove_object(self, item: COSBase) -> bool:
        """Remove the first matching item; alias for ``remove`` returning a bool."""
        return self.remove(item)

    def remove_all(self, items: Iterable[COSBase]) -> bool:
        """Remove every occurrence of each ``items`` entry. Returns ``True``
        if at least one entry was removed."""
        changed = False
        for item in items:
            while item in self._items:
                self._items.remove(item)
                changed = True
        return changed

    def retain_all(self, items: Iterable[COSBase]) -> bool:
        """Keep only entries also present in ``items``. Returns ``True`` if
        the array changed."""
        keep = list(items)
        before = len(self._items)
        self._items = [x for x in self._items if x in keep]
        return len(self._items) != before

    def grow_to_size(self, size: int, fill: COSBase | None = None) -> None:
        """Pad the array with ``fill`` (default ``None``) until it has at
        least ``size`` entries."""
        while len(self._items) < size:
            self._items.append(fill)  # type: ignore[arg-type]

    # ---------- typed convenience accessors ----------

    def set_name(self, index: int, value: str) -> None:
        self.grow_to_size(index + 1)
        self._items[index] = COSName.get_pdf_name(value)

    def get_name(self, index: int, default: str | None = None) -> str | None:
        if index >= len(self._items):
            return default
        item = self._items[index]
        if isinstance(item, COSName):
            return item.get_name()
        return default

    def set_int(self, index: int, value: int) -> None:
        self.grow_to_size(index + 1)
        self._items[index] = COSInteger.get(value)

    def get_int(self, index: int, default: int = -1) -> int:
        if index >= len(self._items):
            return default
        item = self._items[index]
        if isinstance(item, COSInteger):
            return item.value
        if isinstance(item, COSFloat):
            return int(item.value)
        return default

    def set_float(self, index: int, value: float) -> None:
        self.grow_to_size(index + 1)
        self._items[index] = COSFloat(value)

    def get_float(self, index: int, default: float = -1.0) -> float:
        if index >= len(self._items):
            return default
        item = self._items[index]
        if isinstance(item, (COSInteger, COSFloat)):
            return float(item.value)
        return default

    def set_string(self, index: int, value: str) -> None:
        self.grow_to_size(index + 1)
        self._items[index] = COSString(value)

    def get_string(self, index: int, default: str | None = None) -> str | None:
        if index >= len(self._items):
            return default
        item = self._items[index]
        if isinstance(item, COSString):
            return item.get_string()
        return default

    def set_float_array(self, values: Iterable[float]) -> None:
        """Replace contents with ``COSFloat`` instances built from ``values``."""
        self._items = [COSFloat(v) for v in values]

    def to_float_array(self) -> list[float]:
        """Convert numeric entries to floats; ``None`` entries become ``0``."""
        out: list[float] = []
        for item in self._items:
            if isinstance(item, (COSInteger, COSFloat)):
                out.append(float(item.value))
            else:
                out.append(0.0)
        return out

    def to_cos_name_string_list(self) -> list[str | None]:
        """Convert ``COSName`` entries to their string form. Non-name entries
        become ``None``."""
        out: list[str | None] = []
        for item in self._items:
            out.append(item.get_name() if isinstance(item, COSName) else None)
        return out

    def to_cos_string_string_list(self) -> list[str | None]:
        """Convert ``COSString`` entries to their decoded text. Non-string
        entries become ``None``."""
        out: list[str | None] = []
        for item in self._items:
            out.append(item.get_string() if isinstance(item, COSString) else None)
        return out

    def to_cos_number_integer_list(self) -> list[int | None]:
        """Convert numeric entries to ``int``; non-numeric entries become ``None``."""
        out: list[int | None] = []
        for item in self._items:
            if isinstance(item, (COSInteger, COSFloat)):
                out.append(int(item.value))
            else:
                out.append(None)
        return out

    def to_cos_number_float_list(self) -> list[float | None]:
        """Convert numeric entries to ``float``; non-numeric entries become ``None``."""
        out: list[float | None] = []
        for item in self._items:
            if isinstance(item, (COSInteger, COSFloat)):
                out.append(float(item.value))
            else:
                out.append(None)
        return out

    # ---------- factory constructors ----------

    @classmethod
    def of_cos_names(cls, names: Iterable[str]) -> COSArray:
        return cls([COSName.get_pdf_name(n) for n in names])

    @classmethod
    def of_cos_strings(cls, strings: Iterable[str]) -> COSArray:
        return cls([COSString(s) for s in strings])

    @classmethod
    def of_cos_integers(cls, ints: Iterable[int]) -> COSArray:
        return cls([COSInteger.get(i) for i in ints])

    @classmethod
    def of_cos_floats(cls, floats: Iterable[float]) -> COSArray:
        return cls([COSFloat(f) for f in floats])

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
