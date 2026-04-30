from __future__ import annotations

from collections.abc import ItemsView, Iterable, Iterator, KeysView, ValuesView
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

# Sentinel for "no default supplied" — distinguishes from a caller-passed None.
_MISSING: Any = object()


def _as_name(key: COSName | str) -> COSName:
    """Normalize string keys to interned ``COSName`` for storage."""
    if isinstance(key, COSName):
        return key
    if isinstance(key, str):
        return COSName.get_pdf_name(key)
    raise TypeError(f"key must be COSName or str, got {type(key).__name__}")


class COSDictionary(COSBase):
    """
    PDF dictionary — ordered ``COSName → COSBase`` map. Insertion order is
    preserved (Python 3.7+ ``dict`` semantics) so the writer can round-trip
    keys in their original sequence.

    String keys are accepted everywhere a ``COSName`` is expected and are
    normalized to interned ``COSName`` instances internally.
    """

    def __init__(self, items: Iterable[tuple[COSName | str, COSBase]] | None = None) -> None:
        super().__init__()
        self._items: dict[COSName, COSBase] = {}
        if items is not None:
            for k, v in items:
                self.set_item(k, v)

    # ---------- core map operations ----------

    def set_item(self, key: COSName | str, value: COSBase | None) -> None:
        if value is None:
            self.remove_item(key)
        else:
            self._items[_as_name(key)] = value

    def remove_item(self, key: COSName | str) -> COSBase | None:
        return self._items.pop(_as_name(key), None)

    def get_item(self, key: COSName | str, default: COSBase | None = None) -> COSBase | None:
        """Raw entry — may be a ``COSObject`` indirect reference."""
        return self._items.get(_as_name(key), default)

    def _resolve_item(self, key: COSName | str) -> COSBase | None:
        item = self._items.get(_as_name(key))
        if item is None:
            return None
        if isinstance(item, COSObject):
            item = item.get_object()
        if item is COSNull.NULL:
            return None
        return item

    def get_dictionary_object(
        self, key: COSName | str, default: COSBase | None = None
    ) -> COSBase | None:
        """Resolved entry — dereferences ``COSObject`` if needed.

        When ``default`` is a ``COSName`` or ``str``, it is treated as PDFBox's
        second-key overload and is resolved only if the first key is absent or
        resolves to ``COSNull``.
        """
        item = self._resolve_item(key)
        if item is not None:
            return item
        if isinstance(default, (COSName, str)):
            return self._resolve_item(default)
        return default

    def contains_key(self, key: COSName | str) -> bool:
        return _as_name(key) in self._items

    def size(self) -> int:
        return len(self._items)

    def is_empty(self) -> bool:
        return not self._items

    def clear(self) -> None:
        self._items.clear()

    def key_set(self) -> KeysView[COSName]:
        return self._items.keys()

    def values(self) -> ValuesView[COSBase]:
        return self._items.values()

    def entry_set(self) -> ItemsView[COSName, COSBase]:
        return self._items.items()

    def add_all(self, other: COSDictionary) -> None:
        """Merge ``other`` into self, overwriting keys present in both."""
        self._items.update(other._items)

    # ---------- typed convenience setters ----------

    def set_name(self, key: COSName | str, value: str | None) -> None:
        if value is None:
            self.remove_item(key)
        else:
            self.set_item(key, COSName.get_pdf_name(value))

    def set_string(self, key: COSName | str, value: str | bytes | None) -> None:
        if value is None:
            self.remove_item(key)
        else:
            self.set_item(key, COSString(value))

    def set_int(self, key: COSName | str, value: int) -> None:
        self.set_item(key, COSInteger.get(value))

    def set_long(self, key: COSName | str, value: int) -> None:
        """Store an integer value under ``key``. Mirrors PDFBox ``setLong``."""
        self.set_item(key, COSInteger.get(value))

    def set_float(self, key: COSName | str, value: float) -> None:
        self.set_item(key, COSFloat(value))

    def set_boolean(self, key: COSName | str, value: bool) -> None:
        self.set_item(key, COSBoolean.get(value))

    # ---------- typed convenience getters ----------

    def get_string(self, key: COSName | str, default: str | None = None) -> str | None:
        v = self.get_dictionary_object(key)
        if isinstance(v, COSString):
            return v.get_string()
        if isinstance(v, COSName):
            return v.name
        return default

    def get_name(self, key: COSName | str, default: str | None = None) -> str | None:
        v = self.get_dictionary_object(key)
        if isinstance(v, COSName):
            return v.name
        return default

    def get_int(self, key: COSName | str, default: int = -1) -> int:
        v = self.get_dictionary_object(key)
        if isinstance(v, COSInteger):
            return v.value
        if isinstance(v, COSFloat):
            return int(v.value)
        return default

    def get_long(self, key: COSName | str, default: int = -1) -> int:
        """Return a numeric value as an integer, or ``default`` if absent.

        Python has a single unbounded ``int`` type, so this mirrors PDFBox's
        ``getLong`` contract while sharing the same COS storage as integers.
        """
        v = self.get_dictionary_object(key)
        if isinstance(v, (COSInteger, COSFloat)):
            return v.long_value()
        return default

    def get_float(self, key: COSName | str, default: float = -1.0) -> float:
        v = self.get_dictionary_object(key)
        if isinstance(v, (COSInteger, COSFloat)):
            return float(v.value)
        return default

    def get_boolean(self, key: COSName | str, default: bool = False) -> bool:
        v = self.get_dictionary_object(key)
        if isinstance(v, COSBoolean):
            return v.value
        return default

    # ---------- visitor / Python protocols ----------

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_dictionary(self)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[COSName]:
        return iter(self._items)

    def __getitem__(self, key: COSName | str) -> COSBase:
        name = _as_name(key)
        if name not in self._items:
            raise KeyError(key)
        return self._items[name]

    def __setitem__(self, key: COSName | str, value: COSBase) -> None:
        self.set_item(key, value)

    def __delitem__(self, key: COSName | str) -> None:
        name = _as_name(key)
        if name not in self._items:
            raise KeyError(key)
        del self._items[name]

    def __contains__(self, key: object) -> bool:
        if isinstance(key, (COSName, str)):
            return _as_name(key) in self._items
        return False

    def __repr__(self) -> str:
        body = ", ".join(f"{k!s}: {v!r}" for k, v in self._items.items())
        return f"COSDictionary({{{body}}})"
