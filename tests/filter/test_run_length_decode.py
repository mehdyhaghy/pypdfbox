from __future__ import annotations

import io

from pypdfbox.filter import FilterFactory, RunLengthDecode


class _ShortReadBytesIO(io.BytesIO):
    def read(self, size: int | None = -1, /) -> bytes:
        if size is None or size < 0:
            return super().read(size)
        return super().read(min(size, 2))


class _FlushTrackingBytesIO(io.BytesIO):
    def __init__(self) -> None:
        super().__init__()
        self.flush_count = 0

    def flush(self) -> None:
        self.flush_count += 1
        super().flush()


def _encode(data: bytes) -> bytes:
    out = io.BytesIO()
    RunLengthDecode().encode(io.BytesIO(data), out)
    return out.getvalue()


def _decode(data: bytes) -> bytes:
    out = io.BytesIO()
    RunLengthDecode().decode(io.BytesIO(data), out)
    return out.getvalue()


def test_round_trip_simple_mixed() -> None:
    payload = b"the quick brown fox jumps over the lazy dog"
    assert _decode(_encode(payload)) == payload


def test_round_trip_long() -> None:
    # Mix of literal and run-able stretches, deterministic.
    payload = (
        b"\x00" * 300
        + bytes(range(256))
        + b"AB" * 50
        + b"\xff" * 200
        + b"unique-tail-bytes"
    )
    assert _decode(_encode(payload)) == payload


def test_round_trip_empty() -> None:
    encoded = _encode(b"")
    # Empty input: just the EOD marker.
    assert encoded == b"\x80"
    assert _decode(encoded) == b""


def test_decode_literal_only() -> None:
    # Length 4 means the next 5 bytes are literal.
    encoded = b"\x04hello\x80"
    assert _decode(encoded) == b"hello"


def test_wave318_decode_literal_accepts_short_reads() -> None:
    out = io.BytesIO()

    result = RunLengthDecode().decode(_ShortReadBytesIO(b"\x04hello\x80"), out)

    assert out.getvalue() == b"hello"
    assert result.bytes_written == 5


def test_decode_flushes_decoded_sink_after_eod() -> None:
    out = _FlushTrackingBytesIO()

    result = RunLengthDecode().decode(io.BytesIO(b"\x02ABC\x80"), out)

    assert out.getvalue() == b"ABC"
    assert result.bytes_written == 3
    assert out.flush_count == 1


def test_encode_flushes_encoded_sink_after_eod_marker() -> None:
    out = _FlushTrackingBytesIO()

    RunLengthDecode().encode(io.BytesIO(b"ABC"), out)

    assert out.getvalue() == b"\x02ABC\x80"
    assert out.flush_count == 1


def test_decode_run_only() -> None:
    # Length 252 means the next byte is repeated 5 times (257 - 252 = 5).
    encoded = b"\xfcA\x80"
    assert _decode(encoded) == b"AAAAA"


def test_decode_mixed() -> None:
    # Literal "ab" + 4 copies of 'X' + literal "cd" + EOD.
    encoded = b"\x01ab\xfdX\x01cd\x80"
    assert _decode(encoded) == b"abXXXXcd"


def test_decode_eod_marker_stops() -> None:
    # Bytes after EOD are ignored.
    encoded = b"\x02ABC\x80garbage"
    assert _decode(encoded) == b"ABC"


def test_decode_truncated_literal_copies_available_bytes_and_stops() -> None:
    assert _decode(b"\x04abc") == b"abc"


def test_decode_truncated_repeat_stops_without_output() -> None:
    assert _decode(b"\xfd") == b""


def test_factory_resolves_long_and_short_names() -> None:
    long_filter = FilterFactory.get("RunLengthDecode")
    short_filter = FilterFactory.get("RL")
    assert isinstance(long_filter, RunLengthDecode)
    assert long_filter is short_filter


def test_factory_is_registered() -> None:
    assert FilterFactory.is_registered("RunLengthDecode")
    assert FilterFactory.is_registered("RL")
