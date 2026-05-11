from __future__ import annotations


class KeyValue:
    """A basic key/value pair. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.form.FieldUtils.KeyValue``
    (upstream lines 44–70).

    Used to help sort the content of field option entries on choice
    fields, which store option lists either as ``[/export]`` strings
    or as ``[[/export, /display], ...]`` two-element arrays.
    Constructed via :meth:`FieldUtils.to_key_value_list`.
    """

    __slots__ = ("_key", "_value")

    def __init__(self, key: str, value: str) -> None:
        self._key = key
        self._value = value

    def get_key(self) -> str:
        return self._key

    def get_value(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"({self._key}, {self._value})"

    def __str__(self) -> str:
        return self.__repr__()

    def to_string(self) -> str:
        """Return the upstream-style ``(key, value)`` string. Mirrors
        ``FieldUtils.KeyValue.toString`` (Java line 66).

        Provides parity with upstream call sites that invoke
        ``keyValue.toString()`` explicitly rather than relying on
        Java's implicit string conversion.
        """
        return self.__str__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KeyValue):
            return NotImplemented
        return self._key == other._key and self._value == other._value

    def __hash__(self) -> int:
        return hash((self._key, self._value))


__all__ = ["KeyValue"]
