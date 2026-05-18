"""Wave 1351 coverage boost: ``ObjectNumbers`` odd-length /Index path.

Targets lines 43-44 of ``pypdfbox/pdfparser/object_numbers.py`` — the
``StopIteration`` ``break`` on the *second* ``next(it)`` inside the
constructor's ``while True`` loop. This branch fires when the
``/Index`` array has an odd number of integers: the first ``next``
yields the trailing unpaired start value, then the second ``next``
raises ``StopIteration`` and the loop exits gracefully (the trailing
half-pair is dropped, mirroring upstream behaviour).
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger
from pypdfbox.pdfparser import ObjectNumbers


def test_odd_length_index_array_drops_trailing_unpaired_start() -> None:
    """``/Index`` with an odd item count: the trailing half-pair is
    silently dropped because the second ``next(it)`` raises
    ``StopIteration``. Covers lines 43-44.
    """
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSInteger.get(3))
    # Trailing unpaired start value — pair_count = 3 // 2 = 1, but
    # the iterator still tries to read a second pair and breaks out
    # cleanly when it can't find a matching length.
    arr.add(COSInteger.get(99))
    on = ObjectNumbers(arr)
    assert list(on) == [0, 1, 2]
