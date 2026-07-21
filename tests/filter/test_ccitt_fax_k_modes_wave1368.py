"""Wave 1368 (agent D) — CCITTFaxDecode /K negative / zero / positive parity.

ISO 32000-1 §7.4.9 distinguishes three CCITT modes via the ``/K`` parameter:

* ``K = 0``: pure Group 3 1D (T.4 1D-only encoding).
* ``K > 0``: mixed Group 3 2D (T.4 with 2D-coding bit set).
* ``K < 0``: Group 4 (T.6).

These tests round-trip a bitmap through each mode via the Pillow-libtiff
bridge in :class:`CCITTFaxDecode`. The bitmap geometry is small enough
to keep the test deterministic across libtiff versions, and we avoid
asserting on the encoded length (libtiff implementations vary).

NOTE: post-EOD libtiff byte-padding differs between POSIX and Windows
wheels — we never assert on bytes past the declared row*rows footprint.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import CCITTFaxDecode


def _params(*, k: int, columns: int, rows: int,
            black_is_1: bool = False) -> COSDictionary:
    p = COSDictionary()
    p.set_int("K", k)
    p.set_int("Columns", columns)
    p.set_int("Rows", rows)
    if black_is_1:
        p.set_boolean("BlackIs1", True)
    return p


def _make_bitmap(columns: int, rows: int, fill_pattern: bytes) -> bytes:
    """Build a packed 1-bit bitmap with the given pattern repeated per row."""
    row_bytes = (columns + 7) // 8
    assert len(fill_pattern) == row_bytes
    return fill_pattern * rows


def test_ccitt_k_negative_group4_round_trip() -> None:
    """K < 0 selects Group 4 (T.6). Round-trip a small striped bitmap."""
    columns = 32
    rows = 8
    # Alternating horizontal stripes (each row = 0xF0 0xF0 0xF0 0xF0).
    raw = _make_bitmap(columns, rows, b"\xF0\xF0\xF0\xF0")
    f = CCITTFaxDecode()
    params = _params(k=-1, columns=columns, rows=rows)
    enc_buf = io.BytesIO()
    f.encode(io.BytesIO(raw), enc_buf, params)
    encoded = enc_buf.getvalue()
    assert encoded, "Group 4 encode must produce non-empty output"

    dec_buf = io.BytesIO()
    f.decode(io.BytesIO(encoded), dec_buf, params, 0)
    decoded = dec_buf.getvalue()
    # libtiff may produce extra trailing bytes after the declared footprint;
    # only compare the declared row*rows footprint.
    row_bytes = (columns + 7) // 8
    assert decoded[: rows * row_bytes] == raw


def test_ccitt_k_zero_group3_1d_round_trip() -> None:
    """K == 0 selects pure Group 3 1D."""
    columns = 24
    rows = 6
    raw = _make_bitmap(columns, rows, b"\xAA\xAA\xAA")
    f = CCITTFaxDecode()
    params = _params(k=0, columns=columns, rows=rows)
    enc_buf = io.BytesIO()
    f.encode(io.BytesIO(raw), enc_buf, params)
    encoded = enc_buf.getvalue()
    assert encoded

    dec_buf = io.BytesIO()
    f.decode(io.BytesIO(encoded), dec_buf, params, 0)
    decoded = dec_buf.getvalue()
    row_bytes = (columns + 7) // 8
    assert decoded[: rows * row_bytes] == raw


def test_ccitt_k_positive_group3_2d_round_trip() -> None:
    """K > 0 selects mixed Group 3 2D."""
    columns = 24
    rows = 6
    raw = _make_bitmap(columns, rows, b"\xCC\xCC\xCC")
    f = CCITTFaxDecode()
    params = _params(k=4, columns=columns, rows=rows)
    enc_buf = io.BytesIO()
    f.encode(io.BytesIO(raw), enc_buf, params)
    encoded = enc_buf.getvalue()
    assert encoded

    dec_buf = io.BytesIO()
    f.decode(io.BytesIO(encoded), dec_buf, params, 0)
    decoded = dec_buf.getvalue()
    row_bytes = (columns + 7) // 8
    assert decoded[: rows * row_bytes] == raw


def test_ccitt_black_is_1_polarity_flip_round_trip() -> None:
    """/BlackIs1 inverts polarity; round-trip preserves raw bits."""
    columns = 16
    rows = 4
    raw = _make_bitmap(columns, rows, b"\x33\xCC")
    f = CCITTFaxDecode()
    params = _params(k=-1, columns=columns, rows=rows, black_is_1=True)
    enc_buf = io.BytesIO()
    f.encode(io.BytesIO(raw), enc_buf, params)
    dec_buf = io.BytesIO()
    f.decode(io.BytesIO(enc_buf.getvalue()), dec_buf, params, 0)
    decoded = dec_buf.getvalue()
    row_bytes = (columns + 7) // 8
    assert decoded[: rows * row_bytes] == raw


def test_ccitt_columns_default_is_1728() -> None:
    """When /Columns is omitted the decoder uses 1728 (PDF default).

    With no /Rows and no /Height the reconciled row count is 0, which
    PDFBOX-6189 (3.0.8) rejects up front — the error message carries the
    resolved dimensions, proving /Columns defaulted to 1728.
    """
    f = CCITTFaxDecode()
    # /Columns missing → default 1728 inside the filter.
    params = COSDictionary()
    params.set_int("K", -1)
    with pytest.raises(OSError, match=r"cols=1728, rows=0"):
        f.decode(io.BytesIO(b""), io.BytesIO(), params, 0)


def test_ccitt_encode_rejects_zero_columns() -> None:
    """Encode requires /Columns > 0."""
    f = CCITTFaxDecode()
    params = COSDictionary()
    params.set_int("K", -1)
    params.set_int("Columns", 0)
    params.set_int("Rows", 4)
    try:
        f.encode(io.BytesIO(b"\x00" * 4), io.BytesIO(), params)
    except OSError as exc:
        assert "Columns" in str(exc)
    else:
        raise AssertionError("expected OSError on /Columns=0")


def test_ccitt_encode_rejects_zero_rows() -> None:
    """Encode requires /Rows > 0 (unlike decode, which can discover rows)."""
    f = CCITTFaxDecode()
    params = COSDictionary()
    params.set_int("K", -1)
    params.set_int("Columns", 16)
    params.set_int("Rows", 0)
    try:
        f.encode(io.BytesIO(b"\x00" * 4), io.BytesIO(), params)
    except OSError as exc:
        assert "Rows" in str(exc)
    else:
        raise AssertionError("expected OSError on /Rows=0")


def test_ccitt_decode_rejects_negative_columns() -> None:
    """Decode rejects /Columns <= 0 (PDFBOX-6189, upstream message shape)."""
    f = CCITTFaxDecode()
    params = COSDictionary()
    params.set_int("K", -1)
    params.set_int("Columns", -1)
    params.set_int("Rows", 4)
    try:
        f.decode(io.BytesIO(b"\x00\x01\x02"), io.BytesIO(), params, 0)
    except OSError as exc:
        assert "Invalid CCITT image dimensions: cols=-1, rows=4" in str(exc)
    else:
        raise AssertionError("expected OSError on /Columns=-1")
