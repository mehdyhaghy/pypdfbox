"""Upstream-ported tests for the abstract :class:`pypdfbox.filter.Filter`.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/filter/TestFilters.java``
on the apache/pdfbox 3.0 branch — the small subset that targets methods
defined on ``Filter`` itself rather than its concrete subclasses.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import ASCIIHexDecode, Filter, FlateDecode


def test_empty_filter_list() -> None:
    """Port of ``TestFilters#testEmptyFilterList``.

    Upstream raises ``IllegalArgumentException`` when given an empty
    filter list; pypdfbox raises :class:`ValueError`, which is the
    standard Python translation of that exception.
    """
    with pytest.raises(ValueError):
        Filter.decode_chain(io.BytesIO(b""), [], COSDictionary(), None, None)


def test_decode_chain_single_filter() -> None:
    """Single-filter chain decodes identically to ``filter.decode`` directly."""
    flate = FlateDecode()
    raw = b"Hello, decode chain!"
    encoded = io.BytesIO()
    flate.encode(io.BytesIO(raw), encoded)
    decoded = Filter.decode_chain(io.BytesIO(encoded.getvalue()), [flate])
    assert decoded.read() == raw


def test_decode_chain_two_filters() -> None:
    """Cascade ``ASCIIHexDecode`` over ``FlateDecode`` per ISO 32000 §7.4.

    Upstream allows chained ``/Filter`` arrays — mimic by hex-encoding
    the deflate payload, then decoding hex first, then flate.
    """
    flate = FlateDecode()
    hex_filter = ASCIIHexDecode()
    raw = b"chain me twice" * 16
    flate_buf = io.BytesIO()
    flate.encode(io.BytesIO(raw), flate_buf)
    hex_buf = io.BytesIO()
    hex_filter.encode(io.BytesIO(flate_buf.getvalue()), hex_buf)
    # Decode order is the inverse of encode order.
    decoded = Filter.decode_chain(io.BytesIO(hex_buf.getvalue()), [hex_filter, flate])
    assert decoded.read() == raw


def test_decode_chain_collects_results() -> None:
    """When ``results`` is provided, one ``DecodeResult`` per filter is appended."""
    flate = FlateDecode()
    encoded = io.BytesIO()
    flate.encode(io.BytesIO(b"abc"), encoded)
    results: list = []
    Filter.decode_chain(
        io.BytesIO(encoded.getvalue()), [flate], COSDictionary(), None, results
    )
    assert len(results) == 1


def test_decode_chain_dedupes_duplicate_filters() -> None:
    """Mirror upstream's HashSet-based dedupe of repeated filter instances."""
    flate = FlateDecode()
    raw = b"deduplicate me"
    encoded = io.BytesIO()
    flate.encode(io.BytesIO(raw), encoded)
    # Same filter listed twice — upstream warns and runs once.
    decoded = Filter.decode_chain(io.BytesIO(encoded.getvalue()), [flate, flate])
    assert decoded.read() == raw
