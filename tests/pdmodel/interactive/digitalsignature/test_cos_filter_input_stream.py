from __future__ import annotations

import hashlib
from io import BytesIO

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature.cos_filter_input_stream import (
    COSFilterInputStream,
)

# A simulated signed-PDF buffer: 100 bytes, with a 10-byte placeholder
# that /Contents would occupy, bracketed by two ranges.
PAYLOAD = bytes(range(100))
# /ByteRange = [0, 30, 40, 60] — covers bytes 0..29 then 40..99, skipping
# the 10-byte /Contents placeholder at 30..39.
BYTE_RANGE = [0, 30, 40, 60]
EXPECTED = PAYLOAD[0:30] + PAYLOAD[40:100]


# --------------------------------------------------------------- basic reads


def test_read_all_yields_concatenation_of_ranges():
    stream = COSFilterInputStream(BytesIO(PAYLOAD), BYTE_RANGE)
    assert stream.read_all() == EXPECTED


def test_read_minus_one_reads_to_end():
    stream = COSFilterInputStream(BytesIO(PAYLOAD), BYTE_RANGE)
    assert stream.read(-1) == EXPECTED


def test_read_in_small_chunks_matches_full_read():
    stream = COSFilterInputStream(BytesIO(PAYLOAD), BYTE_RANGE)
    out = bytearray()
    while True:
        chunk = stream.read(7)
        if not chunk:
            break
        out.extend(chunk)
    assert bytes(out) == EXPECTED


def test_accepts_bytes_source_directly():
    stream = COSFilterInputStream(PAYLOAD, BYTE_RANGE)
    assert stream.read_all() == EXPECTED


def test_accepts_bytearray_source():
    stream = COSFilterInputStream(bytearray(PAYLOAD), BYTE_RANGE)
    assert stream.read_all() == EXPECTED


# --------------------------------------------------------- input variations


def test_accepts_nested_pair_byte_range():
    stream = COSFilterInputStream(PAYLOAD, [(0, 30), (40, 60)])
    assert stream.read_all() == EXPECTED


def test_unsorted_flat_range_is_normalised():
    # Same total ranges, different order — should yield same bytes.
    stream = COSFilterInputStream(PAYLOAD, [40, 60, 0, 30])
    assert stream.read_all() == EXPECTED


def test_empty_byte_range_yields_no_bytes():
    stream = COSFilterInputStream(PAYLOAD, [])
    assert stream.read_all() == b""
    assert stream.read(10) == b""


def test_zero_length_segments_skipped():
    stream = COSFilterInputStream(PAYLOAD, [0, 0, 0, 30, 40, 60])
    assert stream.read_all() == EXPECTED


def test_range_extending_past_eof_stops_at_eof():
    # Source is 50 bytes, we ask for [0, 20, 30, 9999].
    src = bytes(range(50))
    stream = COSFilterInputStream(src, [0, 20, 30, 9999])
    assert stream.read_all() == src[:20] + src[30:50]


# --------------------------------------------------------------- error cases


def test_odd_flat_range_rejected():
    with pytest.raises(ValueError, match="even number"):
        COSFilterInputStream(PAYLOAD, [0, 30, 40])


def test_negative_start_rejected():
    with pytest.raises(ValueError, match="negative start"):
        COSFilterInputStream(PAYLOAD, [-1, 30, 40, 60])


def test_negative_length_rejected():
    with pytest.raises(ValueError, match="negative length"):
        COSFilterInputStream(PAYLOAD, [0, -30, 40, 60])


def test_nested_entry_wrong_arity_rejected():
    with pytest.raises(ValueError, match="pairs"):
        COSFilterInputStream(PAYLOAD, [(0, 30, 40)])


def test_read_after_close_raises():
    stream = COSFilterInputStream(PAYLOAD, BYTE_RANGE)
    stream.close()
    with pytest.raises(ValueError, match="closed"):
        stream.read(1)


def test_read_zero_returns_empty():
    stream = COSFilterInputStream(PAYLOAD, BYTE_RANGE)
    assert stream.read(0) == b""


# ----------------------------------------------------- digest / context-mgr


def test_concatenated_bytes_match_expected_sha256():
    """Full digest reproduction — what a verifier would compute."""
    stream = COSFilterInputStream(PAYLOAD, BYTE_RANGE)
    h = hashlib.sha256()
    while True:
        chunk = stream.read(8)
        if not chunk:
            break
        h.update(chunk)
    assert h.hexdigest() == hashlib.sha256(EXPECTED).hexdigest()


def test_context_manager_closes_stream():
    with COSFilterInputStream(PAYLOAD, BYTE_RANGE) as stream:
        assert stream.read_all() == EXPECTED
    with pytest.raises(ValueError, match="closed"):
        stream.read(1)


def test_readable_writable_seekable_flags():
    stream = COSFilterInputStream(PAYLOAD, BYTE_RANGE)
    assert stream.readable()
    assert not stream.writable()
    assert not stream.seekable()
    stream.close()
    assert not stream.readable()


def test_non_seekable_source_uses_read_and_discard():
    """Non-seekable stream wrapper — proves the skip fallback works."""

    class NonSeekable:
        def __init__(self, data: bytes) -> None:
            self._buf = BytesIO(data)
            self.closed = False

        def read(self, n: int = -1) -> bytes:
            return self._buf.read(n)

        def close(self) -> None:
            self.closed = True

    src = NonSeekable(PAYLOAD)
    stream = COSFilterInputStream(src, BYTE_RANGE)
    assert stream.read_all() == EXPECTED
    stream.close()
    assert src.closed


def test_two_separate_streams_are_independent():
    s1 = COSFilterInputStream(PAYLOAD, BYTE_RANGE)
    s2 = COSFilterInputStream(PAYLOAD, BYTE_RANGE)
    s1.read(10)
    assert s2.read_all() == EXPECTED
