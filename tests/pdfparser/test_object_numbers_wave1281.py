"""Wave 1281: ObjectNumbers iterator port."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger
from pypdfbox.pdfparser import ObjectNumbers


def _index(*pairs: tuple[int, int]) -> COSArray:
    arr = COSArray()
    for start, length in pairs:
        arr.add(COSInteger.get(start))
        arr.add(COSInteger.get(length))
    return arr


def test_single_range() -> None:
    it = ObjectNumbers(_index((0, 4)))
    assert list(it) == [0, 1, 2, 3]


def test_multi_range() -> None:
    it = ObjectNumbers(_index((0, 2), (10, 3)))
    assert list(it) == [0, 1, 10, 11, 12]


def test_has_next_after_exhausted() -> None:
    it = ObjectNumbers(_index((5, 2)))
    assert it.has_next()
    next(it)
    next(it)
    assert not it.has_next()


def test_next_value_raises_stop_iteration() -> None:
    it = ObjectNumbers(_index((1, 1)))
    next(it)
    with pytest.raises(StopIteration):
        next(it)


def test_zero_length_range() -> None:
    # ``(start, 0)`` produces no numbers; the iterator should be empty.
    it = ObjectNumbers(_index((42, 0)))
    assert list(it) == []
