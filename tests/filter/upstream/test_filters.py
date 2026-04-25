"""Tests ported from PDFBox 3.0 ``TestFilters`` (filter round-trip suite).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/filter/TestFilters.java``
on the apache/pdfbox 3.0 branch. Only the ASCII85 and RunLength portions
are ported here; the other filters live in their own cluster's upstream
test files as they are added.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.filter import Filter, FilterFactory


def _encode_decode(filter_: Filter, payload: bytes) -> bytes:
    """Mirror of ``TestFilters#checkEncodeDecode``: encode then decode."""
    encoded = io.BytesIO()
    filter_.encode(io.BytesIO(payload), encoded)
    decoded = io.BytesIO()
    filter_.decode(io.BytesIO(encoded.getvalue()), decoded)
    return decoded.getvalue()


@pytest.mark.parametrize(
    "payload",
    [
        bytes(0),  # input0
        bytes([1, 2, 3, 4, 5, 128, 140, 180, 0xFF]),  # input1
        bytes(10),  # input2
        bytes(128),  # input3
        bytes(129),  # input4
        bytes(128 + 128),  # input5
        bytes(1),  # input6
        bytes([1, 2]),  # input7
        bytes(2),  # input8
    ],
    ids=[
        "empty",
        "mixed-9bytes",
        "ten-zeros",
        "128-zeros",
        "129-zeros",
        "256-zeros",
        "one-zero",
        "1-2",
        "two-zeros",
    ],
)
def test_rle(payload: bytes) -> None:
    """Port of ``TestFilters#testRLE``."""
    rle = FilterFactory.get("RunLengthDecode")
    assert _encode_decode(rle, payload) == payload


@pytest.mark.parametrize(
    "payload",
    [
        bytes(0),
        b"a",
        b"ab",
        b"abc",
        b"abcd",
        b"abcde",
        bytes(4),  # exercises the 'z' shortcut
        bytes(8),  # exercises consecutive 'z' shortcuts
        bytes((i * 251 + 7) % 256 for i in range(10_000)),
    ],
    ids=["empty", "1byte", "2byte", "3byte", "4byte", "5byte", "4-zeros", "8-zeros", "10k-mixed"],
)
def test_ascii85(payload: bytes) -> None:
    """ASCII85 round-trip; covers the same surface ``TestFilters#testFilters``
    randomly hits (sizes 0..N including those that exercise the 4-byte group
    boundary and the b'z' shortcut)."""
    a85 = FilterFactory.get("ASCII85Decode")
    assert _encode_decode(a85, payload) == payload
