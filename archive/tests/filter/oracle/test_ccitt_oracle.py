"""Live PDFBox differential parity for the CCITTFaxDecode filter — BYTE-EXACT.

CCITT Group 3 (T.4, 1-D and 2-D) and Group 4 (T.6) fax decoding is lossless,
so the decoded scanline buffer must match Apache PDFBox 3.0.7 *byte for byte* —
no tolerance. This complements ``tests/pdmodel/.../oracle/test_ccitt_image_oracle.py``
which only checks a tolerant 16x16 luminance fingerprint of the rendered raster;
here we assert SHA-256 equality of the raw decoded bytes.

The two implementations decode by entirely different machinery — pypdfbox wraps
the encoded strip in a synthetic TIFF and delegates to libtiff, while PDFBox
runs its own pure-Java ``CCITTFaxDecoderStream`` — so a byte-exact match across
all ``/K`` modes and ``/DecodeParms`` polarities is a strong parity signal.

The Java side runs through ``oracle/probes/CcittDecodeProbe.java``: it reads the
raw encoded strip from a file, builds a stream ``COSDictionary`` mirroring a
real image XObject (``/Filter /CCITTFaxDecode`` + ``/DecodeParms`` + ``/Width``
/``/Height``), invokes ``CCITTFaxFilter.decode``, and writes the decoded bytes
to stdout verbatim. We pin ``/Height == /Rows`` on the stream dict so PDFBox's
``rows = max(rows, height)`` reconciliation gives a deterministic buffer size,
which we then compare to pypdfbox's ``rows * rowBytes`` trim.

Coverage:

* ``K < 0`` — Group 4 (T.6): real upstream fixtures ``ccittg4.tif`` /
  ``ccittg4multi.tif`` (single- and multi-strip), default and ``/BlackIs1``.
* ``K == 0`` — Group 3 1-D (T.4): real upstream ``ccittg3.tif`` (leading-EOL
  stream), and a synthesized byte-aligned stream for ``/EncodedByteAlign``.
* ``K > 0`` — Group 3 2-D (T.4 mixed): synthesized via the pypdfbox encoder
  (no real 2-D fixture ships with upstream); the *same* encoded bytes are fed
  to both decoders, so it remains a valid differential decode test.

Fixtures (raw CCITT strips extracted from the upstream TIFFs, see PROVENANCE):
``tests/fixtures/filter/ccittg3.ccitt`` / ``ccittg4.ccitt`` / ``ccittg4multi.ccitt``.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import tempfile
from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import CCITTFaxDecode
from tests.oracle.harness import requires_oracle, run_probe

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "filter"

# Geometry of the upstream CCITT TIFF fixtures (W=344, H=287 for all three).
_REAL_COLS = 344
_REAL_ROWS = 287

# T4Options bits (TIFF 6.0): bit 0 = 2D coding, bit 2 = byte-aligned EOLs.
_T4_2D = 0x1
_T4_BYTE_ALIGN = 0x4
_TIFF_STRIP_OFFSETS = 273
_TIFF_STRIP_BYTE_COUNTS = 279


# ---------------------------------------------------------------------------
# decode helpers
# ---------------------------------------------------------------------------


def _params(
    *,
    k: int,
    columns: int,
    rows: int,
    black_is_1: bool = False,
    encoded_byte_align: bool = False,
    end_of_line: bool = False,
) -> COSDictionary:
    p = COSDictionary()
    p.set_int("K", k)
    p.set_int("Columns", columns)
    p.set_int("Rows", rows)
    if black_is_1:
        p.set_boolean("BlackIs1", True)
    if encoded_byte_align:
        p.set_boolean("EncodedByteAlign", True)
    if end_of_line:
        p.set_boolean("EndOfLine", True)
    return p


def _py_decode(encoded: bytes, params: COSDictionary, columns: int, rows: int) -> bytes:
    """Decode with pypdfbox; trim to the declared ``rows * rowBytes`` footprint
    (libtiff may pad past EOD; we never compare beyond the declared image)."""
    out = io.BytesIO()
    CCITTFaxDecode().decode(io.BytesIO(encoded), out, params, 0)
    row_bytes = (columns + 7) // 8
    return out.getvalue()[: rows * row_bytes]


def _java_args(params: COSDictionary, *, columns: int, rows: int, k: int) -> str:
    parts = [f"K={k}", f"Columns={columns}", f"Rows={rows}"]
    if params.get_boolean("BlackIs1", False):
        parts.append("BlackIs1=1")
    if params.get_boolean("EncodedByteAlign", False):
        parts.append("EncodedByteAlign=1")
    if params.get_boolean("EndOfLine", False):
        parts.append("EndOfLine=1")
    return ",".join(parts)


def _java_decode(encoded: bytes, args: str) -> bytes:
    """Decode with the live PDFBox oracle. The probe reads the encoded strip
    from a file path (args[0]); stage it in a closed temp file (Windows-safe:
    write + close before the probe reopens it, unlink in finally)."""
    fd, tmp = tempfile.mkstemp(suffix=".ccitt")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(encoded)
        return run_probe("CcittDecodeProbe", tmp, args)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)


def _assert_byte_exact(
    encoded: bytes, *, k: int, columns: int, rows: int, **flags: bool
) -> None:
    params = _params(k=k, columns=columns, rows=rows, **flags)
    py = _py_decode(encoded, params, columns, rows)
    java = _java_decode(encoded, _java_args(params, columns=columns, rows=rows, k=k))
    assert py == java, (
        "CCITT decoded bytes diverged from PDFBox (lossless decode must be "
        f"byte-exact):\n  py  len={len(py)} sha={hashlib.sha256(py).hexdigest()}\n"
        f"  java len={len(java)} sha={hashlib.sha256(java).hexdigest()}"
    )
    # Defence-in-depth: confirm we actually compared a non-empty bitmap.
    assert len(py) == rows * ((columns + 7) // 8)


# ---------------------------------------------------------------------------
# synthetic stream builders (no real fixtures exist for these axes)
# ---------------------------------------------------------------------------


def _encode_via_libtiff(
    raw_packed: bytes,
    *,
    columns: int,
    rows: int,
    compression: str,
    t4_options: int,
    black_is_1: bool,
) -> bytes:
    """Build a real CCITT strip via libtiff with an explicit ``T4Options`` so we
    can exercise byte-alignment / 2-D coding axes the pypdfbox encoder API does
    not expose directly. Mirrors the polarity convention of
    :meth:`CCITTFaxDecode.encode` (invert for ``/BlackIs1`` false)."""
    from PIL import Image
    from PIL.TiffImagePlugin import ImageFileDirectory_v2

    pixels = raw_packed if black_is_1 else bytes(b ^ 0xFF for b in raw_packed)
    image = Image.frombytes("1", (columns, rows), pixels)
    buf = io.BytesIO()
    kwargs: dict[str, object] = {"format": "TIFF", "compression": compression}
    if t4_options:
        ifd = ImageFileDirectory_v2()
        ifd[292] = t4_options
        kwargs["tiffinfo"] = ifd
    image.save(buf, **kwargs)  # type: ignore[arg-type]
    tiff = buf.getvalue()
    with Image.open(io.BytesIO(tiff)) as parsed:
        tag = parsed.tag_v2  # type: ignore[attr-defined]
        offsets = tag[_TIFF_STRIP_OFFSETS]
        counts = tag[_TIFF_STRIP_BYTE_COUNTS]
    offset = offsets[0] if isinstance(offsets, tuple) else offsets
    count = counts[0] if isinstance(counts, tuple) else counts
    return tiff[offset : offset + count]


# ---------------------------------------------------------------------------
# K < 0 — Group 4 (T.6), real fixtures
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "name", ["ccittg4.ccitt", "ccittg4multi.ccitt"], ids=["g4", "g4-multi"]
)
def test_group4_decode_byte_exact(name: str) -> None:
    encoded = (_FIXTURES / name).read_bytes()
    _assert_byte_exact(encoded, k=-1, columns=_REAL_COLS, rows=_REAL_ROWS)


@requires_oracle
@pytest.mark.parametrize("black_is_1", [False, True], ids=["blackis0", "blackis1"])
def test_group4_blackis1_polarity_byte_exact(black_is_1: bool) -> None:
    encoded = (_FIXTURES / "ccittg4.ccitt").read_bytes()
    _assert_byte_exact(
        encoded, k=-1, columns=_REAL_COLS, rows=_REAL_ROWS, black_is_1=black_is_1
    )


# ---------------------------------------------------------------------------
# K == 0 — Group 3 1-D (T.4), real leading-EOL fixture + synthetic byte-align
# ---------------------------------------------------------------------------


@requires_oracle
def test_group3_1d_decode_byte_exact() -> None:
    # ccittg3.tif carries a leading EOL (000000000001), so PDFBox auto-detects
    # T.4 (not RLE) under K=0; we make that explicit with /EndOfLine.
    encoded = (_FIXTURES / "ccittg3.ccitt").read_bytes()
    _assert_byte_exact(
        encoded, k=0, columns=_REAL_COLS, rows=_REAL_ROWS, end_of_line=True
    )


@requires_oracle
def test_group3_1d_encoded_byte_align_byte_exact() -> None:
    columns, rows = 24, 6
    raw = b"\xaa\x55\xaa" * rows  # 0=black after BlackIs0 inversion
    encoded = _encode_via_libtiff(
        raw,
        columns=columns,
        rows=rows,
        compression="group3",
        t4_options=_T4_BYTE_ALIGN,
        black_is_1=False,
    )
    _assert_byte_exact(
        encoded, k=0, columns=columns, rows=rows, encoded_byte_align=True
    )


# ---------------------------------------------------------------------------
# K > 0 — Group 3 2-D (T.4 mixed), synthesized (no upstream 2-D fixture)
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "pattern", [b"\xcc\xcc\xcc", b"\xaa\x55\xaa", b"\xff\x00\xff"], ids=["cc", "aa", "ff"]
)
def test_group3_2d_decode_byte_exact(pattern: bytes) -> None:
    columns, rows = 24, 6
    raw = pattern * rows
    encoded = _encode_via_libtiff(
        raw,
        columns=columns,
        rows=rows,
        compression="group3",
        t4_options=_T4_2D,
        black_is_1=False,
    )
    _assert_byte_exact(encoded, k=2, columns=columns, rows=rows)
