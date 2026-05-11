from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.cos.cos_array import COSArray


class ObjectNumbers(Iterator[int]):
    """Iterator over the object numbers encoded in an xref-stream
    ``/Index`` array.

    Mirrors upstream
    ``org.apache.pdfbox.pdfparser.PDFXrefStreamParser.ObjectNumbers``
    (a private static nested class). Hoisted to a top-level class so
    pypdfbox can be referenced by name; upstream keeps it inner. The
    array encodes one or more ``(start, length)`` pairs and this
    iterator yields ``start, start+1, ..., start+length-1`` for each
    pair in order.
    """

    def __init__(self, index_array: COSArray) -> None:
        from pypdfbox.cos.cos_integer import COSInteger  # noqa: PLC0415

        pair_count = len(index_array) // 2
        if pair_count == 0:
            raise OSError("Empty /Index array in xref stream")
        self._start: list[int] = [0] * pair_count
        self._end: list[int] = [0] * pair_count
        counter = 0
        it = iter(index_array)
        while True:
            try:
                base = next(it)
            except StopIteration:
                break
            if not isinstance(base, COSInteger):
                raise OSError("Xref stream must have integer in /Index array")
            start_value = base.long_value()
            try:
                base = next(it)
            except StopIteration:
                break
            if not isinstance(base, COSInteger):
                raise OSError("Xref stream must have integer in /Index array")
            size_value = base.long_value()
            self._start[counter] = start_value
            self._end[counter] = start_value + size_value
            counter += 1
        self._current_range: int = 0
        self._current_number: int = self._start[0]
        self._current_end: int = self._end[0]

    def has_next(self) -> bool:
        """``True`` if more object numbers remain.

        Mirrors upstream ``ObjectNumbers.hasNext`` (Java line 223).
        """
        if len(self._start) == 1:
            return self._current_number < self._current_end
        return (
            self._current_range < len(self._start) - 1
            or self._current_number < self._current_end
        )

    def next(self) -> int:  # noqa: A003 — upstream method name
        """Alias for :meth:`next_value` matching the upstream Java
        ``Iterator.next()`` method name."""
        return self.next_value()

    def next_value(self) -> int:
        """Return the next object number.

        Mirrors upstream ``ObjectNumbers.next`` (Java line 232). The
        Python ``__next__`` magic method delegates here.
        """
        if self._current_number < self._current_end:
            result = self._current_number
            self._current_number += 1
            return result
        if self._current_range >= len(self._start) - 1:
            raise StopIteration
        self._current_range += 1
        self._current_number = self._start[self._current_range]
        self._current_end = self._end[self._current_range]
        result = self._current_number
        self._current_number += 1
        return result

    # ------------------------------------------------------------------
    # Iterator protocol
    # ------------------------------------------------------------------

    def __iter__(self) -> ObjectNumbers:
        return self

    def __next__(self) -> int:
        if not self.has_next():
            raise StopIteration
        return self.next_value()
