from __future__ import annotations

from pypdfbox.cos import COSObjectKey
from pypdfbox.pdfwriter.cos_writer_xref_entry import COSWriterXRefEntry


def test_value_type_basics() -> None:
    e = COSWriterXRefEntry(offset=42, key=COSObjectKey(3, 0))
    assert e.get_offset() == 42
    assert e.getOffset() == 42
    assert e.offset == 42
    assert e.get_key() == COSObjectKey(3, 0)
    assert e.getKey() == COSObjectKey(3, 0)
    assert e.is_free() is False
    assert e.isFree() is False
    assert e.get_object() is None
    assert e.getObject() is None


def test_frozen_immutable() -> None:
    e = COSWriterXRefEntry(offset=42, key=COSObjectKey(3, 0))
    try:
        e.offset = 100  # type: ignore[misc]
    except Exception:  # noqa: BLE001
        return
    raise AssertionError("expected frozen dataclass to forbid attribute mutation")


def test_sort_order_by_object_number() -> None:
    entries = [
        COSWriterXRefEntry(offset=10, key=COSObjectKey(5, 0)),
        COSWriterXRefEntry(offset=20, key=COSObjectKey(1, 0)),
        COSWriterXRefEntry(offset=30, key=COSObjectKey(3, 0)),
    ]
    entries.sort()
    assert [e.key.object_number for e in entries] == [1, 3, 5]


def test_sort_ignores_offset_and_free() -> None:
    a = COSWriterXRefEntry(offset=99, key=COSObjectKey(1, 0))
    b = COSWriterXRefEntry(offset=0, key=COSObjectKey(2, 0), free=True)
    assert a < b
    assert b > a
    assert not (a > b)


def test_null_entry_is_free_object_zero_gen_65535() -> None:
    n = COSWriterXRefEntry.get_null_entry()
    assert n.is_free() is True
    assert n.key == COSObjectKey(0, 65535)
    assert n.offset == 0


def test_nullentry_constant_matches_upstream_singleton() -> None:
    n = COSWriterXRefEntry.NULLENTRY
    assert n is COSWriterXRefEntry.get_null_entry()
    assert n is COSWriterXRefEntry.getNullEntry()
    assert n.is_free() is True
    assert n.key == COSObjectKey(0, 65535)
    assert n.offset == 0


def test_null_entry_singleton() -> None:
    a = COSWriterXRefEntry.get_null_entry()
    b = COSWriterXRefEntry.get_null_entry()
    assert a is b


def test_compare_to_matches_upstream_signs() -> None:
    a = COSWriterXRefEntry(offset=0, key=COSObjectKey(2, 0))
    b = COSWriterXRefEntry(offset=0, key=COSObjectKey(5, 0))
    c = COSWriterXRefEntry(offset=99, key=COSObjectKey(2, 0))
    assert a.compare_to(b) == -1
    assert b.compare_to(a) == 1
    assert a.compareTo(b) == -1
    assert b.compareTo(a) == 1
    # Same object number → 0 regardless of offset/free.
    assert a.compare_to(c) == 0
    assert a.compareTo(c) == 0


def test_compare_to_none_returns_minus_one() -> None:
    # Mirrors upstream ``compareTo(null)`` returning -1.
    a = COSWriterXRefEntry(offset=0, key=COSObjectKey(7, 0))
    assert a.compare_to(None) == -1
    assert a.compareTo(None) == -1


def test_with_free_returns_new_instance() -> None:
    a = COSWriterXRefEntry(offset=42, key=COSObjectKey(3, 0))
    assert a.is_free() is False
    b = a.with_free(True)
    assert b is not a
    assert b.is_free() is True
    # Original is untouched (frozen).
    assert a.is_free() is False
    # Other fields preserved.
    assert b.offset == 42
    assert b.key == COSObjectKey(3, 0)
    assert b.obj is None


def test_with_free_no_op_when_flag_unchanged() -> None:
    a = COSWriterXRefEntry(offset=42, key=COSObjectKey(3, 0))
    # When the flag value isn't changing, return self (no allocation churn).
    assert a.with_free(False) is a
