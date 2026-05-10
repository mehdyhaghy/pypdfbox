from __future__ import annotations

from typing import TYPE_CHECKING

from .ttf_data_stream import TTFDataStream

if TYPE_CHECKING:
    from pypdfbox.io.random_access_read import RandomAccessRead


class TTCDataStream(TTFDataStream):
    """A wrapper for a TTF stream inside a TTC file.

    Mirrors ``org.apache.fontbox.ttf.TTCDataStream`` (``TTCDataStream.java``
    lines 29-92). Wraps an underlying :class:`TTFDataStream` and forwards
    every read / seek to it without taking ownership: :meth:`close` is
    intentionally a no-op so the shared backing stream survives across
    every font in the same TTC. ``TrueTypeCollection.close()`` is the
    sole owner.

    Upstream this class is package-private and extends
    :class:`TTFDataStream`; we mirror that inheritance so the wrapper
    plugs in wherever a ``TTFDataStream`` is expected without an
    adapter.
    """

    def __init__(self, stream: TTFDataStream) -> None:
        """Wrap ``stream`` — mirror ``TTCDataStream(TTFDataStream stream)``
        (``TTCDataStream.java`` lines 33-36)."""
        self._stream: TTFDataStream = stream

    # ---- abstract overrides ----

    def read(self) -> int:
        """Mirror ``int read()`` (``TTCDataStream.java`` lines 38-42)."""
        return self._stream.read()

    def read_long(self) -> int:
        """Mirror ``long readLong()`` (``TTCDataStream.java`` lines 44-48)."""
        return self._stream.read_long()

    def close(self) -> None:
        """No-op — don't close the underlying shared stream.

        Mirrors ``void close()`` (``TTCDataStream.java`` lines 50-55):
        ``TrueTypeCollection.close()`` is the sole owner of the backing
        :class:`TTFDataStream`.
        """
        # do not close the underlying stream, as it is shared by all
        # fonts from the same TTC. ``TrueTypeCollection.close()`` must be
        # called instead.

    def seek(self, pos: int) -> None:
        """Mirror ``void seek(long pos)`` (``TTCDataStream.java`` lines 57-61)."""
        self._stream.seek(pos)

    def read_into(self, buf: bytearray, offset: int, length: int) -> int:
        """Mirror ``int read(byte[] b, int off, int len)``
        (``TTCDataStream.java`` lines 63-67)."""
        return self._stream.read_into(buf, offset, length)

    def get_current_position(self) -> int:
        """Mirror ``long getCurrentPosition()`` (``TTCDataStream.java``
        lines 69-73)."""
        return self._stream.get_current_position()

    def get_original_data(self) -> bytes:
        """Mirror ``InputStream getOriginalData()`` (``TTCDataStream.java``
        lines 75-79). Java returns an ``InputStream``; we mirror the
        existing :class:`TTFDataStream` contract by returning the raw
        ``bytes`` payload."""
        return self._stream.get_original_data()

    def get_original_data_size(self) -> int:
        """Mirror ``long getOriginalDataSize()`` (``TTCDataStream.java``
        lines 81-85)."""
        return self._stream.get_original_data_size()

    def create_sub_view(self, length: int) -> RandomAccessRead | None:
        """Mirror ``RandomAccessRead createSubView(long length)``
        (``TTCDataStream.java`` lines 87-91)."""
        return self._stream.create_sub_view(length)


__all__ = ["TTCDataStream"]
