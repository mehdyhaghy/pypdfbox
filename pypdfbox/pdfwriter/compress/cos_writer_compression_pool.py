"""Document-wide compression orchestrator.

Mirrors ``org.apache.pdfbox.pdfwriter.compress.COSWriterCompressionPool``
(PDFBox 3.0, ``pdfbox/src/main/java/org/apache/pdfbox/pdfwriter/compress/
COSWriterCompressionPool.java``).

The pool walks the document trailer once, classifies each object into
``topLevelObjects`` (large/sensitive entries that must stay outside any
object stream) and ``objectStreamObjects`` (everything else), and exposes
:meth:`create_object_streams` to spin up :class:`COSWriterObjectStream`
batches once writing begins.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.pdfwriter.compress.compress_parameters import CompressParameters
from pypdfbox.pdfwriter.compress.cos_object_pool import COSObjectPool
from pypdfbox.pdfwriter.compress.cos_writer_object_stream import COSWriterObjectStream

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


class COSWriterCompressionPool:
    """Compress the contents of a :class:`PDDocument` for writing."""

    MINIMUM_SUPPORTED_VERSION = 1.6

    def __init__(
        self,
        document: PDDocument,
        parameters: CompressParameters | None = None,
    ) -> None:
        self._document = document
        self._parameters = parameters if parameters is not None else CompressParameters()
        cos_doc = document.get_document()
        self._object_pool = COSObjectPool(cos_doc.get_highest_xref_object_number())

        self._top_level_objects: list[COSObjectKey] = []
        self._object_stream_objects: list[COSObjectKey] = []
        self._all_direct_objects: set[int] = set()

        trailer = cos_doc.get_trailer()
        cos_base_list: list[COSBase] = []
        root = trailer.get_cos_dictionary(COSName.ROOT) if trailer else None
        if root is not None:
            cos_base_list.append(root)
        info = trailer.get_cos_dictionary(COSName.INFO) if trailer else None
        if info is not None:
            cos_base_list.append(info)
        while cos_base_list:
            cos_base_list = self._add_structure_list(cos_base_list)
        self._all_direct_objects.clear()
        self._object_stream_objects.sort(key=lambda k: (k.get_number(), k.get_generation()))
        self._top_level_objects.sort(key=lambda k: (k.get_number(), k.get_generation()))

    # ------------------------------------------------------------------
    # Pool population
    # ------------------------------------------------------------------
    def add_object_to_pool(
        self, key: COSObjectKey | None, base: COSBase
    ) -> COSBase | None:
        """Classify ``base`` and route it into the top-level or object-stream
        bucket. Mirrors upstream private ``addObjectToPool``."""
        current = base.get_object() if isinstance(base, COSObject) else base
        if current is None:
            return None
        if (key is not None and self._object_pool.contains_key(key)) or (
            key is None and self._object_pool.contains_object(current)
        ):
            return current

        encryption = getattr(self._document, "get_encryption", lambda: None)()
        trailer_root = (
            self._document.get_document().get_trailer().get_cos_dictionary(COSName.ROOT)
        )
        not_compressible = (
            (key is not None and key.get_generation() != 0)
            or isinstance(current, COSStream)
            or (encryption is not None and current is encryption.get_cos_object())
            or current is trailer_root
        )
        if not_compressible:
            actual_key = self._object_pool.put(key, current)
            if actual_key is None:
                return current
            if actual_key != key and isinstance(base, COSObject):
                with contextlib.suppress(AttributeError):
                    base.set_key(actual_key)
            self._top_level_objects.append(actual_key)
            return current

        actual_key = self._object_pool.put(key, current)
        if actual_key is None:
            return current
        if actual_key != key and isinstance(base, COSObject):
            with contextlib.suppress(AttributeError):
                base.set_key(actual_key)
        self._object_stream_objects.append(actual_key)
        return current

    def _add_structure_list(self, cos_base_list: list[COSBase]) -> list[COSBase]:
        cos_base_list_next: list[COSBase] = []
        for cos_base in cos_base_list:
            cos_base_list_next.extend(self.add_structure(cos_base))
        return cos_base_list_next

    def add_structure(self, current: COSBase) -> list[COSBase]:
        """Visit a COS structural node, register indirect children, and
        return the next-frontier list. Mirrors upstream private ``addStructure``."""
        base: COSBase | None = current
        if (
            isinstance(current, COSStream)
            or (isinstance(current, COSDictionary) and not current.is_direct())
            or (isinstance(current, COSArray) and not current.is_direct())
        ):
            base = self.add_object_to_pool(current.get_key(), current)
        elif isinstance(current, COSObject):
            inner = current.get_object()
            if inner is not None:  # pragma: no branch
                # Defensive: dangling COSObjects (inner is None) are
                # filtered out upstream of this call; the False arm has
                # no live caller.
                base = self.add_object_to_pool(current.get_key(), current)
        if isinstance(base, COSArray):
            return self.get_elements(list(base))
        if isinstance(base, COSDictionary):
            return self.get_elements(list(base.values()))
        return []

    def get_elements(self, elements: list[COSBase]) -> list[COSBase]:
        """Filter a sequence of COS children down to the ones the walker
        should recurse into. Mirrors upstream private ``getElements``."""
        result: list[COSBase] = []
        for element in elements:
            if self.filter_element(element):
                result.append(element)
        return result

    # Back-compat alias retained for callers using the previous private name.
    _filter_elements = get_elements

    def filter_element(self, element: COSBase) -> bool:
        """Mirrors upstream private ``filterElement`` (the single-element
        predicate used by :meth:`get_elements`)."""
        if isinstance(element, COSObject):
            key = element.get_key()
            if key is not None and self._object_pool.contains_key(key):
                pooled = self._object_pool.get_object(key)
                if pooled is not None and pooled is element.get_object():
                    return False
                element.set_key(None)
            return element.get_object() is not None
        if isinstance(element, COSArray) or (
            isinstance(element, COSDictionary) and id(element) not in self._all_direct_objects
        ):
            self._all_direct_objects.add(id(element))
            return True
        return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_top_level_objects(self) -> list[COSObjectKey]:
        return self._top_level_objects

    def get_object_stream_objects(self) -> list[COSObjectKey]:
        return self._object_stream_objects

    def contains(self, obj: COSBase) -> bool:
        return self._object_pool.contains_object(obj)

    def get_key(self, obj: COSBase) -> COSObjectKey | None:
        return self._object_pool.get_key(obj)

    def get_object(self, key: COSObjectKey) -> COSBase | None:
        return self._object_pool.get_object(key)

    def get_highest_xref_object_number(self) -> int:
        return self._object_pool.get_highest_xref_object_number()

    def get_highest_x_ref_object_number(self) -> int:
        """Mirrors upstream's ``getHighestXRefObjectNumber`` (Java spells
        the prefix ``XRef``; the parity matcher snake-cases that to
        ``x_ref``)."""
        return self._object_pool.get_highest_xref_object_number()

    def create_object_streams(self) -> list[COSWriterObjectStream]:
        """Pack the staged compressible objects into ``/ObjStm`` batches."""
        object_streams: list[COSWriterObjectStream] = []
        current: COSWriterObjectStream | None = None
        stream_size = self._parameters.get_object_stream_size()
        for i, key in enumerate(self._object_stream_objects):
            if current is None or i % stream_size == 0:
                current = COSWriterObjectStream(self)
                object_streams.append(current)
            current.prepare_stream_object(key, self._object_pool.get_object(key))
        return object_streams


__all__ = ["COSWriterCompressionPool"]
