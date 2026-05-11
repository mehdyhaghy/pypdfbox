"""Bidirectional map of ``COSObjectKey`` ↔ ``COSBase`` for the compressor.

Mirrors ``org.apache.pdfbox.pdfwriter.compress.COSObjectPool`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/pdfwriter/compress/COSObjectPool.java``).
"""

from __future__ import annotations

import contextlib

from pypdfbox.cos.cos_base import COSBase
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.cos.cos_object_key import COSObjectKey


class COSObjectPool:
    """Bidirectional lookup map used by :class:`COSWriterCompressionPool`."""

    def __init__(self, highest_xref_object_number: int = 0) -> None:
        self._key_pool: dict[COSObjectKey, COSBase] = {}
        self._object_pool: dict[int, COSObjectKey] = {}
        # Reverse-lookup helper: id(COSBase) → COSObjectKey, since COSBase
        # equality is value-based and we want identity-based lookup like
        # Java's ``HashMap`` with default ``hashCode``.
        self._object_pool_obj: dict[int, COSBase] = {}
        self._highest_xref_object_number = max(0, highest_xref_object_number)

    def put(self, key: COSObjectKey | None, obj: COSBase | None) -> COSObjectKey | None:
        """Register ``obj`` under ``key`` (creating one if needed).

        Returns the actual key under which the object is registered, or
        ``None`` when no insertion happens (object already there).
        """
        if obj is None:
            return None
        if self.contains_object(obj):
            existing = self.get_key(obj)
            if existing is not None and existing == key:
                return None

        actual_key = key
        if actual_key is None or self.contains_key(actual_key):
            self._highest_xref_object_number += 1
            actual_key = COSObjectKey(self._highest_xref_object_number, 0)
            with contextlib.suppress(AttributeError):
                obj.set_key(actual_key)
        else:
            self._highest_xref_object_number = max(
                key.get_number(), self._highest_xref_object_number
            )

        self._key_pool[actual_key] = obj
        self._object_pool[id(obj)] = actual_key
        self._object_pool_obj[id(obj)] = obj
        return actual_key

    def get_key(self, obj: COSBase) -> COSObjectKey | None:
        """Return the registered key for ``obj`` (or its referent)."""
        if isinstance(obj, COSObject):
            inner = obj.get_object()
            if inner is not None:
                k = self._object_pool.get(id(inner))
                if k is not None:
                    return k
        return self._object_pool.get(id(obj))

    def contains_key(self, key: COSObjectKey) -> bool:
        return key in self._key_pool

    def get_object(self, key: COSObjectKey) -> COSBase | None:
        return self._key_pool.get(key)

    def contains_object(self, obj: COSBase) -> bool:
        if isinstance(obj, COSObject):
            inner = obj.get_object()
            if inner is not None and id(inner) in self._object_pool:
                return True
        return id(obj) in self._object_pool

    # Java's overloaded ``contains`` — keep separate names for clarity but
    # provide a unified ``contains`` that dispatches by type for parity.
    def contains(self, target: COSBase | COSObjectKey) -> bool:
        if isinstance(target, COSObjectKey):
            return self.contains_key(target)
        return self.contains_object(target)

    def get_highest_xref_object_number(self) -> int:
        return self._highest_xref_object_number

    def get_highest_x_ref_object_number(self) -> int:
        """Parity alias matching upstream snake-case of ``getHighestXRefObjectNumber``."""
        return self.get_highest_xref_object_number()


__all__ = ["COSObjectPool"]
