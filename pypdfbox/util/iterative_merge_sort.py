"""Iterative (bottom-up) merge sort.

Mirrors ``org.apache.pdfbox.util.IterativeMergeSort`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/util/IterativeMergeSort.java``).

The sort follows upstream's comparison sequence exactly, so it gives the
same order as PDFBox even for a comparator that is not transitive.
"""

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
        """In-place bottom-up merge sort of ``items`` using comparator ``cmp``.

        Port of upstream ``IterativeMergeSort.sort``: blocks of size 1, 2,
        4, ... are merged pairwise, taking from the right block only when
        ``cmp(right, left) < 0``. The exact comparison sequence matters for
        comparators that are not transitive (``TextPositionComparator``),
        which is why upstream uses it as the fallback when ``List.sort``
        rejects such a comparator.
        """
        n = len(items)
        if n < 2:
            return
        arr = list(items)
        aux = list(arr)
        block_size = 1
        while block_size < n:
            start = 0
            while start < n:
                mid = start + block_size
                if mid < n:
                    to = min(start + (block_size << 1), n)
                    i = start
                    j = mid
                    for k in range(start, to):
                        if i == mid:
                            aux[k] = arr[j]
                            j += 1
                        elif j == to:
                            aux[k] = arr[i]
                            i += 1
                        elif cmp(arr[j], arr[i]) < 0:
                            aux[k] = arr[j]
                            j += 1
                        else:
                            aux[k] = arr[i]
                            i += 1
                    arr[start:to] = aux[start:to]
                start += block_size << 1
            block_size <<= 1
        for index, value in enumerate(arr):
            items[index] = value


__all__ = ["IterativeMergeSort"]
