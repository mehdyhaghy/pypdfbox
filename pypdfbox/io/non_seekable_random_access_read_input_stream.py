from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .random_access_read import RandomAccessRead

if TYPE_CHECKING:
    from typing import BinaryIO


_LOG = logging.getLogger(__name__)

_BUFFER_SIZE: int = 4096
_CURRENT: int = 0
_LAST: int = 1
_NEXT: int = 2


class NonSeekableRandomAccessReadInputStream(RandomAccessRead):
    """``RandomAccessRead`` over a non-seekable ``InputStream``.

    Mirrors upstream
    ``org.apache.pdfbox.io.NonSeekableRandomAccessReadInputStream``. The
    source stream is read incrementally into three 4 KiB rolling buffers
    (current / last / next) so :meth:`rewind` works for small look-back
    distances without buffering the entire stream in memory.

    Intended for parsers that scan mostly forward. ``seek`` is not
    supported and raises ``OSError``.
    """

    def __init__(self, input_stream: BinaryIO) -> None:
        self._is: BinaryIO = input_stream
        self._buffers: list[bytearray] = [
            bytearray(_BUFFER_SIZE),
            bytearray(_BUFFER_SIZE),
            bytearray(_BUFFER_SIZE),
        ]
        self._buffer_bytes: list[int] = [-1, -1, -1]
        self._position: int = 0
        self._current_buffer_pointer: int = 0
        self._size: int = 0
        self._closed: bool = False
        self._eof: bool = False

    # ------------------------------------------------------------------
    # Lifecycle / status
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._is.close()
        self._closed = True

    def is_closed(self) -> bool:
        return self._closed

    def is_eof(self) -> bool:
        self._check_closed()
        return self._eof

    def check_closed(self) -> None:
        """Raise ``OSError`` if this stream has been closed.

        Mirrors upstream ``checkClosed`` (Java line 319; protected).
        """
        self._check_closed()

    def _check_closed(self) -> None:
        if self._closed:
            raise OSError(
                f"{type(self).__name__} already closed"
            )

    # ------------------------------------------------------------------
    # RandomAccessRead surface
    # ------------------------------------------------------------------

    def get_position(self) -> int:
        self._check_closed()
        return self._position

    def seek(self, position: int) -> None:
        """Seeking is unsupported.

        Mirrors upstream ``seek`` (Java line 89) which throws
        ``IOException``.
        """
        raise OSError(
            f"{type(self).__name__}.seek isn't supported."
        )

    def skip(self, length: int) -> None:  # type: ignore[override]
        """Advance the read cursor by ``length`` bytes.

        Mirrors upstream ``skip(int)`` (Java line 95).
        """
        size = min(length, _BUFFER_SIZE)
        skip_buffer = bytearray(size)
        remaining = length
        while remaining > 0:
            n = self.read_into(skip_buffer, 0, min(remaining, len(skip_buffer)))
            if n == -1:
                break
            remaining -= n

    def read(self) -> int:
        self._check_closed()
        if self.is_eof():
            return self.EOF
        if self._current_buffer_pointer >= self._buffer_bytes[_CURRENT] and not self._fetch():
            self._eof = True
            return self.EOF
        self._position += 1
        value = self._buffers[_CURRENT][self._current_buffer_pointer] & 0xFF
        self._current_buffer_pointer += 1
        return value

    def read_into(
        self, buf: bytearray, offset: int = 0, length: int | None = None
    ) -> int:
        self._check_closed()
        if length is None:
            length = len(buf) - offset
        if buf is None:  # type: ignore[unreachable]  # pragma: no cover - mirrors upstream null guard; unreachable when Python type-checks pass
            raise ValueError("buffer is null")
        if offset < 0 or length < 0 or offset + length > len(buf):
            raise IndexError(
                f"buffer length={len(buf)} offset={offset} length={length}"
            )
        if length == 0:
            return 0
        if self.is_eof():
            return self.EOF
        number_read = 0
        while number_read < length:
            available = self._buffer_bytes[_CURRENT] - self._current_buffer_pointer
            if available > 0:
                to_copy = min(length - number_read, available)
                start = self._current_buffer_pointer
                buf[offset + number_read : offset + number_read + to_copy] = (
                    self._buffers[_CURRENT][start : start + to_copy]
                )
                self._current_buffer_pointer += to_copy
                self._position += to_copy
                number_read += to_copy
            elif not self._fetch():
                self._eof = True
                break
        return number_read if number_read > 0 else self.EOF

    def read_fully(  # type: ignore[override]
        self,
        buf: bytearray | int,
        offset: int = 0,
        length: int | None = None,
    ) -> bytes | None:
        """Read exactly ``length`` bytes; raise ``EOFError`` on short read.

        Mirrors upstream ``readFully`` (Java line 188). Overrides the
        base implementation because ``length()`` here is an estimate
        based on the underlying stream's ``available``.
        """
        if isinstance(buf, int):
            out = bytearray(buf)
            self.read_fully(out)
            return bytes(out)
        if length is None:
            length = len(buf) - offset
        self._check_closed()
        total = 0
        while total < length:
            n = self.read_into(buf, offset + total, length - total)
            if n <= 0:
                raise EOFError("EOF, should have been detected earlier")
            total += n
        return None

    def length(self) -> int:
        """Total length estimate (already-read + bytes available).

        Mirrors upstream ``length`` (Java line 277). Cannot be relied on
        for total file size before the stream has been fully drained.
        """
        self._check_closed()
        return self._size + self._available_on_underlying()

    def _available_on_underlying(self) -> int:
        # Standard Python file-like streams do not expose ``available``;
        # mirror the upstream method by falling back to 0. Subclasses
        # backed by sockets can override.
        available = getattr(self._is, "available", None)
        if callable(available):
            try:
                return int(available())
            except Exception:
                return 0
        return 0

    def available(self) -> int:  # type: ignore[override]
        self._check_closed()
        buffered = max(0, self._buffer_bytes[_CURRENT] - self._current_buffer_pointer)
        return buffered + self._available_on_underlying()

    def rewind(self, n: int) -> None:  # type: ignore[override]
        """Move the read cursor back by ``n`` bytes.

        Mirrors upstream ``rewind`` (Java line 284). Only rewinds within
        the current and previous buffers; further look-back raises.
        """
        bytes_to_rewind = n
        if self._current_buffer_pointer >= bytes_to_rewind:
            self._current_buffer_pointer -= bytes_to_rewind
            self._position -= bytes_to_rewind
            self._eof = False
            return
        if (
            self._buffer_bytes[_LAST] > 0
            and (bytes_to_rewind - self._current_buffer_pointer)
            <= self._buffer_bytes[_LAST]
        ):
            remaining = bytes_to_rewind - self._current_buffer_pointer
            self._switch_buffers(_CURRENT, _NEXT)
            self._switch_buffers(_CURRENT, _LAST)
            self._buffer_bytes[_LAST] = -1
            self._current_buffer_pointer = self._buffer_bytes[_CURRENT] - remaining
            self._position -= bytes_to_rewind
            self._eof = False
            return
        raise OSError("not enough bytes available to perform the rewind operation")

    def create_view(self, start_position: int, length: int) -> RandomAccessRead:
        """Views are unsupported on non-seekable streams.

        Mirrors upstream ``createView`` (Java line 347) which throws.
        """
        raise OSError(
            f"{type(self).__name__}.createView isn't supported."
        )

    # ------------------------------------------------------------------
    # Internals — buffer rotation
    # ------------------------------------------------------------------

    def switch_buffers(self, first: int, second: int) -> None:
        """Public alias for :meth:`_switch_buffers` mirroring upstream's
        ``switchBuffers`` method name (Java line 204, private)."""
        self._switch_buffers(first, second)

    def fetch(self) -> bool:
        """Public alias for :meth:`_fetch` mirroring upstream's
        ``fetch`` method name (Java line 226, private)."""
        return self._fetch()

    def _switch_buffers(self, first: int, second: int) -> None:
        self._buffers[first], self._buffers[second] = (
            self._buffers[second],
            self._buffers[first],
        )
        self._buffer_bytes[first], self._buffer_bytes[second] = (
            self._buffer_bytes[second],
            self._buffer_bytes[first],
        )

    def _fetch(self) -> bool:
        self._check_closed()
        self._current_buffer_pointer = 0
        if self._buffer_bytes[_NEXT] > -1:
            self._switch_buffers(_CURRENT, _LAST)
            self._switch_buffers(_CURRENT, _NEXT)
            self._buffer_bytes[_NEXT] = -1
            return True
        try:
            if (
                self._buffer_bytes[_LAST] == _BUFFER_SIZE
                and 0 < self._buffer_bytes[_CURRENT] < _BUFFER_SIZE
            ):
                # Likely-EOF salvage path: preserve as much LAST+CURRENT
                # content as possible into LAST so a future rewind has
                # data to consult. Matches upstream's same-named branch.
                cur_len = self._buffer_bytes[_CURRENT]
                preserved = bytearray(_BUFFER_SIZE)
                preserved[: _BUFFER_SIZE - cur_len] = self._buffers[_LAST][cur_len:]
                preserved[_BUFFER_SIZE - cur_len :] = self._buffers[_CURRENT][:cur_len]
                self._buffers[_LAST] = preserved
                self._buffer_bytes[_LAST] = _BUFFER_SIZE
            else:
                self._switch_buffers(_CURRENT, _LAST)
            read = self._is.readinto(self._buffers[_CURRENT])  # type: ignore[union-attr]
            if read is None or read <= 0:
                self._buffer_bytes[_CURRENT] = -1
                return False
            self._buffer_bytes[_CURRENT] = read
            self._size += read
        except OSError as exc:
            _LOG.warning("premature end of stream, some data could be read: %s", exc)
            self._eof = True
            raise
        return True

    def read_fully_int(self, length: int) -> bytes:
        """Compatibility wrapper for the upstream ``int`` overload of
        ``readFully``. Returns the bytes read.
        """
        return self.read_fully(length)  # type: ignore[return-value]
