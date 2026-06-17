"""Live PDFBox differential parity for the stream-filter ENCODE surface.

Counterpart to ``test_filter_decode_oracle.py`` (wave 1412 covered DECODE;
this covers ENCODE + round-trip). The key invariant for an *encoder* is the
**round-trip across the oracle boundary**:

* **pypdfbox-encode -> Java-decode** must recover the original bytes, and
* **Java-encode -> pypdfbox-decode** must recover the original bytes.

Byte-identical encoded output is asserted only for the deterministic encoders
(ASCIIHexDecode, ASCII85Decode, RunLengthDecode) where the spec pins a single
canonical output — and we document the one legitimate place ASCII85 differs.
For the compressors (FlateDecode, LZWDecode) byte-identical output is *not*
required: two conformant compressors legitimately differ in their bit streams,
so we assert round-trip equivalence instead (and merely *observe* that Flate
happens to agree byte-for-byte because both sides wrap zlib/Deflater).

ASCII85 framing note. pypdfbox's ASCII85 encode is a faithful port of upstream
``ASCII85OutputStream`` (wave 1463): hard line breaks every 72 columns, a
trailing ``\n`` after the ``~>`` EOD marker, and zero bytes for empty input.
The FULL encoded output is therefore byte-identical to PDFBox 3.0.7 (the
earlier framing divergence is closed).

The Java side runs through ``oracle/probes/FilterEncodeProbe.java`` (encode)
and ``oracle/probes/FilterDecodeProbe.java`` (decode); both build a minimal
stream ``COSDictionary`` (``/Filter`` plus an optional ``/DecodeParms`` integer
dictionary) and invoke ``FilterFactory.INSTANCE.getFilter(...)``. ``run_probe``
returns the raw bytes verbatim.

Predictor note (documented divergence). PDFBox's ``FlateFilter.encode`` /
``LZWFilter.encode`` are *pure compressors*: they apply no PNG/TIFF predictor,
they only deflate / LZW-pack (verified by decompiling the 3.0.7 jar — the
encode bodies call only ``getCompressionLevel`` + ``DeflaterOutputStream`` /
``createCodeTable``, never ``getDecodeParams`` or a predictor). pypdfbox's
encoders additionally honour a ``/Predictor`` entry passed at the *top level*
of the parameters dict and predictor-transform the data before compressing —
a superset feature so pypdfbox can author predicted streams. That extension
round-trips both within pypdfbox and across the boundary when the matching
``/DecodeParms`` predictor is supplied to the decoder; see
``test_flate_encode_side_predictor_round_trips_through_java``. When the predictor
params live under ``/DecodeParms`` (the real stream-dict shape produced by
``COSOutputStream``) pypdfbox's encode applies *no* predictor — matching PDFBox
exactly — so plain Flate/LZW round-trips agree with the oracle byte-for-byte.
"""

from __future__ import annotations

import io
import os
import tempfile
import zlib

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.filter import FilterFactory
from tests.oracle.harness import requires_oracle, run_probe

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _params_dict(parms: dict[str, int] | None, nested: bool) -> COSDictionary:
    """Build a parameters ``COSDictionary``.

    ``nested=True`` puts the params under ``/DecodeParms`` (the real stream
    dictionary shape); ``nested=False`` puts them at the top level (the shape
    pypdfbox's encode-side predictor extension reads).
    """
    p = COSDictionary()
    if not parms:
        return p
    target = p
    if nested:
        target = COSDictionary()
        p.set_item(COSName.get_pdf_name("DecodeParms"), target)
    for key, value in parms.items():
        target.set_item(COSName.get_pdf_name(key), COSInteger.get(value))
    return p


def _py_encode(
    filter_name: str,
    raw: bytes,
    parms: dict[str, int] | None = None,
    nested: bool = True,
) -> bytes:
    """Encode ``raw`` with pypdfbox's filter and return the encoded bytes."""
    flt = FilterFactory.get(filter_name)
    out = io.BytesIO()
    flt.encode(io.BytesIO(raw), out, _params_dict(parms, nested))
    return out.getvalue()


def _py_decode(
    filter_name: str,
    encoded: bytes,
    parms: dict[str, int] | None = None,
) -> bytes:
    """Decode ``encoded`` with pypdfbox's filter and return the raw bytes."""
    flt = FilterFactory.get(filter_name)
    out = io.BytesIO()
    flt.decode(io.BytesIO(encoded), out, _params_dict(parms, nested=True), 0)
    return out.getvalue()


def _run_probe_with_input(
    probe: str,
    payload: bytes,
    filter_name: str,
    parms: dict[str, int] | None = None,
) -> bytes:
    """Stage ``payload`` to a temp file and run ``probe`` over it.

    The probes read their input from ``args[0]``; we write a fresh temp file
    per call. ``mkstemp`` returns a closed-by-us fd (closed before the
    subprocess reads it) and we unlink after — Windows-safe (no open handle
    held across the subprocess that would lock the file).
    """
    fd, path = tempfile.mkstemp()
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        args = [path, filter_name]
        if parms:
            args.append(",".join(f"{k}={v}" for k, v in parms.items()))
        return run_probe(probe, *args)
    finally:
        os.unlink(path)


def _java_encode(
    filter_name: str,
    raw: bytes,
    parms: dict[str, int] | None = None,
) -> bytes:
    return _run_probe_with_input("FilterEncodeProbe", raw, filter_name, parms)


def _java_decode(
    filter_name: str,
    encoded: bytes,
    parms: dict[str, int] | None = None,
) -> bytes:
    return _run_probe_with_input("FilterDecodeProbe", encoded, filter_name, parms)


def _assert_round_trip(filter_name: str, payload: bytes) -> None:
    """Both boundary round-trips recover ``payload`` for a plain (no-parm) call."""
    py_enc = _py_encode(filter_name, payload)
    java_enc = _java_encode(filter_name, payload)
    assert _java_decode(filter_name, py_enc) == payload, (
        f"{filter_name}: pypdfbox-encode -> Java-decode lost data"
    )
    assert _py_decode(filter_name, java_enc) == payload, (
        f"{filter_name}: Java-encode -> pypdfbox-decode lost data"
    )


# Shared payload corpus exercising the encoders' edge cases.
_PAYLOADS = [
    b"",
    b"A",
    b"Hello, PDFBox!",
    b"TOBEORNOTTOBEORTOBEORNOT",
    b"the quick brown fox jumps over " * 50,
    bytes(range(256)) * 4,
    b"\x00" * 500,
    bytes((i * 37 + 11) % 256 for i in range(777)),
]
_PAYLOAD_IDS = [
    "empty", "one", "short", "classic", "repetitive",
    "all-bytes", "all-zero", "pseudo-random",
]


# ---------------------------------------------------------------------------
# FlateDecode — compressor: round-trip + (observed) byte-identical encode
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_flate_encode_round_trip(payload: bytes) -> None:
    _assert_round_trip("FlateDecode", payload)


@requires_oracle
@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_flate_encode_byte_identical_observed(payload: bytes) -> None:
    # Byte-identity is NOT required of a compressor, but pypdfbox and PDFBox
    # both wrap the same zlib/Deflater at the default level, so in practice
    # their /FlateDecode encode output coincides exactly. We assert it to lock
    # the observation; if a future zlib bump changes the bit stream this test
    # documents the change (and the round-trip tests still guarantee parity).
    assert _py_encode("FlateDecode", payload) == _java_encode("FlateDecode", payload)


@requires_oracle
def test_flate_encode_side_predictor_round_trips_through_java() -> None:
    # DOCUMENTED DIVERGENCE: pypdfbox's FlateDecode.encode honours a top-level
    # /Predictor (PDFBox's does not — its encode is a pure deflate). When the
    # extension is driven via top-level params it produces a genuinely
    # predicted stream that the PDFBox oracle reverses cleanly given the
    # matching /DecodeParms predictor.
    columns, colors, bpc = 4, 1, 8
    row_bytes = (columns * colors * bpc + 7) // 8
    payload = bytes((i * 37 + 11) % 256 for i in range(row_bytes * 6))
    parms = {"Predictor": 12, "Columns": columns, "Colors": colors, "BitsPerComponent": bpc}

    encoded = _py_encode("FlateDecode", payload, parms, nested=False)
    # The encoder really predicted (decompressed body carries the per-row tag
    # bytes, so it is longer than the raw payload).
    assert len(zlib.decompress(encoded)) > len(payload)
    # Java decode with the same predictor params recovers the original.
    assert _java_decode("FlateDecode", encoded, parms) == payload
    # And pypdfbox decodes its own predicted stream identically.
    assert _py_decode("FlateDecode", encoded, parms) == payload


@requires_oracle
def test_flate_encode_matches_pdfbox_no_predictor_when_parms_nested() -> None:
    # When /Predictor lives under /DecodeParms (the real stream-dict shape used
    # by COSOutputStream), pypdfbox's encode applies NO predictor — exactly like
    # PDFBox — so the encoded bytes are byte-identical and round-trip plainly.
    columns, colors, bpc = 4, 1, 8
    payload = bytes((i * 37 + 11) % 256 for i in range(columns * 6))
    parms = {"Predictor": 12, "Columns": columns, "Colors": colors, "BitsPerComponent": bpc}

    py_enc = _py_encode("FlateDecode", payload, parms, nested=True)
    java_enc = _java_encode("FlateDecode", payload, parms)
    assert py_enc == java_enc
    # No predictor was applied either side: the decompressed body is the raw
    # payload, so a plain (no-parm) decode recovers it on both engines.
    assert zlib.decompress(py_enc) == payload
    assert _java_decode("FlateDecode", py_enc) == payload
    assert _py_decode("FlateDecode", py_enc) == payload


# ---------------------------------------------------------------------------
# LZWDecode — compressor: round-trip only (bit streams legitimately differ)
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_lzw_encode_round_trip(payload: bytes) -> None:
    _assert_round_trip("LZWDecode", payload)


@requires_oracle
def test_lzw_encode_bit_stream_may_differ_but_round_trips() -> None:
    # DOCUMENTED: LZW is a conformant-but-non-canonical compressor. pypdfbox and
    # PDFBox make different code-table / chunk-width bookkeeping choices, so the
    # packed bit streams are NOT byte-identical for most inputs — yet each
    # decodes the other's output back to the original. We assert the cross-
    # decode equivalence (the contract) and merely note the bytes differ.
    payload = b"the quick brown fox jumps over " * 50
    py_enc = _py_encode("LZWDecode", payload)
    java_enc = _java_encode("LZWDecode", payload)
    # Round-trip across the boundary either way recovers the data ...
    assert _java_decode("LZWDecode", py_enc) == payload
    assert _py_decode("LZWDecode", java_enc) == payload
    # ... even though the encoders chose different (both valid) bit streams.
    assert py_enc != java_enc


# ---------------------------------------------------------------------------
# ASCIIHexDecode — deterministic: byte-identical encode + round-trip
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_ascii_hex_encode_byte_identical(payload: bytes) -> None:
    # PDFBox's ASCIIHexFilter.encode emits uppercase hex with NO trailing '>'
    # EOD marker; pypdfbox's binascii.hexlify(...).upper() matches byte-for-byte.
    py_enc = _py_encode("ASCIIHexDecode", payload)
    java_enc = _java_encode("ASCIIHexDecode", payload)
    assert py_enc == java_enc
    # Round-trip: append the EOD marker the decoders expect (PDFBox's encode
    # omits it, but its decode stops at EOF too, so a bare hex body round-trips).
    assert _java_decode("ASCIIHexDecode", py_enc) == payload
    assert _py_decode("ASCIIHexDecode", java_enc) == payload


# ---------------------------------------------------------------------------
# ASCII85Decode — deterministic digits; one documented framing difference
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_ascii85_encode_round_trip(payload: bytes) -> None:
    _assert_round_trip("ASCII85Decode", payload)


@requires_oracle
@pytest.mark.parametrize(
    "payload",
    [b"A", b"AB", b"ABC", b"\x00\x00\x00\x00", b"Hello, PDFBox!", bytes(range(256))],
    ids=["one", "two", "three", "four-zero", "hello", "all-bytes"],
)
def test_ascii85_encode_byte_identical(payload: bytes) -> None:
    # Wave 1463 closed the prior framing divergence: pypdfbox now routes
    # encode through a faithful port of upstream ``ASCII85OutputStream``, so
    # the FULL encoded output — base-85 digits, hard line breaks every 72
    # columns, the ``~>`` EOD marker AND the trailing newline after ``>`` —
    # is byte-identical to PDFBox 3.0.7.
    py_enc = _py_encode("ASCII85Decode", payload)
    java_enc = _java_encode("ASCII85Decode", payload)
    assert py_enc == java_enc
    assert py_enc.endswith(b"~>\n")


@requires_oracle
def test_ascii85_encode_empty_emits_nothing() -> None:
    # Wave 1463: pypdfbox now matches upstream exactly for empty input —
    # ``ASCII85OutputStream`` starts ``flushed=true`` so a stream that never
    # received a byte emits NOTHING on flush (not even the ``~>`` marker).
    assert _py_encode("ASCII85Decode", b"") == b""
    assert _java_encode("ASCII85Decode", b"") == b""
    assert _py_decode("ASCII85Decode", b"") == b""


# ---------------------------------------------------------------------------
# RunLengthDecode — deterministic: byte-identical encode + round-trip
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_run_length_encode_byte_identical(payload: bytes) -> None:
    # pypdfbox's greedy state machine is ported directly from PDFBox's
    # RunLengthDecodeFilter, so the packed (length, payload) packets — and the
    # trailing 0x80 EOD marker — match byte-for-byte across all corpus inputs.
    py_enc = _py_encode("RunLengthDecode", payload)
    java_enc = _java_encode("RunLengthDecode", payload)
    assert py_enc == java_enc
    assert _java_decode("RunLengthDecode", py_enc) == payload
    assert _py_decode("RunLengthDecode", java_enc) == payload


@requires_oracle
@pytest.mark.parametrize(
    "payload",
    [
        b"AAAAAAAABBBCDEFGGGGGG" + bytes(range(64)) + b"ZZZZZZZZ",
        b"\xff" * 200,  # one long repeat run spanning multiple max packets
        bytes([0, 255] * 100),  # worst case: no runs, all literal
        b"X",  # single byte
    ],
    ids=["mixed", "long-repeat", "no-runs", "single"],
)
def test_run_length_encode_byte_identical_edge_runs(payload: bytes) -> None:
    assert _py_encode("RunLengthDecode", payload) == _java_encode(
        "RunLengthDecode", payload
    )


# ---------------------------------------------------------------------------
# Sanity guard: the probe jar/build paths resolve (skipped without oracle).
# ---------------------------------------------------------------------------


@requires_oracle
def test_encode_probe_compiles_and_runs() -> None:
    # A trivial smoke check that the encode probe is wired up: ASCIIHex of "A"
    # is the two ASCII bytes "41".
    assert _java_encode("ASCIIHexDecode", b"A") == b"41"
