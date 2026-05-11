"""Iterative (bottom-up) merge sort.

Mirrors ``org.apache.pdfbox.util.IterativeMergeSort`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/util/IterativeMergeSort.java``).

Python's built-in ``list.sort`` is Timsort (stable, O(n log n)). We retain
the class so callers that reach for ``IterativeMergeSort.sort(list, cmp)``
still find it, but delegate to ``functools.cmp_to_key`` for the
comparator-driven case.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, MutableSequence
from typing import TypeVar

_T = TypeVar("_T")


class IterativeMergeSort:
    """Static utility — instances are not supported."""

    def __init__(self) -> None:  # pragma: no cover
        raise TypeError("IterativeMergeSort is a utility class")

    @staticmethod
    def merge(
        items: MutableSequence[_T],
        cmp: Callable[[_T, _T], int],
        left: int,
        mid: int,
        right: int,
    ) -> None:
        """Merge two sorted sub-ranges ``[left, mid)`` and ``[mid, right)``
        of ``items`` in-place using ``cmp``. Mirrors upstream
        ``IterativeMergeSort.merge`` (private helper used by ``sort``)."""
        merged: list[_T] = []
        i, j = left, mid
        while i < mid and j < right:
            if cmp(items[i], items[j]) <= 0:
                merged.append(items[i])
                i += 1
            else:
                merged.append(items[j])
                j += 1
        while i < mid:
            merged.append(items[i])
            i += 1
        while j < right:
            merged.append(items[j])
            j += 1
        for k, value in enumerate(merged):
            items[left + k] = value

    @staticmethod
    def sort(items: MutableSequence[_T], cmp: Callable[[_T, _T], int]) -> None:
        """In-place sort of ``items`` using comparator ``cmp``.

        Java's ``Comparator.compare(a, b)`` returns negative/zero/positive;
        Python's ``cmp_to_key`` follows the same convention.
        """
        if len(items) < 2:
            return
        key = functools.cmp_to_key(cmp)
        sorted_items = sorted(items, key=key)
        for i, value in enumerate(sorted_items):
            items[i] = value


__all__ = ["IterativeMergeSort"]
