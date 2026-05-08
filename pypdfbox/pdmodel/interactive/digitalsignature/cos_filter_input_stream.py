from __future__ import annotations

from collections.abc import Sequence
from contextlib import suppress
from io import BytesIO
from types import TracebackType
from typing import BinaryIO, cast


class COSFilterInputStream:
    """Read stream that emits *only* the byte ranges given by a PDF
    ``/ByteRange`` array.

    Mirrors PDFBox ``org.apache.pdfbox.pdmodel.interactive.digitalsignature.
    COSFilterInputStream``. Use this to recompute the message digest of a
    signed PDF: ``/ByteRange = [start1, len1, start2, len2]`` brackets the
    ``/Contents`` placeholder, so reading through this stream yields the
    concatenation of the two slices that the PKCS#7 SignedData blob covers.

    The ``byte_range`` parameter accepts either:

    * a flat sequence ``[start1, len1, start2, len2, ...]`` (any even count),
      matching the PDF on-disk layout / upstream Java ``int[]``; or
    * a sequence of ``(start, length)`` 2-tuples, matching the upstream Java
      ``int[][]`` overload that some helpers pass.

    Reads outside the requested ranges are simply elided — the stream does
    *not* error if the underlying source is shorter than ``start + length``,
    it just stops at EOF, again matching upstream behavior.
    """

    def __init__(
        self,
        source: BinaryIO | bytes | bytearray | memoryview,
        byte_range: Sequence[int] | Sequence[Sequence[int]],
    ) -> None:
        if isinstance(source, (bytes, bytearray, memoryview)):
            self._source: BinaryIO = BytesIO(bytes(source))
        else:
            self._source = source

        # Normalise ``byte_range`` into a list of (start, length) pairs.
        pairs: list[tuple[int, int]] = []
        if not byte_range:
            self._ranges: list[tuple[int, int]] = []
        else:
            first = byte_range[0]
            if isinstance(first, (list, tuple)):
                nested = cast(Sequence[Sequence[int]], byte_range)
                for entry in nested:
                    if len(entry) != 2:
                        raise ValueError(
                            "COSFilterInputStream: nested byte_range entries "
                            "must be (start, length) pairs"
                        )
                    pairs.append((int(entry[0]), int(entry[1])))
            else:
                flat = list(cast(Sequence[int], byte_range))
                if len(flat) % 2 != 0:
                    raise ValueError(
                        "COSFilterInputStream: flat byte_range must have an "
                        "even number of entries"
                    )
                for i in range(0, len(flat), 2):
                    pairs.append((int(flat[i]), int(flat[i + 1])))

            for start, length in pairs:
                if start < 0:
                    raise ValueError(
                        f"COSFilterInputStream: negative start offset {start}"
                    )
                if length < 0:
                    raise ValueError(
                        f"COSFilterInputStream: negative length {length}"
                    )
            # Sort by start to allow forward-only seeking on non-seekable
            # sources. Upstream relies on /ByteRange being already sorted, but
            # being lenient here costs us nothing and protects callers.
            pairs.sort(key=lambda p: p[0])
            self._ranges = pairs

        self._range_index = 0
        # Bytes left to read in current range.
        self._remaining_in_range = 0
        # Absolute byte offset we've consumed from the underlying source.
        self._source_pos = 0
        self._closed = False
        self._prime_next_range()

    # ------------------------------------------------------------------ helpers

    def _prime_next_range(self) -> None:
        """Advance to the start of the next range, skipping intervening bytes."""
        while self._range_index < len(self._ranges):
            start, length = self._ranges[self._range_index]
            if length == 0:
                # Empty range — move on without touching the source.
                self._range_index += 1
                continue
            if start < self._source_pos:
                # Overlapping / out-of-order range. Skip what's already been
                # consumed; if the whole range is behind us, drop it.
                skip_in_range = self._source_pos - start
                if skip_in_range >= length:
                    self._range_index += 1
                    continue
                self._remaining_in_range = length - skip_in_range
                return
            # Skip forward to the range's start offset.
            to_skip = start - self._source_pos
            if to_skip:
                self._skip_source(to_skip)
            self._remaining_in_range = length
            return
        self._remaining_in_range = 0

    def _skip_source(self, n: int) -> None:
        if n <= 0:
            return
        if hasattr(self._source, "seek") and hasattr(self._source, "tell"):
            try:
                self._source.seek(n, 1)
                self._source_pos += n
                return
            except (OSError, ValueError):
                pass  # Fall through to read-and-discard.
        # Read-and-discard fallback for non-seekable sources.
        remaining = n
        while remaining > 0:
            chunk = self._source.read(min(remaining, 8192))
            if not chunk:
                break
            remaining -= len(chunk)
            self._source_pos += len(chunk)

    # --------------------------------------------------------------- public API

    def read(self, size: int = -1) -> bytes:
        """Read up to ``size`` bytes from within the configured byte ranges.

        ``size < 0`` reads everything that remains in all ranges. Returns
        ``b""`` at EOF, matching the file-object protocol.
        """
        if self._closed:
            raise ValueError("read on closed COSFilterInputStream")

        if size == 0:
            return b""

        out = bytearray()
        unlimited = size is None or size < 0
        wanted = -1 if unlimited else size

        while (unlimited or wanted > 0) and self._range_index < len(self._ranges):
            if self._remaining_in_range == 0:
                self._range_index += 1
                self._prime_next_range()
                continue

            chunk_size = (
                self._remaining_in_range
                if unlimited
                else min(self._remaining_in_range, wanted)
            )
            chunk = self._source.read(chunk_size)
            if not chunk:
                break
            out.extend(chunk)
            self._source_pos += len(chunk)
            self._remaining_in_range -= len(chunk)
            if not unlimited:
                wanted -= len(chunk)
            # If we got short, the source is exhausted — bail out.
            if len(chunk) < chunk_size:
                break

        return bytes(out)

    def read_all(self) -> bytes:
        """Convenience: read every byte covered by ``byte_range`` at once."""
        return self.read(-1)

    def readable(self) -> bool:
        return not self._closed

    def writable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with suppress(Exception):
            self._source.close()

    # Context-manager support, since callers naturally `with` filter streams.
    def __enter__(self) -> COSFilterInputStream:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


__all__ = ["COSFilterInputStream"]
