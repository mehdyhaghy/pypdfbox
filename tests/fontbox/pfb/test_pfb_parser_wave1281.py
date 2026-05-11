"""Tests for ``pypdfbox.fontbox.pfb.PfbParser``."""

from __future__ import annotations

import io

import pytest

from pypdfbox.fontbox.pfb.pfb_parser import PfbParser


def _make_record(record_type: int, payload: bytes) -> bytes:
    size = len(payload)
    header = bytes(
        [
            0x80,
            record_type,
            size & 0xFF,
            (size >> 8) & 0xFF,
            (size >> 16) & 0xFF,
            (size >> 24) & 0xFF,
        ]
    )
    return header + payload


def _build_pfb(ascii_body: bytes, binary_body: bytes, tail: bytes | None = None) -> bytes:
    blocks = b"".join(
        [
            _make_record(0x01, ascii_body),
            _make_record(0x02, binary_body),
        ]
    )
    if tail is not None:
        blocks += _make_record(0x01, tail)
    blocks += bytes([0x80, 0x03])
    return blocks


def test_pfb_parser_round_trip() -> None:
    ascii_body = b"%!PS-AdobeFont\n"
    binary_body = b"\x01\x02\x03\x04\x05"
    blob = _build_pfb(ascii_body, binary_body, tail=b"cleartomark\n")
    parser = PfbParser(blob)
    lengths = parser.get_lengths()
    assert lengths[0] == len(ascii_body)
    assert lengths[1] == len(binary_body)
    assert lengths[2] == len(b"cleartomark\n")
    assert parser.get_segment1() == ascii_body
    assert parser.get_segment2() == binary_body


def test_pfb_parser_input_stream_replays_data() -> None:
    blob = _build_pfb(b"hello\n", b"\xff\xfe", tail=b"cleartomark\n")
    parser = PfbParser(io.BytesIO(blob))
    assert parser.size() > 0
    stream = parser.get_input_stream()
    assert stream.read() == parser.get_pfbdata()


def test_pfb_parser_rejects_invalid_marker() -> None:
    with pytest.raises(OSError):
        PfbParser(b"\x00" * 32)


def test_pfb_parser_rejects_short_input() -> None:
    with pytest.raises(OSError):
        PfbParser(b"\x80")
