"""Coverage-boost tests for ``COSWriterCompressionPool``.

Drives:
 - the trailer walk over both /Root and /Info
 - ``add_object_to_pool`` early-returns (None object, already-in-pool)
 - the not-compressible branches (non-zero gen, COSStream, encryption,
   trailer root)
 - the actual_key reassignment + ``set_key`` callback
 - ``add_structure`` for COSObject + the empty-fall-through
 - ``filter_element`` for COSObject (pool hit / set_key None / no inner)
 - the small accessors (get_top_level_objects, get_object_stream_objects,
   contains, get_key, get_object, get_highest_x_ref_object_number)
 - ``create_object_streams`` batching across the configured stream size
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
from pypdfbox.pdfwriter.compress.compress_parameters import CompressParameters
from pypdfbox.pdfwriter.compress.cos_writer_compression_pool import (
    COSWriterCompressionPool,
)

# ---------------------------------------------------------------------
# Stub PDDocument — keeps the pool decoupled from the full pdmodel layer
# ---------------------------------------------------------------------


class _StubDoc:
    """Minimal PDDocument shape needed by :class:`COSWriterCompressionPool`."""

    def __init__(
        self,
        cos_doc: COSDocument,
        encryption: Any = None,
    ) -> None:
        self._cos = cos_doc
        self._encryption = encryption

    def get_document(self) -> COSDocument:
        return self._cos

    def get_encryption(self) -> Any:
        return self._encryption


def _empty_doc() -> COSDocument:
    cos_doc = COSDocument()
    cos_doc.set_trailer(COSDictionary())
    return cos_doc


def _doc_with_trailer(root: COSDictionary | None, info: COSDictionary | None = None) -> _StubDoc:
    cos_doc = _empty_doc()
    trailer = cos_doc.get_trailer()
    assert trailer is not None
    if root is not None:
        trailer.set_item(COSName.ROOT, root)
    if info is not None:
        trailer.set_item(COSName.INFO, info)
    return _StubDoc(cos_doc)


# ---------------------------------------------------------------------
# Bootstrap — empty trailer / Info-only trailer
# ---------------------------------------------------------------------


def test_pool_with_empty_trailer_initialises_empty_lists() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    assert pool.get_top_level_objects() == []
    assert pool.get_object_stream_objects() == []


def test_pool_picks_up_info_dict_in_trailer() -> None:
    info = COSDictionary()
    info.set_item(COSName.get_pdf_name("Author"), COSInteger.get(1))
    doc = _doc_with_trailer(root=None, info=info)
    pool = COSWriterCompressionPool(doc)
    # /Info is direct (no key set) so the walk visits its values but the
    # info dict itself stays inline — no top-level entry should be created.
    # The integer leaf is also direct, so the pool stays empty.
    assert pool.get_top_level_objects() == []


# ---------------------------------------------------------------------
# Root traversal — indirect root + nested indirect entry
# ---------------------------------------------------------------------


def test_pool_classifies_indirect_root_as_top_level() -> None:
    root = COSDictionary()
    root.set_key(COSObjectKey(1, 0))
    doc = _doc_with_trailer(root)
    pool = COSWriterCompressionPool(doc)
    top = pool.get_top_level_objects()
    assert COSObjectKey(1, 0) in top


def test_pool_classifies_indirect_stream_as_top_level() -> None:
    root = COSDictionary()
    root.set_key(COSObjectKey(1, 0))
    stream = COSStream()
    stream.set_key(COSObjectKey(2, 0))
    root.set_item(COSName.get_pdf_name("Body"), stream)
    doc = _doc_with_trailer(root)
    pool = COSWriterCompressionPool(doc)
    top = pool.get_top_level_objects()
    # Streams always stay top-level.
    assert COSObjectKey(2, 0) in top


def test_pool_routes_indirect_dictionary_into_object_stream() -> None:
    root = COSDictionary()
    root.set_key(COSObjectKey(1, 0))
    child = COSDictionary()
    child.set_key(COSObjectKey(3, 0))
    root.set_item(COSName.get_pdf_name("Child"), child)
    doc = _doc_with_trailer(root)
    pool = COSWriterCompressionPool(doc)
    assert COSObjectKey(3, 0) in pool.get_object_stream_objects()


# ---------------------------------------------------------------------
# Non-compressible branches
# ---------------------------------------------------------------------


def test_non_zero_generation_keeps_object_top_level() -> None:
    root = COSDictionary()
    root.set_key(COSObjectKey(1, 0))
    nested = COSDictionary()
    nested.set_key(COSObjectKey(5, 1))  # gen != 0
    root.set_item(COSName.get_pdf_name("Nested"), nested)
    doc = _doc_with_trailer(root)
    pool = COSWriterCompressionPool(doc)
    assert COSObjectKey(5, 1) in pool.get_top_level_objects()


def test_encryption_cos_object_kept_top_level() -> None:
    root = COSDictionary()
    root.set_key(COSObjectKey(1, 0))
    encrypt_dict = COSDictionary()
    encrypt_dict.set_key(COSObjectKey(7, 0))

    class _Enc:
        def get_cos_object(self) -> COSDictionary:
            return encrypt_dict

    root.set_item(COSName.get_pdf_name("AuxEnc"), encrypt_dict)
    cos_doc = _empty_doc()
    cos_doc.get_trailer().set_item(COSName.ROOT, root)
    stub = _StubDoc(cos_doc, encryption=_Enc())
    pool = COSWriterCompressionPool(stub)
    assert COSObjectKey(7, 0) in pool.get_top_level_objects()
    # And it must NOT also appear in the compressible bucket.
    assert COSObjectKey(7, 0) not in pool.get_object_stream_objects()


def test_root_itself_is_always_top_level() -> None:
    # Root is reachable via the trailer and the not_compressible branch
    # explicitly excludes it via the ``current is trailer_root`` clause.
    root = COSDictionary()
    root.set_key(COSObjectKey(1, 0))
    doc = _doc_with_trailer(root)
    pool = COSWriterCompressionPool(doc)
    assert pool.get_top_level_objects() == [COSObjectKey(1, 0)]
    assert pool.get_object_stream_objects() == []


# ---------------------------------------------------------------------
# add_object_to_pool — None / already-pooled / set_key reassignment
# ---------------------------------------------------------------------


def test_add_object_to_pool_none_object_returns_none() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    # COSObject whose inner resolves to None — should bail at the first
    # ``current is None`` guard.
    indirect = COSObject(99, 0)
    result = pool.add_object_to_pool(None, indirect)
    assert result is None


def test_add_object_to_pool_already_pooled_short_circuits() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    direct = COSDictionary()
    key = COSObjectKey(11, 0)
    # First insertion populates the pool.
    pool.add_object_to_pool(key, direct)
    # Second insertion with the same key — short-circuits at the
    # ``contains_key`` guard and returns ``current`` unchanged.
    again = pool.add_object_to_pool(key, direct)
    assert again is direct


def test_add_object_to_pool_already_pooled_without_key() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    direct = COSDictionary()
    pool.add_object_to_pool(COSObjectKey(2, 0), direct)
    # Re-add the same object with key=None — exercises the
    # ``contains_object`` branch.
    again = pool.add_object_to_pool(None, direct)
    assert again is direct


def test_add_object_to_pool_mints_key_and_calls_set_key_on_wrapper() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    inner = COSDictionary()
    indirect = COSObject(0, 0, resolved=inner)
    # key=None forces the pool to mint a fresh key — ``actual_key != key``
    # branch fires, which propagates the new key back via ``set_key``
    # on the COSObject wrapper.
    pool.add_object_to_pool(None, indirect)
    new_key = indirect.get_key()
    assert new_key is not None
    assert new_key.get_number() >= 1


def test_add_object_to_pool_not_compressible_duplicate_returns_current() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    # COSStream is unconditionally not-compressible. Force-insert via the
    # pool with a known key, then bypass the front-door ``contains_key``
    # guard by removing the key from the pool's reverse map and re-routing
    # under the original key — this drives ``put`` down its
    # "existing == key" branch, which returns None, triggering the
    # ``actual_key is None: return current`` early-out on line 96.
    stream = COSStream()
    key = COSObjectKey(70, 0)
    pool._object_pool.put(key, stream)
    # Now ``contains_key(key)`` is True, but we want to enter the
    # not-compressible path *without* the front-door short-circuit. Use
    # key=None — the front-door check then falls to
    # ``contains_object(current)`` which is True → returns ``current``
    # immediately (line 81 path). To exercise line 96 we must take a
    # different route: force-clear the key map but leave the object map
    # populated so ``contains_object`` stays False initially.
    pool._object_pool._key_pool.pop(key, None)
    # Re-call add_object_to_pool with the original key, which is now
    # NOT in the key pool, so the guard at the top passes. ``put`` then
    # sees ``contains_object(stream)`` True and ``existing == key`` True
    # (same key still mapped via _object_pool[id(stream)]), so it returns
    # None — driving line 96.
    again = pool.add_object_to_pool(key, stream)
    assert again is stream


def test_add_object_to_pool_not_compressible_mints_key_on_wrapper() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    inner_stream = COSStream()
    indirect = COSObject(0, 0, resolved=inner_stream)
    # No key → not-compressible branch (COSStream) mints a key and calls
    # set_key on the wrapper (lines 98-99).
    pool.add_object_to_pool(None, indirect)
    assert indirect.get_key() is not None


def test_add_object_to_pool_compressible_duplicate_returns_current() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    d = COSDictionary()
    key = COSObjectKey(80, 0)
    pool._object_pool.put(key, d)
    # Strip the key→obj entry but leave the obj→key entry so the front
    # guard passes (``contains_key`` False) while ``put`` still finds
    # ``existing == key`` and returns None — exercising line 105.
    pool._object_pool._key_pool.pop(key, None)
    again = pool.add_object_to_pool(key, d)
    assert again is d


def test_add_object_to_pool_repools_foreign_object_under_taken_key() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    first = COSDictionary()
    pool.add_object_to_pool(COSObjectKey(60, 0), first)
    # PDFBOX-6203: adding a *different* object under the same key no longer
    # short-circuits — the mixed-up key is detected (pooled entry is not the
    # same object) and the foreign object is pooled under a freshly minted
    # key, while the original key keeps its original object.
    foreign = COSDictionary()
    result = pool.add_object_to_pool(COSObjectKey(60, 0), foreign)
    assert result is foreign
    assert pool.get_object(COSObjectKey(60, 0)) is first
    foreign_key = pool.get_key(foreign)
    assert foreign_key is not None
    assert foreign_key != COSObjectKey(60, 0)
    assert pool.get_object(foreign_key) is foreign


# ---------------------------------------------------------------------
# add_structure — COSObject branch + empty-tail
# ---------------------------------------------------------------------


def test_add_structure_returns_empty_for_leaf_integer() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    # COSInteger is neither COSStream / COSDictionary / COSArray / COSObject
    # — add_structure should return [] without classifying it.
    leaf = COSInteger.get(7)
    assert pool.add_structure(leaf) == []


def test_add_structure_for_cos_object_with_inner() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    inner = COSDictionary()
    inner.set_item(COSName.get_pdf_name("X"), COSInteger.get(1))
    wrapper = COSObject(0, 0, resolved=inner)
    wrapper.set_key(COSObjectKey(20, 0))
    next_frontier = pool.add_structure(wrapper)
    # The wrapper's resolved dict becomes the pool entry; the recursion
    # frontier is the inner dictionary's values (filtered).
    assert isinstance(next_frontier, list)


def test_add_structure_array_recurses_via_filter() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    arr = COSArray()
    arr.set_key(COSObjectKey(21, 0))  # indirect array
    inner_dict = COSDictionary()
    inner_dict.set_key(COSObjectKey(22, 0))
    arr.add(inner_dict)
    frontier = pool.add_structure(arr)
    # frontier should include the inner dict (it is a COSDictionary not
    # yet seen as direct).
    assert inner_dict in frontier


# ---------------------------------------------------------------------
# filter_element — COSObject branches
# ---------------------------------------------------------------------


def test_filter_element_cos_object_pool_hit_drops_element() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    inner = COSDictionary()
    indirect = COSObject(0, 0, resolved=inner)
    indirect.set_key(COSObjectKey(30, 0))
    pool._object_pool.put(COSObjectKey(30, 0), inner)
    # Pool hit + same inner → filter_element returns False.
    assert pool.filter_element(indirect) is False


def test_filter_element_cos_object_pool_key_with_different_object() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    pooled_inner = COSDictionary()
    foreign_inner = COSDictionary()
    indirect = COSObject(0, 0, resolved=foreign_inner)
    indirect.set_key(COSObjectKey(40, 0))
    pool._object_pool.put(COSObjectKey(40, 0), pooled_inner)
    # Key matches but pooled object is different — element.set_key(None)
    # is called and the element is kept (returns True since inner is not None).
    assert pool.filter_element(indirect) is True
    assert indirect.get_key() is None


def test_filter_element_cos_object_without_key_returns_true_when_inner() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    inner = COSDictionary()
    indirect = COSObject(0, 0, resolved=inner)
    # No key set on the wrapper — covers the "no key" branch.
    assert pool.filter_element(indirect) is True


def test_filter_element_cos_object_without_inner_returns_false() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    indirect = COSObject(7, 0)  # no resolved payload
    assert pool.filter_element(indirect) is False


def test_filter_element_rejects_already_visited_dictionary() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    d = COSDictionary()
    # First call adds id(d) to the visited set and returns True.
    assert pool.filter_element(d) is True
    # Second call should now return False (already visited).
    # NB: in the live walk ``_all_direct_objects`` gets cleared after
    # construction, but ``filter_element`` itself can be called from
    # tests in isolation.
    assert pool.filter_element(d) is False


def test_filter_element_rejects_unknown_type() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    # COSInteger isn't a COSObject / COSArray / COSDictionary — falls
    # through to ``return False``.
    assert pool.filter_element(COSInteger.get(5)) is False


# ---------------------------------------------------------------------
# Small accessors
# ---------------------------------------------------------------------


def test_simple_accessors_round_trip() -> None:
    root = COSDictionary()
    root.set_key(COSObjectKey(1, 0))
    nested = COSDictionary()
    nested.set_key(COSObjectKey(2, 0))
    root.set_item(COSName.get_pdf_name("N"), nested)
    doc = _doc_with_trailer(root)
    pool = COSWriterCompressionPool(doc)

    # contains / get_key / get_object
    assert pool.contains(root)
    assert pool.get_key(root) == COSObjectKey(1, 0)
    assert pool.get_object(COSObjectKey(1, 0)) is root
    # get_highest_x_ref_object_number parity alias matches snake-cased name.
    assert (
        pool.get_highest_x_ref_object_number()
        == pool.get_highest_xref_object_number()
    )
    assert pool.get_highest_xref_object_number() >= 2


# ---------------------------------------------------------------------
# create_object_streams — batching
# ---------------------------------------------------------------------


def test_create_object_streams_empty_when_no_compressibles() -> None:
    cos_doc = _empty_doc()
    pool = COSWriterCompressionPool(_StubDoc(cos_doc))
    assert pool.create_object_streams() == []


def test_create_object_streams_batches_by_stream_size() -> None:
    root = COSDictionary()
    root.set_key(COSObjectKey(1, 0))
    # Five indirect dicts → with stream_size=2 we expect 3 streams (2+2+1).
    for i in range(2, 7):
        child = COSDictionary()
        child.set_key(COSObjectKey(i, 0))
        root.set_item(COSName.get_pdf_name(f"K{i}"), child)
    doc = _doc_with_trailer(root)
    pool = COSWriterCompressionPool(doc, CompressParameters(2))
    streams = pool.create_object_streams()
    assert len(streams) == 3
    # And total prepared keys across the streams matches the bucket size.
    total = sum(len(s.get_prepared_keys()) for s in streams)
    assert total == len(pool.get_object_stream_objects())


def test_create_object_streams_default_size_one_batch() -> None:
    root = COSDictionary()
    root.set_key(COSObjectKey(1, 0))
    nested = COSDictionary()
    nested.set_key(COSObjectKey(2, 0))
    root.set_item(COSName.get_pdf_name("Child"), nested)
    doc = _doc_with_trailer(root)
    pool = COSWriterCompressionPool(doc)
    streams = pool.create_object_streams()
    assert len(streams) == 1
    assert streams[0].get_prepared_keys()[0].get_number() == 2
