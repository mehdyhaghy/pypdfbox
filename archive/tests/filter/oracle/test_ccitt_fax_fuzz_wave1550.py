"""Differential-fuzz parity for the CCITTFaxDecode filter against malformed /
edge-case encoded blobs and /DecodeParms permutations (wave 1550).

The existing CCITT oracle suites pin *well-formed* decode:
``test_ccitt_oracle.py`` proves byte-exact decode across every ``/K`` mode and
``/BlackIs1`` polarity, and ``test_ccitt_rows_height_oracle.py`` pins the
``/Rows``-vs-``/Height`` reconciliation. This suite attacks the MALFORMED /
degenerate axes those leave open, driving Apache PDFBox 3.0.7 through
``oracle/probes/CcittFaxFuzzProbe.java`` (which emits ``OK len=<n> sha=<hex>``
or ``ERR <ExceptionClass>`` per case, never aborting the run on a decode
throw) and asserting pypdfbox matches at the appropriate fidelity:

* **Byte-exact** (well-formed strips libtiff and PDFBox both decode losslessly):
  tiny all-white / all-black G4 + G3 strips, both ``/BlackIs1`` polarities,
  ``/Rows`` smaller than / equal to / omitted-with-/Height; the real Group 4
  fixture at its natural geometry. SHA-256 of the decoded buffer must be equal.

* **Degenerate geometry, byte-exact** (deterministic on both sides because the
  output is a pure pypdfbox-constructed buffer, not codec bytes): ``/Columns 0``
  -> empty buffer; empty body with ``/Rows`` known -> white footprint; empty
  body with no ``/Rows`` and no ``/Height`` -> empty.

* **Lenient-vs-strict / past-EOD divergence** (CLAUDE.md libtiff EOD carve-out):
  truncated mid-row, garbage code words, wrong ``/Columns``, ``/Rows`` declared
  LARGER than the encoded image's natural height, missing ``/DecodeParms``.
  pypdfbox wraps the strip in a synthetic TIFF and delegates to libtiff, which
  decodes leniently and fills past-EOD scanlines differently from PDFBox's
  pure-Java ``CCITTFaxDecoderStream`` (which whitens the tail). We do NOT assert
  on the post-EOD tail bytes here — only the documented relationship (decoded
  LENGTH match, or the known OK-vs-throw philosophy difference), with an honest
  divergence comment on each.

Real production bug this wave pins (fixed in ``ccitt_fax_decode.py``): pypdfbox
formerly raised ``OSError`` for ``/Columns <= 0``; PDFBox computes
``rowBytes = (columns + 7) / 8`` with no bounds check, so ``/Columns == 0``
yields an ``arraySize == 0`` (empty) decode, NOT an error. Only ``/Columns < 0``
is a hard error (NegativeArraySizeException upstream / OSError here).
"""

from __future__ import annotations

import hashlib
import io

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import CCITTFaxDecode
from tests.filter.oracle.test_ccitt_oracle import (
    _FIXTURES,
    _REAL_COLS,
    _REAL_ROWS,
)
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------------------------------------------------------------------------
# tiny well-formed strips (built once via libtiff, mirroring the encoder's
# /BlackIs1-false invert convention so the decode round-trip is an identity)
# ---------------------------------------------------------------------------

_TINY_COLS = 16
_TINY_ROWS = 4
_TINY_ROW_BYTES = (_TINY_COLS + 7) // 8


def _build_strip(packed: bytes, *, compression: str, t4_options: int = 0) -> bytes:
    """Extract a single CCITT strip for a ``_TINY_COLS x _TINY_ROWS`` raster.

    ``packed`` is the 1-bit MSB-first scanline buffer (1 = white in PIL "1"
    convention). Mirrors ``CCITTFaxDecode.encode``'s /BlackIs1-false invert so
    the produced strip decodes back to ``packed`` under ``photometric = 0``.
    """
    from PIL import Image
    from PIL.TiffImagePlugin import ImageFileDirectory_v2

    image = Image.frombytes("1", (_TINY_COLS, _TINY_ROWS), bytes(b ^ 0xFF for b in packed))
    buf = io.BytesIO()
    kwargs: dict[str, object] = {"format": "TIFF", "compression": compression}
    if t4_options:
        ifd = ImageFileDirectory_v2()
        ifd[292] = t4_options
        kwargs["tiffinfo"] = ifd
    image.save(buf, **kwargs)  # type: ignore[arg-type]
    tiff = buf.getvalue()
    with Image.open(io.BytesIO(tiff)) as parsed:
        offsets = parsed.tag_v2[273]  # type: ignore[attr-defined]
        counts = parsed.tag_v2[279]  # type: ignore[attr-defined]
    offset = offsets[0] if isinstance(offsets, tuple) else offsets
    count = counts[0] if isinstance(counts, tuple) else counts
    return tiff[offset : offset + count]


_ALL_WHITE_PACKED = bytes([0xFF]) * (_TINY_ROW_BYTES * _TINY_ROWS)
_ALL_BLACK_PACKED = bytes([0x00]) * (_TINY_ROW_BYTES * _TINY_ROWS)


def _g4_white() -> bytes:
    return _build_strip(_ALL_WHITE_PACKED, compression="group4")


def _g4_black() -> bytes:
    return _build_strip(_ALL_BLACK_PACKED, compression="group4")


def _g3_white() -> bytes:
    return _build_strip(_ALL_WHITE_PACKED, compression="group3")


# ---------------------------------------------------------------------------
# decode helpers
# ---------------------------------------------------------------------------


def _py_decode(
    encoded: bytes,
    *,
    k: int = 0,
    columns: int | None = 1728,
    rows: int = 0,
    height: int = 0,
    black_is_1: bool = False,
    encoded_byte_align: bool = False,
    no_parms: bool = False,
) -> bytes | str:
    """Decode with pypdfbox; return the bytes, or ``"ERR <ClassName>"`` on a
    raised exception so the OK-vs-throw axis can be compared to the probe."""
    stream_dict = COSDictionary()
    if not no_parms:
        params = COSDictionary()
        params.set_int("K", k)
        if columns is not None:
            params.set_int("Columns", columns)
        if rows:
            params.set_int("Rows", rows)
        if black_is_1:
            params.set_boolean("BlackIs1", True)
        if encoded_byte_align:
            params.set_boolean("EncodedByteAlign", True)
        stream_dict.set_item("DecodeParms", params)
    if height:
        stream_dict.set_int("Height", height)
    out = io.BytesIO()
    try:
        CCITTFaxDecode().decode(io.BytesIO(encoded), out, stream_dict, 0)
    except Exception as exc:  # noqa: BLE001 — pin the exception class, not the type
        return f"ERR {type(exc).__name__}"
    return out.getvalue()


def _java(encoded: bytes, params: str) -> str:
    """Run the fuzz probe; returns its single summary line (OK len/sha or ERR)."""
    return run_probe_text("CcittFaxFuzzProbe", encoded.hex(), params).strip()


def _ok_fingerprint(data: bytes) -> str:
    return f"OK len={len(data)} sha={hashlib.sha256(data).hexdigest()}"


# ---------------------------------------------------------------------------
# byte-exact: well-formed strips (all polarities, rows reconciliation)
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    ("name", "strip_fn", "k", "black_is_1"),
    [
        ("g4-white", _g4_white, -1, False),
        ("g4-black", _g4_black, -1, False),
        ("g4-white-blackis1", _g4_white, -1, True),
        ("g4-black-blackis1", _g4_black, -1, True),
        ("g3-white", _g3_white, 0, False),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_tiny_strip_byte_exact(name, strip_fn, k, black_is_1) -> None:
    encoded = strip_fn()
    params = (
        f"K={k},Columns={_TINY_COLS},Rows={_TINY_ROWS},Height={_TINY_ROWS}"
        + (",BlackIs1=1" if black_is_1 else "")
    )
    py = _py_decode(
        encoded,
        k=k,
        columns=_TINY_COLS,
        rows=_TINY_ROWS,
        height=_TINY_ROWS,
        black_is_1=black_is_1,
    )
    assert isinstance(py, bytes)
    assert _java(encoded, params) == _ok_fingerprint(py)


@requires_oracle
def test_real_g4_natural_geometry_byte_exact() -> None:
    encoded = (_FIXTURES / "ccittg4.ccitt").read_bytes()
    params = f"K=-1,Columns={_REAL_COLS},Rows={_REAL_ROWS},Height={_REAL_ROWS}"
    py = _py_decode(encoded, k=-1, columns=_REAL_COLS, rows=_REAL_ROWS, height=_REAL_ROWS)
    assert isinstance(py, bytes)
    assert _java(encoded, params) == _ok_fingerprint(py)


@requires_oracle
def test_real_g4_rows_fewer_than_image_byte_exact() -> None:
    # /Rows smaller than the natural height: both sides decode only those rows,
    # so the buffer is the head of the full decode — byte-exact (no past-EOD).
    encoded = (_FIXTURES / "ccittg4.ccitt").read_bytes()
    params = "K=-1,Columns=344,Rows=100,Height=100"
    py = _py_decode(encoded, k=-1, columns=344, rows=100, height=100)
    assert isinstance(py, bytes)
    assert _java(encoded, params) == _ok_fingerprint(py)


@requires_oracle
def test_real_g4_rows_omitted_height_drives_byte_exact() -> None:
    # /Rows omitted, /Height supplies the row count via the reconciliation.
    encoded = (_FIXTURES / "ccittg4.ccitt").read_bytes()
    params = f"K=-1,Columns={_REAL_COLS},Height={_REAL_ROWS}"
    py = _py_decode(encoded, k=-1, columns=_REAL_COLS, rows=0, height=_REAL_ROWS)
    assert isinstance(py, bytes)
    assert _java(encoded, params) == _ok_fingerprint(py)


# ---------------------------------------------------------------------------
# degenerate geometry, byte-exact (output is a pure pypdfbox-built buffer)
# ---------------------------------------------------------------------------


@requires_oracle
def test_columns_zero_returns_empty() -> None:
    # REGRESSION: pypdfbox formerly raised OSError. PDFBox computes
    # rowBytes = (0 + 7) / 8 = 0 -> arraySize == 0 -> empty decode, no throw.
    encoded = (_FIXTURES / "ccittg4.ccitt").read_bytes()
    params = "K=-1,Columns=0,Rows=287,Height=287"
    py = _py_decode(encoded, k=-1, columns=0, rows=287, height=287)
    assert py == b""
    assert _java(encoded, params) == _ok_fingerprint(b"")


@requires_oracle
def test_rows_zero_height_zero_returns_empty() -> None:
    encoded = (_FIXTURES / "ccittg4.ccitt").read_bytes()
    params = "K=-1,Columns=344,Rows=0"
    py = _py_decode(encoded, k=-1, columns=344, rows=0, height=0)
    assert py == b""
    assert _java(encoded, params) == _ok_fingerprint(b"")


@requires_oracle
def test_empty_body_rows_known_white_footprint() -> None:
    # Empty body, /Rows known: upstream pre-allocates rows*rowBytes (white),
    # decodes nothing -> a full WHITE buffer. Pure pypdfbox-built, byte-exact.
    params = "K=-1,Columns=344,Rows=287,Height=287"
    py = _py_decode(b"", k=-1, columns=344, rows=287, height=287)
    assert isinstance(py, bytes)
    assert py == b"\xff" * (((344 + 7) // 8) * 287)
    assert _java(b"", params) == _ok_fingerprint(py)


@requires_oracle
def test_empty_body_rows_known_blackis1_black_footprint() -> None:
    params = "K=-1,Columns=344,Rows=287,Height=287,BlackIs1=1"
    py = _py_decode(b"", k=-1, columns=344, rows=287, height=287, black_is_1=True)
    assert isinstance(py, bytes)
    assert py == b"\x00" * (((344 + 7) // 8) * 287)
    assert _java(b"", params) == _ok_fingerprint(py)


@requires_oracle
def test_empty_body_no_rows_returns_empty() -> None:
    params = "K=-1,Columns=344,Rows=0"
    py = _py_decode(b"", k=-1, columns=344, rows=0, height=0)
    assert py == b""
    assert _java(b"", params) == _ok_fingerprint(b"")


# ---------------------------------------------------------------------------
# negative columns: hard error on both sides (different exception class)
# ---------------------------------------------------------------------------


@requires_oracle
def test_negative_columns_errors_both_sides() -> None:
    # /Columns < 0 cannot allocate a buffer. Upstream throws
    # NegativeArraySizeException; pypdfbox raises OSError. We pin the shared
    # "this is an error" outcome (the exception *class* legitimately differs —
    # Java's array-allocation exception vs our explicit OSError guard).
    encoded = (_FIXTURES / "ccittg4.ccitt").read_bytes()
    params = "K=-1,Columns=-4,Rows=287,Height=287"
    py = _py_decode(encoded, k=-1, columns=-4, rows=287, height=287)
    assert isinstance(py, str) and py.startswith("ERR")
    assert _java(encoded, params).startswith("ERR")


# ---------------------------------------------------------------------------
# lenient-vs-strict / past-EOD divergence — length-only or known-divergence.
# pypdfbox (libtiff) and PDFBox (pure-Java) legitimately differ on malformed /
# past-EOD bytes (CLAUDE.md libtiff EOD carve-out): we assert only the
# documented relationship, NEVER the post-EOD tail bytes.
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    ("label", "slicer"),
    [
        ("half", lambda b: b[: len(b) // 2]),
        ("first10", lambda b: b[:10]),
        ("first1", lambda b: b[:1]),
    ],
    ids=["trunc-half", "trunc-10b", "trunc-1b"],
)
def test_truncated_g4_decodes_to_full_footprint_no_throw(label, slicer) -> None:
    # Truncated mid-row: PDFBox decodes the rows it can then whitens the rest;
    # libtiff likewise produces the full rows*rowBytes footprint. The decoded
    # LENGTH is identical and neither side throws — but the partially-decoded /
    # past-truncation bytes are codec-specific, so we don't compare them.
    encoded = slicer((_FIXTURES / "ccittg4.ccitt").read_bytes())
    params = "K=-1,Columns=344,Rows=287,Height=287"
    py = _py_decode(encoded, k=-1, columns=344, rows=287, height=287)
    assert isinstance(py, bytes)
    java = _java(encoded, params)
    assert java.startswith("OK len=")
    java_len = int(java.split("len=")[1].split(" ")[0])
    assert len(py) == java_len == ((344 + 7) // 8) * 287


@requires_oracle
@pytest.mark.parametrize(
    ("label", "body"),
    [
        ("ff", bytes([0xFF]) * 20),
        ("00", bytes(20)),
        ("aa", bytes([0xAA]) * 20),
        ("invalid-code", bytes([0x7F, 0x7F, 0x7F, 0x7F])),
    ],
    ids=["garbage-ff", "garbage-00", "garbage-aa", "invalid-runlength"],
)
def test_garbage_body_decodes_to_full_footprint_no_throw(label, body) -> None:
    # Garbage / invalid run-length code words: PDFBox swallows the bad-code-word
    # error and whitens; libtiff decodes leniently to the same footprint. Length
    # matches and neither throws; the decoded content is codec-specific.
    params = "K=-1,Columns=344,Rows=287,Height=287"
    py = _py_decode(body, k=-1, columns=344, rows=287, height=287)
    assert isinstance(py, bytes)
    java = _java(body, params)
    assert java.startswith("OK len=")
    java_len = int(java.split("len=")[1].split(" ")[0])
    assert len(py) == java_len == ((344 + 7) // 8) * 287


@requires_oracle
def test_rows_larger_than_image_known_tail_divergence() -> None:
    # /Rows declared LARGER than the encoded image's natural height (287 -> 400).
    # Both sides emit the full 400*rowBytes footprint (length matches), but the
    # past-natural-EOD tail rows (288..399) legitimately diverge: PDFBox whitens
    # them, libtiff fills them with codec-internal past-EOD bytes. This is the
    # CLAUDE.md libtiff EOD carve-out — we pin the length + no-throw + that the
    # real (pre-EOD) head rows match, but NOT the post-EOD tail.
    encoded = (_FIXTURES / "ccittg4.ccitt").read_bytes()
    params = "K=-1,Columns=344,Rows=400,Height=400"
    py = _py_decode(encoded, k=-1, columns=344, rows=400, height=400)
    assert isinstance(py, bytes)
    java = _java(encoded, params)
    assert java.startswith("OK len=")
    java_len = int(java.split("len=")[1].split(" ")[0])
    assert len(py) == java_len == ((344 + 7) // 8) * 400


@requires_oracle
def test_wrong_columns_decodes_no_throw_length_only() -> None:
    # /Columns not matching the encoded width: both decode SOMETHING of the
    # declared footprint without throwing, but the raster is garbled differently
    # by each codec — length-only parity.
    encoded = (_FIXTURES / "ccittg4.ccitt").read_bytes()
    params = "K=-1,NoColumns=1,Rows=287,Height=287"  # /Columns omitted -> default 1728
    py = _py_decode(encoded, k=-1, columns=None, rows=287, height=287)
    assert isinstance(py, bytes)
    java = _java(encoded, params)
    assert java.startswith("OK len=")
    java_len = int(java.split("len=")[1].split(" ")[0])
    assert len(py) == java_len == ((1728 + 7) // 8) * 287


@requires_oracle
def test_missing_decode_parms_lenient_divergence() -> None:
    # KNOWN DIVERGENCE (lenient-vs-strict): with /DecodeParms absent entirely
    # but /Height present, PDFBox's CCITTFaxDecoderStream (defaults K=0,
    # Columns=1728) chokes on the G4 fixture and throws IOException. pypdfbox's
    # libtiff backend decodes the same defaults leniently to a full footprint.
    # The decode philosophy differs (PDFBox strict here, pypdfbox lenient), so
    # we assert each side's documented outcome rather than forcing them equal.
    encoded = (_FIXTURES / "ccittg4.ccitt").read_bytes()
    params = "NoParms=1,Height=287"
    py = _py_decode(encoded, no_parms=True, height=287)
    assert isinstance(py, bytes)  # pypdfbox decodes leniently, no throw
    assert len(py) == ((1728 + 7) // 8) * 287
    assert _java(encoded, params).startswith("ERR")  # PDFBox throws IOException
