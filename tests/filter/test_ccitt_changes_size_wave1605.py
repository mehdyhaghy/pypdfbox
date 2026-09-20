"""PDFBOX-6243 — charge the CCITT ``changes`` arrays against the cap too.

Wave 1602 ported PDFBOX-6189, which caps the pre-allocated *bitmap*
(``((cols + 7) / 8) * rows``) at 256 MB. That left a hole: the decoder
also builds two ``int`` arrays of ``cols + 2`` entries
(``changesReferenceRow`` / ``changesCurrentRow``), which scale with
``/Columns`` alone. A single-row image with an absurd ``/Columns`` slipped
under the bitmap-only cap while still asking for hundreds of megabytes.
Upstream 3.0.9 adds ``changesSize = (cols + 2) * 4 * 2`` to the compared
total and names both halves in the error message.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.filter.ccitt_fax_decode import _DEFAULT_MAX_DECODE_BYTES
from pypdfbox.filter.ccitt_fax_filter import CCITTFaxFilter
from pypdfbox.filter.filter import Filter

SYSPROP = Filter.SYSPROP_CCITTFAX_MAXBYTES


def _parms(columns: int, rows: int, k: int = 0) -> COSDictionary:
    parms = COSDictionary()
    parms.set_item(COSName.get_pdf_name("K"), COSInteger.get(k))
    parms.set_item(COSName.get_pdf_name("Columns"), COSInteger.get(columns))
    parms.set_item(COSName.get_pdf_name("Rows"), COSInteger.get(rows))
    return parms


def _decode(columns: int, rows: int, encoded: bytes = b"\x00" * 16) -> None:
    CCITTFaxFilter().decode(io.BytesIO(encoded), io.BytesIO(), _parms(columns, rows), 0)


# ---------------------------------------------------------------------------
# the changes-array budget
# ---------------------------------------------------------------------------


def test_single_row_with_absurd_columns_is_rejected() -> None:
    """Bitmap alone is ~12.5 MB — well under the 256 MB cap — but the two
    changes arrays want ~800 MB. PDFBOX-6243 makes this fail."""
    columns, rows = 100_000_000, 1
    bitmap_size = (columns + 7) // 8 * rows
    assert bitmap_size < _DEFAULT_MAX_DECODE_BYTES  # would have passed pre-6243
    with pytest.raises(OSError, match="CCITT decode buffer too large"):
        _decode(columns, rows)


def test_error_message_names_both_allocations() -> None:
    columns, rows = 100_000_000, 1
    bitmap_size = (columns + 7) // 8 * rows
    changes_size = (columns + 2) * 4 * 2
    with pytest.raises(OSError) as exc:
        _decode(columns, rows)
    message = str(exc.value)
    assert f"bitmapSize: {bitmap_size}" in message
    assert f"changesSize: {changes_size}" in message
    assert f"cols={columns}, rows={rows}" in message
    assert f"max allowed={_DEFAULT_MAX_DECODE_BYTES}" in message
    assert SYSPROP in message


def test_sum_is_compared_not_each_half(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neither allocation alone exceeds the cap; their sum does."""
    monkeypatch.setenv(SYSPROP, "85000")
    columns, rows = 10_000, 8
    bitmap_size = (columns + 7) // 8 * rows  # 10_000
    changes_size = (columns + 2) * 4 * 2  # 80_016
    assert bitmap_size < 85_000
    assert changes_size < 85_000
    assert bitmap_size + changes_size > 85_000
    with pytest.raises(OSError, match="CCITT decode buffer too large"):
        _decode(columns, rows)


def test_modest_dimensions_still_decode() -> None:
    """Regression: the tightened budget must not reject ordinary images."""
    out = io.BytesIO()
    CCITTFaxFilter().decode(
        io.BytesIO(b"\x00" * 64), out, _parms(64, 8), 0
    )
    assert len(out.getvalue()) == (64 + 7) // 8 * 8


def test_sysprop_override_still_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    columns, rows = 100_000_000, 1
    with pytest.raises(OSError, match="CCITT decode buffer too large"):
        _decode(columns, rows)
    monkeypatch.setenv(SYSPROP, str(2 * 1024 * 1024 * 1024))
    # Now under the raised cap — decoding proceeds (and simply runs out of
    # encoded data), so no dimension error is raised.
    CCITTFaxFilter().decode(
        io.BytesIO(b""), io.BytesIO(), _parms(1024, 4), 0
    )


# ---------------------------------------------------------------------------
# PDFBOX-6189 guard (wave 1602) still applies first
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("columns", "rows"),
    [(0, 8), (8, 0), (-8, 8), (8, -8), (0, 0)],
    ids=["zero_cols", "zero_rows", "neg_cols", "neg_rows", "both_zero"],
)
def test_non_positive_dimensions_rejected(columns: int, rows: int) -> None:
    with pytest.raises(OSError, match="Invalid CCITT image dimensions"):
        _decode(columns, rows)
