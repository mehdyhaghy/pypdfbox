from __future__ import annotations

import pytest

from pypdfbox.cos import COSName, COSObjectKey
from pypdfbox.pdfwriter.cos_writer_xref_entry import COSWriterXRefEntry


def test_wave378_compare_to_ignores_generation_like_upstream() -> None:
    a = COSWriterXRefEntry(offset=10, key=COSObjectKey(7, 0))
    b = COSWriterXRefEntry(offset=20, key=COSObjectKey(7, 3), free=True)

    assert a.compare_to(b) == 0
    assert b.compare_to(a) == 0
    assert a.compareTo(b) == 0
    assert a != b


def test_wave378_sort_is_stable_for_same_object_number() -> None:
    first = COSWriterXRefEntry(offset=30, key=COSObjectKey(4, 2))
    second = COSWriterXRefEntry(offset=10, key=COSObjectKey(4, 0))
    third = COSWriterXRefEntry(offset=20, key=COSObjectKey(5, 0))

    assert sorted([first, third, second]) == [first, second, third]


def test_wave378_rich_comparisons_reject_unrelated_types() -> None:
    entry = COSWriterXRefEntry(offset=1, key=COSObjectKey(1, 0))

    with pytest.raises(TypeError):
        _ = entry < object()
    with pytest.raises(TypeError):
        _ = entry <= object()
    with pytest.raises(TypeError):
        _ = entry > object()
    with pytest.raises(TypeError):
        _ = entry >= object()


def test_wave378_with_free_preserves_object_identity() -> None:
    obj = COSName.get_pdf_name("Marker")
    entry = COSWriterXRefEntry(offset=42, key=COSObjectKey(8, 0), obj=obj)

    free = entry.with_free(True)

    assert free is not entry
    assert free.obj is obj
    assert free.offset == 42
    assert free.key == COSObjectKey(8, 0)
    assert free.free is True


def test_wave378_null_entry_can_be_copied_without_mutating_singleton() -> None:
    null_entry = COSWriterXRefEntry.NULLENTRY

    used = null_entry.with_free(False)

    assert used is not null_entry
    assert used.free is False
    assert used.offset == 0
    assert used.key == COSObjectKey(0, 65535)
    assert COSWriterXRefEntry.NULLENTRY.free is True


def test_wave378_frozen_entry_is_hashable_when_payload_is_hashable() -> None:
    entry = COSWriterXRefEntry(
        offset=7,
        key=COSObjectKey(9, 0),
        obj=COSName.get_pdf_name("Payload"),
    )

    assert {entry, entry} == {entry}
