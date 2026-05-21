from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)


class COSArrayList[E]:
    """List that mirrors its contents into a backing ``COSArray``.

    Mirrors ``org.apache.pdfbox.pdmodel.common.COSArrayList`` (Java
    lines 40-597). Used pervasively by PDModel wrappers when a dictionary
    entry holds an array of typed objects (annotations, fields, kids, etc):
    callers mutate the ``COSArrayList`` like a regular ``list`` and the
    backing ``COSArray`` stays in sync.

    Like upstream, a list constructed with a pre-filtered Python list and
    a non-matching backing array enters "read-only" mode (the ``is_filtered``
    flag) — mutation methods then raise.
    """

    def __init__(
        self,
        actual_list: list[E] | E | None = None,
        cos_array: COSArray | COSBase | None = None,
        dictionary: COSDictionary | None = None,
        dictionary_key: COSName | None = None,
    ) -> None:
        """Four upstream overloads collapsed into one keyword-driven form.

        See module docstring for the four shapes (Java constructors at
        lines 55, 75, 95, 118).
        """
        self._is_filtered: bool = False
        self._parent_dict: COSDictionary | None = None
        self._dict_key: COSName | None = None

        if actual_list is None and cos_array is None and dictionary is None:
            # ``COSArrayList()`` — empty list, fresh backing array.
            self._array: COSArray = COSArray()
            self._actual: list[E] = []
        elif isinstance(actual_list, list) and isinstance(cos_array, COSArray):
            # ``COSArrayList(actualList, cosArray)`` — wrap the pair.
            self._actual = actual_list
            self._array = cos_array
            if len(self._actual) != self._array.size():
                self._is_filtered = True
        elif (
            dictionary is not None
            and dictionary_key is not None
            and actual_list is None
            and cos_array is None
        ):
            # ``COSArrayList(dictionary, dictionaryKey)`` — lazy: backing array
            # is added to ``dictionary[dictionary_key]`` on first ``add``.
            self._array = COSArray()
            self._actual = []
            self._parent_dict = dictionary
            self._dict_key = dictionary_key
        elif (
            actual_list is not None
            and not isinstance(actual_list, list)
            and isinstance(cos_array, COSBase)
            and dictionary is not None
            and dictionary_key is not None
        ):
            # ``COSArrayList(actualObject, item, dictionary, dictionaryKey)``
            # Single-item seed where the dict entry currently holds the item
            # directly; growing the list upgrades it to an array.
            self._array = COSArray()
            self._array.add(cos_array)
            self._actual = [actual_list]  # type: ignore[list-item]
            self._parent_dict = dictionary
            self._dict_key = dictionary_key
        else:
            raise TypeError(
                "COSArrayList: unsupported argument combination — use "
                "one of the four upstream constructor shapes"
            )

    # ---------- read-only ----------

    def size(self) -> int:
        return len(self._actual)

    def is_empty(self) -> bool:
        return not self._actual

    def contains(self, o: object) -> bool:
        return o in self._actual

    def contains_all(self, c: Iterable[object]) -> bool:
        return all(item in self._actual for item in c)

    def iterator(self) -> Iterator[E]:
        return iter(self._actual)

    def list_iterator(self, index: int = 0) -> Iterator[E]:
        return iter(self._actual[index:])

    def to_array(self) -> list[E]:
        return list(self._actual)

    def get(self, index: int) -> E:
        return self._actual[index]

    def index_of(self, o: object) -> int:
        try:
            return self._actual.index(o)  # type: ignore[arg-type]
        except ValueError:
            return -1

    def last_index_of(self, o: object) -> int:
        for i in range(len(self._actual) - 1, -1, -1):
            if self._actual[i] == o:
                return i
        return -1

    def sub_list(self, from_index: int, to_index: int) -> list[E]:
        return list(self._actual[from_index:to_index])

    def to_list(self) -> COSArray:
        """Return the underlying ``COSArray``. Mirrors upstream
        ``toList()`` (Java line 592)."""
        return self._array

    # ---------- mutation ----------

    def _promote_parent_dict(self) -> None:
        if self._parent_dict is not None:
            self._parent_dict.set_item(self._dict_key, self._array)
            self._parent_dict = None

    def add(self, item: E, index: int | None = None) -> bool:
        """Append ``item`` (or insert at ``index``). Mirrors upstream
        ``add(E)`` (Java line 188) and ``add(int, E)`` (Java line 492)."""
        if self._is_filtered:
            raise NotImplementedError(
                "Adding an element in a filtered List is not permitted"
            )
        self._promote_parent_dict()
        if index is None:
            self._actual.append(item)
            self._array.add(_to_cos(item))
            return True
        self._actual.insert(index, item)
        self._array.add_at(index, _to_cos(item))
        return True

    def add_all(self, items: Iterable[E], index: int | None = None) -> bool:
        """Mirrors upstream ``addAll(Collection)`` (Java line 252) and
        ``addAll(int, Collection)`` (Java line 275)."""
        if self._is_filtered:
            raise NotImplementedError(
                "Adding to a filtered List is not permitted"
            )
        materialized = list(items)
        if materialized and self._parent_dict is not None:
            self._promote_parent_dict()
        cos_items = [_to_cos(item) for item in materialized]
        if index is None:
            self._actual.extend(materialized)
            for cos in cos_items:
                self._array.add(cos)
        else:
            for offset, (py_item, cos) in enumerate(
                zip(materialized, cos_items, strict=True)
            ):
                self._actual.insert(index + offset, py_item)
                self._array.add_at(index + offset, cos)
        return bool(materialized)

    def set(self, index: int, element: E) -> E:
        if self._is_filtered:
            raise NotImplementedError(
                "Replacing an element in a filtered List is not permitted"
            )
        cos = _to_cos(element)
        if self._parent_dict is not None and index == 0:
            self._parent_dict.set_item(self._dict_key, cos)
        self._array.set(index, cos)
        previous = self._actual[index]
        self._actual[index] = element
        return previous

    def remove(self, index_or_object: int | object) -> Any:
        if self._is_filtered:
            raise NotImplementedError(
                "removing entries from a filtered List is not permitted"
            )
        if isinstance(index_or_object, int) and not isinstance(index_or_object, bool):
            self._array.remove_at(index_or_object)
            return self._actual.pop(index_or_object)
        # Object-by-value remove.
        try:
            idx = self._actual.index(index_or_object)  # type: ignore[arg-type]
        except ValueError:
            return False
        self._actual.pop(idx)
        self._array.remove_at(idx)
        return True

    def remove_all(self, c: Iterable[object]) -> bool:
        """Mirrors upstream ``removeAll(Collection)`` (Java line 213).

        Upstream's contract (``java.util.Collection#removeAll``) is to
        remove *all* elements that match — duplicates included. The
        Python-list ``.remove()`` only drops the first match, so iterate
        the backing list in reverse and pop every occurrence.
        """
        if self._is_filtered:
            raise NotImplementedError(
                "removing entries from a filtered List is not permitted"
            )
        changed = False
        for item in c:
            cos_item = _to_cos(item)
            for i in range(self._array.size() - 1, -1, -1):
                if self._array.get_object(i) == cos_item:
                    self._array.remove_at(i)
            for i in range(len(self._actual) - 1, -1, -1):
                if self._actual[i] == item:  # type: ignore[comparison-overlap]
                    self._actual.pop(i)
                    changed = True
        return changed

    def retain_all(self, c: Iterable[object]) -> bool:
        retain = list(c)
        retain_cos = {id(_to_cos(item)) for item in retain}
        for i in range(self._array.size() - 1, -1, -1):
            obj = self._array.get_object(i)
            if id(obj) not in retain_cos and obj not in retain_cos:
                self._array.remove_at(i)
        before = len(self._actual)
        self._actual[:] = [item for item in self._actual if item in retain]  # type: ignore[operator]
        return before != len(self._actual)

    def clear(self) -> None:
        if self._parent_dict is not None:
            self._parent_dict.set_item(self._dict_key, None)
        self._actual.clear()
        self._array.clear()

    # ---------- conversion ----------

    @staticmethod
    def converter_to_cos_array(cos_objectable_list: Iterable[Any] | None) -> COSArray | None:
        """Convert a Python iterable into a ``COSArray``.

        Mirrors upstream ``converterToCOSArray(List<?>)`` (Java line 304).
        Returns the existing backing array if ``cos_objectable_list`` is
        already a :class:`COSArrayList`.
        """
        if cos_objectable_list is None:
            return None
        if isinstance(cos_objectable_list, COSArrayList):
            return cos_objectable_list._array
        array = COSArray()
        for entry in cos_objectable_list:
            array.add(_to_cos(entry))
        return array

    # ---------- Python protocols ----------

    def __len__(self) -> int:
        return self.size()

    def __iter__(self) -> Iterator[E]:
        return iter(self._actual)

    def __contains__(self, item: object) -> bool:
        return item in self._actual

    def __getitem__(self, index: int) -> E:
        return self._actual[index]

    def __setitem__(self, index: int, value: E) -> None:
        self.set(index, value)

    def __delitem__(self, index: int) -> None:
        self.remove(index)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, COSArrayList):
            return self._actual == other._actual
        if isinstance(other, list):
            return self._actual == other
        return NotImplemented

    def __hash__(self) -> int:  # type: ignore[override]
        return id(self)

    def __repr__(self) -> str:
        return self.to_string()

    # ---------- parity surface (Java Object overrides + private helper) ----------

    def equals(self, o: object) -> bool:
        """Mirrors upstream ``equals(Object)`` (Java line 433)."""
        return self.__eq__(o) is True

    def hash_code(self) -> int:
        """Mirrors upstream ``hashCode()`` (Java line 442)."""
        return hash(tuple(id(item) for item in self._actual))

    def to_string(self) -> str:
        """Mirrors upstream ``toString()`` (Java line 582)."""
        return f"COSArrayList{{{self._array!r}}}"

    def to_cos_object_list(self, collection: Iterable[Any]) -> list[COSBase]:
        """Mirrors upstream private ``toCOSObjectList(Collection<?>)``
        (Java line 351) — convert a Python iterable of ``COSObjectable``
        instances to a list of ``COSBase`` for direct insertion into the
        backing array.
        """
        return [_to_cos(item) for item in collection]


def _to_cos(value: Any) -> COSBase:
    """Convert ``value`` to a ``COSBase`` for storage in the array.

    Mirrors upstream's conversion logic in ``converterToCOSArray`` (Java
    line 304) and ``add`` (Java line 188).
    """
    if isinstance(value, COSBase):
        return value
    if isinstance(value, str):
        return COSString(value)
    if isinstance(value, bool):
        # Booleans are ints in Python — check before int to avoid mis-encoding.
        from pypdfbox.cos import COSBoolean  # noqa: PLC0415

        return COSBoolean.get_boolean(value)
    if isinstance(value, int):
        return COSInteger.get(value)
    if isinstance(value, float):
        return COSFloat(value)
    if value is None:
        return COSNull.NULL
    get_cos = getattr(value, "get_cos_object", None)
    if callable(get_cos):
        return get_cos()
    raise TypeError(
        f"COSArrayList: cannot convert {type(value).__name__} to COSBase"
    )


__all__ = ["COSArrayList"]
