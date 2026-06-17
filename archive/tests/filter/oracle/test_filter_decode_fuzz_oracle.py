"""Differential stream-filter DECODE fuzz vs Apache PDFBox 3.0.7 (wave 1505).

A follow-on to the wave-1503 parser mutation-fuzz and wave-1504 content-stream
fuzz, applying the same deterministic-corpus method to the lenient *stream
filter decode contract* — the path ``COSStream.create_input_stream`` drives when
it hands a (possibly malformed) /Filter body to ``Filter.decode``.

For each filter we craft a small valid encoded body and then apply a fixed set
of byte-level mutations that exercise the lenient-recovery branches: truncated
codes / deflate data, corrupt headers, garbage tails, missing EOD markers,
predictor-geometry mismatches, and out-of-range codes. Both sides decode the
*identical* bytes and are compared on a stable projection:

    ok=true
    len=<decoded byte count>
    sha=<first 8 hex of SHA-256 of the decoded bytes>

or the sole line ``ok=false`` on any decode-time throw. The Java side is
``oracle/probes/FilterFuzzProbe.java``; ``_py_dump`` reproduces the same
fingerprint on the pypdfbox side.

Two REAL divergences this wave found + fixed (both: pypdfbox raised where
PDFBox recovers partial output):

* ``FlateDecode`` used a one-shot ``zlib.decompress`` (strict — raises Error -5
  on a truncated body / missing Z_STREAM_END) instead of routing through
  ``FlateFilterDecoderStream`` (PDFBOX-1232: catch DataFormatException, keep the
  already-inflated bytes). Now matches upstream's partial-inflate tolerance.
* ``LZWDecode`` raised ``OSError`` on a corrupt / out-of-range code; upstream
  throws ``EOFException`` there which its own try/catch turns into a lenient
  "premature EOF" stop (whatever decoded so far is kept). Now raises
  ``EOFError`` to take the same graceful exit.

For the pure byte-stream filters (Flate / LZW / ASCIIHex / ASCII85 /
RunLength) the projection is exact (ok + len + sha): both engines share the
same decode algorithm so byte-equality is the right bar. For the image filters
(CCITTFaxDecode / DCTDecode) the two libraries decode by entirely different
machinery (libtiff / Pillow vs PDFBox's pure-Java codecs) and pad past EOD
differently (CLAUDE.md libtiff/Pillow EOD carve-out), so the *partial-decode*
mutants there are pinned LOOSELY — only the ``ok`` boolean (decode succeeds vs
throws) is compared, never len/sha. The exception (wave 1506) is the CCITT
libtiff-FAILURE path: when libtiff rejects a body outright, ``CCITTFaxDecode``
falls back to a deterministic, fully pypdfbox-constructed ``rows * rowBytes``
zero-fill buffer that reproduces PDFBox's "decoded 0 rows" outcome byte-for-
byte — no codec output is in that buffer, so those mutants are pinned EXACT.

Deterministic generator, fixed PRNG seed ``random.Random(1505)``.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import random
import tempfile
import zlib

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.filter import FilterFactory
from tests.oracle.harness import requires_oracle, run_probe_text

_RNG = random.Random(1505)


# ---------------------------------------------------------------------------
# encode helpers (build the clean bodies we then mutate)
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
# deterministic mutation corpus
#
# Each entry: (name, filter_name, encoded_bytes, stream_ints, parm_ints, mode)
# mode is "exact" (compare ok+len+sha) or "ok" (compare only the ok boolean).
# ---------------------------------------------------------------------------
_Mut = tuple[str, str, bytes, dict[str, int], dict[str, int], str]


def _flate_mutants() -> list[_Mut]:
    raw = b"the quick brown fox jumps over the lazy dog. " * 8
    enc = _flate_encode(raw)
    out: list[_Mut] = []

    def add(name: str, body: bytes, parm: dict[str, int] | None = None) -> None:
        out.append((name, "FlateDecode", body, {}, parm or {}, "exact"))

    add("flate_clean", enc)
    add("flate_empty", _flate_encode(b""))
    add("flate_trunc_half", enc[: len(enc) // 2])
    add("flate_trunc_one_byte", enc[:1])
    add("flate_trunc_drop_adler", enc[:-2])
    add("flate_trunc_drop_one", enc[:-1])
    # corrupt the 2-byte zlib header.
    bad_hdr = bytearray(enc)
    bad_hdr[0] ^= 0xFF
    add("flate_corrupt_header", bytes(bad_hdr))
    # garbage tail after a complete deflate stream.
    add("flate_garbage_tail", enc + b"GARBAGEGARBAGEGARBAGE")
    # raw deflate, no zlib wrapper (documented divergence: pypdfbox recovers,
    # PDFBox yields 0 — so this one is "ok"-only, the len/sha differ).
    co = zlib.compressobj(wbits=-zlib.MAX_WBITS)
    out.append(
        (
            "flate_raw_deflate_no_header",
            "FlateDecode",
            co.compress(raw) + co.flush(),
            {},
            {},
            "ok",
        )
    )
    # flip a byte in the middle of the deflate body.
    mid = bytearray(enc)
    mid[len(mid) // 2] ^= 0xAA
    add("flate_mid_byte_flip", bytes(mid))
    add("flate_just_garbage", b"not a deflate stream at all")

    # -- predictor geometry mismatches (PNG + TIFF) ---------------------
    pred_raw = bytes((i * 37 + 11) % 256 for i in range(4 * 6))
    pred_enc = _flate_encode(
        pred_raw, {"Predictor": 12, "Columns": 4, "Colors": 1, "BitsPerComponent": 8}
    )
    add(
        "flate_png12_correct",
        pred_enc,
        {"Predictor": 12, "Columns": 4, "Colors": 1, "BitsPerComponent": 8},
    )
    add(
        "flate_png12_wrong_columns",
        pred_enc,
        {"Predictor": 12, "Columns": 7, "Colors": 1, "BitsPerComponent": 8},
    )
    add(
        "flate_png12_wrong_colors",
        pred_enc,
        {"Predictor": 12, "Columns": 4, "Colors": 3, "BitsPerComponent": 8},
    )
    add(
        "flate_png12_wrong_bpc",
        pred_enc,
        {"Predictor": 12, "Columns": 4, "Colors": 1, "BitsPerComponent": 16},
    )
    # PNG predictor with a truncated predicted body (drop the last row's tail).
    add(
        "flate_png12_row_truncated",
        _flate_encode(
            pred_raw[:-3],
            {"Predictor": 12, "Columns": 4, "Colors": 1, "BitsPerComponent": 8},
        ),
        {"Predictor": 12, "Columns": 4, "Colors": 1, "BitsPerComponent": 8},
    )
    # TIFF predictor 2 with a non-multiple row size (Columns mismatch).
    tiff_raw = bytes((i * 19 + 3) % 256 for i in range(6 * 4))
    tiff_enc = _flate_encode(
        tiff_raw, {"Predictor": 2, "Columns": 6, "Colors": 1, "BitsPerComponent": 8}
    )
    add(
        "flate_tiff2_correct",
        tiff_enc,
        {"Predictor": 2, "Columns": 6, "Colors": 1, "BitsPerComponent": 8},
    )
    add(
        "flate_tiff2_wrong_columns",
        tiff_enc,
        {"Predictor": 2, "Columns": 5, "Colors": 1, "BitsPerComponent": 8},
    )
    return out


def _lzw_mutants() -> list[_Mut]:
    raw = b"TOBEORNOTTOBEORTOBEORNOT" * 6
    enc = _lzw_encode(raw)
    out: list[_Mut] = []

    def add(
        name: str, body: bytes, parm: dict[str, int] | None = None, mode: str = "exact"
    ) -> None:
        out.append((name, "LZWDecode", body, {}, parm or {}, mode))

    add("lzw_clean", enc)
    add("lzw_empty", _lzw_encode(b""))
    add("lzw_trunc_half", enc[: len(enc) // 2])
    add("lzw_trunc_one_byte", enc[:1])
    add("lzw_drop_eod", enc[:-1])  # likely drops the trailing EOD marker
    add("lzw_garbage_tail", enc + b"\x00\x00\x00")
    # an out-of-range code at the very start: 9-bit 0x1FF = 511.
    add("lzw_invalid_code_first", bytes([0xFF, 0x80]))
    add("lzw_all_ones", b"\xff" * 8)
    add("lzw_just_zero", b"\x00")
    # EarlyChange variants on a clean stream (EC=1 is the encode default).
    add("lzw_early_change_1", enc, {"EarlyChange": 1})
    add("lzw_early_change_0", enc, {"EarlyChange": 0})
    # corrupt a middle byte.
    mid = bytearray(enc)
    if len(mid) > 4:
        mid[len(mid) // 2] ^= 0x55
    add("lzw_mid_byte_flip", bytes(mid))
    # LZW + PNG predictor with wrong columns.
    pred_raw = bytes((i * 41 + 5) % 256 for i in range(8 * 6))
    flt = FilterFactory.get("LZWDecode")
    p = COSDictionary()
    dp = COSDictionary()
    for k, v in {"Predictor": 12, "Columns": 8, "Colors": 1}.items():
        dp.set_item(COSName.get_pdf_name(k), COSInteger.get(v))
    p.set_item(COSName.get_pdf_name("DecodeParms"), dp)
    buf = io.BytesIO()
    flt.encode(io.BytesIO(pred_raw), buf, p)
    pred_enc = buf.getvalue()
    add("lzw_png_correct", pred_enc, {"Predictor": 12, "Columns": 8, "Colors": 1})
    add(
        "lzw_png_wrong_columns",
        pred_enc,
        {"Predictor": 12, "Columns": 5, "Colors": 1},
    )
    return out


def _asciihex_mutants() -> list[_Mut]:
    raw = b"Hello, fuzz!" * 3
    enc = _asciihex_encode(raw)
    out: list[_Mut] = []

    def add(name: str, body: bytes) -> None:
        out.append((name, "ASCIIHexDecode", body, {}, {}, "exact"))

    add("ahx_clean", enc)
    add("ahx_no_eod", enc[:-1])  # drop the '>'
    add("ahx_odd_nibble", raw.hex().encode("ascii")[:-1] + b">")
    add("ahx_invalid_char", b"48Z56C>")
    add("ahx_both_nibbles_invalid", b"GGHH>")
    add("ahx_whitespace_split", b"4 8 6 5>")
    add("ahx_eod_only", b">")
    add("ahx_empty", b"")
    add("ahx_truncated_mid", raw.hex().encode("ascii")[:5])
    add("ahx_nul_ff_ws", b"\x00\x0c48\x0065\x0c6c>")
    return out


def _ascii85_mutants() -> list[_Mut]:
    raw = b"ASCII85 fuzzing payload sample" * 2
    enc = _ascii85_encode(raw)
    out: list[_Mut] = []

    def add(name: str, body: bytes) -> None:
        out.append((name, "ASCII85Decode", body, {}, {}, "exact"))

    add("a85_clean", enc)
    add("a85_no_terminator", enc[:-2])  # drop '~>'
    # Truncating mid-group AND removing the '~>' terminator is the one
    # documented ASCII85 divergence (see ascii85_decode.py header): without
    # the EOD marker PDFBox's ASCII85InputStream reads past EOF and can
    # duplicate / over-extend the final partial group, whereas pypdfbox stops
    # at the buffer end. Real PDF ASCII85 streams always carry '~>', so this
    # is a harness-only artifact — pinned loosely (ok-only), not byte-exact.
    out.append(
        ("a85_truncated_final_group", "ASCII85Decode", enc[: len(enc) - 5], {}, {}, "ok")
    )
    add("a85_z_midgroup", b"8z7cUR~>")
    add("a85_z_solo", b"z~>")
    add("a85_invalid_char_high", b"87cU\x7f~>")  # 0x7f, above '~'
    add("a85_empty_eod", b"~>")
    add("a85_empty", b"")
    add("a85_lone_digit", b"87cURD~>")
    add("a85_brace_digit", b"87cU{~>")
    add("a85_whitespace", b"8 7\nc\rUR~>")
    return out


def _runlength_mutants() -> list[_Mut]:
    raw = b"AAAAAAAABBBCDEFGGGGGG" + bytes(range(40)) + b"ZZZZZ"
    enc = _runlength_encode(raw)
    out: list[_Mut] = []

    def add(name: str, body: bytes) -> None:
        out.append((name, "RunLengthDecode", body, {}, {}, "exact"))

    add("rl_clean", enc)
    add("rl_no_eod", enc.rstrip(b"\x80"))  # drop trailing 0x80 EOD
    add("rl_eod_only", b"\x80")
    add("rl_empty", b"")
    add("rl_literal_overrun", b"\x7fABC")  # length byte 127 -> wants 128 bytes
    add("rl_repeat_truncated", b"\xfe")  # repeat-run length byte, no data byte
    add("rl_literal_truncated", b"\x04AB")  # wants 5 literal bytes, only 2
    add("rl_garbage_after_eod", b"\x04Hello\x80GARBAGE")
    add("rl_single_no_eod", b"\x00X")
    add("rl_repeat_no_eod", b"\xffQ")
    return out


def _ccitt_encode(raw: bytes, cols: int, rows: int, k: int) -> bytes:
    flt = FilterFactory.get("CCITTFaxDecode")
    p = COSDictionary()
    dp = COSDictionary()
    for kk, vv in {"K": k, "Columns": cols, "Rows": rows}.items():
        dp.set_item(COSName.get_pdf_name(kk), COSInteger.get(vv))
    p.set_item(COSName.get_pdf_name("DecodeParms"), dp)
    out = io.BytesIO()
    flt.encode(io.BytesIO(raw), out, p)
    return out.getvalue()


def _ccitt_mutants() -> list[_Mut]:
    """CCITT mutants vs Apache PDFBox.

    LIBRARY-GAP CONTRACT (wave 1506, closing the wave-1505 deferral): PDFBox's
    pure-Java ``CCITTFaxDecoderStream`` pre-allocates a fixed
    ``(cols+7)/8 * rows`` buffer (zero-filled), fills only the scanlines it
    manages to decode, swallows the EOF/AIOOBE on the rest, and — when
    /BlackIs1 is false — inverts the whole buffer (``CCITTFaxFilter.decode`` →
    ``readFromDecoderStream``). It therefore NEVER throws on a malformed body:
    a truncated / garbage / empty strip yields a fixed WHITE buffer (decoded
    0 rows → all 0xFF). pypdfbox decodes via libtiff (Pillow), which is
    materially stricter and *raises* on those inputs — so ``CCITTFaxDecode``
    now wraps libtiff failures in a deterministic, pypdfbox-constructed
    ``rows * rowBytes`` zero-fill that reproduces upstream's outcome byte-for-
    byte (and empty bodies no longer short-circuit to 0 bytes).

    Pinning split:

    * libtiff-FAILURE cases (truncated G4 / garbage / empty with /Rows known) →
      the fallback buffer is entirely pypdfbox-constructed and deterministic,
      so they are pinned ``exact`` (ok + len + sha) — NOT subject to the
      libtiff EOD carve-out (no codec output is in the buffer).
    * libtiff-SUCCESS-with-partial-content cases (a wrong-/Columns geometry or
      a truncated G3 strip that libtiff decodes to *some* bytes) → the head
      bytes are libtiff/Pillow codec output and differ from PDFBox's pure-Java
      bytes (CLAUDE.md libtiff EOD carve-out), so they stay ``ok``-only.
    * the /Rows==0-with-no-/Height case is now pinned ``exact`` (wave 1507,
      closing the wave-1506 deferral): the filter mirrors
      ``CCITTFaxFilter.decode`` exactly — ``arraySize = rowBytes *
      max(rows, height) == 0`` → ZERO bytes. pypdfbox formerly invented a
      data-driven row estimate inside the filter; that estimator now lives only
      in the standalone ``CCITTFaxDecoderStream`` consumer (which genuinely
      discovers its own row count), not in the filter contract. Both sides
      emit an empty body here, so it is byte-exact.
    """
    out: list[_Mut] = []
    stream = {"Width": 8, "Height": 2}
    raw = bytes([0b10101010, 0b11001100])  # 8x2 bilevel image
    g4 = _ccitt_encode(raw, 8, 2, -1)
    g3 = _ccitt_encode(raw, 8, 2, 0)

    def add(
        name: str, body: bytes, k: int, cols: int, rows: int, mode: str
    ) -> None:
        out.append(
            (
                name,
                "CCITTFaxDecode",
                body,
                stream,
                {"K": k, "Columns": cols, "Rows": rows},
                mode,
            )
        )

    # --- cases where libtiff and PDFBox already agreed (kept) -------------
    add("ccitt_g3_1d_garbage", bytes([0xAA, 0x55, 0xAA, 0x55]), 0, 8, 2, "ok")
    add("ccitt_g3_2d_garbage", bytes([0xFF, 0x00, 0xFF]), 1, 8, 2, "ok")

    # --- libtiff-FAILURE -> deterministic zero-fill, pinned EXACT ---------
    # (the four mutants wave 1505 dropped, now closed at byte parity).
    # Empty G4 body with /Rows known: upstream allocates 2x1 bytes, decodes
    # zero rows, inverts -> 0xFF*2; pypdfbox no longer short-circuits to 0.
    add("ccitt_g4_empty", b"", -1, 8, 2, "exact")
    # Truncated G4 strip: libtiff rejects -> zero-fill 0xFF*2 == PDFBox.
    add("ccitt_g4_truncated", g4[: len(g4) // 2], -1, 8, 2, "exact")
    # Random non-CCITT bytes with /Rows known: libtiff rejects -> zero-fill.
    add("ccitt_garbage_rows_known", b"\x00\x00\x00\x00\x00", -1, 8, 2, "exact")

    # --- libtiff-SUCCESS-with-partial-content -> codec-dependent, OK-only -
    # Wrong /Columns: both engines decode *some* bytes; head bytes are codec
    # output (libtiff EOD carve-out), so only the ok boolean is pinned.
    add("ccitt_g4_wrong_columns", g4, -1, 32, 2, "ok")
    # Truncated G3 strip: libtiff decodes partial content that differs from
    # PDFBox's zero-fill (libtiff did NOT fail here) — ok-only.
    add("ccitt_g3_truncated", g3[: len(g3) // 2], 0, 8, 2, "ok")

    # --- /Rows==0 with no /Height -> arraySize == 0 -> EXACT (zero bytes) --
    # Both engines emit nothing: upstream's allocation is empty, and pypdfbox
    # now mirrors that (no more filter-level row estimation). Stream dict is {}
    # (no /Height), /Rows is 0, so max(rows, height) == 0.
    out.append(
        (
            "ccitt_g4_zero_rows",
            "CCITTFaxDecode",
            g4,
            {},
            {"K": -1, "Columns": 8, "Rows": 0},
            "exact",
        )
    )
    return out


def _dct_mutants() -> list[_Mut]:
    """DCT mutants — LOOSE (ok-only): JPEG decoding is decoder-dependent
    (Pillow vs ImageIO), so only the ok/throw classification is pinned."""
    out: list[_Mut] = []
    # Minimal JPEG SOI + garbage (not a complete frame).
    jpeg_soi = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"

    def add(name: str, body: bytes) -> None:
        out.append((name, "DCTDecode", body, {}, {}, "ok"))

    add("dct_soi_only", b"\xff\xd8")
    add("dct_truncated_header", jpeg_soi)
    add("dct_garbage", b"not a jpeg at all, just bytes")
    # An EMPTY DCT body now matches upstream (wave 1506, closing the wave-1505
    # deferral): pypdfbox no longer short-circuits to ok / 0 bytes; like
    # PDFBox's DCTFilter (which feeds the empty stream to ImageIO -> no SOI
    # marker -> throw) it surfaces ok=false. Both sides classify as a throw.
    add("dct_empty", b"")
    return out


def _generate_corpus() -> list[_Mut]:
    corpus: list[_Mut] = []
    corpus += _flate_mutants()
    corpus += _lzw_mutants()
    corpus += _asciihex_mutants()
    corpus += _ascii85_mutants()
    corpus += _runlength_mutants()
    corpus += _ccitt_mutants()
    corpus += _dct_mutants()
    # A handful of randomised byte flips on the clean flate / lzw bodies.
    flate_clean = _flate_encode(b"random flip target " * 6)
    lzw_clean = _lzw_encode(b"random flip target " * 6)
    for i in range(3):
        b = bytearray(flate_clean)
        b[_RNG.randrange(2, len(b))] ^= 1 << _RNG.randrange(8)
        corpus.append(
            (f"flate_rand_flip_{i}", "FlateDecode", bytes(b), {}, {}, "exact")
        )
    for i in range(3):
        b = bytearray(lzw_clean)
        b[_RNG.randrange(len(b))] ^= 1 << _RNG.randrange(8)
        corpus.append((f"lzw_rand_flip_{i}", "LZWDecode", bytes(b), {}, {}, "exact"))
    return corpus


_CORPUS = _generate_corpus()
_CORPUS_IDS = [m[0] for m in _CORPUS]


# ---------------------------------------------------------------------------
# pypdfbox side: reproduce FilterFuzzProbe's projection exactly.
# ---------------------------------------------------------------------------
def _sha_prefix(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:8]


def _build_stream_dict(
    filter_name: str, stream_ints: dict[str, int], parm_ints: dict[str, int]
) -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Filter"), COSName.get_pdf_name(filter_name))
    for k, v in stream_ints.items():
        d.set_item(COSName.get_pdf_name(k), COSInteger.get(v))
    if parm_ints:
        dp = COSDictionary()
        for k, v in parm_ints.items():
            dp.set_item(COSName.get_pdf_name(k), COSInteger.get(v))
        d.set_item(COSName.get_pdf_name("DecodeParms"), dp)
    return d


def _py_dump(
    filter_name: str,
    encoded: bytes,
    stream_ints: dict[str, int],
    parm_ints: dict[str, int],
    mode: str,
) -> str:
    try:
        flt = FilterFactory.get(filter_name)
        stream_dict = _build_stream_dict(filter_name, stream_ints, parm_ints)
        out = io.BytesIO()
        flt.decode(io.BytesIO(encoded), out, stream_dict, 0)
        decoded = out.getvalue()
    except Exception:
        return "ok=false\n"
    if mode == "ok":
        return "ok=true\n"
    return f"ok=true\nlen={len(decoded)}\nsha={_sha_prefix(decoded)}\n"


def _java_dump(
    filter_name: str,
    encoded: bytes,
    stream_ints: dict[str, int],
    parm_ints: dict[str, int],
    mode: str,
) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".bin")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(encoded)
        stream_spec = ",".join(f"{k}={v}" for k, v in stream_ints.items())
        parm_spec = ",".join(f"{k}={v}" for k, v in parm_ints.items())
        raw = run_probe_text(
            "FilterFuzzProbe", tmp, filter_name, stream_spec, parm_spec
        )
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
    if mode == "ok":
        # Collapse to the ok line only (drop len/sha for the loose filters).
        return "ok=false\n" if raw.startswith("ok=false") else "ok=true\n"
    return raw


# ---------------------------------------------------------------------------
# Differential parity: every mutant must produce the identical projection.
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.parametrize(
    ("name", "filter_name", "encoded", "stream_ints", "parm_ints", "mode"),
    _CORPUS,
    ids=_CORPUS_IDS,
)
def test_filter_decode_fuzz_parity(
    name: str,
    filter_name: str,
    encoded: bytes,
    stream_ints: dict[str, int],
    parm_ints: dict[str, int],
    mode: str,
) -> None:
    java = _java_dump(filter_name, encoded, stream_ints, parm_ints, mode)
    py = _py_dump(filter_name, encoded, stream_ints, parm_ints, mode)
    assert py == java, (
        f"divergence on filter mutant {name!r} ({filter_name}, mode={mode}):\n"
        f" java={java!r}\n  py={py!r}"
    )


# ---------------------------------------------------------------------------
# Sanity: the clean bodies decode to their original payloads on pypdfbox, so a
# corpus-build regression can't silently turn every mutant into a vacuous pass.
# ---------------------------------------------------------------------------
def _decode_only(filter_name: str, encoded: bytes) -> bytes:
    out = io.BytesIO()
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Filter"), COSName.get_pdf_name(filter_name))
    FilterFactory.get(filter_name).decode(io.BytesIO(encoded), out, d, 0)
    return out.getvalue()


def test_clean_bodies_round_trip() -> None:
    assert _decode_only("FlateDecode", _flate_encode(b"abc" * 10)) == b"abc" * 10
    assert _decode_only("LZWDecode", _lzw_encode(b"abc" * 10)) == b"abc" * 10
    assert _decode_only("ASCIIHexDecode", _asciihex_encode(b"abc")) == b"abc"
    assert _decode_only("ASCII85Decode", _ascii85_encode(b"abcdef")) == b"abcdef"
    assert _decode_only("RunLengthDecode", _runlength_encode(b"aaa" * 5)) == b"aaa" * 5
