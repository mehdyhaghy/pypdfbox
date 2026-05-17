"""Coverage-boost tests for ``pypdfbox.pdfwriter.compress.cos_object_pool``.

Exercises the bidirectional key/object lookups, COSObject indirection paths,
the parity ``contains`` overload, and the ``set_key`` AttributeError swallow
when the registered object isn't a real ``COSBase``.
"""

from __future__ import annotations

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_string import COSString
from pypdfbox.pdfwriter.compress.cos_object_pool import COSObjectPool

# ----------------------------------------------------------- put / get_key


def test_put_none_object_returns_none() -> None:
    pool = COSObjectPool()
    assert pool.put(COSObjectKey(1, 0), None) is None
    # Nothing got registered.
    assert pool.contains_key(COSObjectKey(1, 0)) is False


def test_put_existing_object_with_matching_key_returns_none() -> None:
    """Putting the same object under the same key is a no-op (returns None)."""
    pool = COSObjectPool()
    obj = COSString(b"x")
    key = COSObjectKey(5, 0)
    actual = pool.put(key, obj)
    assert actual == key
    # Same key, same object → no-op.
    assert pool.put(key, obj) is None


def test_put_existing_object_under_different_key_assigns_fresh_number() -> None:
    """When obj already registered under a different key, a new number is minted."""
    pool = COSObjectPool(highest_xref_object_number=10)
    obj = COSString(b"y")
    original = pool.put(COSObjectKey(3, 0), obj)
    assert original == COSObjectKey(3, 0)
    # Re-registering with a None key falls through to fresh-number branch.
    fresh = pool.put(None, obj)
    assert fresh is not None
    assert fresh.get_number() == 11
    # Highest counter bumped.
    assert pool.get_highest_xref_object_number() == 11


def test_put_none_key_mints_fresh_number_and_attaches_to_object() -> None:
    """``key=None`` should assign a fresh number AND propagate via set_key."""
    pool = COSObjectPool(highest_xref_object_number=4)
    obj = COSString(b"z")
    actual = pool.put(None, obj)
    assert actual is not None
    assert actual.get_number() == 5
    assert actual.get_generation() == 0
    # The pool now contains the object under the minted key.
    assert pool.contains_key(actual) is True
    assert pool.get_object(actual) is obj


def test_put_with_already_used_key_mints_fresh_number() -> None:
    """When the requested key is already taken, a fresh one is generated."""
    pool = COSObjectPool()
    first = COSString(b"a")
    second = COSString(b"b")
    pool.put(COSObjectKey(7, 0), first)
    actual = pool.put(COSObjectKey(7, 0), second)
    assert actual is not None
    assert actual.get_number() != 7
    # The originally-requested key still maps to the first object.
    assert pool.get_object(COSObjectKey(7, 0)) is first
    # The second object lives under the minted key.
    assert pool.get_object(actual) is second


def test_put_advances_highest_when_supplied_key_is_larger() -> None:
    pool = COSObjectPool(highest_xref_object_number=2)
    pool.put(COSObjectKey(20, 0), COSString(b"big"))
    assert pool.get_highest_xref_object_number() == 20


def test_put_does_not_lower_highest_when_supplied_key_is_smaller() -> None:
    pool = COSObjectPool(highest_xref_object_number=50)
    pool.put(COSObjectKey(3, 0), COSString(b"small"))
    assert pool.get_highest_xref_object_number() == 50


def test_put_swallows_set_key_attribute_error_on_non_cosbase() -> None:
    """The pool gracefully accepts plain objects lacking ``set_key``."""
    pool = COSObjectPool()

    class _NoSetKey:
        pass

    # Should not raise AttributeError — the suppress() block handles it.
    actual = pool.put(None, _NoSetKey())
    assert actual is not None
    assert actual.get_number() == 1


# ----------------------------------------------------------------- get_key


def test_get_key_for_direct_object() -> None:
    pool = COSObjectPool()
    obj = COSString(b"q")
    key = pool.put(COSObjectKey(9, 0), obj)
    assert pool.get_key(obj) == key


def test_get_key_resolves_cos_object_indirection() -> None:
    """A ``COSObject`` wrapper resolves to the referent's key."""
    pool = COSObjectPool()
    target = COSDictionary()
    pool.put(COSObjectKey(2, 0), target)
    wrapper = COSObject(2, 0, resolved=target)
    assert pool.get_key(wrapper) == COSObjectKey(2, 0)


def test_get_key_for_unknown_object_returns_none() -> None:
    pool = COSObjectPool()
    assert pool.get_key(COSString(b"orphan")) is None


def test_get_key_for_unregistered_cos_object_with_unregistered_referent() -> None:
    """A COSObject pointing at an unregistered referent yields None."""
    pool = COSObjectPool()
    wrapper = COSObject(99, 0, resolved=COSDictionary())
    assert pool.get_key(wrapper) is None


def test_get_key_for_cos_object_with_none_referent_returns_none() -> None:
    """A COSObject whose loader returns None falls through to id-lookup."""
    pool = COSObjectPool()
    wrapper = COSObject(7, 0)
    # No resolution — inner is None. Falls to id-based lookup → None.
    assert pool.get_key(wrapper) is None


# ----------------------------------------------------------- contains_*


def test_contains_key_and_object() -> None:
    pool = COSObjectPool()
    obj = COSArray()
    key = pool.put(COSObjectKey(11, 0), obj)
    assert pool.contains_key(key) is True
    assert pool.contains_object(obj) is True
    assert pool.contains_key(COSObjectKey(999, 0)) is False
    assert pool.contains_object(COSArray()) is False


def test_contains_object_for_cos_object_referent_match() -> None:
    pool = COSObjectPool()
    target = COSString(b"r")
    pool.put(COSObjectKey(15, 0), target)
    wrapper = COSObject(15, 0, resolved=target)
    assert pool.contains_object(wrapper) is True


def test_contains_object_for_cos_object_with_unregistered_referent() -> None:
    pool = COSObjectPool()
    wrapper = COSObject(20, 0, resolved=COSString(b"new"))
    assert pool.contains_object(wrapper) is False


def test_contains_object_for_cos_object_without_referent() -> None:
    pool = COSObjectPool()
    wrapper = COSObject(21, 0)
    assert pool.contains_object(wrapper) is False


# ------------------------------------------------- overloaded ``contains``


def test_contains_dispatches_by_type() -> None:
    pool = COSObjectPool()
    obj = COSString(b"d")
    key = pool.put(COSObjectKey(30, 0), obj)
    # Key path.
    assert pool.contains(key) is True
    # Object path.
    assert pool.contains(obj) is True
    # Both miss correctly.
    assert pool.contains(COSObjectKey(999, 0)) is False
    assert pool.contains(COSString(b"miss")) is False


# ------------------------------------------------------------ get_object


def test_get_object_returns_registered_value() -> None:
    pool = COSObjectPool()
    obj = COSDictionary()
    pool.put(COSObjectKey(40, 0), obj)
    assert pool.get_object(COSObjectKey(40, 0)) is obj


def test_get_object_returns_none_for_unknown_key() -> None:
    pool = COSObjectPool()
    assert pool.get_object(COSObjectKey(123, 0)) is None


# ---------------------------- highest-xref-object-number snake-case alias


def test_get_highest_x_ref_object_number_matches_canonical() -> None:
    pool = COSObjectPool(highest_xref_object_number=15)
    assert pool.get_highest_x_ref_object_number() == 15
    pool.put(None, COSString(b"bump"))
    assert pool.get_highest_x_ref_object_number() == 16
    assert pool.get_highest_x_ref_object_number() == pool.get_highest_xref_object_number()


def test_initial_highest_clamps_at_zero() -> None:
    """A negative seed is clamped to 0 (per ``max(0, …)``)."""
    pool = COSObjectPool(highest_xref_object_number=-5)
    assert pool.get_highest_xref_object_number() == 0
