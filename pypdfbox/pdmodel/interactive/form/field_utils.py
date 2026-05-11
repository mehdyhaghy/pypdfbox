from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSString

from .key_value import KeyValue


class FieldUtils:
    """A set of utility methods to help with common AcroForm form and
    field related functions. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.form.FieldUtils``
    (upstream lines 31–168).

    All methods are static helpers — this class is never instantiated
    upstream (private constructor); the Python port matches that by
    raising on ``__init__``.
    """

    def __init__(self) -> None:
        raise TypeError("FieldUtils is a static-utility class")

    @staticmethod
    def to_key_value_list(
        key: list[str], value: list[str]
    ) -> list[KeyValue]:
        """Return two related lists as a single list with key/value
        pairs. Mirrors upstream ``toKeyValueList`` (lines 86–94)."""
        return [KeyValue(k, v) for k, v in zip(key, value, strict=False)]

    @staticmethod
    def sort_by_value(pairs: list[KeyValue]) -> None:
        """Sort ``pairs`` in place by the value element. Mirrors
        upstream ``sortByValue`` (lines 101–104)."""
        pairs.sort(key=lambda kv: kv.get_value())

    @staticmethod
    def sort_by_key(pairs: list[KeyValue]) -> None:
        """Sort ``pairs`` in place by the key element. Mirrors
        upstream ``sortByKey`` (lines 111–114)."""
        pairs.sort(key=lambda kv: kv.get_key())

    @staticmethod
    def get_pairable_items(items: COSBase | None, pair_idx: int) -> list[str]:
        """Return one column of a list which can have two-element array
        entries. Mirrors upstream ``getPairableItems`` (lines 133–167).

        Some choice-field dictionary entries can be either an array of
        strings or an array of two-element arrays (``[/export, /display]``).
        ``pair_idx`` selects either column 0 (export) or column 1
        (display) — passing any other value raises ``ValueError``
        (upstream raises ``IllegalArgumentException``).
        """
        if pair_idx < 0 or pair_idx > 1:
            raise ValueError(
                "Only 0 and 1 are allowed as an index into two-element arrays"
            )

        if isinstance(items, COSString):
            return [items.get_string()]

        if isinstance(items, COSArray):
            entry_list: list[str] = []
            for entry in items:
                if isinstance(entry, COSString):
                    entry_list.append(entry.get_string())
                elif isinstance(entry, COSArray) and (
                    len(entry) >= pair_idx + 1
                    and isinstance(entry[pair_idx], COSString)
                ):
                    entry_list.append(entry[pair_idx].get_string())
            return entry_list

        return []


__all__ = ["FieldUtils"]
