from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from .cos_base import COSBase
from .cos_boolean import COSBoolean
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

    def addAll(self, items: Iterable[COSBase]) -> None:  # noqa: N802 - upstream Java name
        self.add_all(items)

    def get(self, index: int) -> COSBase:
        """Raw entry at ``index`` — may be a ``COSObject`` indirect ref."""
        return self._items[index]

    @staticmethod
    def _resolve(item: COSBase) -> COSBase | None:
        if isinstance(item, COSObject):
            resolved = item.get_object()
            item = COSNull.NULL if resolved is None else resolved
        if item is COSNull.NULL:
            return None
        return item

    def get_object(self, index: int) -> COSBase | None:
        """Resolved entry — if the entry is a ``COSObject``, returns its
        target; otherwise returns the entry itself."""
        return self._resolve(self._items[index])

    def getObject(self, index: int) -> COSBase | None:  # noqa: N802 - upstream Java name
        return self.get_object(index)

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

    def removeAt(self, index: int) -> COSBase:  # noqa: N802
        return self.remove_at(index)

    def clear(self) -> None:
        self._items.clear()

    def size(self) -> int:
        return len(self._items)

    def is_empty(self) -> bool:
        return not self._items

    def isEmpty(self) -> bool:  # noqa: N802 - upstream Java name
        return self.is_empty()

    def contains(self, item: COSBase) -> bool:
        return item in self._items

    def to_list(self) -> list[COSBase]:
        """Return a defensive copy of the underlying list."""
        return list(self._items)

    def toList(self) -> list[COSBase]:  # noqa: N802 - upstream Java name
        return self.to_list()

    def index_of(self, item: COSBase) -> int:
        """``index_of`` mirrors PDFBox; returns -1 if not present."""
        try:
            return self._items.index(item)
        except ValueError:
            return -1

    def indexOf(self, item: COSBase) -> int:  # noqa: N802 - upstream Java name
        return self.index_of(item)

    def index_of_object(self, item: COSBase) -> int:
        """Return the index of ``item``, resolving indirect object entries."""
        for index, candidate in enumerate(self._items):
            if candidate == item:
                return index
            if isinstance(candidate, COSObject) and candidate.get_object() == item:
                return index
        return -1

    def indexOfObject(self, item: COSBase) -> int:  # noqa: N802 - upstream Java name
        return self.index_of_object(item)

    def remove_object(self, item: COSBase) -> bool:
        """Remove the first matching item, resolving indirect object entries."""
        index = self.index_of_object(item)
        if index == -1:
            return False
        self.remove_at(index)
        return True

    def removeObject(self, item: COSBase) -> bool:  # noqa: N802 - upstream Java name
        return self.remove_object(item)

    def remove_all(self, items: Iterable[COSBase]) -> bool:
        """Remove every occurrence of each ``items`` entry. Returns ``True``
        if at least one entry was removed."""
        changed = False
        for item in items:
            while item in self._items:
                self._items.remove(item)
                changed = True
        return changed

    def removeAll(self, items: Iterable[COSBase]) -> bool:  # noqa: N802 - upstream Java name
        return self.remove_all(items)

    def retain_all(self, items: Iterable[COSBase]) -> bool:
        """Keep only entries also present in ``items``. Returns ``True`` if
        the array changed."""
        keep = list(items)
        before = len(self._items)
        self._items = [x for x in self._items if x in keep]
        return len(self._items) != before

    def retainAll(self, items: Iterable[COSBase]) -> bool:  # noqa: N802 - upstream Java name
        return self.retain_all(items)

    def grow_to_size(self, size: int, fill: COSBase | None = None) -> None:
        """Pad the array with ``fill`` (default ``None``) until it has at
        least ``size`` entries."""
        while len(self._items) < size:
            self._items.append(fill)  # type: ignore[arg-type]

    def growToSize(self, size: int, fill: COSBase | None = None) -> None:  # noqa: N802
        self.grow_to_size(size, fill)

    # ---------- typed convenience accessors ----------

    def set_name(self, index: int, value: str) -> None:
        self.grow_to_size(index + 1)
        self._items[index] = COSName.get_pdf_name(value)

    def setName(self, index: int, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_name(index, value)

    def get_name(self, index: int, default: str | None = None) -> str | None:
        if index >= len(self._items):
            return default
        item = self.get_object(index)
        if isinstance(item, COSName):
            return item.get_name()
        return default

    def getName(self, index: int, default: str | None = None) -> str | None:  # noqa: N802
        return self.get_name(index, default)

    def set_int(self, index: int, value: int) -> None:
        self.grow_to_size(index + 1)
        self._items[index] = COSInteger.get(value)

    def setInt(self, index: int, value: int) -> None:  # noqa: N802 - upstream Java name
        self.set_int(index, value)

    def get_int(self, index: int, default: int = -1) -> int:
        if index >= len(self._items):
            return default
        item = self.get_object(index)
        if isinstance(item, COSInteger):
            return item.value
        if isinstance(item, COSFloat):
            return int(item.value)
        return default

    def getInt(self, index: int, default: int = -1) -> int:  # noqa: N802
        return self.get_int(index, default)

    def set_float(self, index: int, value: float) -> None:
        self.grow_to_size(index + 1)
        self._items[index] = COSFloat(value)

    def setFloat(self, index: int, value: float) -> None:  # noqa: N802 - upstream Java name
        self.set_float(index, value)

    def get_float(self, index: int, default: float = -1.0) -> float:
        if index >= len(self._items):
            return default
        item = self.get_object(index)
        if isinstance(item, (COSInteger, COSFloat)):
            return float(item.value)
        return default

    def getFloat(self, index: int, default: float = -1.0) -> float:  # noqa: N802
        return self.get_float(index, default)

    def set_boolean(self, index: int, value: bool) -> None:
        self.grow_to_size(index + 1)
        self._items[index] = COSBoolean.get(value)

    def setBoolean(self, index: int, value: bool) -> None:  # noqa: N802
        self.set_boolean(index, value)

    def get_boolean(self, index: int, default: bool = False) -> bool:
        if index >= len(self._items):
            return default
        item = self.get_object(index)
        if isinstance(item, COSBoolean):
            return item.value
        return default

    def getBoolean(self, index: int, default: bool = False) -> bool:  # noqa: N802
        return self.get_boolean(index, default)

    def set_string(self, index: int, value: str) -> None:
        self.grow_to_size(index + 1)
        self._items[index] = COSString(value)

    def setString(self, index: int, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_string(index, value)

    def get_string(self, index: int, default: str | None = None) -> str | None:
        if index >= len(self._items):
            return default
        item = self.get_object(index)
        if isinstance(item, COSString):
            return item.get_string()
        return default

    def getString(self, index: int, default: str | None = None) -> str | None:  # noqa: N802
        return self.get_string(index, default)

    def set_float_array(self, values: Iterable[float]) -> None:
        """Replace contents with ``COSFloat`` instances built from ``values``."""
        self._items = [COSFloat(v) for v in values]

    def setFloatArray(self, values: Iterable[float]) -> None:  # noqa: N802
        self.set_float_array(values)

    def to_float_array(self) -> list[float]:
        """Convert numeric entries to floats; ``None`` entries become ``0``."""
        out: list[float] = []
        for raw_item in self._items:
            item = self._resolve(raw_item)
            if isinstance(item, (COSInteger, COSFloat)):
                out.append(float(item.value))
            else:
                out.append(0.0)
        return out

    def toFloatArray(self) -> list[float]:  # noqa: N802 - upstream Java name
        return self.to_float_array()

    def to_cos_name_string_list(self) -> list[str | None]:
        """Convert ``COSName`` entries to their string form. Non-name entries
        become ``None``."""
        out: list[str | None] = []
        for raw_item in self._items:
            item = self._resolve(raw_item)
            out.append(item.get_name() if isinstance(item, COSName) else None)
        return out

    def toCOSNameStringList(self) -> list[str | None]:  # noqa: N802 - upstream Java name
        return self.to_cos_name_string_list()

    def to_cos_string_string_list(self) -> list[str | None]:
        """Convert ``COSString`` entries to their decoded text. Non-string
        entries become ``None``."""
        out: list[str | None] = []
        for raw_item in self._items:
            item = self._resolve(raw_item)
            out.append(item.get_string() if isinstance(item, COSString) else None)
        return out

    def toCOSStringStringList(self) -> list[str | None]:  # noqa: N802
        return self.to_cos_string_string_list()

    def to_cos_number_integer_list(self) -> list[int | None]:
        """Convert numeric entries to ``int``; non-numeric entries become ``None``."""
        out: list[int | None] = []
        for raw_item in self._items:
            item = self._resolve(raw_item)
            if isinstance(item, (COSInteger, COSFloat)):
                out.append(int(item.value))
            else:
                out.append(None)
        return out

    def toCOSNumberIntegerList(self) -> list[int | None]:  # noqa: N802
        return self.to_cos_number_integer_list()

    def to_cos_number_float_list(self) -> list[float | None]:
        """Convert numeric entries to ``float``; non-numeric entries become ``None``."""
        out: list[float | None] = []
        for raw_item in self._items:
            item = self._resolve(raw_item)
            if isinstance(item, (COSInteger, COSFloat)):
                out.append(float(item.value))
            else:
                out.append(None)
        return out

    def toCOSNumberFloatList(self) -> list[float | None]:  # noqa: N802
        return self.to_cos_number_float_list()

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
