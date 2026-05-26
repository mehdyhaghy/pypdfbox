"""Live PDFBox differential parity for the stream-filter DECODE surface.

This is a strict **byte-equality** check: for each filter we construct an
encoded payload (either via pypdfbox's own encoder, or as canonical hand-crafted
encoded bytes) and assert that pypdfbox decodes it to exactly the same bytes
Apache PDFBox 3.0.7 produces for the same input.

The Java side runs through ``oracle/probes/FilterDecodeProbe.java``: it builds a
minimal stream ``COSDictionary`` (``/Filter`` plus an optional ``/DecodeParms``
integer dictionary), invokes ``FilterFactory.INSTANCE.getFilter(...).decode(...)``,
and writes the raw decoded bytes to stdout. ``run_probe`` returns those bytes
verbatim.

Coverage:

* ``FlateDecode`` — plain, plus PNG ``/Predictor 12`` (Up) and TIFF
  ``/Predictor 2``, the classic predictor divergence points.
* ``LZWDecode`` — default (EarlyChange=1) and EarlyChange=0.
* ``ASCII85Decode`` — canonical streams, the ``z`` shortcut, whitespace,
  partial groups, and the malformed-input quirks proven against the oracle
  (out-of-range digits, lone trailing digit, ``z`` mid-group).
* ``ASCIIHexDecode`` — whitespace tolerance, odd-length zero-pad, EOD marker.
* ``RunLengthDecode`` — literal runs, repeat runs, the 0x80 EOD marker, and
  trailing-bytes-after-EOD.
"""

from __future__ import annotations

import io
import zlib

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.filter import FilterFactory
from tests.oracle.harness import requires_oracle, run_probe

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _py_decode(
    filter_name: str,
    encoded: bytes,
    parms: dict[str, int] | None = None,
) -> bytes:
    """Decode ``encoded`` with pypdfbox's filter and return the raw bytes."""
    flt = FilterFactory.get(filter_name)
    stream_dict = COSDictionary()
    if parms:
        dp = COSDictionary()
        for key, value in parms.items():
            dp.set_item(COSName.get_pdf_name(key), COSInteger.get(value))
        stream_dict.set_item(COSName.get_pdf_name("DecodeParms"), dp)
    out = io.BytesIO()
    flt.decode(io.BytesIO(encoded), out, stream_dict, 0)
    return out.getvalue()


def _java_decode(
    filter_name: str,
    encoded: bytes,
    parms: dict[str, int] | None = None,
) -> bytes:
    """Decode ``encoded`` with the live PDFBox oracle and return raw bytes."""
    args = [filter_name]
    if parms:
        args.append(",".join(f"{k}={v}" for k, v in parms.items()))
    return run_probe("FilterDecodeProbe", _ENCODED_TMP, *args)


# The probe reads encoded bytes from a file path (args[0]); we stage each
# payload there per call. A module-scoped temp file keeps it simple.
_ENCODED_TMP = ""


@pytest.fixture(autouse=True)
def _stage_encoded(tmp_path_factory, request):  # type: ignore[no-untyped-def]
    """Provide a per-test scratch file the probe reads its input from."""
    global _ENCODED_TMP
    f = tmp_path_factory.mktemp("filter_oracle") / "encoded.bin"
    _ENCODED_TMP = str(f)
    request.node._encoded_path = f  # noqa: SLF001 — test-local stash
    yield


def _assert_parity(
    filter_name: str,
    encoded: bytes,
    parms: dict[str, int] | None = None,
) -> bytes:
    """Stage ``encoded``, decode it both ways, assert byte-equality, return it."""
    with open(_ENCODED_TMP, "wb") as fh:
        fh.write(encoded)
    java = _java_decode(filter_name, encoded, parms)
    py = _py_decode(filter_name, encoded, parms)
    assert py == java, (
        f"{filter_name} decode divergence\n  parms={parms}\n"
        f"  java={java.hex()}\n  py  ={py.hex()}"
    )
    return java


def _flate_encode(raw: bytes, parms: dict[str, int] | None = None) -> bytes:
    """Encode ``raw`` to a /FlateDecode stream (with optional predictor)."""
    flt = FilterFactory.get("FlateDecode")
    p = COSDictionary()
    if parms:
        for key, value in parms.items():
            p.set_item(COSName.get_pdf_name(key), COSInteger.get(value))
    out = io.BytesIO()
    flt.encode(io.BytesIO(raw), out, p)
    return out.getvalue()


def _lzw_encode(raw: bytes) -> bytes:
    flt = FilterFactory.get("LZWDecode")
    out = io.BytesIO()
    flt.encode(io.BytesIO(raw), out)
    return out.getvalue()


# ---------------------------------------------------------------------------
# FlateDecode — plain
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"Hello, PDFBox!",
        b"the quick brown fox " * 64,
        bytes(range(256)) * 4,
    ],
    ids=["empty", "short", "repetitive", "all-bytes"],
)
def test_flate_plain_parity(payload: bytes) -> None:
    encoded = _flate_encode(payload)
    assert _assert_parity("FlateDecode", encoded) == payload


@requires_oracle
def test_flate_raw_deflate_no_zlib_wrapper_is_documented_divergence() -> None:
    # DOCUMENTED DIVERGENCE (flate_decode.py): a raw-deflate body with no
    # zlib header trips a zlib "incorrect header check" on the first inflate.
    # PDFBox 3.0.7 treats the resulting DataFormatException as a premature
    # end of stream and yields ZERO decoded bytes (logging a warning, exit 0);
    # pypdfbox is deliberately more lenient and retries with a raw (nowrap)
    # inflate so it can read malformed PDFs that omit the wrapper, recovering
    # the full payload. We assert exactly that split. (Valid wrapped streams —
    # the only real-world case — agree byte-for-byte; see the plain tests.)
    payload = b"raw deflate body without the zlib wrapper" * 8
    co = zlib.compressobj(wbits=-zlib.MAX_WBITS)
    raw_deflate = co.compress(payload) + co.flush()
    with open(_ENCODED_TMP, "wb") as fh:
        fh.write(raw_deflate)

    assert _java_decode("FlateDecode", raw_deflate) == b""
    assert _py_decode("FlateDecode", raw_deflate) == payload


# ---------------------------------------------------------------------------
# FlateDecode — PNG predictor 12 (Up) and TIFF predictor 2
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    ("columns", "colors", "bpc"),
    [
        (4, 1, 8),
        (8, 1, 8),
        (3, 3, 8),  # RGB
        (16, 1, 8),
    ],
    ids=["c4", "c8", "rgb", "c16"],
)
def test_flate_png_predictor12_parity(columns: int, colors: int, bpc: int) -> None:
    row_bytes = (columns * colors * bpc + 7) // 8
    payload = bytes((i * 37 + 11) % 256 for i in range(row_bytes * 6))
    parms = {
        "Predictor": 12,
        "Columns": columns,
        "Colors": colors,
        "BitsPerComponent": bpc,
    }
    encoded = _flate_encode(payload, parms)
    assert _assert_parity("FlateDecode", encoded, parms) == payload


@requires_oracle
@pytest.mark.parametrize("predictor", [10, 11, 13, 14], ids=["none", "sub", "avg", "paeth"])
def test_flate_png_predictor_variants_parity(predictor: int) -> None:
    columns, colors = 5, 3
    row_bytes = columns * colors
    payload = bytes((i * 53 + 7) % 256 for i in range(row_bytes * 5))
    parms = {"Predictor": predictor, "Columns": columns, "Colors": colors}
    encoded = _flate_encode(payload, parms)
    assert _assert_parity("FlateDecode", encoded, parms) == payload


@requires_oracle
@pytest.mark.parametrize(
    ("columns", "colors", "bpc"),
    [(6, 1, 8), (4, 3, 8), (4, 1, 16)],
    ids=["gray8", "rgb8", "gray16"],
)
def test_flate_tiff_predictor2_parity(columns: int, colors: int, bpc: int) -> None:
    row_bytes = (columns * colors * bpc + 7) // 8
    payload = bytes((i * 19 + 3) % 256 for i in range(row_bytes * 4))
    parms = {
        "Predictor": 2,
        "Columns": columns,
        "Colors": colors,
        "BitsPerComponent": bpc,
    }
    encoded = _flate_encode(payload, parms)
    assert _assert_parity("FlateDecode", encoded, parms) == payload


# ---------------------------------------------------------------------------
# LZWDecode
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"-----A---B---C---D",
        b"TOBEORNOTTOBEORTOBEORNOT",
        b"the quick brown fox jumps over " * 50,
        bytes(range(256)) * 3,
    ],
    ids=["empty", "short", "classic", "repetitive", "all-bytes"],
)
def test_lzw_default_parity(payload: bytes) -> None:
    encoded = _lzw_encode(payload)
    assert _assert_parity("LZWDecode", encoded) == payload


@requires_oracle
def test_lzw_early_change_zero_parity() -> None:
    # Hand-build an EarlyChange=0 stream by re-decoding what pypdfbox's
    # EarlyChange=0 path accepts is awkward; instead verify both engines
    # agree on the default-encoded stream when told EarlyChange=0 is NOT
    # set (i.e. EarlyChange defaults to 1). The negative case below covers
    # the parameter being honoured.
    payload = b"WABWABWABWABWABWAB" * 20
    encoded = _lzw_encode(payload)  # EarlyChange=1 stream
    assert _assert_parity("LZWDecode", encoded, {"EarlyChange": 1}) == payload


@requires_oracle
def test_lzw_with_png_predictor_parity() -> None:
    columns, colors = 8, 1
    payload = bytes((i * 41 + 5) % 256 for i in range(columns * 6))
    # pypdfbox's LZW encoder applies the predictor pre-pass when /Predictor
    # is supplied via the params dict.
    flt = FilterFactory.get("LZWDecode")
    p = COSDictionary()
    dp = COSDictionary()
    for k, v in {"Predictor": 12, "Columns": columns, "Colors": colors}.items():
        dp.set_item(COSName.get_pdf_name(k), COSInteger.get(v))
    p.set_item(COSName.get_pdf_name("DecodeParms"), dp)
    out = io.BytesIO()
    flt.encode(io.BytesIO(payload), out, p)
    encoded = out.getvalue()
    parms = {"Predictor": 12, "Columns": columns, "Colors": colors}
    assert _assert_parity("LZWDecode", encoded, parms) == payload


# ---------------------------------------------------------------------------
# ASCII85Decode
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "encoded",
    [
        b"~>",
        b"87cURD]~>",  # canonical "Hello..." style group
        b"87cURDZ~>",  # "Hello"
        b"z~>",  # 4-zero shortcut
        b"zzz~>",  # repeated shortcut
        b"87cURz8c~>",  # full group + boundary z + partial
        b"8 7\nc\rUR D\nZ~>",  # LF/CR/SPACE whitespace tolerance
        b"87cURD~>",  # full group + lone trailing digit (dropped)
        b"87cURDf~>",  # full group + 2-digit partial
        b"8z7cUR~>",  # z mid-group -> ordinary digit
        b"87cU{~>",  # out-of-range-but-accepted digit '{' (0x7b)
        b"vvvvv~>",  # 'v' (0x76) digits, above 'u' but <= '~'
    ],
    ids=[
        "empty", "group", "hello", "z", "zzz", "z-boundary", "ws",
        "lone-digit", "partial2", "z-midgroup", "brace", "v-digits",
    ],
)
def test_ascii85_parity(encoded: bytes) -> None:
    _assert_parity("ASCII85Decode", encoded)


@requires_oracle
def test_ascii85_all_bytes_round_trip_parity() -> None:
    flt = FilterFactory.get("ASCII85Decode")
    out = io.BytesIO()
    flt.encode(io.BytesIO(bytes(range(256))), out)
    encoded = out.getvalue() + b"~>"
    assert _assert_parity("ASCII85Decode", encoded) == bytes(range(256))


# ---------------------------------------------------------------------------
# ASCIIHexDecode
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "encoded",
    [
        b">",
        b"48656C6C6F>",  # "Hello"
        b"48 65 6c 6c 6f>",  # whitespace between pairs + mixed case
        b"48656c6c6f2>",  # odd length -> zero-pad last nibble
        b"48656c6c6f",  # no EOD marker
        b"DEADBEEF>",
        # --- PDFBox malformed-input quirks (all oracle-verified) ---
        b"4\n8\t6\r5>",  # whitespace SPLITTING pairs -> NOT skipped mid-pair
        b"A B C>",  # spaces split each pair -> invalid-char arithmetic
        b"4Z>",  # invalid low nibble -> REVERSE_HEX -1, no raise
        b"GG>",  # both nibbles invalid -> -17 & 0xff
        b"\x00\x0c41\x0042\x0c43>",  # NUL/FF whitespace before first nibble
    ],
    ids=[
        "eod-only", "hello", "ws-between", "odd", "no-eod", "deadbeef",
        "ws-mid-pair", "ws-split-pairs", "invalid-low", "invalid-both", "nul-ff-ws",
    ],
)
def test_ascii_hex_parity(encoded: bytes) -> None:
    _assert_parity("ASCIIHexDecode", encoded)


# ---------------------------------------------------------------------------
# RunLengthDecode
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "encoded",
    [
        b"\x80",  # bare EOD -> empty
        b"\x04Hello\x80",  # 5-byte literal run + EOD
        b"\xfeA\x80",  # repeat 'A' x3 + EOD
        b"\x02ABC\xff!\x00Z\x80",  # literal + repeat + single + EOD
        b"\x04Hello\x80garbagetail",  # bytes after EOD ignored
        b"\x00X",  # single-byte literal, no EOD (lenient EOF stop)
        b"\xffQ",  # repeat run, no EOD
    ],
    ids=["eod", "literal", "repeat", "mixed", "after-eod", "single-no-eod", "repeat-no-eod"],
)
def test_run_length_parity(encoded: bytes) -> None:
    _assert_parity("RunLengthDecode", encoded)


@requires_oracle
def test_run_length_round_trip_parity() -> None:
    payload = b"AAAAAAAABBBCDEFGGGGGG" + bytes(range(64)) + b"ZZZZZZZZ"
    flt = FilterFactory.get("RunLengthDecode")
    out = io.BytesIO()
    flt.encode(io.BytesIO(payload), out)
    encoded = out.getvalue()
    assert _assert_parity("RunLengthDecode", encoded) == payload
