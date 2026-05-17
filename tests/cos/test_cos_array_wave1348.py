"""Wave 1348 coverage-boost tests for ``pypdfbox.cos.cos_array``.

Targets residual branches:

  * module-level ``_add_to_collection`` ``append`` fallback (lines 27-29).
  * ``growToSize`` camelCase Java-name alias (line 220).
  * ``reset_object_keys`` short-circuit when an indirect key is already
    in the visited set (line 496) and addition of unseen indirect keys
    (line 499 / ``elif`` arm).
  * ``iterator()`` and ``maybe_wrap`` (lines 529, 544-554).
"""
from __future__ import annotations

from pypdfbox.cos.cos_array import COSArray, _add_to_collection
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.cos.cos_object_key import COSObjectKey

# ---------- _add_to_collection ----------


def test_add_to_collection_append_fallback() -> None:
    """A plain ``list`` lacks ``add``; the helper falls back to ``append``."""
    sink: list[int] = []
    _add_to_collection(sink, 7)
    assert sink == [7]


def test_add_to_collection_no_op_when_neither_method() -> None:
    """Objects exposing neither ``add`` nor ``append`` are silently ignored."""

    class _Sink:
        pass

    sink = _Sink()
    # Must not raise.
    _add_to_collection(sink, "x")


# ---------- growToSize alias ----------


def test_grow_to_size_camel_case_alias() -> None:
    arr = COSArray()
    arr.growToSize(3)  # noqa: N802 — testing the Java-name alias
    assert len(arr) == 3


# ---------- reset_object_keys ----------


def test_reset_object_keys_skips_already_visited_keys() -> None:
    """When an indirect ``COSObject`` shares its key with an entry already
    in the ``indirect_objects`` collection, the loop short-circuits (line
    496) rather than recursing into it."""
    inner = COSDictionary()
    inner.set_key(COSObjectKey(7, 0))
    indirect = COSObject(7, 0, resolved=inner)

    arr = COSArray([indirect])
    visited: set[COSObjectKey] = {COSObjectKey(7, 0)}
    result = arr.reset_object_keys(visited)
    # No new keys recorded — the only key was already in the set.
    assert result == {COSObjectKey(7, 0)}


def test_reset_object_keys_recurses_into_nested_array() -> None:
    """A nested ``COSArray`` (direct, no indirect wrap) triggers the
    recursive ``child.reset_object_keys(...)`` branch (line 499)."""
    inner_leaf_obj = COSObject(5, 0, resolved=COSInteger.get(7))
    inner_arr = COSArray([inner_leaf_obj])
    outer = COSArray([inner_arr])
    visited: set[COSObjectKey] = set()
    outer.reset_object_keys(visited)
    # The recursion descended into ``inner_arr`` and recorded the inner key.
    assert COSObjectKey(5, 0) in visited


def test_reset_object_keys_records_indirect_simple_value() -> None:
    """An indirect ``COSObject`` resolving to a non-dict/non-array (i.e.
    a leaf) takes the ``elif indirect_key is not None`` arm and the key
    gets recorded in the visited set."""
    leaf = COSInteger.get(42)
    indirect = COSObject(11, 0, resolved=leaf)
    arr = COSArray([indirect])
    visited: set[COSObjectKey] = set()
    arr.reset_object_keys(visited)
    assert COSObjectKey(11, 0) in visited


# ---------- iterator + maybe_wrap ----------


def test_iterator_alias_matches_iter() -> None:
    arr = COSArray([COSInteger.get(1), COSInteger.get(2)])
    assert list(arr.iterator()) == list(iter(arr))


def test_maybe_wrap_indirect_dict_is_rewrapped() -> None:
    """A non-direct ``COSDictionary`` with a recorded key is rewrapped in
    a ``COSObject`` pointing at the same key."""
    inner = COSDictionary()
    inner.set_direct(False)
    inner.set_key(COSObjectKey(3, 0))

    wrapped = COSArray.maybe_wrap(inner)
    assert isinstance(wrapped, COSObject)
    assert wrapped.object_number == 3
    assert wrapped.generation_number == 0
    assert wrapped.get_object() is inner


def test_maybe_wrap_direct_value_pass_through() -> None:
    """Direct dicts (the common case) pass through unchanged."""
    inner = COSDictionary()
    assert COSArray.maybe_wrap(inner) is inner


def test_maybe_wrap_indirect_dict_without_key_pass_through() -> None:
    """An indirect dict missing a recorded key passes through unchanged."""
    inner = COSDictionary()
    inner.set_direct(False)
    # No set_object_key call => get_key() returns None.
    assert COSArray.maybe_wrap(inner) is inner


def test_maybe_wrap_leaf_pass_through() -> None:
    """Non-dict/array leaves pass through unchanged."""
    leaf = COSInteger.get(5)
    assert COSArray.maybe_wrap(leaf) is leaf
