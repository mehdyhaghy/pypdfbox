"""Wave 1483 (agent L) — CCITTFaxDecode ``/K == 0`` compression-type sniffing
parity with Apache PDFBox 3.0.7.

Apache PDFBox's ``CCITTFaxFilter.decode`` does NOT blindly treat every ``K == 0``
stream as Group 3 1-D (T.4). When ``/EndOfLine`` is absent from ``/DecodeParms``
it sniffs the first 20 bytes for a leading end-of-line code (``0b000000000001``):

    type = COMPRESSION_CCITT_T4;                 // assume Group 3 1-D
    if (streamData[0] != 0 || (streamData[1] >> 4 != 1 && streamData[1] != 1)) {
        // no leading EOL -> search further, else fall back to MH-RLE
        type = COMPRESSION_CCITT_MODIFIED_HUFFMAN_RLE;
        ...scan bits 12.. for an embedded EOL; if found -> T.4...
    }

So a stream with a leading EOL decodes as T.4, while one with no EOL anywhere
falls back to *Modified Huffman RLE* (TIFF compression 2). pypdfbox's
``CCITTFaxDecode`` decodes ``K == 0`` exclusively as T.4 (compression 3) through
libtiff. These tests pin — against the live oracle when present, and against
oracle-confirmed literal bytes otherwise — that both forms decode byte-exact
anyway:

* a real leading-EOL Group 3 fixture (``ccittg3.ccitt``) decoded with ``K == 0``
  and NO ``/EndOfLine`` (exercising the sniff -> T.4 arm), and
* a pure Modified-Huffman-RLE strip with no EOL anywhere (exercising the
  sniff -> RLE arm in PDFBox; libtiff's T.4 path decodes the identical
  Huffman run codes for a per-row-constant pattern).

The byte vectors below were captured from Apache PDFBox 3.0.7's
``CCITTFaxFilter.decode`` via ``oracle/probes/CcittDecodeProbe.java`` (see the
``@requires_oracle`` differential variants), so the non-oracle assertions are a
true cross-implementation parity pin, not a self-consistency check.

Cross-platform note: we only assert on the declared
``rows * rowBytes`` footprint — never on libtiff's post-EOD padding tail, which
differs between POSIX and Windows wheels.

upstream: PDFBox 3.0.7 ``filter/CCITTFaxFilter.java`` (``decode``, K==0 arm).
"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import CCITTFaxDecode
from tests.oracle.harness import requires_oracle, run_probe

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "filter"

# Geometry of the real upstream Group 3 fixture (W=344, H=287).
_G3_COLS = 344
_G3_ROWS = 287

# ---------------------------------------------------------------------------
# Pure Modified-Huffman-RLE strip: 24x6 buffer over a per-row 0xAA55AA bitmap
# (after the default /BlackIs1=false inversion). Encoded by libtiff as TIFF
# compression 2 (MH-RLE) — note NO leading EOL: byte0 = 0x1d != 0, so PDFBox's
# sniff falls back to the MH-RLE decode path. The bytes are a fixed test vector,
# not re-encoded at test time, so the test pins the *decoder* (production code)
# against a frozen input rather than depending on libtiff's encoder output.
#
# Both decoders recover the first 3 scanlines of data and then run out of strip,
# so the fixed rows*rowBytes buffer is white-padded (0xFF for /BlackIs1=false)
# for the remaining rows — pypdfbox (libtiff T.4) and PDFBox (MH-RLE) agree on
# BOTH the decoded data and the padded tail. The padding here is part of the
# *declared* rows*rowBytes footprint (PDFBox's own pre-allocated buffer), NOT
# libtiff's nondeterministic post-EOD overrun, so it is safe to assert on.
# ---------------------------------------------------------------------------
_MHRLE_COLS = 24
_MHRLE_ROWS = 6
_MHRLE_STRIP = bytes.fromhex(
    "1d0e8743e3a1d0e9d0e8743a1d0e8743e3a1d0e9d0e8743a"
    "1d0e8743e3a1d0e9d0e8743a"
)
# Oracle-confirmed decoded scanlines (default /BlackIs1=false): 3 data rows
# (0xAA55AA each) + 3 white-padded rows (0xFFFFFF each).
_MHRLE_DECODED = bytes.fromhex("aa55aaaa55aaaa55aaffffffffffffffffff")


def _params(*, k: int, columns: int, rows: int, **flags: bool) -> COSDictionary:
    p = COSDictionary()
    p.set_int("K", k)
    p.set_int("Columns", columns)
    p.set_int("Rows", rows)
    for key, val in flags.items():
        if val:
            p.set_boolean(key, True)
    return p


def _py_decode(encoded: bytes, params: COSDictionary, columns: int, rows: int) -> bytes:
    out = io.BytesIO()
    CCITTFaxDecode().decode(io.BytesIO(encoded), out, params, 0)
    row_bytes = (columns + 7) // 8
    return out.getvalue()[: rows * row_bytes]


def _java_decode(encoded: bytes, args: str) -> bytes:
    fd, tmp = tempfile.mkstemp(suffix=".ccitt")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(encoded)
        return run_probe("CcittDecodeProbe", tmp, args)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# Modified-Huffman-RLE (no EOL) — PDFBox sniffs -> RLE; pypdfbox uses T.4.
# ---------------------------------------------------------------------------


def test_mhrle_no_eol_k0_decode_matches_pinned_bytes() -> None:
    """A no-leading-EOL MH-RLE strip decodes byte-exact under ``K == 0``.

    PDFBox routes this through the Modified-Huffman-RLE decoder; pypdfbox's
    libtiff T.4 path yields the identical scanlines for this per-row-constant
    bitmap. Pinned to oracle-captured bytes — passes without the oracle."""
    params = _params(k=0, columns=_MHRLE_COLS, rows=_MHRLE_ROWS)
    decoded = _py_decode(_MHRLE_STRIP, params, _MHRLE_COLS, _MHRLE_ROWS)
    assert decoded == _MHRLE_DECODED


@requires_oracle
def test_mhrle_no_eol_k0_decode_byte_exact_oracle() -> None:
    """Differential: same MH-RLE strip, live PDFBox vs pypdfbox, byte-exact."""
    args = f"K=0,Columns={_MHRLE_COLS},Rows={_MHRLE_ROWS}"
    java = _java_decode(_MHRLE_STRIP, args)
    params = _params(k=0, columns=_MHRLE_COLS, rows=_MHRLE_ROWS)
    py = _py_decode(_MHRLE_STRIP, params, _MHRLE_COLS, _MHRLE_ROWS)
    assert py == java
    # Sanity: the pinned literal still matches the live oracle.
    assert java == _MHRLE_DECODED


# ---------------------------------------------------------------------------
# Real Group 3 leading-EOL fixture decoded with K==0 and NO /EndOfLine
# (exercises the sniff -> T.4 arm; the existing oracle test always sets
# /EndOfLine, so the implicit-detection path was unpinned).
# ---------------------------------------------------------------------------


@requires_oracle
def test_group3_leading_eol_k0_no_endofline_byte_exact_oracle() -> None:
    encoded = (_FIXTURES / "ccittg3.ccitt").read_bytes()
    args = f"K=0,Columns={_G3_COLS},Rows={_G3_ROWS}"
    java = _java_decode(encoded, args)
    params = _params(k=0, columns=_G3_COLS, rows=_G3_ROWS)
    py = _py_decode(encoded, params, _G3_COLS, _G3_ROWS)
    assert py == java
    assert len(py) == _G3_ROWS * ((_G3_COLS + 7) // 8)


# ---------------------------------------------------------------------------
# Truncated /Rows (declared SMALLER than the image's natural row count):
# upstream allocates a fixed rows*rowBytes buffer and decodes only that many
# scanlines. pypdfbox trims to the same footprint -> byte-exact prefix.
# (Over-declared /Rows lands in libtiff's post-EOD padding tail, which differs
# per-OS — deliberately NOT asserted here, per the project's cross-platform
# rule.)
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("rows", [_G3_ROWS - 100, _G3_ROWS - 50, _G3_ROWS - 1])
def test_group3_truncated_rows_byte_exact_oracle(rows: int) -> None:
    encoded = (_FIXTURES / "ccittg3.ccitt").read_bytes()
    args = f"K=0,Columns={_G3_COLS},Rows={rows},EndOfLine=1"
    java = _java_decode(encoded, args)
    params = _params(k=0, columns=_G3_COLS, rows=rows, EndOfLine=True)
    py = _py_decode(encoded, params, _G3_COLS, rows)
    assert py == java
    assert len(py) == rows * ((_G3_COLS + 7) // 8)
