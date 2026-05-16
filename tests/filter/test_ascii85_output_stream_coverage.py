"""Coverage-boost for ``pypdfbox.filter.ascii85_output_stream`` (wave 1321).

Targets the previously-untested branches:

* ``write`` — multi-byte buffer path (length-returning).
* ``flush`` — short-circuit when already flushed.
* ``transform_ascii85`` — input-validation, zero-group fast path (``z``
  marker), and regular 4-byte word encoding.
* ``set_terminator`` — validation (out-of-range, ``z`` rejected, int + str
  forms) plus ``get_terminator`` round-trip.
* ``set_line_length`` / ``get_line_length`` round-trip.
* ``close`` — idempotency and underlying-stream close.
* Round-trip through ``ASCII85InputStream`` to prove the wire format is
  decodable.
"""

from __future__ import annotations

import base64
import io

import pytest

from pypdfbox.filter.ascii85_input_stream import ASCII85InputStream
from pypdfbox.filter.ascii85_output_stream import ASCII85OutputStream


def test_write_bytes_returns_length() -> None:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    n = stream.write(b"abc")
    assert n == 3


def test_write_int_returns_one() -> None:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    # Integer write path.
    n = stream.write(0x41)
    assert n == 1


def test_writable_is_true() -> None:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    assert stream.writable() is True


def test_flush_then_round_trip_via_input_stream() -> None:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    payload = b"The quick brown fox jumps over the lazy dog."
    stream.write(payload)
    stream.flush()
    encoded = sink.getvalue()
    # Body ends with terminator + '>' + '\n'.
    assert encoded.endswith(b"~>\n")
    # Re-decode via the input stream to confirm wire format compatibility.
    encoded_body = encoded[:-1]  # drop trailing newline
    decoder = ASCII85InputStream(io.BytesIO(encoded_body))
    assert decoder.read(-1) == payload


def test_flush_short_circuits_when_already_flushed() -> None:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    stream.write(b"x")
    stream.flush()
    size_after_first_flush = len(sink.getvalue())
    # Second flush takes the ``if self._flushed: return`` branch.
    stream.flush()
    assert len(sink.getvalue()) == size_after_first_flush


def test_flush_when_nothing_written_does_nothing() -> None:
    """A pristine stream has ``_flushed=True`` so flush is a no-op."""
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    stream.flush()
    assert sink.getvalue() == b""


def test_line_length_breaks_long_encoded_body() -> None:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    stream.set_line_length(10)
    assert stream.get_line_length() == 10
    stream.write(b"X" * 200)
    stream.flush()
    encoded = sink.getvalue()
    # At least one embedded newline within the encoded body.
    body = encoded.rstrip(b"\n")[: -len(b"~>")]
    assert b"\n" in body


def test_set_terminator_int_form_round_trip() -> None:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    stream.set_terminator(126)  # '~' default
    assert stream.get_terminator() == "~"


def test_set_terminator_string_form() -> None:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    # 120 == 'x'; in range and != z.
    stream.set_terminator("x")
    assert stream.get_terminator() == "x"


def test_set_terminator_rejects_z() -> None:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    with pytest.raises(ValueError, match="Terminator"):
        stream.set_terminator("z")


def test_set_terminator_rejects_out_of_range_low() -> None:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    with pytest.raises(ValueError, match="Terminator"):
        stream.set_terminator(117)


def test_set_terminator_rejects_out_of_range_high() -> None:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    with pytest.raises(ValueError, match="Terminator"):
        stream.set_terminator(127)


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
    stream = ASCII85OutputStream(sink)
    stream.write(b"payload")
    stream.close()
    encoded = b"".join(written)
    assert encoded.endswith(b"~>\n")
    assert sink.closed is True


def test_close_is_idempotent() -> None:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    stream.write(b"payload")
    stream.close()
    # Second close: super().close() short-circuits, inner.close() is
    # wrapped in contextlib.suppress so even calling it on an already-closed
    # BytesIO is harmless.
    stream.close()


def test_close_is_safe_when_underlying_close_raises() -> None:
    class BadSink:
        def __init__(self) -> None:
            self.buf = bytearray()

        def write(self, b: bytes) -> int:
            self.buf.extend(b)
            return len(b)

        def flush(self) -> None:
            pass

        def close(self) -> None:
            raise RuntimeError("underlying close failed")

    sink = BadSink()
    stream = ASCII85OutputStream(sink)
    stream.write(b"data")
    # contextlib.suppress(Exception) on the underlying close.
    stream.close()


def test_transform_ascii85_requires_four_bytes() -> None:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    with pytest.raises(ValueError, match="4-byte input group"):
        stream.transform_ascii85(b"abc")


def test_transform_ascii85_zero_group_emits_z_marker() -> None:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    out = stream.transform_ascii85(b"\x00\x00\x00\x00")
    assert out[0] == ord("z")
    # Trailing 4 bytes are zero-padded per spec.
    assert out[1:] == bytes(4)


def test_transform_ascii85_regular_group_matches_base64_codec() -> None:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    payload = b"abcd"
    out = stream.transform_ascii85(payload)
    # Compare against base64.a85encode (without adobe markers).
    expected = base64.a85encode(payload, adobe=False)
    assert out == expected


def test_transform_ascii85_handles_bytearray_and_memoryview() -> None:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    payload = b"WXYZ"
    expected = base64.a85encode(payload, adobe=False)
    assert stream.transform_ascii85(bytearray(payload)) == expected
    assert stream.transform_ascii85(memoryview(payload)) == expected
