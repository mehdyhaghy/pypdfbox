"""Wave 1368 (agent D) — RunLengthDecode packet-type parity.

ISO 32000-1 §7.4.5 packet grammar:

* length byte 0..127  → next ``length + 1`` bytes are copied verbatim
  (1..128-byte literal run);
* length byte == 128  → end-of-data marker, decoder stops;
* length byte 129..255 → next single byte is repeated ``257 - length``
  times (2..128-byte repeat run).

Tests pin every band of the length-byte alphabet and the EOD handling.
"""

from __future__ import annotations

import io

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import RunLengthDecode
from pypdfbox.filter.run_length_decode import RUN_LENGTH_EOD


def _decode(encoded: bytes) -> bytes:
    f = RunLengthDecode()
    out = io.BytesIO()
    f.decode(io.BytesIO(encoded), out, COSDictionary(), 0)
    return out.getvalue()


def _encode(raw: bytes) -> bytes:
    f = RunLengthDecode()
    out = io.BytesIO()
    f.encode(io.BytesIO(raw), out, COSDictionary())
    return out.getvalue()


def test_run_length_eod_constant_value() -> None:
    """EOD sentinel byte is 0x80 per ISO 32000-1 §7.4.5."""
    assert RUN_LENGTH_EOD == 128
    assert RunLengthDecode.RUN_LENGTH_EOD == 128


def test_decode_single_byte_literal_packet() -> None:
    """Length=0 + 1 byte = 1-byte literal run."""
    encoded = bytes([0, 0x42, 128])
    assert _decode(encoded) == b"\x42"


def test_decode_max_length_literal_packet() -> None:
    """Length=127 + 128 bytes = max literal run."""
    payload = bytes(range(128))
    encoded = bytes([127]) + payload + bytes([128])
    assert _decode(encoded) == payload


def test_decode_two_byte_repeat_packet() -> None:
    """Length=255 (0xFF) + 1 byte = 2-copy repeat (257-255=2)."""
    encoded = bytes([255, 0x99, 128])
    assert _decode(encoded) == b"\x99\x99"


def test_decode_max_length_repeat_packet() -> None:
    """Length=129 + 1 byte = 128-copy repeat (257-129=128)."""
    encoded = bytes([129, 0xAB, 128])
    assert _decode(encoded) == b"\xAB" * 128


def test_decode_eod_terminates_immediately() -> None:
    """A leading 128 byte means EOD with no payload — empty output."""
    encoded = bytes([128, 0xFF, 0xFF, 0xFF])  # bytes after EOD ignored
    assert _decode(encoded) == b""


def test_decode_truncated_literal_packet_stops_cleanly() -> None:
    """Length promising more bytes than the stream has — stop where we can.

    PDFBox tolerates the truncation rather than raising.
    """
    encoded = bytes([10, 1, 2, 3])  # promises 11 bytes, gives 3
    # Decoder should not raise; output is what it managed to read.
    assert _decode(encoded) == bytes([1, 2, 3])


def test_decode_truncated_repeat_packet_stops_cleanly() -> None:
    """A 129..255 length byte with no following data byte stops."""
    encoded = bytes([200])  # promised 1 repeat byte, no payload
    assert _decode(encoded) == b""


def test_decode_mixed_packets_round_trip() -> None:
    """Hand-crafted mixed packet stream: literal + repeat + literal + EOD."""
    encoded = bytes([
        2, ord('A'), ord('B'), ord('C'),     # 3-byte literal "ABC"
        253, ord('X'),                        # 4-copy repeat "XXXX"
        0, ord('Y'),                          # 1-byte literal "Y"
        128,                                  # EOD
    ])
    assert _decode(encoded) == b"ABCXXXXY"


def test_encode_decode_round_trip_empty() -> None:
    """Empty input encodes to just an EOD byte."""
    enc = _encode(b"")
    assert enc == bytes([128])
    assert _decode(enc) == b""


def test_encode_decode_round_trip_single_byte() -> None:
    """1-byte input: literal of 1."""
    enc = _encode(b"\x42")
    assert _decode(enc) == b"\x42"
    assert enc[-1] == 128  # ends with EOD


def test_encode_decode_round_trip_128_zeros() -> None:
    """128 identical bytes → one max-length repeat packet."""
    raw = b"\x00" * 128
    enc = _encode(raw)
    assert _decode(enc) == raw


def test_encode_decode_round_trip_129_zeros() -> None:
    """129 identical bytes → must split into two packets."""
    raw = b"\x00" * 129
    enc = _encode(raw)
    assert _decode(enc) == raw


def test_encode_decode_round_trip_128_literal_mixed() -> None:
    """128 distinct bytes → one max-length literal packet."""
    raw = bytes(range(128))
    enc = _encode(raw)
    assert _decode(enc) == raw


def test_encode_decode_round_trip_alternating_pattern() -> None:
    """Alternating bytes — pathological for run-length encoding."""
    raw = bytes([0xAA, 0x55] * 64)
    enc = _encode(raw)
    assert _decode(enc) == raw


def test_decode_ends_on_eof_without_eod_marker() -> None:
    """A stream ending mid-packet (EOF) is treated as a clean stop.

    Matches upstream's leniency: a missing 0x80 marker is non-fatal.
    """
    # Length=5 + 5 bytes + no EOD: should decode the 5 bytes and stop.
    encoded = bytes([4, 1, 2, 3, 4, 5])
    assert _decode(encoded) == bytes([1, 2, 3, 4, 5])
