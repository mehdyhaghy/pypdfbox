from __future__ import annotations

from collections.abc import ItemsView, Iterable, Iterator, KeysView, ValuesView
from typing import Any

from .cos_array import COSArray
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

    def setItem(self, key: COSName | str, value: COSBase | None) -> None:  # noqa: N802
        self.set_item(key, value)

    def remove_item(self, key: COSName | str) -> COSBase | None:
        return self._items.pop(_as_name(key), None)

    def removeItem(self, key: COSName | str) -> COSBase | None:  # noqa: N802
        return self.remove_item(key)

    def get_item(
        self, key: COSName | str, default: COSBase | COSName | str | None = None
    ) -> COSBase | None:
        """Raw entry — may be a ``COSObject`` indirect reference.

        When ``default`` is a ``COSName`` or ``str``, it is treated as PDFBox's
        second-key overload and returns that raw item only if the first key is
        absent.
        """
        item = self._items.get(_as_name(key))
        if item is not None:
            return item
        if isinstance(default, (COSName, str)):
            return self._items.get(_as_name(default))
        return default

    def getItem(  # noqa: N802
        self, key: COSName | str, default: COSBase | COSName | str | None = None
    ) -> COSBase | None:
        return self.get_item(key, default)

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
        self, key: COSName | str, default: COSBase | COSName | str | None = None
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

    def getDictionaryObject(  # noqa: N802
        self, key: COSName | str, default: COSBase | COSName | str | None = None
    ) -> COSBase | None:
        return self.get_dictionary_object(key, default)

    def contains_key(self, key: COSName | str) -> bool:
        return _as_name(key) in self._items

    def containsKey(self, key: COSName | str) -> bool:  # noqa: N802
        return self.contains_key(key)

    def contains_value(self, value: object) -> bool:
        """Return true if any entry stores ``value``.

        Mirrors PDFBox ``COSDictionary.containsValue`` and uses normal
        value equality, just like Java's ``Map.containsValue``.
        """
        return value in self._items.values()

    def containsValue(self, value: object) -> bool:  # noqa: N802 - upstream Java name
        return self.contains_value(value)

    def get_key_for_value(self, value: object) -> COSName | None:
        """Return the first key whose value equals ``value``, if any.

        Dictionary insertion order is preserved, so "first" is deterministic
        and matches the order used when writing or iterating the dictionary.
        """
        for key, item in self._items.items():
            if item == value:
                return key
        return None

    def getKeyForValue(self, value: object) -> COSName | None:  # noqa: N802
        return self.get_key_for_value(value)

    def clear_item(self, key: COSName | str) -> None:
        """Remove ``key`` if present."""
        self.remove_item(key)

    def clearItem(self, key: COSName | str) -> None:  # noqa: N802
        self.clear_item(key)

    def size(self) -> int:
        return len(self._items)

    def is_empty(self) -> bool:
        return not self._items

    def isEmpty(self) -> bool:  # noqa: N802 - upstream Java name
        return self.is_empty()

    def clear(self) -> None:
        self._items.clear()

    def key_set(self) -> KeysView[COSName]:
        return self._items.keys()

    def keySet(self) -> KeysView[COSName]:  # noqa: N802 - upstream Java name
        return self.key_set()

    def values(self) -> ValuesView[COSBase]:
        return self._items.values()

    def entry_set(self) -> ItemsView[COSName, COSBase]:
        return self._items.items()

    def entrySet(self) -> ItemsView[COSName, COSBase]:  # noqa: N802 - upstream Java name
        return self.entry_set()

    def add_all(self, other: COSDictionary) -> None:
        """Merge ``other`` into self, overwriting keys present in both."""
        self._items.update(other._items)

    def addAll(self, other: COSDictionary) -> None:  # noqa: N802 - upstream Java name
        self.add_all(other)

    # ---------- typed convenience setters ----------

    def set_name(self, key: COSName | str, value: str | None) -> None:
        if value is None:
            self.remove_item(key)
        else:
            self.set_item(key, COSName.get_pdf_name(value))

    def setName(self, key: COSName | str, value: str | None) -> None:  # noqa: N802
        self.set_name(key, value)

    def set_string(self, key: COSName | str, value: str | bytes | None) -> None:
        if value is None:
            self.remove_item(key)
        else:
            self.set_item(key, COSString(value))

    def setString(self, key: COSName | str, value: str | bytes | None) -> None:  # noqa: N802
        self.set_string(key, value)

    def set_int(self, key: COSName | str, value: int) -> None:
        self.set_item(key, COSInteger.get(value))

    def setInt(self, key: COSName | str, value: int) -> None:  # noqa: N802 - upstream Java name
        self.set_int(key, value)

    def set_long(self, key: COSName | str, value: int) -> None:
        """Store an integer value under ``key``. Mirrors PDFBox ``setLong``."""
        self.set_item(key, COSInteger.get(value))

    def setLong(self, key: COSName | str, value: int) -> None:  # noqa: N802 - upstream Java name
        self.set_long(key, value)

    def set_float(self, key: COSName | str, value: float) -> None:
        self.set_item(key, COSFloat(value))

    def setFloat(self, key: COSName | str, value: float) -> None:  # noqa: N802
        self.set_float(key, value)

    def set_boolean(self, key: COSName | str, value: bool) -> None:
        self.set_item(key, COSBoolean.get(value))

    def setBoolean(self, key: COSName | str, value: bool) -> None:  # noqa: N802
        self.set_boolean(key, value)

    # ---------- typed convenience getters ----------

    def get_string(self, key: COSName | str, default: str | None = None) -> str | None:
        v = self.get_dictionary_object(key)
        if isinstance(v, COSString):
            return v.get_string()
        if isinstance(v, COSName):
            return v.name
        return default

    def getString(self, key: COSName | str, default: str | None = None) -> str | None:  # noqa: N802
        return self.get_string(key, default)

    def has_string(self, key: COSName | str) -> bool:
        """Return true when ``key`` resolves to a string-like COS value."""
        return isinstance(self.get_dictionary_object(key), (COSString, COSName))

    def hasString(self, key: COSName | str) -> bool:  # noqa: N802
        return self.has_string(key)

    def clear_string(self, key: COSName | str) -> None:
        self.clear_item(key)

    def clearString(self, key: COSName | str) -> None:  # noqa: N802
        self.clear_string(key)

    def get_name(self, key: COSName | str, default: str | None = None) -> str | None:
        v = self.get_dictionary_object(key)
        if isinstance(v, COSName):
            return v.name
        return default

    def getName(self, key: COSName | str, default: str | None = None) -> str | None:  # noqa: N802
        return self.get_name(key, default)

    def get_name_as_string(
        self, key: COSName | str, default: str | None = None
    ) -> str | None:
        """Return a name-like value as text.

        Mirrors PDFBox ``COSDictionary.getNameAsString``: names return their
        PDF name, strings return their decoded string, and other shapes fall
        back to ``default``.
        """
        return self.get_string(key, default)

    def getNameAsString(  # noqa: N802
        self, key: COSName | str, default: str | None = None
    ) -> str | None:
        return self.get_name_as_string(key, default)

    def has_name(self, key: COSName | str) -> bool:
        return isinstance(self.get_dictionary_object(key), COSName)

    def hasName(self, key: COSName | str) -> bool:  # noqa: N802
        return self.has_name(key)

    def clear_name(self, key: COSName | str) -> None:
        self.clear_item(key)

    def clearName(self, key: COSName | str) -> None:  # noqa: N802
        self.clear_name(key)

    def get_int(
        self, key: COSName | str, default: int | COSName | str = -1, fallback: int = -1
    ) -> int:
        if isinstance(default, (COSName, str)):
            v = self.get_dictionary_object(key, default)
            default_value = fallback
        else:
            v = self.get_dictionary_object(key)
            default_value = default
        if isinstance(v, COSInteger):
            return v.value
        if isinstance(v, COSFloat):
            return int(v.value)
        return default_value

    def getInt(  # noqa: N802
        self, key: COSName | str, default: int | COSName | str = -1, fallback: int = -1
    ) -> int:
        return self.get_int(key, default, fallback)

    def has_int(self, key: COSName | str) -> bool:
        return isinstance(self.get_dictionary_object(key), (COSInteger, COSFloat))

    def hasInt(self, key: COSName | str) -> bool:  # noqa: N802
        return self.has_int(key)

    def clear_int(self, key: COSName | str) -> None:
        self.clear_item(key)

    def clearInt(self, key: COSName | str) -> None:  # noqa: N802
        self.clear_int(key)

    def get_long(
        self, key: COSName | str, default: int | COSName | str = -1, fallback: int = -1
    ) -> int:
        """Return a numeric value as an integer, or ``default`` if absent.

        Python has a single unbounded ``int`` type, so this mirrors PDFBox's
        ``getLong`` contract while sharing the same COS storage as integers.
        """
        if isinstance(default, (COSName, str)):
            v = self.get_dictionary_object(key, default)
            default_value = fallback
        else:
            v = self.get_dictionary_object(key)
            default_value = default
        if isinstance(v, (COSInteger, COSFloat)):
            return v.long_value()
        return default_value

    def getLong(  # noqa: N802
        self, key: COSName | str, default: int | COSName | str = -1, fallback: int = -1
    ) -> int:
        return self.get_long(key, default, fallback)

    def has_long(self, key: COSName | str) -> bool:
        return isinstance(self.get_dictionary_object(key), (COSInteger, COSFloat))

    def hasLong(self, key: COSName | str) -> bool:  # noqa: N802
        return self.has_long(key)

    def clear_long(self, key: COSName | str) -> None:
        self.clear_item(key)

    def clearLong(self, key: COSName | str) -> None:  # noqa: N802
        self.clear_long(key)

    def get_float(
        self, key: COSName | str, default: float | COSName | str = -1.0, fallback: float = -1.0
    ) -> float:
        if isinstance(default, (COSName, str)):
            v = self.get_dictionary_object(key, default)
            default_value = fallback
        else:
            v = self.get_dictionary_object(key)
            default_value = default
        if isinstance(v, (COSInteger, COSFloat)):
            return float(v.value)
        return default_value

    def getFloat(  # noqa: N802
        self, key: COSName | str, default: float | COSName | str = -1.0, fallback: float = -1.0
    ) -> float:
        return self.get_float(key, default, fallback)

    def has_float(self, key: COSName | str) -> bool:
        return isinstance(self.get_dictionary_object(key), (COSInteger, COSFloat))

    def hasFloat(self, key: COSName | str) -> bool:  # noqa: N802
        return self.has_float(key)

    def clear_float(self, key: COSName | str) -> None:
        self.clear_item(key)

    def clearFloat(self, key: COSName | str) -> None:  # noqa: N802
        self.clear_float(key)

    def get_boolean(
        self, key: COSName | str, default: bool | COSName | str = False, fallback: bool = False
    ) -> bool:
        if isinstance(default, (COSName, str)):
            v = self.get_dictionary_object(key, default)
            default_value = fallback
        else:
            v = self.get_dictionary_object(key)
            default_value = default
        if isinstance(v, COSBoolean):
            return v.value
        return default_value

    def getBoolean(  # noqa: N802
        self, key: COSName | str, default: bool | COSName | str = False, fallback: bool = False
    ) -> bool:
        return self.get_boolean(key, default, fallback)

    def has_boolean(self, key: COSName | str) -> bool:
        return isinstance(self.get_dictionary_object(key), COSBoolean)

    def hasBoolean(self, key: COSName | str) -> bool:  # noqa: N802
        return self.has_boolean(key)

    def clear_boolean(self, key: COSName | str) -> None:
        self.clear_item(key)

    def clearBoolean(self, key: COSName | str) -> None:  # noqa: N802
        self.clear_boolean(key)

    def get_cos_dictionary(self, key: COSName | str) -> COSDictionary | None:
        """Return the resolved value as a ``COSDictionary`` when present.

        Mirrors PDFBox ``COSDictionary.getCOSDictionary`` while keeping the
        local snake_case API style.
        """
        v = self.get_dictionary_object(key)
        if isinstance(v, COSDictionary):
            return v
        return None

    def getCOSDictionary(self, key: COSName | str) -> COSDictionary | None:  # noqa: N802
        return self.get_cos_dictionary(key)

    def has_cos_dictionary(self, key: COSName | str) -> bool:
        return isinstance(self.get_dictionary_object(key), COSDictionary)

    def hasCOSDictionary(self, key: COSName | str) -> bool:  # noqa: N802
        return self.has_cos_dictionary(key)

    def clear_cos_dictionary(self, key: COSName | str) -> None:
        self.clear_item(key)

    def clearCOSDictionary(self, key: COSName | str) -> None:  # noqa: N802
        self.clear_cos_dictionary(key)

    def get_cos_array(self, key: COSName | str) -> COSArray | None:
        """Return the resolved value as a ``COSArray`` when present.

        Mirrors PDFBox ``COSDictionary.getCOSArray`` while keeping the local
        snake_case API style.
        """
        v = self.get_dictionary_object(key)
        if isinstance(v, COSArray):
            return v
        return None

    def getCOSArray(self, key: COSName | str) -> COSArray | None:  # noqa: N802
        return self.get_cos_array(key)

    def has_cos_array(self, key: COSName | str) -> bool:
        return isinstance(self.get_dictionary_object(key), COSArray)

    def hasCOSArray(self, key: COSName | str) -> bool:  # noqa: N802
        return self.has_cos_array(key)

    def clear_cos_array(self, key: COSName | str) -> None:
        self.clear_item(key)

    def clearCOSArray(self, key: COSName | str) -> None:  # noqa: N802
        self.clear_cos_array(key)

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
