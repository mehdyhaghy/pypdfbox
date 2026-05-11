"""Memory-frugal Map implementation for short key/value lists.

Mirrors ``org.apache.pdfbox.util.SmallMap`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/util/SmallMap.java``).

Upstream marks this class ``@Deprecated`` for removal in 4.0. We retain it
so ports of older PDFBox code that wire up ``SmallMap`` continue to work.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableMapping
from typing import Any


class SmallMapEntry:
    """Map entry view — mirrors the inner ``SmallMap.SmallMapEntry`` class."""

    __slots__ = ("_owner", "_key_idx")

    def __init__(self, owner: SmallMap, key_idx: int) -> None:
        self._owner = owner
        self._key_idx = key_idx

    def get_key(self) -> Any:
        return self._owner._map_arr[self._key_idx]

    def get_value(self) -> Any:
        return self._owner._map_arr[self._key_idx + 1]

    def set_value(self, value: Any) -> Any:
        if value is None:
            raise TypeError("Key or value must not be null.")
        old = self.get_value()
        self._owner._map_arr[self._key_idx + 1] = value
        return old

    def __hash__(self) -> int:
        return hash(self.get_key())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SmallMapEntry):
            return False
        return self.get_key() == other.get_key() and self.get_value() == other.get_value()

    # --- Upstream parity surface -------------------------------------
    def equals(self, other: object) -> bool:
        """Mirror of ``SmallMapEntry.equals``."""
        return self.__eq__(other)

    def hash_code(self) -> int:
        """Mirror of ``SmallMapEntry.hashCode``."""
        return self.__hash__()


class SmallMap(MutableMapping):
    """O(n)-everywhere map backed by a single flat list."""

    def __init__(self, init_map: Mapping[Any, Any] | None = None) -> None:
        self._map_arr: list[Any] | None = None
        if init_map is not None:
            self.put_all(init_map)

    # ---- private lookup helpers ----------------------------------------
    def find_key(self, key: Any) -> int:
        """Mirror of upstream's private ``findKey``."""
        if self.is_empty() or key is None:
            return -1
        assert self._map_arr is not None
        for a_idx in range(0, len(self._map_arr), 2):
            if key == self._map_arr[a_idx]:
                return a_idx
        return -1

    def find_value(self, value: Any) -> int:
        """Mirror of upstream's private ``findValue``."""
        if self.is_empty() or value is None:
            return -1
        assert self._map_arr is not None
        for a_idx in range(1, len(self._map_arr), 2):
            if value == self._map_arr[a_idx]:
                return a_idx
        return -1

    # Underscore-prefixed aliases retained for in-module callers.
    _find_key = find_key
    _find_value = find_value

    # ---- Map API -------------------------------------------------------
    def size(self) -> int:
        return 0 if self._map_arr is None else len(self._map_arr) >> 1

    def is_empty(self) -> bool:
        return self._map_arr is None or len(self._map_arr) == 0

    def contains_key(self, key: Any) -> bool:
        return self._find_key(key) >= 0

    def contains_value(self, value: Any) -> bool:
        return self._find_value(value) >= 0

    def get(self, key: Any, default: Any = None) -> Any:  # type: ignore[override]
        k_idx = self._find_key(key)
        if k_idx < 0:
            return default
        assert self._map_arr is not None
        return self._map_arr[k_idx + 1]

    def put(self, key: Any, value: Any) -> Any:
        if key is None or value is None:
            raise TypeError("Key or value must not be null.")
        if self._map_arr is None:
            self._map_arr = [key, value]
            return None
        k_idx = self._find_key(key)
        if k_idx < 0:
            self._map_arr.extend([key, value])
            return None
        old = self._map_arr[k_idx + 1]
        self._map_arr[k_idx + 1] = value
        return old

    def remove(self, key: Any) -> Any:
        k_idx = self._find_key(key)
        if k_idx < 0:
            return None
        assert self._map_arr is not None
        old = self._map_arr[k_idx + 1]
        del self._map_arr[k_idx : k_idx + 2]
        if not self._map_arr:
            self._map_arr = None
        return old

    def put_all(self, other_map: Mapping[Any, Any]) -> None:
        for k, v in other_map.items():
            self.put(k, v)

    def clear(self) -> None:
        self._map_arr = None

    def key_set(self) -> list[Any]:
        if self.is_empty():
            return []
        assert self._map_arr is not None
        return [self._map_arr[i] for i in range(0, len(self._map_arr), 2)]

    def values(self) -> list[Any]:  # type: ignore[override]
        if self.is_empty():
            return []
        assert self._map_arr is not None
        return [self._map_arr[i] for i in range(1, len(self._map_arr), 2)]

    def entry_set(self) -> list[SmallMapEntry]:
        if self.is_empty():
            return []
        assert self._map_arr is not None
        return [SmallMapEntry(self, i) for i in range(0, len(self._map_arr), 2)]

    # ---- MutableMapping glue ------------------------------------------
    def __getitem__(self, key: Any) -> Any:
        k_idx = self._find_key(key)
        if k_idx < 0:
            raise KeyError(key)
        assert self._map_arr is not None
        return self._map_arr[k_idx + 1]

    def __setitem__(self, key: Any, value: Any) -> None:
        self.put(key, value)

    def __delitem__(self, key: Any) -> None:
        if self._find_key(key) < 0:
            raise KeyError(key)
        self.remove(key)

    def __iter__(self) -> Iterator[Any]:
        return iter(self.key_set())

    def __len__(self) -> int:
        return self.size()

    def __contains__(self, key: Any) -> bool:  # type: ignore[override]
        return self.contains_key(key)


__all__ = ["SmallMap", "SmallMapEntry"]
