from __future__ import annotations

from typing import TYPE_CHECKING

from .random_access_read import RandomAccessRead

if TYPE_CHECKING:
    from collections.abc import Sequence


class SequenceRandomAccessRead(RandomAccessRead):
    """Wraps several ``RandomAccessRead`` instances and exposes them as
    a single logical stream.

    Mirrors upstream
    ``org.apache.pdfbox.io.SequenceRandomAccessRead``. Empty sources are
    filtered out at construction; the resolved set must be non-empty.
    Seeking and reading transparently dispatch to the underlying source
    whose range covers the requested offset.
    """

    def __init__(self, reader_list: Sequence[RandomAccessRead]) -> None:
        if reader_list is None:
            raise ValueError("Missing input parameter")
        materialized = list(reader_list)
        if not materialized:
            raise ValueError("Empty list")
        try:
            self._readers: list[RandomAccessRead] = [
                r for r in materialized if r.length() > 0
            ]
        except OSError as exc:
            raise ValueError("Problematic list") from exc
        if not self._readers:
            raise ValueError("Empty list")
        self._number_of_readers: int = len(self._readers)
        self._current_index: int = 0
        self._current_position: int = 0
        self._total_length: int = 0
        self._is_closed: bool = False
        self._current: RandomAccessRead = self._readers[0]
        self._start_positions: list[int] = [0] * self._number_of_readers
        self._end_positions: list[int] = [0] * self._number_of_readers
        for i in range(self._number_of_readers):
            try:
                self._start_positions[i] = self._total_length
                self._total_length += self._readers[i].length()
                self._end_positions[i] = self._total_length - 1
            except OSError as exc:
                raise ValueError("Problematic list") from exc

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        for reader in self._readers:
            reader.close()
        self._readers.clear()
        self._current = None  # type: ignore[assignment]
        self._is_closed = True

    def is_closed(self) -> bool:
        return self._is_closed

    def check_closed(self) -> None:
        """Raise ``OSError`` if the sequence has been closed.

        Mirrors upstream ``checkClosed`` (Java line 196, private).
        """
        if self._is_closed:
            raise OSError("RandomAccessBuffer already closed")

    # ------------------------------------------------------------------
    # RandomAccessRead surface
    # ------------------------------------------------------------------

    def get_current_reader(self) -> RandomAccessRead:
        """Return the currently active sub-reader, advancing past
        exhausted readers if necessary.

        Mirrors upstream ``getCurrentReader`` (Java line 90, private).
        """
        if (
            self._current.is_eof()
            and self._current_index < self._number_of_readers - 1
        ):
            self._current_index += 1
            self._current = self._readers[self._current_index]
            self._current.seek(0)
        return self._current

    def read(self) -> int:
        self.check_closed()
        reader = self.get_current_reader()
        value = reader.read()
        if value > -1:
            self._current_position += 1
        return value

    def read_into(
        self, b: bytearray, offset: int = 0, length: int | None = None
    ) -> int:
        self.check_closed()
        if length is None:
            length = len(b) - offset
        if length == 0:
            return 0
        max_avail = min(self.available(), length)
        if max_avail == 0:
            return self.EOF
        reader = self.get_current_reader()
        n = reader.read_into(b, offset, max_avail)
        while n > -1 and n < max_avail:
            reader = self.get_current_reader()
            n += reader.read_into(b, offset + n, max_avail - n)
        self._current_position += n
        return n

    def get_position(self) -> int:
        self.check_closed()
        return self._current_position

    def seek(self, position: int) -> None:
        self.check_closed()
        if position < 0:
            raise OSError(f"Invalid position {position}")
        if position >= self._total_length:
            self._current_index = self._number_of_readers - 1
            self._current_position = self._total_length
        else:
            increment = -1 if position < self._current_position else 1
            i = self._current_index
            while 0 <= i < self._number_of_readers:
                if self._start_positions[i] <= position <= self._end_positions[i]:
                    self._current_index = i
                    break
                i += increment
            self._current_position = position
        self._current = self._readers[self._current_index]
        self._current.seek(
            self._current_position - self._start_positions[self._current_index]
        )

    def length(self) -> int:
        self.check_closed()
        return self._total_length

    def is_eof(self) -> bool:
        self.check_closed()
        return self._current_position >= self._total_length

    def create_view(self, start_position: int, length: int) -> RandomAccessRead:
        """Views are unsupported on sequence readers.

        Mirrors upstream ``createView`` (Java line 213) which throws
        ``UnsupportedOperationException``.
        """
        raise NotImplementedError(
            f"{type(self).__name__}.createView isn't supported."
        )
