from __future__ import annotations

from dataclasses import dataclass

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

    # ---------- well-known instances ----------

    @classmethod
    def get_null_entry(cls) -> COSWriterXRefEntry:
        """Return the canonical free-list head: offset 0, generation 65535,
        marked free. Mirrors upstream ``COSWriterXRefEntry.NULLENTRY``."""
        return _NULL_ENTRY


_NULL_ENTRY = COSWriterXRefEntry(
    offset=0,
    key=COSObjectKey(0, 65535),
    obj=None,
    free=True,
)
