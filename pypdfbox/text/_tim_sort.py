"""TimSort with the run, merge and galloping policy of Java's ``List.sort``.

Upstream ``PDFTextStripper.writePage`` sorts each article with
``Collections.sort(textList, new TextPositionComparator())``. That
comparator is not transitive, so the resulting order depends on the exact
sequence of comparisons the sort makes, and Java's sort can also reject the
input ("Comparison method violates its general contract!"), after which
PDFBox falls back to ``IterativeMergeSort``. Python's ``list.sort`` is a
TimSort too, but since Python 3.11 it schedules merges differently (and it
sizes its minimum run differently), so for a non-transitive comparator it can
produce another order. This module implements TimSort as Tim Peters
described it (``Objects/listsort.txt``) with the parameters Java uses: a
minimum merge size of 32, an initial gallop threshold of 7, the
two-condition merge-collapse invariant, and the contract check at the end of
a merge.
"""

from collections.abc import Callable
from typing import Any

_MIN_MERGE = 32
_MIN_GALLOP = 7


class ComparisonContractError(ValueError):
    """The comparator is inconsistent (Java's ``IllegalArgumentException``)."""


def tim_sort(items: list[Any], compare: Callable[[Any, Any], int]) -> None:
    """Sort ``items`` in place; raise :class:`ComparisonContractError` when a
    merge detects that ``compare`` is inconsistent (``items`` is then left
    partially sorted, as Java leaves its array)."""
    lo = 0
    hi = len(items)
    remaining = hi - lo
    if remaining < 2:
        return
    if remaining < _MIN_MERGE:
        initial = _count_run_and_make_ascending(items, lo, hi, compare)
        _binary_sort(items, lo, hi, lo + initial, compare)
        return
    sorter = _TimSort(items, compare)
    min_run = _min_run_length(remaining)
    while True:
        run_length = _count_run_and_make_ascending(items, lo, hi, compare)
        if run_length < min_run:
            force = min(remaining, min_run)
            _binary_sort(items, lo, lo + force, lo + run_length, compare)
            run_length = force
        sorter.push_run(lo, run_length)
        sorter.merge_collapse()
        lo += run_length
        remaining -= run_length
        if remaining == 0:
            break
    sorter.merge_force_collapse()


def _min_run_length(n: int) -> int:
    r = 0
    while n >= _MIN_MERGE:
        r |= n & 1
        n >>= 1
    return n + r


def _binary_sort(
    a: list[Any], lo: int, hi: int, start: int, compare: Callable[[Any, Any], int]
) -> None:
    """Binary insertion sort of ``a[lo:hi]`` whose prefix ``a[lo:start]`` is
    already sorted."""
    if start == lo:
        start += 1
    while start < hi:
        pivot = a[start]
        left = lo
        right = start
        while left < right:
            mid = (left + right) >> 1
            if compare(pivot, a[mid]) < 0:
                right = mid
            else:
                left = mid + 1
        a[left + 1 : start + 1] = a[left:start]
        a[left] = pivot
        start += 1


def _count_run_and_make_ascending(
    a: list[Any], lo: int, hi: int, compare: Callable[[Any, Any], int]
) -> int:
    """Length of the run starting at ``lo``; a strictly descending run is
    reversed in place."""
    run_hi = lo + 1
    if run_hi == hi:
        return 1
    if compare(a[run_hi], a[lo]) < 0:
        run_hi += 1
        while run_hi < hi and compare(a[run_hi], a[run_hi - 1]) < 0:
            run_hi += 1
        a[lo:run_hi] = a[lo:run_hi][::-1]
    else:
        run_hi += 1
        while run_hi < hi and compare(a[run_hi], a[run_hi - 1]) >= 0:
            run_hi += 1
    return run_hi - lo


def _gallop_left(
    key: Any,
    a: list[Any],
    base: int,
    length: int,
    hint: int,
    compare: Callable[[Any, Any], int],
) -> int:
    """Leftmost insertion point of ``key`` in the sorted ``a[base:base+length]``."""
    last_ofs = 0
    ofs = 1
    if compare(key, a[base + hint]) > 0:
        max_ofs = length - hint
        while ofs < max_ofs and compare(key, a[base + hint + ofs]) > 0:
            last_ofs = ofs
            ofs = (ofs << 1) + 1
        ofs = min(ofs, max_ofs)
        last_ofs += hint
        ofs += hint
    else:
        max_ofs = hint + 1
        while ofs < max_ofs and compare(key, a[base + hint - ofs]) <= 0:
            last_ofs = ofs
            ofs = (ofs << 1) + 1
        ofs = min(ofs, max_ofs)
        last_ofs, ofs = hint - ofs, hint - last_ofs
    last_ofs += 1
    while last_ofs < ofs:
        m = last_ofs + ((ofs - last_ofs) >> 1)
        if compare(key, a[base + m]) > 0:
            last_ofs = m + 1
        else:
            ofs = m
    return ofs


def _gallop_right(
    key: Any,
    a: list[Any],
    base: int,
    length: int,
    hint: int,
    compare: Callable[[Any, Any], int],
) -> int:
    """Rightmost insertion point of ``key`` in the sorted ``a[base:base+length]``."""
    ofs = 1
    last_ofs = 0
    if compare(key, a[base + hint]) < 0:
        max_ofs = hint + 1
        while ofs < max_ofs and compare(key, a[base + hint - ofs]) < 0:
            last_ofs = ofs
            ofs = (ofs << 1) + 1
        ofs = min(ofs, max_ofs)
        last_ofs, ofs = hint - ofs, hint - last_ofs
    else:
        max_ofs = length - hint
        while ofs < max_ofs and compare(key, a[base + hint + ofs]) >= 0:
            last_ofs = ofs
            ofs = (ofs << 1) + 1
        ofs = min(ofs, max_ofs)
        last_ofs += hint
        ofs += hint
    last_ofs += 1
    while last_ofs < ofs:
        m = last_ofs + ((ofs - last_ofs) >> 1)
        if compare(key, a[base + m]) < 0:
            ofs = m
        else:
            last_ofs = m + 1
    return ofs


class _TimSort:
    """The pending-run stack and the merge procedures."""

    def __init__(self, a: list[Any], compare: Callable[[Any, Any], int]) -> None:
        self.a = a
        self.compare = compare
        self.min_gallop = _MIN_GALLOP
        self.run_base: list[int] = []
        self.run_len: list[int] = []

    def push_run(self, base: int, length: int) -> None:
        self.run_base.append(base)
        self.run_len.append(length)

    def merge_collapse(self) -> None:
        run_len = self.run_len
        while len(run_len) > 1:
            n = len(run_len) - 2
            if (n > 0 and run_len[n - 1] <= run_len[n] + run_len[n + 1]) or (
                n > 1 and run_len[n - 2] <= run_len[n] + run_len[n - 1]
            ):
                if run_len[n - 1] < run_len[n + 1]:
                    n -= 1
            elif run_len[n] > run_len[n + 1]:
                break
            self.merge_at(n)

    def merge_force_collapse(self) -> None:
        run_len = self.run_len
        while len(run_len) > 1:
            n = len(run_len) - 2
            if n > 0 and run_len[n - 1] < run_len[n + 1]:
                n -= 1
            self.merge_at(n)

    def merge_at(self, i: int) -> None:
        a = self.a
        compare = self.compare
        base1 = self.run_base[i]
        len1 = self.run_len[i]
        base2 = self.run_base[i + 1]
        len2 = self.run_len[i + 1]
        self.run_len[i] = len1 + len2
        del self.run_base[i + 1]
        del self.run_len[i + 1]
        k = _gallop_right(a[base2], a, base1, len1, 0, compare)
        base1 += k
        len1 -= k
        if len1 == 0:
            return
        len2 = _gallop_left(a[base1 + len1 - 1], a, base2, len2, len2 - 1, compare)
        if len2 == 0:
            return
        if len1 <= len2:
            self.merge_lo(base1, len1, base2, len2)
        else:
            self.merge_hi(base1, len1, base2, len2)

    def merge_lo(self, base1: int, len1: int, base2: int, len2: int) -> None:
        a = self.a
        compare = self.compare
        tmp = a[base1 : base1 + len1]
        cursor1 = 0
        cursor2 = base2
        dest = base1
        a[dest] = a[cursor2]
        dest += 1
        cursor2 += 1
        len2 -= 1
        if len2 == 0:
            a[dest : dest + len1] = tmp[cursor1 : cursor1 + len1]
            return
        if len1 == 1:
            a[dest : dest + len2] = a[cursor2 : cursor2 + len2]
            a[dest + len2] = tmp[cursor1]
            return
        min_gallop = self.min_gallop
        done = False
        while not done:
            count1 = 0
            count2 = 0
            # One-at-a-time merging until one run starts winning consistently.
            while True:
                if compare(a[cursor2], tmp[cursor1]) < 0:
                    a[dest] = a[cursor2]
                    dest += 1
                    cursor2 += 1
                    count2 += 1
                    count1 = 0
                    len2 -= 1
                    if len2 == 0:
                        done = True
                        break
                else:
                    a[dest] = tmp[cursor1]
                    dest += 1
                    cursor1 += 1
                    count1 += 1
                    count2 = 0
                    len1 -= 1
                    if len1 == 1:
                        done = True
                        break
                if (count1 | count2) >= min_gallop:
                    break
            if done:
                break
            # Galloping until neither run is winning consistently.
            while True:
                count1 = _gallop_right(a[cursor2], tmp, cursor1, len1, 0, compare)
                if count1 != 0:
                    a[dest : dest + count1] = tmp[cursor1 : cursor1 + count1]
                    dest += count1
                    cursor1 += count1
                    len1 -= count1
                    if len1 <= 1:
                        done = True
                        break
                a[dest] = a[cursor2]
                dest += 1
                cursor2 += 1
                len2 -= 1
                if len2 == 0:
                    done = True
                    break
                count2 = _gallop_left(tmp[cursor1], a, cursor2, len2, 0, compare)
                if count2 != 0:
                    a[dest : dest + count2] = a[cursor2 : cursor2 + count2]
                    dest += count2
                    cursor2 += count2
                    len2 -= count2
                    if len2 == 0:
                        done = True
                        break
                a[dest] = tmp[cursor1]
                dest += 1
                cursor1 += 1
                len1 -= 1
                if len1 == 1:
                    done = True
                    break
                min_gallop -= 1
                if not (count1 >= _MIN_GALLOP or count2 >= _MIN_GALLOP):
                    break
            if done:
                break
            min_gallop = max(min_gallop, 0) + 2
        self.min_gallop = max(min_gallop, 1)
        if len1 == 1:
            a[dest : dest + len2] = a[cursor2 : cursor2 + len2]
            a[dest + len2] = tmp[cursor1]
        elif len1 == 0:
            raise ComparisonContractError(
                "Comparison method violates its general contract!"
            )
        else:
            a[dest : dest + len1] = tmp[cursor1 : cursor1 + len1]

    def merge_hi(self, base1: int, len1: int, base2: int, len2: int) -> None:
        a = self.a
        compare = self.compare
        tmp = a[base2 : base2 + len2]
        cursor1 = base1 + len1 - 1
        cursor2 = len2 - 1
        dest = base2 + len2 - 1
        a[dest] = a[cursor1]
        dest -= 1
        cursor1 -= 1
        len1 -= 1
        if len1 == 0:
            a[dest - (len2 - 1) : dest + 1] = tmp[0:len2]
            return
        if len2 == 1:
            dest -= len1
            cursor1 -= len1
            a[dest + 1 : dest + 1 + len1] = a[cursor1 + 1 : cursor1 + 1 + len1]
            a[dest] = tmp[cursor2]
            return
        min_gallop = self.min_gallop
        done = False
        while not done:
            count1 = 0
            count2 = 0
            while True:
                if compare(tmp[cursor2], a[cursor1]) < 0:
                    a[dest] = a[cursor1]
                    dest -= 1
                    cursor1 -= 1
                    count1 += 1
                    count2 = 0
                    len1 -= 1
                    if len1 == 0:
                        done = True
                        break
                else:
                    a[dest] = tmp[cursor2]
                    dest -= 1
                    cursor2 -= 1
                    count2 += 1
                    count1 = 0
                    len2 -= 1
                    if len2 == 1:
                        done = True
                        break
                if (count1 | count2) >= min_gallop:
                    break
            if done:
                break
            while True:
                count1 = len1 - _gallop_right(tmp[cursor2], a, base1, len1, len1 - 1, compare)
                if count1 != 0:
                    dest -= count1
                    cursor1 -= count1
                    len1 -= count1
                    a[dest + 1 : dest + 1 + count1] = a[cursor1 + 1 : cursor1 + 1 + count1]
                    if len1 == 0:
                        done = True
                        break
                a[dest] = tmp[cursor2]
                dest -= 1
                cursor2 -= 1
                len2 -= 1
                if len2 == 1:
                    done = True
                    break
                count2 = len2 - _gallop_left(a[cursor1], tmp, 0, len2, len2 - 1, compare)
                if count2 != 0:
                    dest -= count2
                    cursor2 -= count2
                    len2 -= count2
                    a[dest + 1 : dest + 1 + count2] = tmp[cursor2 + 1 : cursor2 + 1 + count2]
                    if len2 <= 1:
                        done = True
                        break
                a[dest] = a[cursor1]
                dest -= 1
                cursor1 -= 1
                len1 -= 1
                if len1 == 0:
                    done = True
                    break
                min_gallop -= 1
                if not (count1 >= _MIN_GALLOP or count2 >= _MIN_GALLOP):
                    break
            if done:
                break
            min_gallop = max(min_gallop, 0) + 2
        self.min_gallop = max(min_gallop, 1)
        if len2 == 1:
            dest -= len1
            cursor1 -= len1
            a[dest + 1 : dest + 1 + len1] = a[cursor1 + 1 : cursor1 + 1 + len1]
            a[dest] = tmp[cursor2]
        elif len2 == 0:
            raise ComparisonContractError(
                "Comparison method violates its general contract!"
            )
        else:
            a[dest - (len2 - 1) : dest + 1] = tmp[0:len2]


__all__ = ["ComparisonContractError", "tim_sort"]
