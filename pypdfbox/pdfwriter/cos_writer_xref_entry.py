from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from pypdfbox.cos import COSBase, COSObjectKey


@dataclass(frozen=True, order=False)
class COSWriterXRefEntry:
    """
    Frozen value type captured during the body-emit pass: the absolute
    offset of an indirect object, its ``COSObjectKey``, and whether the
    entry represents a ``free`` xref slot.

    Mirrors ``org.apache.pdfbox.pdfwriter.COSWriterXRefEntry``. Sortable
    by object number (matches upstream ``compareTo``).
    """

    offset: int
    key: COSObjectKey
    obj: COSBase | None = None
    free: bool = False
    NULLENTRY: ClassVar[COSWriterXRefEntry]

    # ---------- accessors (PDFBox-style) ----------

    def get_offset(self) -> int:
        return self.offset

    def get_key(self) -> COSObjectKey:
        return self.key

    def get_object(self) -> COSBase | None:
        return self.obj

    def is_free(self) -> bool:
        return self.free

    # ---------- ordering ----------

    def compare_to(self, other: COSWriterXRefEntry | None) -> int:
        """Mirrors upstream ``compareTo``: compares by object number, and
        returns ``-1`` when ``other`` is ``None`` (matches the Java behavior
        used by code that sorts xref tables and tolerates null sentinels)."""
        if other is None:
            return -1
        a = self.key.object_number
        b = other.key.object_number
        if a < b:
            return -1
        if a > b:
            return 1
        return 0

    # ``order=False`` on the dataclass + custom ``__lt__`` so sorting matches
    # upstream ``compareTo`` (object number only, ignoring offset / free flag).
    def __lt__(self, other: object) -> bool:
        if not isinstance(other, COSWriterXRefEntry):
            return NotImplemented
        return self.key.object_number < other.key.object_number

    def __le__(self, other: object) -> bool:
        if not isinstance(other, COSWriterXRefEntry):
            return NotImplemented
        return self.key.object_number <= other.key.object_number

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, COSWriterXRefEntry):
            return NotImplemented
        return self.key.object_number > other.key.object_number

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, COSWriterXRefEntry):
            return NotImplemented
        return self.key.object_number >= other.key.object_number

    # ---------- functional update helpers ----------

    def with_free(self, free: bool) -> COSWriterXRefEntry:
        """Functional substitute for upstream ``setFree(boolean)``.

        Upstream mutates ``free`` in-place; our value type is frozen, so we
        return a new instance with the flag toggled. Callers that previously
        wrote ``entry.setFree(true)`` should write
        ``entry = entry.with_free(True)``.
        """
        if self.free == free:
            return self
        return COSWriterXRefEntry(
            offset=self.offset, key=self.key, obj=self.obj, free=free
        )

    # ---------- well-known instances ----------

    @classmethod
    def get_null_entry(cls) -> COSWriterXRefEntry:
        """Return the canonical free-list head: offset 0, generation 65535,
        marked free. Mirrors upstream ``COSWriterXRefEntry.NULLENTRY``."""
        return cls.NULLENTRY


_NULL_ENTRY = COSWriterXRefEntry(
    offset=0,
    key=COSObjectKey(0, 65535),
    obj=None,
    free=True,
)
COSWriterXRefEntry.NULLENTRY = _NULL_ENTRY
