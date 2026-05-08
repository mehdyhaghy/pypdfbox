from __future__ import annotations

import io

import pytest

from pypdfbox.filter import ASCII85Decode, FilterFactory


def _encode(data: bytes) -> bytes:
    out = io.BytesIO()
    ASCII85Decode().encode(io.BytesIO(data), out)
    return out.getvalue()


def _decode(data: bytes) -> bytes:
    out = io.BytesIO()
    ASCII85Decode().decode(io.BytesIO(data), out)
    return out.getvalue()


class _FlushTrackingBytesIO(io.BytesIO):
    def __init__(self) -> None:
        super().__init__()
        self.flush_count = 0

    def flush(self) -> None:
        self.flush_count += 1
        super().flush()


def test_round_trip_simple() -> None:
    payload = b"Man is distinguished, not only by his reason"
    assert _decode(_encode(payload)) == payload


def test_round_trip_long_random() -> None:
    # Deterministic pseudo-random bytes: covers all-byte-values without RNG flakiness.
    payload = bytes((i * 251 + 7) % 256 for i in range(10_000))
    assert _decode(_encode(payload)) == payload


def test_round_trip_empty() -> None:
    # Empty input must encode to just the EOD marker, decode back to empty.
    encoded = _encode(b"")
    assert encoded == b"~>"
    assert _decode(encoded) == b""


def test_z_shortcut_on_encode() -> None:
    # 4 zero bytes collapse to 'z' on encode (Adobe rule).
    encoded = _encode(b"\x00\x00\x00\x00")
    assert encoded == b"z~>"


def test_z_shortcut_on_decode() -> None:
    assert _decode(b"z~>") == b"\x00\x00\x00\x00"
    assert _decode(b"zz~>") == b"\x00" * 8


def test_partial_trailing_group_one_byte() -> None:
    # 1 -> 2 chars
    raw = b"M"
    encoded = _encode(raw)
    # Adobe ASCII85 of b"M" is b"9`~>": 2 chars + EOD.
    assert encoded == b"9`~>"
    assert _decode(encoded) == raw


def test_partial_trailing_group_two_bytes() -> None:
    raw = b"Ma"
    encoded = _encode(raw)
    # 2 -> 3 chars + EOD.
    assert encoded == b"9jn~>"
    assert _decode(encoded) == raw


def test_partial_trailing_group_three_bytes() -> None:
    raw = b"Man"
    encoded = _encode(raw)
    # 3 -> 4 chars + EOD.
    assert encoded == b"9jqo~>"
    assert _decode(encoded) == raw


def test_decode_ignores_embedded_whitespace() -> None:
    # Sprinkle space, tab, newline, carriage return, NUL into a valid stream.
    encoded = b"9j\nq\to \r ~>"
    assert _decode(encoded) == b"Man"


def test_decode_flushes_decoded_sink_after_write() -> None:
    out = _FlushTrackingBytesIO()

    result = ASCII85Decode().decode(io.BytesIO(b"9jqo~>"), out)

    assert out.getvalue() == b"Man"
    assert result.bytes_written == 3
    assert out.flush_count == 1


def test_encode_flushes_encoded_sink_after_eod_marker() -> None:
    out = _FlushTrackingBytesIO()

    ASCII85Decode().encode(io.BytesIO(b"Man"), out)

    assert out.getvalue() == b"9jqo~>"
    assert out.flush_count == 1


def test_decode_stops_at_eod_marker() -> None:
    # Bytes after ~> are ignored entirely (including garbage).
    encoded = b"9jqo~>trailinggarbage!@#"
    assert _decode(encoded) == b"Man"


def test_decode_without_eod_marker() -> None:
    # PDFBox is lenient: missing ~> still decodes the content seen so far.
    assert _decode(b"9jqo") == b"Man"


def test_decode_invalid_char_raises() -> None:
    with pytest.raises(OSError):
        _decode(b"9jqo|~>")  # '|' is 0x7C, above 'u' (0x75).


def test_decode_z_mid_group_raises() -> None:
    # 'z' is only valid at the start of a 5-char group.
    with pytest.raises(OSError):
        _decode(b"9jz~>")


def test_factory_resolves_long_and_short_names() -> None:
    long_filter = FilterFactory.get("ASCII85Decode")
    short_filter = FilterFactory.get("A85")
    assert isinstance(long_filter, ASCII85Decode)
    assert long_filter is short_filter


def test_factory_is_registered() -> None:
    assert FilterFactory.is_registered("ASCII85Decode")
    assert FilterFactory.is_registered("A85")
