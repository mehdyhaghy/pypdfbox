from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from pypdfbox.cos import (
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)


class COSDictionaryMap[K, V]:
    """Map view backed by a ``COSDictionary``.

    Mirrors ``org.apache.pdfbox.pdmodel.common.COSDictionaryMap`` (Java
    lines 39-271). The map's keys are PDF name strings; values are the
    Python objects mapped to the underlying ``COSBase`` entries. Mutations
    propagate to the backing dictionary.
    """

    def __init__(
        self,
        actuals_map: dict[K, V],
        dic_map: COSDictionary,
    ) -> None:
        self._map: COSDictionary = dic_map
        self._actuals: dict[K, V] = actuals_map

    # ---------- read-only ----------

    def size(self) -> int:
        return self._map.size()

    def is_empty(self) -> bool:
        return self.size() == 0

    def contains_key(self, key: object) -> bool:
        return key in self._actuals

    def contains_value(self, value: object) -> bool:
        return value in self._actuals.values()

    def get(self, key: K) -> V | None:
        return self._actuals.get(key)

    def key_set(self) -> set[K]:
        return set(self._actuals.keys())

    def values(self) -> list[V]:
        return list(self._actuals.values())

    def entry_set(self) -> list[tuple[K, V]]:
        return list(self._actuals.items())

    # ---------- mutation ----------

    def put(self, key: K, value: V) -> V | None:
        cos = _to_cos(value)
        self._map.set_item(COSName.get_pdf_name(str(key)), cos)
        previous = self._actuals.get(key)
        self._actuals[key] = value
        return previous

    def remove(self, key: K) -> V | None:
        self._map.remove_item(COSName.get_pdf_name(str(key)))
        return self._actuals.pop(key, None)

    def put_all(self, t: Mapping[K, V]) -> None:
        raise NotImplementedError("Not yet implemented")

    def clear(self) -> None:
        self._map.clear()
        self._actuals.clear()

    # ---------- Python protocols ----------

    def __len__(self) -> int:
        return self.size()

    def __iter__(self) -> Iterator[K]:
        return iter(self._actuals)

    def __contains__(self, key: object) -> bool:
        return self.contains_key(key)

    def __getitem__(self, key: K) -> V:
        return self._actuals[key]

    def __setitem__(self, key: K, value: V) -> None:
        self.put(key, value)

    def __delitem__(self, key: K) -> None:
        self.remove(key)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, COSDictionaryMap):
            return self._map == other._map
        return False

    def __hash__(self) -> int:
        return id(self._map)

    def __repr__(self) -> str:
        return self.to_string()

    # ---------- parity surface (Java Object overrides) ----------

    def equals(self, o: object) -> bool:
        """Mirrors upstream ``equals(Object)`` (Java line 174)."""
        return self.__eq__(o)

    def to_string(self) -> str:
        """Mirrors upstream ``toString()`` (Java line 189)."""
        return repr(self._actuals)

    def hash_code(self) -> int:
        """Mirrors upstream ``hashCode()`` (Java line 198)."""
        return self.__hash__()

    # ---------- factory helpers ----------

    @staticmethod
    def convert(some_map: Mapping[str, Any]) -> COSDictionary:
        """Materialise a ``Mapping`` of ``str -> COSObjectable`` into a
        fresh ``COSDictionary``.

        Mirrors upstream ``convert(Map<String, ?>)`` (Java line 211).
        """
        dic = COSDictionary()
        for name, objectable in some_map.items():
            cos = _to_cos(objectable)
            dic.set_item(COSName.get_pdf_name(name), cos)
        return dic

    @staticmethod
    def convert_basic_types_to_map(
        map_: COSDictionary | None,
    ) -> COSDictionaryMap[str, Any] | None:
        """Convert a ``COSDictionary`` into a :class:`COSDictionaryMap` whose
        values are unwrapped Python primitives.

        Mirrors upstream ``convertBasicTypesToMap(COSDictionary)`` (Java
        line 230). Raises :class:`OSError` (Python equivalent of Java
        ``IOException``) when a value is not one of
        ``COSString``/``COSInteger``/``COSName``/``COSFloat``/``COSBoolean``.
        """
        if map_ is None:
            return None
        actual_map: dict[str, Any] = {}
        for key in map_.key_set():
            cos_obj = map_.get_dictionary_object(key)
            if isinstance(cos_obj, COSString):
                actual_object: Any = cos_obj.get_string()
            elif isinstance(cos_obj, COSInteger):
                actual_object = cos_obj.int_value()
            elif isinstance(cos_obj, COSName):
                actual_object = cos_obj.get_name()
            elif isinstance(cos_obj, COSFloat):
                actual_object = cos_obj.float_value()
            elif isinstance(cos_obj, COSBoolean):
                actual_object = cos_obj.get_value()
            else:
                raise OSError(
                    f"Error:unknown type of object to convert:{cos_obj}"
                )
            actual_map[key.get_name() if isinstance(key, COSName) else str(key)] = (
                actual_object
            )
        return COSDictionaryMap(actual_map, map_)


def _to_cos(value: Any) -> COSBase:
    if isinstance(value, COSBase):
        return value
    if isinstance(value, str):
        return COSString(value)
    if isinstance(value, bool):
        return COSBoolean.get_boolean(value)
    if isinstance(value, int):
        return COSInteger.get(value)
    if isinstance(value, float):
        return COSFloat(value)
    get_cos = getattr(value, "get_cos_object", None)
    if callable(get_cos):
        return get_cos()
    raise TypeError(
        f"COSDictionaryMap: cannot convert {type(value).__name__} to COSBase"
    )


__all__ = ["COSDictionaryMap"]
