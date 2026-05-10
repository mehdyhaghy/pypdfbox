"""Ported / parity tests for ``COSFilterInputStream``.

Upstream PDFBox does not ship a dedicated ``COSFilterInputStreamTest`` —
the class is exercised indirectly via signing-end-to-end tests in
``pdfbox-examples`` (which require live PKCS#7 crypto and signed sample
PDFs we don't carry here). The tests below mirror the public Java API
surface defined in
``org.apache.pdfbox.pdmodel.interactive.digitalsignature.COSFilterInputStream``
to keep behavior parity verifiable without those external fixtures.
"""

from __future__ import annotations

from io import BytesIO

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature.cos_filter_input_stream import (
    COSFilterInputStream,
)

PAYLOAD = bytes(range(100))
BYTE_RANGE = [0, 30, 40, 60]
EXPECTED = PAYLOAD[0:30] + PAYLOAD[40:100]


def test_upstream_has_no_dedicated_cos_filter_input_stream_test():
    # Marker — see module docstring. Behavior parity is exercised in this
    # module and the hand-written ``test_cos_filter_input_stream.py``.
    assert True


# --------------------------------------------------------- Java API parity


def test_to_byte_array_mirrors_read_all():
    """Upstream ``toByteArray()`` returns the concatenation of all ranges."""
    stream = COSFilterInputStream(BytesIO(PAYLOAD), BYTE_RANGE)
    assert stream.to_byte_array() == EXPECTED


def test_to_byte_array_with_bytes_input_overload():
    """Mirrors the ``COSFilterInputStream(byte[], int[])`` constructor."""
    stream = COSFilterInputStream(PAYLOAD, BYTE_RANGE)
    assert stream.to_byte_array() == EXPECTED


def test_calculate_ranges_returns_start_end_pairs():
    """Upstream stores ``[start, start + length]`` per range."""
    stream = COSFilterInputStream(PAYLOAD, BYTE_RANGE)
    pairs = stream.calculate_ranges([0, 30, 40, 60])
    assert pairs == [(0, 30), (40, 100)]


def test_calculate_ranges_rejects_odd_length():
    stream = COSFilterInputStream(PAYLOAD, BYTE_RANGE)
    with pytest.raises(ValueError, match="even number"):
        stream.calculate_ranges([0, 10, 20])


def test_get_remaining_tracks_current_range_consumption():
    """``getRemaining()`` shrinks as bytes are pulled from the current range."""
    stream = COSFilterInputStream(PAYLOAD, BYTE_RANGE)
    assert stream.get_remaining() == 30
    stream.read(10)
    assert stream.get_remaining() == 20
    # Drain the rest of range 0; next read primes range 1 (length 60).
    stream.read(20)
    stream.read(1)
    assert stream.get_remaining() == 59


def test_next_range_returns_false_when_exhausted():
    """``nextRange()`` returns ``false`` past the final range."""
    stream = COSFilterInputStream(PAYLOAD, BYTE_RANGE)
    # Two ranges configured; advancing past the last yields False.
    stream.read_all()
    assert stream.next_range() is False


def test_next_range_can_be_driven_manually():
    """``nextRange()`` is the upstream pump; calling it advances the cursor."""
    stream = COSFilterInputStream(PAYLOAD, [0, 5, 10, 5, 20, 5])
    # First range is primed by the constructor.
    assert stream.read(5) == bytes(range(5))
    # Manually advance to range 2.
    assert stream.next_range() is True
    assert stream.read(5) == bytes(range(10, 15))
    assert stream.next_range() is True
    assert stream.read(5) == bytes(range(20, 25))
    assert stream.next_range() is False
