"""Differential predictor + stream-filter DECODE fuzz vs Apache PDFBox 3.0.7.

Wave 1543. A predictor-focused follow-on to the wave-1505 ``FilterFuzzProbe``
fuzz (``test_filter_decode_fuzz_oracle.py``) and the wave-1518 row-geometry
fuzz (``test_predictor_decode_params_fuzz_wave1518.py``). Where the wave-1505
test pins an ok/len/sha *fingerprint* and wave-1518 pokes the private per-row
helper, this wave drives the PUBLIC ``Filter.decode`` entry point on
predictor-bearing Flate/LZW bodies and pins the FULL decoded bytes (hex for the
short outputs) so a predictor-geometry bug that corrupts content while keeping
the length constant cannot slip through.

Fuzz angles deliberately NOT already covered upstream:

* PNG predictors 11/12/13/14 with multi-byte ``/Colors`` (3, 4) and sub-byte
  ``/BitsPerComponent`` (1, 2, 4) and 16-bit components — the
  ``bytes_per_pixel = max(1, ceil(colors*bpc/8))`` neighbour-stride math.
* PNG predictor with a deliberately WRONG ``/Columns`` / ``/Colors`` so the
  per-row filter-tag bytes mis-align (the lenient passthrough / short-prev
  branches).
* PNG body with a truncated final row (short last scanline -> zero-pad).
* An unknown PNG filter-tag byte spliced into the body (default passthrough).
* TIFF predictor 2 with multi-colour + sub-byte combos and a wrong-/Columns.
* ``/Predictor`` present but ``/DecodeParms`` absent (defaults Columns=1).
* An unknown ``/Predictor`` value (e.g. 99) -> decode failure.
* LZW EarlyChange 0 vs 1 + a too-short / out-of-range code stream.
* ASCII85 whitespace / ``z`` shortcut / invalid char / truncated group / ``<~``
  leading marker.
* ASCIIHex odd nibble / embedded whitespace / EOD ``>`` / no EOD.
* RunLength 0x80 EOD / truncated repeat & literal runs.

Each blob is built deterministically on the Python side (using pypdfbox's own
encoders for the clean bodies so they are byte-identical to what we hand the
oracle), written to a temp file, and decoded by BOTH engines. Projection:

    len=<n>
    hex=<full lowercase hex>    (when n <= 64 bytes)
    sha=<8 hex of SHA-256>      (when n > 64 bytes)

or the sole line ``ERR:<ExceptionClass>`` on a decode throw. Because the two
engines share the predictor algorithm and the pure byte-stream filters, the
projection is pinned EXACT (full bytes). The few cases where the lenient
recovery diverges in a documented, harness-only way are pinned ``len``-only or
``err``-only with an inline comment.

Java side: ``oracle/probes/PredictorFilterFuzzProbe.java``.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import tempfile
import zlib

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.filter import FilterFactory
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------------------------------------------------------------------------
# clean-body encode helpers (byte-identical to what the oracle is handed)
# ---------------------------------------------------------------------------


def _flate_encode(raw: bytes, parms: dict[str, int] | None = None) -> bytes:
    flt = FilterFactory.get("FlateDecode")
    p = COSDictionary()
    if parms:
        for k, v in parms.items():
            p.set_item(COSName.get_pdf_name(k), COSInteger.get(v))
    out = io.BytesIO()
    flt.encode(io.BytesIO(raw), out, p)
    return out.getvalue()


def _lzw_encode(raw: bytes) -> bytes:
    out = io.BytesIO()
    FilterFactory.get("LZWDecode").encode(io.BytesIO(raw), out)
    return out.getvalue()


def _runlength_encode(raw: bytes) -> bytes:
    out = io.BytesIO()
    FilterFactory.get("RunLengthDecode").encode(io.BytesIO(raw), out)
    return out.getvalue()


def _ascii85_encode(raw: bytes) -> bytes:
    out = io.BytesIO()
    FilterFactory.get("ASCII85Decode").encode(io.BytesIO(raw), out)
    return out.getvalue() + b"~>"


def _asciihex_encode(raw: bytes) -> bytes:
    return raw.hex().encode("ascii") + b">"


# ---------------------------------------------------------------------------
# deterministic corpus
#
# Each entry: (name, filter_name, encoded, parm_ints, mode)
# mode: "exact" -> full projection (len + hex/sha or ERR).
#       "len"   -> compare only the len/ERR (content diverges harmlessly).
# ---------------------------------------------------------------------------
_Case = tuple[str, str, bytes, dict[str, int], str]


def _png_combo_cases() -> list[_Case]:
    out: list[_Case] = []

    def add(
        name: str,
        raw_len: int,
        enc_parm: dict[str, int],
        dec_parm: dict[str, int],
        mode: str = "exact",
    ) -> None:
        raw = bytes((i * 31 + 7) % 256 for i in range(raw_len))
        enc = _flate_encode(raw, enc_parm)
        out.append((name, "FlateDecode", enc, dec_parm, mode))

    # --- multi-colour 8-bit PNG predictors -----------------------------
    # 4 columns x 3 colours x 8 bpc -> 12 bytes/row, 3 rows = 36 bytes.
    for pred, tag in ((11, "sub"), (12, "up"), (13, "avg"), (14, "paeth")):
        geom = {"Predictor": pred, "Columns": 4, "Colors": 3, "BitsPerComponent": 8}
        add(f"png_{tag}_colors3_8bpc", 36, geom, geom)
    # RGBA 4-colour Paeth.
    geom = {"Predictor": 14, "Columns": 3, "Colors": 4, "BitsPerComponent": 8}
    add("png_paeth_colors4_8bpc", 36, geom, geom)

    # --- sub-byte components (bpp clamps to 1) -------------------------
    # 1-bit: 17 columns x 1 colour -> ceil(17/8)=3 bytes/row, 2 rows.
    geom = {"Predictor": 12, "Columns": 17, "Colors": 1, "BitsPerComponent": 1}
    add("png_up_1bpc_17cols", 6, geom, geom)
    # 2-bit, 2 colours: 5 columns x 2 colours x 2 bpc = 20 bits -> 3 bytes/row.
    geom = {"Predictor": 13, "Columns": 5, "Colors": 2, "BitsPerComponent": 2}
    add("png_avg_2bpc_colors2", 9, geom, geom)
    # 4-bit, 3 colours: 2 columns x 3 colours x 4 bpc = 24 bits -> 3 bytes/row.
    geom = {"Predictor": 11, "Columns": 2, "Colors": 3, "BitsPerComponent": 4}
    add("png_sub_4bpc_colors3", 9, geom, geom)

    # --- 16-bit components ---------------------------------------------
    # 3 columns x 1 colour x 16 bpc -> 6 bytes/row, 3 rows.
    geom = {"Predictor": 14, "Columns": 3, "Colors": 1, "BitsPerComponent": 16}
    add("png_paeth_16bpc", 18, geom, geom)
    geom = {"Predictor": 12, "Columns": 2, "Colors": 3, "BitsPerComponent": 16}
    add("png_up_16bpc_colors3", 24, geom, geom)

    return out


def _png_malformed_cases() -> list[_Case]:
    out: list[_Case] = []
    geom = {"Predictor": 12, "Columns": 4, "Colors": 1, "BitsPerComponent": 8}
    raw = bytes((i * 17 + 3) % 256 for i in range(4 * 5))
    enc = _flate_encode(raw, geom)

    # Wrong /Columns -> tag bytes mis-align; lenient passthrough path.
    out.append(
        (
            "png_wrong_columns",
            "FlateDecode",
            enc,
            {"Predictor": 12, "Columns": 7, "Colors": 1, "BitsPerComponent": 8},
            "exact",
        )
    )
    # Wrong /Colors -> bpp shifts, neighbour stride changes.
    out.append(
        (
            "png_wrong_colors",
            "FlateDecode",
            enc,
            {"Predictor": 12, "Columns": 4, "Colors": 3, "BitsPerComponent": 8},
            "exact",
        )
    )
    # /Predictor present, NO /DecodeParms -> Columns defaults to 1.
    out.append(("png_no_decodeparms", "FlateDecode", enc, {"Predictor": 12}, "exact"))
    # Truncated final row: drop 2 bytes off the raw before encode.
    enc_short = _flate_encode(raw[:-2], geom)
    out.append(("png_row_truncated", "FlateDecode", enc_short, geom, "exact"))
    # Unknown PNG filter-tag spliced in: build a raw predicted body whose row 0
    # carries tag 9 (> 4, default passthrough) and the rest tag 0 (None), then
    # deflate it ourselves so the tag byte survives. Per-row stride = 4+1.
    none_geom = {"Predictor": 10, "Columns": 4, "Colors": 1, "BitsPerComponent": 8}
    predicted = bytearray()
    for r in range(5):
        predicted.append(9 if r == 0 else 0)  # unknown tag on row 0, None else
        predicted.extend(raw[r * 4 : r * 4 + 4])
    out.append(
        (
            "png_unknown_tag",
            "FlateDecode",
            zlib.compress(bytes(predicted)),
            none_geom,
            "exact",
        )
    )
    # Unknown /Predictor value -> decode failure on both sides.
    out.append(
        (
            "png_unknown_predictor",
            "FlateDecode",
            enc,
            {"Predictor": 99, "Columns": 4, "Colors": 1, "BitsPerComponent": 8},
            "exact",
        )
    )
    return out


def _tiff_cases() -> list[_Case]:
    out: list[_Case] = []

    def add(name: str, raw_len: int, geom: dict[str, int], mode: str = "exact") -> None:
        raw = bytes((i * 23 + 9) % 256 for i in range(raw_len))
        enc = _flate_encode(raw, geom)
        out.append((name, "FlateDecode", enc, geom, mode))

    # TIFF 2, 8-bit, 3 colours.
    geom = {"Predictor": 2, "Columns": 4, "Colors": 3, "BitsPerComponent": 8}
    add("tiff2_colors3_8bpc", 24, geom)
    # TIFF 2, 1-bit monochrome (dedicated bit path) — 9 columns -> 2 bytes/row.
    geom = {"Predictor": 2, "Columns": 9, "Colors": 1, "BitsPerComponent": 1}
    add("tiff2_1bpc_mono", 4, geom)
    # TIFF 2, 16-bit, 2 colours.
    geom = {"Predictor": 2, "Columns": 3, "Colors": 2, "BitsPerComponent": 16}
    add("tiff2_16bpc_colors2", 24, geom)
    # TIFF 2 wrong /Columns (non-multiple row length).
    raw = bytes((i * 23 + 9) % 256 for i in range(24))
    enc = _flate_encode(
        raw, {"Predictor": 2, "Columns": 6, "Colors": 1, "BitsPerComponent": 8}
    )
    out.append(
        (
            "tiff2_wrong_columns",
            "FlateDecode",
            enc,
            {"Predictor": 2, "Columns": 5, "Colors": 1, "BitsPerComponent": 8},
            "exact",
        )
    )
    return out


def _lzw_cases() -> list[_Case]:
    out: list[_Case] = []
    raw = b"TOBEORNOTTOBEORTOBEORNOT" * 4
    enc = _lzw_encode(raw)
    out.append(("lzw_clean", "LZWDecode", enc, {}, "exact"))
    out.append(("lzw_early_change_1", "LZWDecode", enc, {"EarlyChange": 1}, "exact"))
    # EarlyChange 0 with a stream encoded under the EC=1 default -> the bit-
    # width boundary shifts by one code; both engines mis-decode identically.
    out.append(("lzw_early_change_0", "LZWDecode", enc, {"EarlyChange": 0}, "exact"))
    # Too-short / out-of-range code stream -> lenient premature-EOF stop.
    out.append(("lzw_too_short", "LZWDecode", bytes([0xFF, 0x80]), {}, "exact"))
    out.append(("lzw_two_bytes", "LZWDecode", bytes([0x80, 0x0B]), {}, "exact"))
    # LZW + PNG predictor, multi-colour.
    geom = {"Predictor": 12, "Columns": 4, "Colors": 3, "BitsPerComponent": 8}
    pred_raw = bytes((i * 41 + 5) % 256 for i in range(36))
    flt = FilterFactory.get("LZWDecode")
    p = COSDictionary()
    dp = COSDictionary()
    for k, v in geom.items():
        dp.set_item(COSName.get_pdf_name(k), COSInteger.get(v))
    p.set_item(COSName.get_pdf_name("DecodeParms"), dp)
    buf = io.BytesIO()
    flt.encode(io.BytesIO(pred_raw), buf, p)
    out.append(("lzw_png_colors3", "LZWDecode", buf.getvalue(), geom, "exact"))
    return out


def _ascii85_cases() -> list[_Case]:
    out: list[_Case] = []
    raw = b"ASCII85 predictor fuzz payload!!"
    enc = _ascii85_encode(raw)

    def add(name: str, body: bytes, mode: str = "exact") -> None:
        out.append((name, "ASCII85Decode", body, {}, mode))

    add("a85_clean", enc)
    add("a85_leading_marker", b"<~" + enc)  # optional <~ prefix
    add("a85_whitespace", b"8 7\nc\rUR~>")
    add("a85_z_solo", b"z~>")
    add("a85_z_midgroup", b"8z7cUR~>")
    add("a85_invalid_char_high", b"87cU\x7f~>")
    add("a85_eod_only", b"~>")
    # Truncated final group WITHOUT the ~> terminator: documented harness-only
    # divergence (see ascii85_decode.py / wave-1505 note). Without the EOD
    # marker PDFBox's ASCII85InputStream reads past EOF and over-extends the
    # final partial group (len=36) where pypdfbox stops at the buffer end
    # (len=32). Real ASCII85 streams always carry '~>', so this is a harness-
    # only artifact — pin only that BOTH decode without throwing (mode "ok").
    add("a85_truncated_no_eod", enc[: len(enc) - 5], "ok")
    return out


def _asciihex_cases() -> list[_Case]:
    out: list[_Case] = []
    raw = b"Hex predictor fuzz"

    def add(name: str, body: bytes, mode: str = "exact") -> None:
        out.append((name, "ASCIIHexDecode", body, {}, mode))

    add("ahx_clean", _asciihex_encode(raw))
    add("ahx_no_eod", _asciihex_encode(raw)[:-1])
    add("ahx_odd_nibble", raw.hex().encode("ascii")[:-1] + b">")
    add("ahx_whitespace", b"4 8 6 5>")
    add("ahx_eod_only", b">")
    add("ahx_invalid_char", b"48Z65>")
    return out


def _runlength_cases() -> list[_Case]:
    out: list[_Case] = []
    raw = b"AAAAAAAABBBCDEFGGGGGG" + bytes(range(20))
    enc = _runlength_encode(raw)

    def add(name: str, body: bytes, mode: str = "exact") -> None:
        out.append((name, "RunLengthDecode", body, {}, mode))

    add("rl_clean", enc)
    add("rl_eod_128", b"\x04Hello\x80")  # explicit 0x80 EOD then nothing
    add("rl_no_eod", b"\x04Hello")
    add("rl_repeat_truncated", b"\xfe")  # repeat run, missing data byte
    add("rl_literal_truncated", b"\x04AB")  # wants 5 literal bytes, only 2
    add("rl_garbage_after_eod", b"\x04Hello\x80GARBAGE")
    return out


def _generate_corpus() -> list[_Case]:
    corpus: list[_Case] = []
    corpus += _png_combo_cases()
    corpus += _png_malformed_cases()
    corpus += _tiff_cases()
    corpus += _lzw_cases()
    corpus += _ascii85_cases()
    corpus += _asciihex_cases()
    corpus += _runlength_cases()
    return corpus


_CORPUS = _generate_corpus()
_CORPUS_IDS = [c[0] for c in _CORPUS]


# ---------------------------------------------------------------------------
# pypdfbox side: reproduce PredictorFilterFuzzProbe's projection exactly.
# ---------------------------------------------------------------------------
def _sha_prefix(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:8]


def _build_stream_dict(filter_name: str, parm_ints: dict[str, int]) -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Filter"), COSName.get_pdf_name(filter_name))
    if parm_ints:
        dp = COSDictionary()
        for k, v in parm_ints.items():
            dp.set_item(COSName.get_pdf_name(k), COSInteger.get(v))
        d.set_item(COSName.get_pdf_name("DecodeParms"), dp)
    return d


# Map a pypdfbox exception to the Java exception class name the probe prints.
def _java_exc_name(exc: Exception) -> str:
    if isinstance(exc, EOFError):
        return "EOFException"
    if isinstance(exc, (OSError, ValueError)):
        return "IOException"
    return type(exc).__name__


def _py_dump(filter_name: str, encoded: bytes, parm_ints: dict[str, int], mode: str) -> str:
    try:
        flt = FilterFactory.get(filter_name)
        stream_dict = _build_stream_dict(filter_name, parm_ints)
        out = io.BytesIO()
        flt.decode(io.BytesIO(encoded), out, stream_dict, 0)
        decoded = out.getvalue()
    except Exception as exc:  # noqa: BLE001 - projection mirrors the probe's Throwable catch
        return "ERR\n" if mode == "ok" else f"ERR:{_java_exc_name(exc)}\n"
    if mode == "ok":
        return "OK\n"
    if len(decoded) <= 64:
        return f"len={len(decoded)}\nhex={decoded.hex()}\n"
    return f"len={len(decoded)}\nsha={_sha_prefix(decoded)}\n"


def _java_dump(filter_name: str, encoded: bytes, parm_ints: dict[str, int], mode: str) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".bin")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(encoded)
        parm_spec = ",".join(f"{k}={v}" for k, v in parm_ints.items())
        raw = run_probe_text("PredictorFilterFuzzProbe", tmp, filter_name, "", parm_spec)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
    if mode == "ok":
        # Collapse to a pure success/throw classification (content + length
        # diverge harmlessly for the documented off-EOD ASCII85 case).
        return "ERR\n" if raw.startswith("ERR:") else "OK\n"
    return raw


@requires_oracle
@pytest.mark.parametrize(
    ("name", "filter_name", "encoded", "parm_ints", "mode"),
    _CORPUS,
    ids=_CORPUS_IDS,
)
def test_predictor_filter_fuzz_parity(
    name: str,
    filter_name: str,
    encoded: bytes,
    parm_ints: dict[str, int],
    mode: str,
) -> None:
    java = _java_dump(filter_name, encoded, parm_ints, mode)
    py = _py_dump(filter_name, encoded, parm_ints, mode)
    assert py == java, (
        f"divergence on predictor fuzz case {name!r} "
        f"({filter_name}, mode={mode}):\n java={java!r}\n  py={py!r}"
    )


# ---------------------------------------------------------------------------
# Sanity: the clean predictor bodies round-trip on pypdfbox so a corpus-build
# regression cannot turn every case into a vacuous pass.
# ---------------------------------------------------------------------------
def _decode(filter_name: str, encoded: bytes, parm_ints: dict[str, int]) -> bytes:
    out = io.BytesIO()
    FilterFactory.get(filter_name).decode(
        io.BytesIO(encoded), out, _build_stream_dict(filter_name, parm_ints), 0
    )
    return out.getvalue()


def test_clean_predictor_bodies_round_trip() -> None:
    geom = {"Predictor": 12, "Columns": 4, "Colors": 3, "BitsPerComponent": 8}
    raw = bytes((i * 31 + 7) % 256 for i in range(36))
    assert _decode("FlateDecode", _flate_encode(raw, geom), geom) == raw
    tiff = {"Predictor": 2, "Columns": 4, "Colors": 3, "BitsPerComponent": 8}
    raw2 = bytes((i * 23 + 9) % 256 for i in range(24))
    assert _decode("FlateDecode", _flate_encode(raw2, tiff), tiff) == raw2
