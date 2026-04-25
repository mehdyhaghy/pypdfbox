from __future__ import annotations

import io

import pytest

from pypdfbox.filter import FilterFactory, RunLengthDecode


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


def test_decode_truncated_literal_raises() -> None:
    # Length 4 promises 5 bytes but only 3 follow.
    with pytest.raises(OSError):
        _decode(b"\x04abc")


def test_decode_truncated_repeat_raises() -> None:
    # 0xFD promises a byte to repeat but stream ends.
    with pytest.raises(OSError):
        _decode(b"\xfd")


def test_factory_resolves_long_and_short_names() -> None:
    long_filter = FilterFactory.get("RunLengthDecode")
    short_filter = FilterFactory.get("RL")
    assert isinstance(long_filter, RunLengthDecode)
    assert long_filter is short_filter


def test_factory_is_registered() -> None:
    assert FilterFactory.is_registered("RunLengthDecode")
    assert FilterFactory.is_registered("RL")


