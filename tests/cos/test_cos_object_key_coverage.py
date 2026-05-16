"""Coverage backfill for :class:`pypdfbox.cos.cos_object_key.COSObjectKey`.

Targets the legacy alias surface (``object_number`` / ``generation_number``
/ ``stream_index``), the Java-name parity aliases (``equals``, ``hash_code``,
``to_string``, ``compare_to``), the ordering operators, and the constructor
guards.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_object_key import COSObjectKey


def test_get_internal_hash_packs_number_and_generation() -> None:
    key = COSObjectKey(5, 7)
    # number << 16 | generation
    assert key.get_internal_hash() == (5 << 16) | 7


def test_get_stream_index_defaults_to_minus_one() -> None:
    assert COSObjectKey(3).get_stream_index() == -1


def test_get_stream_index_explicit() -> None:
    assert COSObjectKey(3, 0, 42).get_stream_index() == 42


def test_legacy_property_aliases() -> None:
    key = COSObjectKey(11, 2, 4)
    assert key.object_number == 11
    assert key.generation_number == 2
    assert key.stream_index == 4


def test_constructor_rejects_negative_number() -> None:
    with pytest.raises(ValueError, match="Object number"):
        COSObjectKey(-1)


def test_constructor_rejects_negative_generation() -> None:
    with pytest.raises(ValueError, match="Generation number"):
        COSObjectKey(1, -1)


def test_eq_same_number_and_generation() -> None:
    assert COSObjectKey(5, 1) == COSObjectKey(5, 1)


def test_eq_different_numbers_not_equal() -> None:
    assert COSObjectKey(5, 1) != COSObjectKey(6, 1)


def test_eq_with_non_key_returns_notimplemented() -> None:
    key = COSObjectKey(5, 1)
    assert key.__eq__("not a key") is NotImplemented
    assert key.__ne__("not a key") is NotImplemented


def test_eq_against_non_key_is_false_when_compared() -> None:
    # __eq__ returning NotImplemented falls back to object identity ⇒ False.
    assert (COSObjectKey(5, 1) == 42) is False
    assert (COSObjectKey(5, 1) != 42) is True


def test_hash_consistency_with_equality() -> None:
    a = COSObjectKey(7, 3)
    b = COSObjectKey(7, 3)
    assert hash(a) == hash(b)


def test_lt_comparisons() -> None:
    smaller = COSObjectKey(1, 0)
    larger = COSObjectKey(2, 0)
    assert smaller < larger
    assert larger > smaller
    assert smaller <= larger
    assert larger >= smaller
    assert smaller <= smaller
    assert larger >= larger


def test_lt_returns_notimplemented_on_non_key() -> None:
    key = COSObjectKey(1)
    assert key.__lt__("x") is NotImplemented
    assert key.__le__("x") is NotImplemented
    assert key.__gt__("x") is NotImplemented
    assert key.__ge__("x") is NotImplemented


def test_str_matches_pdf_reference_form() -> None:
    assert str(COSObjectKey(8, 2)) == "8 2 R"


def test_repr_round_trip_contains_all_fields() -> None:
    r = repr(COSObjectKey(8, 2, 5))
    assert "num=8" in r and "gen=2" in r and "index=5" in r


def test_equals_alias_matches_dunder() -> None:
    a = COSObjectKey(4, 0)
    b = COSObjectKey(4, 0)
    assert a.equals(b) is True
    assert a.equals("nope") is False


def test_hash_code_alias_matches_python_hash() -> None:
    key = COSObjectKey(4, 0)
    assert key.hash_code() == hash(key)


def test_to_string_alias_matches_str() -> None:
    key = COSObjectKey(9, 1)
    assert key.to_string() == str(key)


def test_compare_to_returns_minus_one_zero_one() -> None:
    a = COSObjectKey(1, 0)
    b = COSObjectKey(2, 0)
    assert a.compare_to(b) == -1
    assert b.compare_to(a) == 1
    assert a.compare_to(COSObjectKey(1, 0)) == 0


def test_compute_internal_hash_static_helper() -> None:
    assert COSObjectKey.compute_internal_hash(3, 5) == (3 << 16) | 5


def test_get_number_round_trip_with_large_value() -> None:
    # Upstream allows >16-bit object numbers; serialization is the guard.
    big = (1 << 24) - 1
    key = COSObjectKey(big, 0)
    assert key.get_number() == big


def test_sorted_by_object_number() -> None:
    keys = [COSObjectKey(3), COSObjectKey(1), COSObjectKey(2)]
    keys.sort()
    assert [k.get_number() for k in keys] == [1, 2, 3]
