"""Differential LZWDecode fuzz vs Apache PDFBox 3.0.7 (wave 1523).

A LZW-specific complement to the generic wave-1505 ``FilterFuzzProbe`` decode
fuzz. Where that probe applies byte-level mutations to a clean LZW body, this
wave hand-builds *bit-level* LZW code streams that stress the codec's own
internal state machine:

* the reserved codes ``CLEAR_TABLE`` (256) and ``EOD`` (257),
* the variable-width code transitions 9->10->11->12 bits,
* the ``/EarlyChange`` boundary (default 1 vs 0) that shifts the width-grow
  point by one entry,
* the KwKwK special case (a code that references the entry about to be
  created) vs a genuinely out-of-range code,
* premature EOF (missing EOD), EOD appearing mid-stream,
* a stream without a leading CLEAR,
* table growth past 4096 entries without an intervening CLEAR, and
* ``/Predictor`` (TIFF 2 / PNG 12) layered on top of the LZW core.

Both engines decode the *identical* bytes and are compared on the stable
``FilterFuzzProbe``-style projection::

    ok=true
    len=<decoded byte count>
    sha=<first 8 hex of SHA-256 of the decoded bytes>

or the sole line ``ok=false`` on any decode-time throw. The Java side is
``oracle/probes/LzwDecodeFuzzProbe.java``; ``_py_dump`` reproduces the same
fingerprint on the pypdfbox side.

Outcome of this wave: pypdfbox's ``LZWDecode`` is already at byte-for-byte
parity with upstream across every LZW-specific edge case probed here (the
lenient EOFException-as-stop contract, the 258-entry initial table with null
placeholders at 256/257, and the post-growth ``calculate_chunk`` width were all
already faithful from earlier waves). No production change was needed; these
cases pin that parity so a future LZW refactor cannot silently regress the
codec's malformed-input behaviour.

The projection is pinned EXACT (ok + len + sha) for the pure-LZW cases — both
engines share the same decode algorithm so byte-equality is the correct bar.
Predictor cases stay EXACT too: the predictor post-pass is deterministic and
shared, and the wave-1518 predictor-fuzz surface already proved its parity.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import tempfile

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.filter import FilterFactory
from tests.oracle.harness import requires_oracle, run_probe_text

CLEAR_TABLE = 256
EOD = 257


# ---------------------------------------------------------------------------
# bit-level LZW stream builders (MSB-first, matching the PDF packing)
# ---------------------------------------------------------------------------
class _BitWriter:
    """Minimal MSB-first bit writer used to hand-craft raw LZW code streams."""

    def __init__(self) -> None:
        self._buffer = 0
        self._bits = 0
        self._out = bytearray()

    def write(self, value: int, width: int) -> _BitWriter:
        self._buffer = (self._buffer << width) | (value & ((1 << width) - 1))
        self._bits += width
        while self._bits >= 8:
            self._bits -= 8
            self._out.append((self._buffer >> self._bits) & 0xFF)
        return self

    def done(self) -> bytes:
        if self._bits > 0:
            self._out.append((self._buffer << (8 - self._bits)) & 0xFF)
        return bytes(self._out)


def _chunk(table_size: int, early: bool) -> int:
    """Decoder's next-code width given table size — mirrors LZWDecode."""
    i = table_size + (1 if early else 0)
    if i >= 2048:
        return 12
    if i >= 1024:
        return 11
    if i >= 512:
        return 10
    return 9


def _emit(codes: list[int], early: bool = True) -> bytes:
    """Emit ``codes`` at the width the *decoder* expects before each code.

    Tracks the same state the decode loop does: width starts at 9, resets to 9
    after CLEAR, and after every data code becomes ``_chunk(table_size)`` where
    the table grows by one entry per data code that follows a previous string.
    """
    bw = _BitWriter()
    table = 258
    width = 9
    has_prev = False
    for c in codes:
        bw.write(c, width)
        if c == CLEAR_TABLE:
            table = 258
            width = 9
            has_prev = False
            continue
        if c == EOD:
            continue
        if has_prev:
            table += 1
        has_prev = True
        width = _chunk(table, early)
    return bw.done()


def _grow_no_clear(n_extra: int, early: bool = True) -> bytes:
    """Build a CLEAR-less stream that chain-grows the table via KwKwK codes.

    Starts with literal 0, then repeatedly emits the code equal to the current
    table size (the KwKwK / "code about to be created" case), which adds one
    entry each step. Pushes past the 4096 cap to exercise table-full handling
    with no intervening CLEAR.
    """
    bw = _BitWriter()
    table = 258
    width = 9
    bw.write(0, width)
    width = _chunk(table, early)
    code = 258
    for _ in range(n_extra):
        if code > 4095:
            break
        bw.write(code, width)
        table += 1
        code += 1
        width = _chunk(table, early)
    bw.write(EOD, min(width, 12))
    return bw.done()


def _lzw_encode(raw: bytes) -> bytes:
    out = io.BytesIO()
    FilterFactory.get("LZWDecode").encode(io.BytesIO(raw), out)
    return out.getvalue()


def _lzw_encode_pred(raw: bytes, parm: dict[str, int]) -> bytes:
    flt = FilterFactory.get("LZWDecode")
    p = COSDictionary()
    dp = COSDictionary()
    for k, v in parm.items():
        dp.set_item(COSName.get_pdf_name(k), COSInteger.get(v))
    p.set_item(COSName.get_pdf_name("DecodeParms"), dp)
    out = io.BytesIO()
    flt.encode(io.BytesIO(raw), out, p)
    return out.getvalue()


# ---------------------------------------------------------------------------
# deterministic corpus: (name, encoded_bytes, parm_ints)
# ---------------------------------------------------------------------------
_Case = tuple[str, bytes, dict[str, int]]


def _build_corpus() -> list[_Case]:
    out: list[_Case] = []

    def add(name: str, body: bytes, parm: dict[str, int] | None = None) -> None:
        out.append((name, body, parm or {}))

    # -- reserved-code / structural edges --------------------------------
    add("empty", b"")
    add("single_byte", b"\x00")
    add("just_eod", _emit([EOD]))
    add("clear_then_eod", _emit([CLEAR_TABLE, EOD]))
    add("all_clears", _emit([CLEAR_TABLE, CLEAR_TABLE, CLEAR_TABLE, EOD]))
    add("clear_ab_eod", _emit([CLEAR_TABLE, 65, 66, EOD]))
    add("no_leading_clear", _emit([65, 66, EOD]))
    add("eod_mid_stream", _emit([CLEAR_TABLE, 65, EOD, 66]))
    add("missing_eod", _emit([CLEAR_TABLE, 65, 66]))

    # -- KwKwK valid vs out-of-range -------------------------------------
    add("kwkwk_valid", _emit([CLEAR_TABLE, 65, 258, EOD]))
    add("kwkwk_chained", _emit([CLEAR_TABLE, 65, 258, 259, EOD]))
    add("kwkwk_no_prev", _emit([CLEAR_TABLE, 258, EOD]))
    add("code_eq_size_no_prev", _emit([258, EOD]))
    add("oor_first_300", _emit([300, EOD]))
    add("kwk_then_oor", _emit([CLEAR_TABLE, 65, 258, 300, EOD]))
    add("nine_bit_511_first", _emit([511, EOD]))

    # -- truncation / garbage at the bit level ---------------------------
    add("trunc_5bits", bytes([0b10000000]))
    add("all_ones_8", b"\xff" * 8)
    add("all_ones_16", b"\xff" * 16)
    add("alt_bytes", bytes([0xAA, 0x55] * 10))
    add("just_zero", b"\x00")

    # -- EarlyChange variants on structural streams ----------------------
    add("clear_eod_ec0", _emit([CLEAR_TABLE, EOD], early=False), {"EarlyChange": 0})
    add("no_clear_ec0", _emit([65, 66, EOD], early=False), {"EarlyChange": 0})
    add("zero_ec0", b"\x00", {"EarlyChange": 0})

    # -- width-transition crossings (9->10->11), real encoded bodies -----
    big = bytes((i * 7 + 3) % 256 for i in range(2000))
    enc_big = _lzw_encode(big)
    add("big_default", enc_big)
    add("big_ec1", enc_big, {"EarlyChange": 1})
    add("big_ec0_mismatch", enc_big, {"EarlyChange": 0})
    add("big_trunc_mid", enc_big[: len(enc_big) // 2])
    add("big_trunc_mid_ec0", enc_big[: len(enc_big) // 2], {"EarlyChange": 0})
    add("big_drop_last", enc_big[:-1])
    add("big_garbage_tail", enc_big + b"\xab\xcd\xef")

    # -- table fills to 4096 (encoder inserts CLEAR), decode lenient ------
    huge = bytes((i * 13 + 1) % 256 for i in range(20000))
    enc_huge = _lzw_encode(huge)
    add("huge_default", enc_huge)
    add("huge_ec0_mismatch", enc_huge, {"EarlyChange": 0})
    add("huge_trunc", enc_huge[: len(enc_huge) // 3])
    add("huge_drop_last", enc_huge[:-1])

    # -- table grows past 4096 with NO intervening CLEAR (KwKwK chain) ----
    add("grow_no_clear", _grow_no_clear(4000))
    add("grow_no_clear_ec0", _grow_no_clear(4000, early=False), {"EarlyChange": 0})
    add("overgrow_past_4096", _grow_no_clear(5000))

    # -- /Predictor layered on the LZW core ------------------------------
    praw = bytes((i * 5 + 2) % 256 for i in range(4 * 5))
    pred2 = {"Predictor": 2, "Columns": 4, "Colors": 1, "BitsPerComponent": 8}
    enc_p2 = _lzw_encode_pred(praw, pred2)
    add("pred2_correct", enc_p2, pred2)
    add(
        "pred2_wrong_cols",
        enc_p2,
        {"Predictor": 2, "Columns": 3, "Colors": 1, "BitsPerComponent": 8},
    )
    pred12 = {"Predictor": 12, "Columns": 4, "Colors": 1, "BitsPerComponent": 8}
    enc_p12 = _lzw_encode_pred(praw, pred12)
    add("pred12_correct", enc_p12, pred12)
    add("pred12_trunc", enc_p12[:-1], pred12)

    return out


_CORPUS = _build_corpus()
_CORPUS_IDS = [c[0] for c in _CORPUS]


# ---------------------------------------------------------------------------
# projection helpers (mirror LzwDecodeFuzzProbe exactly)
# ---------------------------------------------------------------------------
def _sha_prefix(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:8]


def _build_stream_dict(parm_ints: dict[str, int]) -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Filter"), COSName.get_pdf_name("LZWDecode"))
    if parm_ints:
        dp = COSDictionary()
        for k, v in parm_ints.items():
            dp.set_item(COSName.get_pdf_name(k), COSInteger.get(v))
        d.set_item(COSName.get_pdf_name("DecodeParms"), dp)
    return d


def _py_dump(encoded: bytes, parm_ints: dict[str, int]) -> str:
    try:
        flt = FilterFactory.get("LZWDecode")
        out = io.BytesIO()
        flt.decode(io.BytesIO(encoded), out, _build_stream_dict(parm_ints), 0)
        decoded = out.getvalue()
    except Exception:
        return "ok=false\n"
    return f"ok=true\nlen={len(decoded)}\nsha={_sha_prefix(decoded)}\n"


def _java_dump(encoded: bytes, parm_ints: dict[str, int]) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".bin")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(encoded)
        parm_spec = ",".join(f"{k}={v}" for k, v in parm_ints.items())
        return run_probe_text("LzwDecodeFuzzProbe", tmp, parm_spec)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# Differential parity: every crafted stream produces the identical projection.
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.parametrize(("name", "encoded", "parm_ints"), _CORPUS, ids=_CORPUS_IDS)
def test_lzw_decode_fuzz_parity(
    name: str, encoded: bytes, parm_ints: dict[str, int]
) -> None:
    java = _java_dump(encoded, parm_ints)
    py = _py_dump(encoded, parm_ints)
    assert py == java, (
        f"LZW decode divergence on {name!r}:\n java={java!r}\n  py={py!r}"
    )


# ---------------------------------------------------------------------------
# Sanity: the crafted "valid" streams really decode to non-empty output, so a
# corpus-build regression cannot turn every case into a vacuous ok=true|len=0.
# ---------------------------------------------------------------------------
def test_crafted_valid_streams_decode_nonempty() -> None:
    cases = {
        "clear_ab_eod": (b"AB", {}),
        "kwkwk_valid": (b"AAA", {}),
        "no_leading_clear": (b"AB", {}),
    }
    body_by_name = {c[0]: (c[1], c[2]) for c in _CORPUS}
    for name, (expected, _parm) in cases.items():
        enc, parm = body_by_name[name]
        out = io.BytesIO()
        FilterFactory.get("LZWDecode").decode(
            io.BytesIO(enc), out, _build_stream_dict(parm), 0
        )
        assert out.getvalue() == expected, name
