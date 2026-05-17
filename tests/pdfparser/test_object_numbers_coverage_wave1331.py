"""Wave 1331 coverage boost: ``ObjectNumbers`` error paths + aliases.

Targets lines 28, 39, 43-44, 46, 70, 83 of
``pypdfbox/pdfparser/object_numbers.py`` — error branches in the
constructor, the ``next()`` alias, and the ``next_value`` range-advance
path that ``__next__`` skips because it consults ``has_next`` first.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName
from pypdfbox.pdfparser import ObjectNumbers


def _index(*pairs: tuple[int, int]) -> COSArray:
    arr = COSArray()
    for start, length in pairs:
        arr.add(COSInteger.get(start))
        arr.add(COSInteger.get(length))
    return arr


# --------------------------------------------------------------------------
# Constructor error paths
# --------------------------------------------------------------------------


def test_empty_index_array_raises_oserror() -> None:
    """Line 28: an empty /Index array is rejected with ``OSError``."""
    with pytest.raises(OSError, match="Empty /Index array"):
        ObjectNumbers(COSArray())


def test_non_integer_in_start_position_raises_oserror() -> None:
    """Line 39: first element of a pair must be a COSInteger."""
    arr = COSArray()
    arr.add(COSName.A)  # not a COSInteger
    arr.add(COSInteger.get(1))
    with pytest.raises(OSError, match="integer in /Index array"):
        ObjectNumbers(arr)


def test_non_integer_in_length_position_raises_oserror() -> None:
    """Line 46: second element of a pair must be a COSInteger."""
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.B)  # not a COSInteger
    with pytest.raises(OSError, match="integer in /Index array"):
        ObjectNumbers(arr)


# --------------------------------------------------------------------------
# next() alias
# --------------------------------------------------------------------------


def test_next_method_alias_returns_value() -> None:
    """Line 70: ``next()`` is an alias of ``next_value()``."""
    it = ObjectNumbers(_index((5, 2)))
    assert it.next() == 5
    assert it.next() == 6


def test_next_method_alias_raises_after_exhaustion() -> None:
    it = ObjectNumbers(_index((5, 1)))
    assert it.next() == 5
    with pytest.raises(StopIteration):
        it.next()


# --------------------------------------------------------------------------
# next_value: range-advance path that __next__ skips
# --------------------------------------------------------------------------


def test_next_value_advances_to_next_range() -> None:
    """Line 83: when ``next_value`` runs out of the current range it
    should advance the cursor to the next ``(start, length)`` pair.

    ``__next__`` consults ``has_next`` first, so it never lands on
    line 83 directly. We call ``next_value`` ourselves to hit it.
    """
    it = ObjectNumbers(_index((0, 2), (100, 1)))
    assert it.next_value() == 0
    assert it.next_value() == 1
    # Cursor now at end-of-range; next call must roll over.
    assert it.next_value() == 100


def test_next_value_raises_after_last_range() -> None:
    """``StopIteration`` is raised once both ranges are exhausted."""
    it = ObjectNumbers(_index((1, 1), (5, 1)))
    assert it.next_value() == 1
    assert it.next_value() == 5
    with pytest.raises(StopIteration):
        it.next_value()
