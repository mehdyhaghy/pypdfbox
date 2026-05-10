from __future__ import annotations

import io

from pypdfbox.io.random_access_read import RandomAccessRead


class RandomAccessReadNonClosingInputStream(io.RawIOBase):
    """Stream view of a :class:`RandomAccessRead` that does not close it.

    Mirrors the nested static class
    ``org.apache.fontbox.ttf.RandomAccessReadUnbufferedDataStream.RandomAccessReadNonClosingInputStream``
    (``RandomAccessReadUnbufferedDataStream.java`` lines 147-188).

    Upstream packages this as a private nested type inside
    :class:`RandomAccessReadUnbufferedDataStream`; we expose it as a
    standalone module so other clusters (e.g. font-program
    re-serialisation) can wrap a :class:`RandomAccessRead` as a stdlib
    ``InputStream``-shaped object without re-implementing the no-close
    behaviour each time.

    The lifetime of this stream is bound by the caller — it will not
    close the underlying :class:`RandomAccessRead` on :meth:`close`.
    This matches upstream's explicit ``// WARNING: .close() will close
    RandomAccessReadMemoryMappedFile if this View was based on it``
    comment (``RandomAccessReadUnbufferedDataStream.java`` line 185).
    """

    def __init__(self, random_access_read: RandomAccessRead) -> None:
        """Wrap ``random_access_read``.

        Mirrors ``RandomAccessReadNonClosingInputStream(RandomAccessReadView)``
        (``RandomAccessReadUnbufferedDataStream.java`` lines 152-155).
        Upstream uses the more specific ``RandomAccessReadView`` static
        type; we accept any :class:`RandomAccessRead` because the
        wrapper only relies on the read / seek surface defined on the
        ABC. The two callers in upstream (``getOriginalData`` and
        downstream font program code) both pass a
        ``createView(...)``-produced view, so behaviour is identical.
        """
        super().__init__()
        self._random_access_read: RandomAccessRead = random_access_read

    # ---- stdlib RawIOBase surface ----------------------------------

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        """Read up to ``size`` bytes.

        Mirrors the two upstream overloads ``int read()`` /
        ``int read(byte[])`` / ``int read(byte[], int, int)``
        (``RandomAccessReadUnbufferedDataStream.java`` lines 157-173)
        collapsed into a single stdlib-shaped call.
        """
        if size is None or size < 0:
            # Read everything remaining.
            length = self._random_access_read.length()
            remaining = length - self._random_access_read.get_position()
            if remaining <= 0:
                return b""
            buf = bytearray(remaining)
            n = self._random_access_read.read_into(buf, 0, remaining)
            if n <= 0:
                return b""
            return bytes(buf[:n])
        if size == 0:
            return b""
        buf = bytearray(size)
        n = self._random_access_read.read_into(buf, 0, size)
        if n <= 0:
            return b""
        return bytes(buf[:n])

    def readinto(self, buf: memoryview | bytearray) -> int:
        """Bulk read into ``buf``.

        Mirrors ``int read(byte[] b, int off, int len)``
        (``RandomAccessReadUnbufferedDataStream.java`` lines 169-173).
        ``RawIOBase.readinto`` only takes a buffer + length (no
        ``offset``), so a 0 offset is implied.
        """
        # ``memoryview`` lets us hand the underlying buffer through
        # without an intermediate copy; the cast to ``bytearray`` keeps
        # ``read_into``'s typed signature happy.
        target: bytearray
        if isinstance(buf, memoryview):
            # ``read_into`` writes through the memoryview when we hand it
            # a bytearray that aliases the same memory. ``memoryview``
            # exposes a ``.obj`` attribute back to the original buffer
            # — use it when available, fall back to a temporary copy.
            owner = getattr(buf, "obj", None)
            if isinstance(owner, bytearray) and buf.nbytes == len(owner):
                target = owner
                length = buf.nbytes
            else:
                temp = bytearray(buf.nbytes)
                n = self._random_access_read.read_into(temp, 0, buf.nbytes)
                if n <= 0:
                    return 0
                buf[:n] = temp[:n]
                return n
        else:
            target = buf
            length = len(buf)
        n = self._random_access_read.read_into(target, 0, length)
        return 0 if n <= 0 else n

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        """Random-access seek mirror; ``skip(n)``-flavoured calls map onto
        ``SEEK_CUR``.

        Mirrors ``long skip(long n)``
        (``RandomAccessReadUnbufferedDataStream.java`` lines 175-180).
        Upstream's only seek-shaped operation is ``skip``; we expose the
        full stdlib ``seek`` so file-like consumers (``io.BufferedReader``
        etc.) keep working.
        """
        if whence == io.SEEK_SET:
            target = offset
        elif whence == io.SEEK_CUR:
            target = self._random_access_read.get_position() + offset
        elif whence == io.SEEK_END:
            target = self._random_access_read.length() + offset
        else:
            msg = f"unsupported whence: {whence}"
            raise ValueError(msg)
        if target < 0:
            target = 0
        self._random_access_read.seek(target)
        return target

    def tell(self) -> int:
        return self._random_access_read.get_position()

    def skip(self, n: int) -> int:
        """Advance the read position by ``n`` bytes.

        Mirrors upstream ``long skip(long n)``
        (``RandomAccessReadUnbufferedDataStream.java`` L175-180).
        Returns the number of bytes actually skipped (clamped to the
        underlying stream's remaining length).
        """
        if n <= 0:
            return 0
        position = self._random_access_read.get_position()
        length = self._random_access_read.length()
        skipped = min(n, length - position)
        if skipped <= 0:
            return 0
        self._random_access_read.seek(position + skipped)
        return skipped

    def seekable(self) -> bool:
        return True

    def close(self) -> None:
        """No-op close — preserve upstream's "don't close the underlying
        random access read" contract.

        Mirrors ``void close()`` (``RandomAccessReadUnbufferedDataStream.java``
        lines 182-187). The ``WARNING`` comment upstream notes that
        closing the view could free a memory-mapped file the caller is
        still using; we mirror that defensive design.
        """
        super().close()


__all__ = ["RandomAccessReadNonClosingInputStream"]
