"""Predictor-decoding output stream.

Mirrors the private static inner class
``Predictor.PredictorOutputStream`` in upstream PDFBox. Data is buffered
until a complete scanline is available, the predictor is reversed
in-place (via :func:`pypdfbox.filter._predictor.decode_predictor_row`),
and the decoded row is written to the underlying sink. The previous row
is retained as context for the next row.

Promoted to a module-level class because Python doesn't have Java's
nested-class visibility model; users should treat this as an
implementation detail of :class:`pypdfbox.filter.predictor.Predictor`.
"""

from __future__ import annotations

import contextlib
import io
import os
from typing import BinaryIO

from ._predictor import calculate_row_length, decode_predictor_row

#: PDFBOX-6265: default cap on the computed scanline length. A crafted
#: ``/DecodeParms`` with extreme ``/Colors``, ``/BitsPerComponent`` or
#: ``/Columns`` otherwise asks for two multi-GB row buffers before a
#: single encoded byte is inspected.
_DEFAULT_MAX_ROW_LENGTH = 10_000_000


def _max_row_length() -> int:
    """Resolve the predictor row-length cap (PDFBOX-6265).

    Mirrors upstream's read of the
    ``Filter.SYSPROP_PREDICTOR_MAX_ROW_LENGTH`` system property —
    consumed as an environment variable on the Python side, the same
    convention :meth:`Filter.get_compression_level` uses for
    ``SYSPROP_DEFLATELEVEL``. A positive integer overrides the 10,000,000
    default; zero, negative or unparseable values are ignored (default
    kept), matching upstream.
    """
    # Imported lazily: ``filter`` pulls in the whole codec surface and
    # this module sits below it in the import graph.
    from .filter import Filter

    max_row_length = _DEFAULT_MAX_ROW_LENGTH
    sys_prop = os.environ.get(Filter.SYSPROP_PREDICTOR_MAX_ROW_LENGTH)
    if sys_prop is not None:
        try:
            parsed = int(sys_prop)
        except ValueError:
            # ignore invalid value, keep default
            pass
        else:
            if parsed > 0:
                max_row_length = parsed
            # else ignore zero/negative values
    return max_row_length


class PredictorOutputStream(io.RawIOBase):
    """Output stream that implements predictor decoding.

    Constructor mirrors upstream's ``PredictorOutputStream(OutputStream,
    int predictor, int colors, int bitsPerComponent, int columns)``.
    """

    def __init__(
        self,
        out: BinaryIO,
        predictor: int,
        colors: int,
        bits_per_component: int,
        columns: int,
    ) -> None:
        super().__init__()
        self._out: BinaryIO = out
        self._predictor: int = predictor
        self._colors: int = colors
        self._bits_per_component: int = bits_per_component
        self._columns: int = columns
        # Seed the row state before the validation below. Java simply never
        # publishes an object whose constructor threw; CPython still runs
        # ``RawIOBase.__del__`` -> ``close()`` -> ``flush()`` on the
        # half-built instance, which would blow up on the missing
        # attributes and surface as an unraisable exception.
        self._row_length: int = 0
        self._predictor_per_row: bool = predictor >= 10
        self._current_row: bytearray = bytearray()
        self._last_row: bytearray = bytearray()
        self._current_row_data: int = 0
        self._predictor_read: bool = False
        row_length = calculate_row_length(colors, bits_per_component, columns)
        if row_length < 0:
            raise OSError(f"Calculated row length is negative: {row_length}")
        # PDFBOX-6265: prevent OOM with extreme values
        max_row_length = _max_row_length()
        if row_length > max_row_length:
            raise OSError(
                f"Calculated row length is too high: {row_length} "
                f"(colors: {colors}, bitsPerComponent: {bits_per_component}, "
                f"columns: {columns})"
            )
        self._row_length = row_length
        # PNG predictor (>=10) means each row starts with a per-row tag.
        self._current_row = bytearray(row_length)
        self._last_row = bytearray(row_length)

    # ------------------------------------------------------------------
    # IOBase
    # ------------------------------------------------------------------

    def writable(self) -> bool:
        return True

    def write(self, b) -> int:  # type: ignore[override]
        if isinstance(b, int):
            # Upstream's single-byte write() throws — mirror that.
            raise NotImplementedError("Not supported")
        data = bytes(b)
        self._write_bytes(data, 0, len(data))
        return len(data)

    def _write_bytes(self, data: bytes, off: int, length: int) -> None:
        current_offset = off
        max_offset = current_offset + length
        while current_offset < max_offset:
            if (
                self._predictor_per_row
                and self._current_row_data == 0
                and not self._predictor_read
            ):
                # PNG predictor; each row starts with predictor type
                # (0..4). Add 10 so the helpers treat 0 as 10, 1 as 11, ….
                self._predictor = data[current_offset] + 10
                current_offset += 1
                self._predictor_read = True
            else:
                to_read = min(
                    self._row_length - self._current_row_data,
                    max_offset - current_offset,
                )
                self._current_row[
                    self._current_row_data : self._current_row_data + to_read
                ] = data[current_offset : current_offset + to_read]
                self._current_row_data += to_read
                current_offset += to_read

                if self._current_row_data == self._row_length:
                    self.decode_and_write_row()

    def decode_and_write_row(self) -> None:
        """Reverse the predictor for the buffered row and emit it.

        Mirrors upstream's private ``decodeAndWriteRow()``: applies the
        configured predictor against the previous row, writes the decoded
        row to the underlying stream, then rotates buffers via
        :meth:`flip_rows`.
        """
        decode_predictor_row(
            self._predictor,
            self._colors,
            self._bits_per_component,
            self._columns,
            self._current_row,
            self._last_row,
        )
        self._out.write(bytes(self._current_row))
        self.flip_rows()

    def flip_rows(self) -> None:
        """Swap current and previous row buffers and reset offsets.

        Mirrors upstream's private ``flipRows()``: after a row has been
        decoded and emitted, the just-decoded row becomes the *reference*
        (previous) row for the next decode pass.
        """
        self._last_row, self._current_row = self._current_row, self._last_row
        self._current_row_data = 0
        self._predictor_read = False

    def flush(self) -> None:
        # The last row may be incomplete; zero-pad and emit it.
        if self._current_row_data > 0:
            for i in range(self._current_row_data, self._row_length):
                self._current_row[i] = 0
            self.decode_and_write_row()
        with contextlib.suppress(Exception):
            self._out.flush()

    def close(self) -> None:
        try:
            self.flush()
        finally:
            with contextlib.suppress(Exception):
                self._out.close()
            super().close()
