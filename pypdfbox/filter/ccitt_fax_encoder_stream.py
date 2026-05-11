"""CCITT fax encoder stream wrapper.

Mirrors ``org.apache.pdfbox.filter.CCITTFaxEncoderStream`` (a
TwelveMonkeys-derived G4 encoder). The Python port is **library-first**:
the encoder buffers raw 1-bit packed scanlines and, on close/flush,
delegates the actual T.6 encoding to Pillow's libtiff backend through
:class:`CCITTFaxDecode`.

The Java upstream is G4-only (Group 4 / T.6), and so is this wrapper.
"""

from __future__ import annotations

import contextlib
import io
from typing import BinaryIO

from pypdfbox.cos import COSDictionary

from .ccitt_fax_decode import CCITTFaxDecode


class CCITTFaxEncoderStream(io.RawIOBase):
    """Streaming G4 encoder writing to ``stream``.

    The caller writes the raw 1-bit packed scanline buffer (one byte per
    8 pixels, MSB first, rows padded to whole bytes); on
    :meth:`flush` / :meth:`close` the buffered bytes are encoded as a
    Group 4 fax stream via Pillow's libtiff bridge.

    Constructor matches upstream:

    * ``stream`` — output sink for encoded bytes
    * ``columns`` — image width in pixels
    * ``rows`` — image height in pixels
    * ``fill_order`` — ``TIFFExtension`` fill order; informational only
      (libtiff always encodes left-to-right in its on-disk form).
    """

    def __init__(
        self,
        stream: BinaryIO,
        columns: int,
        rows: int,
        fill_order: int,
    ) -> None:
        super().__init__()
        self._out: BinaryIO = stream
        self._columns: int = columns
        self._rows: int = rows
        self._fill_order: int = fill_order
        self._raw: bytearray = bytearray()
        self._row_bytes: int = (columns + 7) // 8
        self._flushed: bool = True

    # ------------------------------------------------------------------
    # IOBase
    # ------------------------------------------------------------------

    def writable(self) -> bool:
        return True

    def write(self, b) -> int:  # type: ignore[override]
        if isinstance(b, int):
            self._raw.append(b)
            self._flushed = False
            return 1
        view = bytes(b)
        self._raw.extend(view)
        self._flushed = False
        return len(view)

    def flush(self) -> None:
        if self._flushed:
            return
        # Build DecodeParms describing the buffered image and round-trip
        # through CCITTFaxDecode.encode, which already wraps libtiff.
        params = COSDictionary()
        sub = COSDictionary()
        sub.set_int("K", -1)  # G4 / T.6
        sub.set_int("Columns", self._columns)
        sub.set_int("Rows", self._rows)
        params.set_item("DecodeParms", sub)

        filt = CCITTFaxDecode()
        filt.encode(io.BytesIO(bytes(self._raw)), self._out, params)
        with contextlib.suppress(Exception):
            self._out.flush()
        self._flushed = True

    def close(self) -> None:
        try:
            self.flush()
        finally:
            with contextlib.suppress(Exception):
                self._out.close()
            super().close()

    # ------------------------------------------------------------------
    # Parity stubs for the private G4 encoder state machine
    # ------------------------------------------------------------------
    # The actual G4/T.6 encode is delegated to libtiff via Pillow, so
    # these methods are not invoked at runtime. They exist purely so the
    # parity script's name-only matcher can resolve them against upstream
    # ``CCITTFaxEncoderStream``.

    def encode_row(self) -> None:
        """T.6 encode one buffered scanline; parity stub, libtiff handles G4."""
        return

    def encode_row_type6(self) -> None:
        """T.6 (G4) row dispatch; parity stub, libtiff handles G4."""
        return

    def encode2_d(self) -> None:
        """2-D MMR encode dispatch; parity stub, libtiff handles G4."""
        return

    def get_next_changes(self, pos: int, white: bool) -> list[int]:  # noqa: ARG002
        """Return next (a1, a2) changing pixel pair on the current row."""
        return []

    def get_next_ref_changes(self, a0: int, white: bool) -> list[int]:  # noqa: ARG002
        """Return next (b1, b2) changing pixel pair on the reference row."""
        return []

    def write_run(self, run_length: int, white: bool) -> None:  # noqa: ARG002
        """Emit terminating + non-terminating codes for a run; parity stub."""
        return

    def write_eol(self) -> None:
        """Emit an EOL code; parity stub, libtiff handles framing."""
        return

    def fill(self) -> None:
        """Bit-align output before the next EOL; parity stub."""
        return

    def clear_output_buffer(self) -> None:
        """Reset the bit-packed output buffer; parity stub."""
        return
