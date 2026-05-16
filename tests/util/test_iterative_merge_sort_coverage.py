"""Coverage boost for ``pypdfbox.util.iterative_merge_sort`` (wave 1318).

Exercises the static ``merge`` helper and additional ``sort`` edge cases
beyond the smoke tests in ``test_util_wave1281.py``.
"""

from __future__ import annotations

import pytest

from pypdfbox.util import IterativeMergeSort


def test_merge_two_sorted_subranges_in_place() -> None:
    items = [1, 3, 5, 2, 4, 6]
    IterativeMergeSort.merge(items, lambda a, b: a - b, 0, 3, 6)
    assert items == [1, 2, 3, 4, 5, 6]


def test_merge_left_runs_out_first_copies_remaining_right() -> None:
    items = [1, 2, 3, 4, 5, 6]
    # Left run [1,2,3], right run [4,5,6] — left exhausts at i==mid.
    IterativeMergeSort.merge(items, lambda a, b: a - b, 0, 3, 6)
    assert items == [1, 2, 3, 4, 5, 6]


def test_merge_right_runs_out_first_copies_remaining_left() -> None:
    items = [4, 5, 6, 1, 2, 3]
    IterativeMergeSort.merge(items, lambda a, b: a - b, 0, 3, 6)
    assert items == [1, 2, 3, 4, 5, 6]


def test_merge_with_equal_values_is_stable() -> None:
    # Tagged values — when cmp returns 0 the left side wins (i.e. left
    # element is appended first), preserving stable ordering.
    left = [("a", 1), ("b", 1)]
    right = [("c", 1), ("d", 1)]
    items = left + right
    IterativeMergeSort.merge(items, lambda a, b: a[1] - b[1], 0, 2, 4)
    assert [tag for tag, _ in items] == ["a", "b", "c", "d"]


def test_merge_empty_right_range_is_noop() -> None:
    items = [1, 2, 3]
    IterativeMergeSort.merge(items, lambda a, b: a - b, 0, 3, 3)
    assert items == [1, 2, 3]


def test_merge_empty_left_range_is_noop() -> None:
    items = [1, 2, 3]
    IterativeMergeSort.merge(items, lambda a, b: a - b, 0, 0, 3)
    assert items == [1, 2, 3]


def test_merge_subrange_inside_larger_list() -> None:
    # Sort only the middle [9, 7] sub-range — outer elements untouched.
    items = [100, 1, 3, 2, 4, 200]
    IterativeMergeSort.merge(items, lambda a, b: a - b, 1, 3, 5)
    assert items == [100, 1, 2, 3, 4, 200]


def test_sort_empty_list_is_noop() -> None:
    items: list[int] = []
    IterativeMergeSort.sort(items, lambda a, b: a - b)
    assert items == []


def test_sort_with_reverse_comparator() -> None:
    items = [1, 3, 2, 5, 4]
    IterativeMergeSort.sort(items, lambda a, b: b - a)
    assert items == [5, 4, 3, 2, 1]


def test_sort_strings_with_custom_comparator() -> None:
    items = ["banana", "apple", "cherry"]
    IterativeMergeSort.sort(items, lambda a, b: (a > b) - (a < b))
    assert items == ["apple", "banana", "cherry"]


def test_sort_already_sorted_is_stable() -> None:
    items = [1, 2, 3, 4, 5]
    IterativeMergeSort.sort(items, lambda a, b: a - b)
    assert items == [1, 2, 3, 4, 5]


def test_instance_construction_is_forbidden() -> None:
    with pytest.raises(TypeError, match="utility class"):
        IterativeMergeSort()
