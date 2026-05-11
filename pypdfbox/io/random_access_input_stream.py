from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .random_access_read import RandomAccessRead


_LOG = logging.getLogger(__name__)


class RandomAccessInputStream(io.RawIOBase):
    """An ``InputStream``-style adapter over a ``RandomAccessRead``.

    Mirrors upstream
    ``org.apache.pdfbox.io.RandomAccessInputStream``. Maintains an
    independent read position so the underlying ``RandomAccessRead``
    can be shared between adapters; the adapter restores its position
    on every call.
    """

    def __init__(self, random_access_read: RandomAccessRead) -> None:
        super().__init__()
        self._input: RandomAccessRead = random_access_read
        self._position: int = 0

    # ------------------------------------------------------------------
    # Position bookkeeping
    # ------------------------------------------------------------------

    def restore_position(self) -> None:
        """Seek the underlying source to this adapter's logical position.

        Mirrors upstream ``RandomAccessInputStream.restorePosition``
        (Java line 50, package-private).
        """
        self._input.seek(self._position)

    # ------------------------------------------------------------------
    # IOBase plumbing
    # ------------------------------------------------------------------

    def readable(self) -> bool:
        return True

    def available(self) -> int:
        """Bytes ready to be read without blocking.

        Mirrors upstream ``RandomAccessInputStream.available`` (Java
        line 56). Clamped to ``sys.maxsize`` to mirror Java's
        ``Integer.MAX_VALUE`` ceiling.
        """
        try:
            remaining = self._input.length() - self._position
        except Exception:
            return 0
        return max(0, min(remaining, (1 << 31) - 1))

    def read(self, size: int = -1) -> bytes:  # type: ignore[override]
        if size is None or size < 0:
            # Read to EOF.
            chunks: list[bytes] = []
            buf = bytearray(4096)
            while True:
                n = self._read_into(buf, 0, len(buf))
                if n <= 0:
                    break
                chunks.append(bytes(buf[:n]))
            return b"".join(chunks)
        if size == 0:
            return b""
        buf = bytearray(size)
        n = self._read_into(buf, 0, size)
        if n <= 0:
            return b""
        return bytes(buf[:n])

    def readinto(self, b: bytearray | memoryview) -> int:  # type: ignore[override]
        # ``b`` may be a memoryview-of-bytearray; ``RandomAccessRead.read_into``
        # only accepts ``bytearray``. Round-trip through a temporary when
        # we are handed a memoryview.
        if isinstance(b, memoryview):
            tmp = bytearray(b.nbytes)
            n = self._read_into(tmp, 0, len(tmp))
            if n > 0:
                b[:n] = tmp[:n]
            return max(n, 0)
        return max(self._read_into(b, 0, len(b)), 0)

    def _read_into(self, b: bytearray, offset: int, length: int) -> int:
        self.restore_position()
        try:
            if self._input.is_eof():
                return -1
        except Exception:
            return -1
        n = self._input.read_into(b, offset, length)
        if n != -1:
            self._position += n
        else:
            _LOG.error(
                "read() returns -1, assumed position: %s, actual position: %s",
                self._position,
                self._input.get_position(),
            )
        return n

    def read1(self, size: int = -1) -> bytes:  # type: ignore[override]
        return self.read(size)

    def skip(self, n: int) -> int:
        """Skip ``n`` bytes forward in the stream.

        Mirrors upstream ``RandomAccessInputStream.skip`` (Java line 108).
        """
        if n <= 0:
            return 0
        self.restore_position()
        self._input.seek(self._position + n)
        self._position += n
        return n

    def seekable(self) -> bool:
        return False

    def tell(self) -> int:
        return self._position
