from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from pypdfbox.cos import COSObjectKey


def test_basic_construction() -> None:
    k = COSObjectKey(7, 0)
    assert k.object_number == 7
    assert k.generation_number == 0


def test_default_generation_zero() -> None:
    assert COSObjectKey(3).generation_number == 0


def test_negative_numbers_rejected() -> None:
    with pytest.raises(ValueError):
        COSObjectKey(-1, 0)
    with pytest.raises(ValueError):
        COSObjectKey(1, -1)


def test_equality_and_hashable() -> None:
    a = COSObjectKey(5, 0)
    b = COSObjectKey(5, 0)
    c = COSObjectKey(5, 1)
    assert a == b
    assert hash(a) == hash(b)
    assert a != c
    assert {a, b, c} == {a, c}


def test_ordering() -> None:
    keys = [COSObjectKey(3, 0), COSObjectKey(1, 0), COSObjectKey(2, 1), COSObjectKey(2, 0)]
    keys.sort()
    pairs = [(k.object_number, k.generation_number) for k in keys]
    assert pairs == [(1, 0), (2, 0), (2, 1), (3, 0)]


def test_frozen() -> None:
    k = COSObjectKey(1, 0)
    with pytest.raises(FrozenInstanceError):
        k.object_number = 99  # type: ignore[misc]


def test_str_uses_pdf_indirect_syntax() -> None:
    assert str(COSObjectKey(7, 0)) == "7 0 R"


def test_dict_key_usage() -> None:
    table: dict[COSObjectKey, str] = {}
    table[COSObjectKey(1, 0)] = "a"
    table[COSObjectKey(2, 0)] = "b"
    assert table[COSObjectKey(1, 0)] == "a"
    assert len(table) == 2
