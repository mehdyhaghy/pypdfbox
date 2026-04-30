from __future__ import annotations

from pypdfbox.cos import COSObjectKey
from pypdfbox.pdfwriter.cos_writer_xref_entry import COSWriterXRefEntry


def test_value_type_basics() -> None:
    e = COSWriterXRefEntry(offset=42, key=COSObjectKey(3, 0))
    assert e.get_offset() == 42
    assert e.offset == 42
    assert e.get_key() == COSObjectKey(3, 0)
    assert e.is_free() is False
    assert e.get_object() is None


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
    assert n.is_free() is True
    assert n.key == COSObjectKey(0, 65535)
    assert n.offset == 0


def test_null_entry_singleton() -> None:
    a = COSWriterXRefEntry.get_null_entry()
    b = COSWriterXRefEntry.get_null_entry()
    assert a is b
