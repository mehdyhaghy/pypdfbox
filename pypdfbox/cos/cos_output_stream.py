from __future__ import annotations

import io
from typing import TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pypdfbox.filter.filter import Filter
    from pypdfbox.io.random_access_read_buffered_file import RandomAccess

    from .cos_dictionary import COSDictionary

# Stream cache interface lives in pypdfbox.io but importing it eagerly
# would form a cycle through ``COSStream``; resolve lazily.


class COSOutputStream(io.RawIOBase):
    """An ``OutputStream`` which writes to an encoded COS stream.

    Mirrors upstream ``org.apache.pdfbox.cos.COSOutputStream`` (a final
    subclass of ``FilterOutputStream``). Writes accumulate in a temporary
    ``RandomAccess`` buffer; on close the buffer is encoded by each
    filter in reverse order and the final bytes are flushed to the
    enclosed output stream.
    """

    def __init__(
        self,
        filters: Sequence[Filter],
        parameters: COSDictionary,
        output: BinaryIO,
        stream_cache: object,
    ) -> None:
        super().__init__()
        self._filters: list[Filter] = list(filters)
        self._parameters: COSDictionary = parameters
        self._out: BinaryIO = output
        self._stream_cache: object = stream_cache
        self._buffer: RandomAccess | None = (
            None if not filters else self._create_buffer()
        )
        self._closed_flag: bool = False

    def _create_buffer(self) -> RandomAccess:
        create = getattr(self._stream_cache, "create_buffer", None)
        if create is None:
            raise TypeError(
                "stream_cache must expose create_buffer() returning a "
                "RandomAccess buffer"
            )
        return create()

    # ------------------------------------------------------------------
    # OutputStream-shaped writes
    # ------------------------------------------------------------------

    def write(self, b: bytes | bytearray | memoryview | int) -> int:  # type: ignore[override]
        """Write ``b`` (an ``int`` 0-255 or a bytes-like object) into the
        encoded stream. Mirrors upstream
        ``COSOutputStream.write(int)`` / ``write(byte[], int, int)``.
        """
        data = bytes((b & 0xFF,)) if isinstance(b, int) else bytes(b)
        if self._buffer is not None:
            self._buffer.write_bytes(data)
        else:
            self._out.write(data)
        return len(data)

    def writable(self) -> bool:
        return True

    def flush(self) -> None:
        """Flush the underlying output stream. When a buffer is in use no
        flush is required until :meth:`close` triggers encoding.

        Mirrors upstream ``COSOutputStream.flush`` (Java line 96).
        """
        if self._buffer is None:
            self._out.flush()

    # ------------------------------------------------------------------
    # Close — applies the filter chain in reverse order.
    # ------------------------------------------------------------------

    def close(self) -> None:  # type: ignore[override]
        if self._closed_flag:
            return
        self._closed_flag = True
        try:
            if self._buffer is not None:
                self._apply_filter_chain()
        finally:
            # Mark closed on RawIOBase first so the super().close()
            # flush hook is a no-op against the already-closed sink.
            try:
                super().close()
            finally:
                self._out.close()

    def _apply_filter_chain(self) -> None:
        # Local import — Filter pulls in cos modules.
        from pypdfbox.io.random_access_input_stream import (  # noqa: PLC0415
            RandomAccessInputStream,
        )
        from pypdfbox.io.random_access_output_stream import (  # noqa: PLC0415
            RandomAccessOutputStream,
        )

        buffer = self._buffer
        assert buffer is not None
        for i in range(len(self._filters) - 1, -1, -1):
            unfiltered = RandomAccessInputStream(buffer)
            try:
                if i == 0:
                    self._filters[i].encode(
                        unfiltered, self._out, self._parameters, i
                    )
                else:
                    filtered_buffer = self._create_buffer()
                    filtered_out = RandomAccessOutputStream(filtered_buffer)
                    try:
                        self._filters[i].encode(
                            unfiltered, filtered_out, self._parameters, i
                        )
                    finally:
                        filtered_out.close()
                        try:
                            buffer.close()
                        finally:
                            buffer = filtered_buffer
            finally:
                unfiltered.close()
        # Drop the final buffer reference once everything is encoded out.
        try:
            buffer.close()
        finally:
            self._buffer = None
