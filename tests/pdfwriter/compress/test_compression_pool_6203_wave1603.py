"""PDFBOX-6203 (parts 1+2) — compression pool mixed-up-key handling.

Net upstream shape (commits 139fa725/f02a510a as amended by the PDFBOX-5660
follow-ups, final 513aa3ed):

- ``add_object_to_pool``: when ``key`` is already pooled, only skip if the
  pooled object *is* the same object (identity against the resolved object
  or the wrapper) — otherwise pool the object anyway under a fresh key.
- ``add_structure``: pool only when ``not current.is_direct()`` and current
  is a COSDictionary or COSArray; COSStream is a COSDictionary subclass, so
  the direct-check now applies to streams too.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_document import COSDocument
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.pdfwriter.compress.cos_writer_compression_pool import (
    COSWriterCompressionPool,
)


class _StubDoc:
    """Minimal PDDocument shape needed by :class:`COSWriterCompressionPool`."""

    def __init__(self, cos_doc: COSDocument, encryption: Any = None) -> None:
        self._cos = cos_doc
        self._encryption = encryption

    def get_document(self) -> COSDocument:
        return self._cos

    def get_encryption(self) -> Any:
        return self._encryption


def _pool() -> COSWriterCompressionPool:
    cos_doc = COSDocument()
    cos_doc.set_trailer(COSDictionary())
    return COSWriterCompressionPool(_StubDoc(cos_doc))


# ---------------------------------------------------------------------
# add_object_to_pool — identity-skip vs mixed-up-key re-pool
# ---------------------------------------------------------------------


def test_same_object_under_same_key_is_skipped() -> None:
    pool = _pool()
    d = COSDictionary()
    key = COSObjectKey(10, 0)
    assert pool.add_object_to_pool(key, d) is d
    before = list(pool.get_object_stream_objects())
    # Identity match: pooled entry IS the same object → skip, no re-pool.
    assert pool.add_object_to_pool(key, d) is d
    assert pool.get_object_stream_objects() == before
    assert pool.get_object(key) is d


def test_same_resolved_object_via_wrapper_is_skipped() -> None:
    pool = _pool()
    inner = COSDictionary()
    key = COSObjectKey(11, 0)
    pool.add_object_to_pool(key, inner)
    wrapper = COSObject(11, 0, resolved=inner)
    wrapper.set_key(key)
    before = list(pool.get_object_stream_objects())
    # pooled is current (the resolved dict) → identity-skip.
    assert pool.add_object_to_pool(key, wrapper) is inner
    assert pool.get_object_stream_objects() == before


def test_pooled_wrapper_identity_also_skips() -> None:
    pool = _pool()
    inner = COSDictionary()
    wrapper = COSObject(12, 0, resolved=inner)
    key = COSObjectKey(12, 0)
    # Force the wrapper itself in as the pooled entry so the ``pooled is
    # base`` arm of the identity check is what fires.
    pool._object_pool.put(key, wrapper)
    before = list(pool.get_object_stream_objects())
    assert pool.add_object_to_pool(key, wrapper) is inner
    assert pool.get_object_stream_objects() == before


def test_mixed_up_key_repools_under_fresh_key() -> None:
    pool = _pool()
    first = COSDictionary()
    key = COSObjectKey(20, 0)
    pool.add_object_to_pool(key, first)
    # Same key, different object: pre-6203 this was skipped and the object
    # was silently dropped from the output; now it is pooled anyway.
    second = COSDictionary()
    second.set_item(COSName.get_pdf_name("Marker"), COSInteger.get(1))
    assert pool.add_object_to_pool(key, second) is second
    assert pool.get_object(key) is first  # original mapping untouched
    fresh_key = pool.get_key(second)
    assert fresh_key is not None
    assert fresh_key != key
    assert pool.get_object(fresh_key) is second
    assert fresh_key in pool.get_object_stream_objects()


def test_mixed_up_key_updates_wrapper_key() -> None:
    pool = _pool()
    first = COSDictionary()
    key = COSObjectKey(30, 0)
    pool.add_object_to_pool(key, first)
    inner = COSDictionary()
    wrapper = COSObject(30, 0, resolved=inner)
    wrapper.set_key(key)
    assert pool.add_object_to_pool(key, wrapper) is inner
    # The wrapper's key is rewritten to the freshly minted one.
    assert wrapper.get_key() is not None
    assert wrapper.get_key() != key
    assert pool.get_object(wrapper.get_key()) is inner


def test_mixed_up_key_stream_repools_as_top_level() -> None:
    pool = _pool()
    first = COSDictionary()
    key = COSObjectKey(40, 0)
    pool.add_object_to_pool(key, first)
    stream = COSStream()
    assert pool.add_object_to_pool(key, stream) is stream
    fresh_key = pool.get_key(stream)
    assert fresh_key is not None
    assert fresh_key != key
    # Streams are never compressible → the re-pooled entry is top-level.
    assert fresh_key in pool.get_top_level_objects()
    assert fresh_key not in pool.get_object_stream_objects()


# ---------------------------------------------------------------------
# add_structure — is_direct guard (incl. COSStream)
# ---------------------------------------------------------------------


def test_add_structure_direct_dictionary_not_pooled() -> None:
    pool = _pool()
    d = COSDictionary()
    d.set_direct(True)
    d.set_item(COSName.get_pdf_name("A"), COSInteger.get(1))
    pool.add_structure(d)
    assert not pool.contains(d)
    assert pool.get_top_level_objects() == []
    assert pool.get_object_stream_objects() == []


def test_add_structure_indirect_dictionary_pooled() -> None:
    pool = _pool()
    d = COSDictionary()
    d.set_key(COSObjectKey(50, 0))
    pool.add_structure(d)
    assert pool.contains(d)
    assert COSObjectKey(50, 0) in pool.get_object_stream_objects()


def test_add_structure_direct_array_not_pooled() -> None:
    pool = _pool()
    arr = COSArray()
    arr.set_direct(True)
    arr.add(COSInteger.get(1))
    pool.add_structure(arr)
    assert not pool.contains(arr)
    assert pool.get_object_stream_objects() == []


def test_add_structure_direct_stream_not_pooled() -> None:
    pool = _pool()
    stream = COSStream()
    stream.set_direct(True)
    # Pre-6203 the COSStream branch pooled unconditionally; the direct-check
    # now applies to streams too (COSStream is a COSDictionary subclass).
    pool.add_structure(stream)
    assert not pool.contains(stream)
    assert pool.get_top_level_objects() == []
    assert pool.get_object_stream_objects() == []


def test_add_structure_indirect_stream_pooled_top_level() -> None:
    pool = _pool()
    stream = COSStream()
    stream.set_key(COSObjectKey(60, 0))
    assert not stream.is_direct()
    pool.add_structure(stream)
    assert pool.contains(stream)
    assert COSObjectKey(60, 0) in pool.get_top_level_objects()
    assert COSObjectKey(60, 0) not in pool.get_object_stream_objects()


def test_add_structure_direct_stream_children_still_walked() -> None:
    pool = _pool()
    stream = COSStream()
    stream.set_direct(True)
    child = COSDictionary()
    child.set_key(COSObjectKey(70, 0))
    stream.set_item(COSName.get_pdf_name("Child"), child)
    frontier = pool.add_structure(stream)
    # The stream itself is skipped but its values remain on the frontier.
    assert child in frontier
