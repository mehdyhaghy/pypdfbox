"""Wave 1369 — PFB three-segment framing parity tests.

Adobe Printer Font Binary (PFB) wraps a Type 1 PostScript font in three
record-typed segments:

* segment 1 (record type 0x01) — ASCII PostScript header up to ``eexec``;
* segment 2 (record type 0x02) — raw eexec ciphertext;
* segment 3 (record type 0x01) — final ASCII tail containing
  ``cleartomark`` and the trailing zero-padding.

Each record carries a 6-byte header: ``80 <type> <len:4 LE>`` followed
by the payload. The file is terminated with ``80 03``.

These tests verify the segmenter's three-segment split, the
length-field round-trip, and the cleartomark heuristic that excludes
the trailing ASCII record from segment 1.
"""
from __future__ import annotations

import io

import pytest

from pypdfbox.fontbox.pfb.pfb_parser import PfbParser

# ---------- record builder ----------


def _record(record_type: int, payload: bytes) -> bytes:
    """Wrap ``payload`` in one PFB record header."""
    n = len(payload)
    header = bytes(
        [0x80, record_type, n & 0xFF, (n >> 8) & 0xFF, (n >> 16) & 0xFF, (n >> 24) & 0xFF]
    )
    return header + payload


def _eof() -> bytes:
    return bytes([0x80, 0x03])


def _build_pfb(seg1: bytes, seg2: bytes, seg3: bytes) -> bytes:
    return _record(0x01, seg1) + _record(0x02, seg2) + _record(0x01, seg3) + _eof()


# ---------- happy-path three-segment split ----------


def test_pfb_three_segment_split() -> None:
    seg1 = b"%!PS-AdobeFont-1.0: Foo 001.000\n... header ...\ncurrentfile eexec\n"
    seg2 = bytes(range(64))  # arbitrary 64-byte ciphertext
    seg3 = (b"0" * 64) + b"\ncleartomark\n"
    pfb = _build_pfb(seg1, seg2, seg3)

    parser = PfbParser(pfb)
    lengths = parser.get_lengths()
    assert lengths[0] == len(seg1)
    assert lengths[1] == len(seg2)
    assert lengths[2] == len(seg3)

    # Segment slices reconstruct exactly.
    assert parser.get_segment1() == seg1
    assert parser.get_segment2() == seg2
    data = parser.get_pfbdata()
    assert data[lengths[0]:lengths[0] + lengths[1]] == seg2
    assert data[lengths[0] + lengths[1]:] == seg3


def test_pfb_size_matches_sum_of_segments() -> None:
    seg1 = b"%!PS\n"
    seg2 = b"\x01\x02\x03\x04\x05"
    seg3 = b"\ncleartomark\n"
    parser = PfbParser(_build_pfb(seg1, seg2, seg3))
    assert parser.size() == len(seg1) + len(seg2) + len(seg3)


# ---------- length-field round-trip ----------


@pytest.mark.parametrize(
    "size",
    [0, 1, 255, 256, 65535, 65536, 1_000_000],
    ids=["zero", "one", "u8_max", "u8_max_plus_1", "u16_max", "u16_max_plus_1", "1M"],
)
def test_pfb_length_field_round_trip(size: int) -> None:
    # The 4-byte little-endian length encoding must round-trip cleanly
    # for any 32-bit unsigned value. We only test sane sizes (under 8 MB)
    # to keep the test fast.
    seg1 = b"%!PS\n"
    seg2 = b"\xaa" * size
    seg3 = b"\ncleartomark\n"
    parser = PfbParser(_build_pfb(seg1, seg2, seg3))
    assert parser.get_lengths()[1] == size
    assert parser.get_segment2() == seg2


# ---------- cleartomark heuristic ----------


def test_trailing_ascii_with_cleartomark_excluded_from_segment1() -> None:
    # When the final ASCII record contains ``cleartomark`` and is short,
    # the parser must keep it as segment 3, not append it to segment 1.
    seg1 = b"%!PS\nheader-only\n"
    seg2 = b"binary-body"
    seg3 = b"0000000000\ncleartomark\n"
    parser = PfbParser(_build_pfb(seg1, seg2, seg3))
    assert parser.get_segment1() == seg1
    assert parser.get_lengths()[2] == len(seg3)


def test_long_trailing_ascii_with_cleartomark_falls_back_into_segment1() -> None:
    # If the final ASCII record is >= 600 bytes the cleartomark
    # heuristic does NOT exclude it — upstream falls back to including
    # it in segment 1. This is the documented PfbParser behaviour.
    big_trailer = b"x" * 700 + b"\ncleartomark\n"
    seg1 = b"%!PS\nheader\n"
    seg2 = b"body"
    parser = PfbParser(
        _record(0x01, seg1) + _record(0x02, seg2) + _record(0x01, big_trailer) + _eof()
    )
    # Segment 1 length now includes the big trailer.
    assert parser.get_lengths()[0] == len(seg1) + len(big_trailer)
    # And there is no separate segment 3.
    assert parser.get_lengths()[2] == 0


# ---------- file-like / bytes / bytearray inputs ----------


def test_pfb_accepts_binary_stream() -> None:
    pfb = _build_pfb(b"%!PS\n", b"data", b"\ncleartomark\n")
    parser = PfbParser(io.BytesIO(pfb))
    assert parser.get_segment2() == b"data"


def test_pfb_accepts_bytearray() -> None:
    pfb = _build_pfb(b"%!PS\n", b"data", b"\ncleartomark\n")
    parser = PfbParser(bytearray(pfb))
    assert parser.get_segment2() == b"data"


# ---------- error path ----------


def test_pfb_short_header_raises() -> None:
    # Anything shorter than 18 bytes is rejected as "header missing".
    with pytest.raises(OSError, match="header missing"):
        PfbParser(b"\x80\x01\x00\x00")


def test_pfb_wrong_start_marker_raises() -> None:
    # First byte must be 0x80 — any other value is rejected.
    body = bytes([0x7F, 0x01]) + b"x" * 16
    with pytest.raises(OSError, match="Start marker missing"):
        PfbParser(body)


# ---------- multi-record per type (upstream concatenates) ----------


def test_pfb_multiple_ascii_records_concatenate() -> None:
    # A PFB may legitimately split a long header into several ASCII
    # records. The parser concatenates them in order.
    pfb = (
        _record(0x01, b"%!PS\n")
        + _record(0x01, b"more-header\n")
        + _record(0x02, b"body")
        + _record(0x01, b"\ncleartomark\n")
        + _eof()
    )
    parser = PfbParser(pfb)
    assert parser.get_segment1() == b"%!PS\nmore-header\n"
    assert parser.get_segment2() == b"body"
