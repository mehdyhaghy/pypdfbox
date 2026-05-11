from __future__ import annotations

from .random_access import RandomAccess
from .random_access_read_write_buffer import RandomAccessReadWriteBuffer
from .random_access_stream_cache import RandomAccessStreamCache


class RandomAccessStreamCacheImpl(RandomAccessStreamCache):
    """Default ``RandomAccessStreamCache`` backed by in-memory buffers.

    Mirrors upstream
    ``org.apache.pdfbox.io.RandomAccessStreamCacheImpl``. Each call to
    :meth:`create_buffer` returns a fresh ``RandomAccessReadWriteBuffer``.
    """

    def create_buffer(self) -> RandomAccess:
        return RandomAccessReadWriteBuffer()

    def close(self) -> None:  # noqa: D401 — match upstream signature
        # Nothing to do — the buffers we hand out are managed by callers.
        pass
