"""Live PDFBox differential parity for CCITTFaxDecode's /Rows-vs-/Height
reconciliation — BYTE-EXACT.

``test_ccitt_oracle.py`` proves the decoded scanline buffer matches Apache
PDFBox 3.0.7 byte-for-byte across every ``/K`` mode and ``/BlackIs1`` polarity,
but it always pins ``/Height == /Rows`` so the buffer size is deterministic.
That left the *reconciliation* itself unpinned: an image XObject carries its
authoritative scanline count in ``/Height`` (alias ``/H``) on the stream dict,
while ``/Rows`` lives in ``/DecodeParms`` and is optional. Apache PDFBox's
``CCITTFaxFilter.decode`` reconciles the two EXACTLY as::

    if (rows > 0 && height > 0) rows = height;     // /Height wins outright
    else                        rows = max(rows, height);

i.e. when BOTH are present the stream-dict ``/Height`` *overrides* ``/Rows``
even when ``/Rows`` is the larger value (it is NOT a plain ``max``); when only
one is present the non-zero one is used. This suite drives PDFBox to decode the
real Group 4 fixture with ``/Rows`` and ``/Height`` set INDEPENDENTLY (smaller,
larger, equal, each omitted) via ``oracle/probes/CcittRowsProbe.java`` and
asserts pypdfbox's decoded body is byte-identical.

Root cause this pins (fixed wave 1471): pypdfbox previously read ``/Rows`` from
``/DecodeParms`` only and never consulted the stream-dict ``/Height``, so when
``/Rows`` was absent it under-sized the decoded buffer (its row-count estimate
could undershoot the real height), and when ``/Rows`` and ``/Height`` were both
present but unequal it used the wrong one. The fix applies PDFBox's exact
``if both -> height else max`` reconciliation against the stream-dict ``/Height``.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import tempfile
from pathlib import Path

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import CCITTFaxDecode
from tests.oracle.harness import requires_oracle, run_probe

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "filter"

# Geometry of the upstream Group 4 CCITT fixture (W=344, H=287).
_COLS = 344
_NATURAL_ROWS = 287


def _stream_dict(
    *, k: int, columns: int, rows: int, height: int, black_is_1: bool = False
) -> COSDictionary:
    """Mirror a real image XObject: /DecodeParms nested under the stream dict
    (carrying /K /Columns and optionally /Rows), with /Height on the stream
    dict itself. ``rows``/``height`` of 0 mean "omit that key"."""
    parms = COSDictionary()
    parms.set_int("K", k)
    parms.set_int("Columns", columns)
    if rows > 0:
        parms.set_int("Rows", rows)
    if black_is_1:
        parms.set_boolean("BlackIs1", True)
    stream = COSDictionary()
    stream.set_item("DecodeParms", parms)
    stream.set_int("Width", columns)
    if height > 0:
        stream.set_int("Height", height)
    return stream


def _py_decode(encoded: bytes, stream: COSDictionary) -> bytes:
    out = io.BytesIO()
    CCITTFaxDecode().decode(io.BytesIO(encoded), out, stream, 0)
    return out.getvalue()


def _java_args(
    *, k: int, columns: int, rows: int, height: int, black_is_1: bool = False
) -> str:
    parts = [f"K={k}", f"Columns={columns}", f"Rows={rows}", f"Height={height}"]
    if black_is_1:
        parts.append("BlackIs1=1")
    return ",".join(parts)


def _java_decode(encoded: bytes, args: str) -> bytes:
    fd, tmp = tempfile.mkstemp(suffix=".ccitt")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(encoded)
        return run_probe("CcittRowsProbe", tmp, args)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)


def _assert_byte_exact(
    encoded: bytes,
    *,
    k: int,
    columns: int,
    rows: int,
    height: int,
    black_is_1: bool = False,
) -> None:
    stream = _stream_dict(
        k=k, columns=columns, rows=rows, height=height, black_is_1=black_is_1
    )
    py = _py_decode(encoded, stream)
    java = _java_decode(
        encoded,
        _java_args(
            k=k, columns=columns, rows=rows, height=height, black_is_1=black_is_1
        ),
    )
    assert py == java, (
        "CCITT /Rows-vs-/Height reconciliation diverged from PDFBox "
        f"(rows={rows}, height={height}):\n"
        f"  py   len={len(py)} sha={hashlib.sha256(py).hexdigest()}\n"
        f"  java len={len(java)} sha={hashlib.sha256(java).hexdigest()}"
    )
    # Effective row count mirrors PDFBox CCITTFaxFilter.decode:
    #   both set  -> /Height wins outright (NOT a plain max);
    #   one set   -> the non-zero one.
    # Confirm the decoded buffer is the exact fixed footprint PDFBox allocates.
    effective = height if (rows > 0 and height > 0) else max(rows, height)
    assert len(py) == effective * ((columns + 7) // 8)


@requires_oracle
def test_rows_omitted_uses_height() -> None:
    """/Rows absent in /DecodeParms — PDFBox falls back to the stream-dict
    /Height; pypdfbox must too (rows = max(0, height) = height)."""
    encoded = (_FIXTURES / "ccittg4.ccitt").read_bytes()
    _assert_byte_exact(encoded, k=-1, columns=_COLS, rows=0, height=_NATURAL_ROWS)


@requires_oracle
def test_rows_equals_height() -> None:
    """Baseline: /Rows == /Height (the max() is a no-op)."""
    encoded = (_FIXTURES / "ccittg4.ccitt").read_bytes()
    _assert_byte_exact(
        encoded, k=-1, columns=_COLS, rows=_NATURAL_ROWS, height=_NATURAL_ROWS
    )


@requires_oracle
def test_rows_smaller_than_height_widens_to_height() -> None:
    """/Rows (100) < /Height (287), BOTH set — /Height wins, so the buffer is
    the full image height and decoded rows beyond /Rows are still emitted."""
    encoded = (_FIXTURES / "ccittg4.ccitt").read_bytes()
    _assert_byte_exact(encoded, k=-1, columns=_COLS, rows=100, height=_NATURAL_ROWS)


@requires_oracle
def test_rows_larger_than_height_height_wins() -> None:
    """/Rows (400) > /Height (287), BOTH set — PDFBox does NOT take the max:
    when both are present /Height overrides /Rows outright, so the effective
    count is 287, not 400. This is the subtle facet the plain-max reading
    would get wrong."""
    encoded = (_FIXTURES / "ccittg4.ccitt").read_bytes()
    _assert_byte_exact(encoded, k=-1, columns=_COLS, rows=400, height=_NATURAL_ROWS)


# NOTE: an over-long count (e.g. /Rows 400 with /Height omitted, so the
# effective rows exceeds the encoded image's ~287 natural rows) is deliberately
# NOT pinned byte-exact here. PDFBox white-pads the post-EOD tail
# deterministically, but pypdfbox's libtiff backend leaves the bytes past
# end-of-data UNINITIALISED on some platforms/wheels (the documented
# "libtiff / Pillow byte-padding" cross-platform hazard — never assert on the
# post-EOD tail). The reconciliation RULE itself is fully pinned by the cases
# above/below where the effective count stays within the encoded image.


@requires_oracle
def test_height_omitted_uses_rows() -> None:
    """/Height absent — PDFBox uses /Rows alone (max(rows, 0) = rows)."""
    encoded = (_FIXTURES / "ccittg4.ccitt").read_bytes()
    _assert_byte_exact(encoded, k=-1, columns=_COLS, rows=_NATURAL_ROWS, height=0)


@requires_oracle
def test_rows_smaller_height_blackis1_polarity() -> None:
    """/Rows < /Height with /BlackIs1 true — exercises the widening reconcile
    on the inverted-polarity decode path."""
    encoded = (_FIXTURES / "ccittg4.ccitt").read_bytes()
    _assert_byte_exact(
        encoded, k=-1, columns=_COLS, rows=50, height=_NATURAL_ROWS, black_is_1=True
    )
