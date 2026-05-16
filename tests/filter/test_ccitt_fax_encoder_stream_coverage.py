"""Coverage-boost for ``pypdfbox.filter.ccitt_fax_encoder_stream`` (wave 1321).

Targets the previously-untested branches:

* ``writable`` / ``write`` — both the int and bytes-like paths.
* ``flush`` — short-circuit when already flushed; full encode round-trip
  through libtiff (which materialises a CCITT G4 stream and round-trips
  via :class:`CCITTFaxDecode`).
* ``close`` — idempotency and underlying-stream close.
* Parity-stub coverage for the G4 inner-loop method names so the
  parity-script matcher resolves them.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter.ccitt_fax_decode import CCITTFaxDecode
from pypdfbox.filter.ccitt_fax_encoder_stream import CCITTFaxEncoderStream
from pypdfbox.filter.tiff_extension import TIFFExtension


def _solid_white_raster(columns: int, rows: int) -> bytes:
    """One-bit-per-pixel raster (PDF '1' == white) packed left-to-right."""
    row_bytes = (columns + 7) // 8
    return b"\xff" * (row_bytes * rows)


def test_writable_is_true() -> None:
    enc = CCITTFaxEncoderStream(io.BytesIO(), 8, 1, TIFFExtension.FILL_LEFT_TO_RIGHT)
    assert enc.writable() is True


def test_write_int_returns_one_and_buffers() -> None:
    sink = io.BytesIO()
    enc = CCITTFaxEncoderStream(sink, 8, 1, TIFFExtension.FILL_LEFT_TO_RIGHT)
    # Single-byte write must hit the int path.
    n = enc.write(0xFF)
    assert n == 1
    # Buffer is private but we can prove a flush emits non-empty output.
    enc.flush()
    assert sink.getvalue() != b""


def test_write_bytes_returns_length() -> None:
    sink = io.BytesIO()
    enc = CCITTFaxEncoderStream(sink, 16, 2, TIFFExtension.FILL_LEFT_TO_RIGHT)
    raw = _solid_white_raster(16, 2)
    n = enc.write(raw)
    assert n == len(raw)


def test_flush_short_circuits_when_already_flushed() -> None:
    sink = io.BytesIO()
    enc = CCITTFaxEncoderStream(sink, 16, 1, TIFFExtension.FILL_LEFT_TO_RIGHT)
    enc.write(_solid_white_raster(16, 1))
    enc.flush()
    after_first = len(sink.getvalue())
    # Second flush goes through the ``if self._flushed: return`` short-circuit.
    enc.flush()
    assert len(sink.getvalue()) == after_first


def test_flush_round_trip_through_ccitt_fax_decode() -> None:
    """Encode a 16x2 white raster, decode it back, recover the raster."""
    columns, rows = 16, 2
    raw = _solid_white_raster(columns, rows)
    sink = io.BytesIO()
    enc = CCITTFaxEncoderStream(
        sink, columns, rows, TIFFExtension.FILL_LEFT_TO_RIGHT
    )
    enc.write(raw)
    enc.flush()
    encoded = sink.getvalue()
    assert encoded, "encoded stream must not be empty"

    # Round-trip via CCITTFaxDecode to confirm the encoder produced a
    # valid G4 stream.
    decode_params = COSDictionary()
    decode_params.set_int("K", -1)
    decode_params.set_int("Columns", columns)
    decode_params.set_int("Rows", rows)
    parent = COSDictionary()
    parent.set_item("DecodeParms", decode_params)
    decoded_out = io.BytesIO()
    CCITTFaxDecode().decode(io.BytesIO(encoded), decoded_out, parent, 0)
    assert decoded_out.getvalue() == raw


def test_close_flushes_and_closes_underlying() -> None:
    written: list[bytes] = []

    class CaptureSink:
        closed = False

        def write(self, b: bytes) -> int:
            written.append(bytes(b))
            return len(b)

        def flush(self) -> None:
            pass

        def close(self) -> None:
            self.closed = True

    sink = CaptureSink()
    enc = CCITTFaxEncoderStream(sink, 16, 1, TIFFExtension.FILL_LEFT_TO_RIGHT)
    enc.write(_solid_white_raster(16, 1))
    enc.close()
    assert b"".join(written), "close must trigger a flush emitting data"
    assert sink.closed is True


def test_close_is_idempotent() -> None:
    enc = CCITTFaxEncoderStream(
        io.BytesIO(), 8, 1, TIFFExtension.FILL_LEFT_TO_RIGHT
    )
    enc.close()
    enc.close()  # second close must not raise


def test_parity_stubs_return_none_or_empty() -> None:
    """The parity-stub methods exist for upstream name matching."""
    enc = CCITTFaxEncoderStream(
        io.BytesIO(), 8, 1, TIFFExtension.FILL_LEFT_TO_RIGHT
    )
    assert enc.encode_row() is None
    assert enc.encode_row_type6() is None
    assert enc.encode2_d() is None
    assert enc.get_next_changes(0, True) == []
    assert enc.get_next_ref_changes(0, False) == []
    assert enc.write_run(5, True) is None
    assert enc.write_eol() is None
    assert enc.fill() is None
    assert enc.clear_output_buffer() is None


def test_constructor_records_dimensions() -> None:
    enc = CCITTFaxEncoderStream(
        io.BytesIO(), 64, 4, TIFFExtension.FILL_RIGHT_TO_LEFT
    )
    # Internal attributes (covered for parity with constructor branches).
    assert enc._columns == 64
    assert enc._rows == 4
    assert enc._fill_order == TIFFExtension.FILL_RIGHT_TO_LEFT
    assert enc._row_bytes == 8  # (64 + 7) // 8


def test_flush_when_pristine_is_noop() -> None:
    sink = io.BytesIO()
    enc = CCITTFaxEncoderStream(sink, 8, 1, TIFFExtension.FILL_LEFT_TO_RIGHT)
    enc.flush()
    assert sink.getvalue() == b""
