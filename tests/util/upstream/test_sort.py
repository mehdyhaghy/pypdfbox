"""Ported upstream tests for ``IterativeMergeSort``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/util/TestSort.java``
(PDFBox 3.0.x).

Upstream covers the static ``IterativeMergeSort.sort(List, Comparator)``
entry point with a handful of hand-crafted inputs plus a 100-iteration
randomized parity loop. The Python port lives in
``pypdfbox.util.iterative_merge_sort`` and delegates to Timsort via
``functools.cmp_to_key``, so behaviour parity is automatic; the tests
here pin the public contract anyway.
"""

from __future__ import annotations

import random

from pypdfbox.util import IterativeMergeSort


def _do_test(input_items: list[int], expected: list[int]) -> None:
    items = list(input_items)
    IterativeMergeSort.sort(items, lambda a, b: (a > b) - (a < b))
    assert items == expected


def test_sort_descending_to_ascending() -> None:
    _do_test([9, 8, 7, 6, 5, 4, 3, 2, 1], [1, 2, 3, 4, 5, 6, 7, 8, 9])


def test_sort_mixed_runs() -> None:
    _do_test([4, 3, 2, 1, 9, 8, 7, 6, 5], [1, 2, 3, 4, 5, 6, 7, 8, 9])


def test_sort_empty() -> None:
    _do_test([], [])


def test_sort_singleton() -> None:
    _do_test([5], [5])


def test_sort_two_already_sorted() -> None:
    _do_test([5, 6], [5, 6])


def test_sort_two_reversed() -> None:
    _do_test([6, 5], [5, 6])


def test_sort_randomized_parity() -> None:
    """Mirror upstream's 100-iteration randomised loop with the same seed."""
    rng = random.Random(12345)
    for _ in range(100):
        length = rng.randint(2, 20001)
        # Generate values with duplicates, matching upstream's
        # ``rnd.nextInt(rnd.nextInt(100)+1)`` shape.
        items = [rng.randint(0, rng.randint(0, 99)) for _ in range(length)]
        expected = sorted(items)
        _do_test(items, expected)
