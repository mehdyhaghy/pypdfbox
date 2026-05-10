from __future__ import annotations

from .random_access_read import RandomAccessRead


class RandomAccessReadView(RandomAccessRead):
    """
    A read-only slice view onto another ``RandomAccessRead``.

    The view exposes positions ``[0, length)`` that map to the parent's
    ``[start_position, start_position + length)``. The parent's seek/read
    cursor is moved on every operation; do not assume parent position is
    preserved across view operations.

    Mirrors ``org.apache.pdfbox.io.RandomAccessReadView`` (PDFBox 3.0):
    a thin window onto a backing ``RandomAccessRead`` with translated
    positions, clamping seeks past the logical end, and refusing nested
    ``create_view`` calls.
    """

    def __init__(
        self,
        random_access_read: RandomAccessRead,
        start_position: int,
        stream_length: int,
        close_input: bool = False,
        *,
        # Legacy pypdfbox positional/keyword names. ``parent``/``length``/
        # ``close_parent`` predate the upstream-aligned rename and remain as
        # accepted aliases so callers in sibling io modules keep working.
        close_parent: bool | None = None,
    ) -> None:
        if start_position < 0:
            raise ValueError("start_position must be non-negative")
        if stream_length < 0:
            raise ValueError("stream_length must be non-negative")
        # PDFBox upstream does not validate that start_position + stream_length
        # fits within the parent: the view is a logical window; reads stop at
        # parent EOF or view EOF, whichever comes first.
        self._random_access_read: RandomAccessRead | None = random_access_read
        self._start_position = start_position
        self._stream_length = stream_length
        self._close_input = close_input if close_parent is None else close_parent
        self._current_position = 0

    # ------------------------------------------------------------------
    # Mirror of upstream private helpers.
    # ------------------------------------------------------------------

    def restore_position(self) -> None:
        """Restore the current position within the underlying random access read."""
        # Upstream RandomAccessReadView.restorePosition (line 188) — private
        # in Java but exposed here for parity-tool method matching. Direct
        # callers from outside the class are not intended.
        assert self._random_access_read is not None
        self._random_access_read.seek(self._start_position + self._current_position)

    def check_closed(self) -> None:
        """Ensure that the view isn't closed; raise if it is."""
        # Upstream RandomAccessReadView.checkClosed (line 198).
        if self.is_closed():
            raise OSError("RandomAccessReadView already closed")

    # ------------------------------------------------------------------
    # RandomAccessRead overrides.
    # ------------------------------------------------------------------

    def get_position(self) -> int:
        # Upstream getPosition (line 73): checkClosed + return currentPosition.
        self.check_closed()
        return self._current_position

    def seek(self, new_offset: int) -> None:
        # Upstream seek (line 83): checkClosed, reject negative, then seek the
        # parent to startPosition + min(newOffset, streamLength). The parent
        # cursor is intentionally moved on every seek so subsequent reads find
        # the right byte even if a sibling reader interleaved.
        self.check_closed()
        if new_offset < 0:
            raise OSError(f"Invalid position {new_offset}")
        assert self._random_access_read is not None
        self._random_access_read.seek(
            self._start_position + min(new_offset, self._stream_length)
        )
        self._current_position = new_offset

    def read(self) -> int:
        # Upstream read() (line 98): EOF -> -1, else restorePosition + parent
        # read; only advance currentPosition if a byte was actually returned.
        if self.is_eof():
            return self.EOF
        self.restore_position()
        assert self._random_access_read is not None
        read_value = self._random_access_read.read()
        if read_value > self.EOF:
            self._current_position += 1
        return read_value

    def read_into(
        self, buf: bytearray, offset: int = 0, length: int | None = None
    ) -> int:
        # Upstream read(byte[], int, int) (line 117): EOF -> -1, else
        # restorePosition + parent read clipped to view's available().
        if length is None:
            length = len(buf) - offset
        if length < 0:
            raise ValueError("length must be non-negative")
        if offset < 0 or offset + length > len(buf):
            raise ValueError("offset/length out of range for buf")
        if length == 0:
            # Java's read(b, off, 0) returns 0 even at EOF; preserve that here
            # so callers that probe with a zero-length read don't mistake it
            # for EOF.
            self.check_closed()
            return 0
        if self.is_eof():
            return self.EOF
        self.restore_position()
        assert self._random_access_read is not None
        clipped = min(length, self.available())
        read_bytes = self._random_access_read.read_into(buf, offset, clipped)
        if read_bytes > 0:
            self._current_position += read_bytes
        return read_bytes

    def length(self) -> int:
        # Upstream length() (line 133): checkClosed + return streamLength.
        self.check_closed()
        return self._stream_length

    def close(self) -> None:
        # Upstream close() (line 143): close parent only when closeInput is
        # set, then drop the parent reference so isClosed() returns true.
        if self._close_input and self._random_access_read is not None:
            self._random_access_read.close()
        self._random_access_read = None

    def is_closed(self) -> bool:
        # Upstream isClosed() (line 156): closed iff parent is null or itself
        # closed.
        return (
            self._random_access_read is None or self._random_access_read.is_closed()
        )

    def rewind(self, bytes_count: int) -> None:
        # Upstream rewind(int) (line 165): checkClosed, restorePosition, then
        # delegate rewind to the parent and adjust currentPosition. Java's
        # default RandomAccessRead.rewind() chains seek(getPosition()-n);
        # this override skips that indirection so the parent stays in sync.
        self.check_closed()
        self.restore_position()
        assert self._random_access_read is not None
        self._random_access_read.rewind(bytes_count)
        self._current_position -= bytes_count

    def is_eof(self) -> bool:
        # Upstream isEOF() (line 177): checkClosed + currentPosition >=
        # streamLength. Overrides the base implementation (which calls peek)
        # so EOF probing does not mutate the underlying parent.
        self.check_closed()
        return self._current_position >= self._stream_length

    def create_view(self, start_position: int, stream_length: int) -> RandomAccessRead:
        # Upstream createView (line 208): explicitly forbidden — nested views
        # are unsupported.
        raise OSError(
            f"{type(self).__name__}.create_view isn't supported."
        )
