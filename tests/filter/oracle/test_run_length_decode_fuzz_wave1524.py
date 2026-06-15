"""Differential RunLengthDecode fuzz vs Apache PDFBox 3.0.7 (wave 1524).

A RunLength-specific complement to the generic wave-1505 ``FilterFuzzProbe``
decode fuzz and to wave 1523's LZW / ASCII85 / ASCIIHex surfaces. Where those
stress other codecs, this wave hand-builds raw RunLength packet streams that
exercise the codec's own state machine and its lenient EOF handling.

PDF RunLength packets (ISO 32000-1 §7.4.5):

* a length byte ``L`` in ``0..127`` copies the next ``L + 1`` bytes verbatim,
* ``L == 128`` is end-of-data (decode stops, no further bytes consumed),
* ``L`` in ``129..255`` repeats the next single byte ``257 - L`` times.

The crafted corpus covers: empty input, EOD (128) as the first byte, a literal
run that overruns the input (``L`` promises more bytes than remain), a repeat
run with no following byte, a missing trailing EOD, multiple EOD bytes, data
after EOD (decode must stop), ``L == 127`` (max 128-byte literal), ``L == 129``
(max 128x repeat), ``L == 255`` (repeat twice), a lone length byte, an
all-EOD stream, and interleaved literal+repeat runs.

Both engines decode the *identical* bytes and are compared on the stable
``FilterFuzzProbe``-style projection::

    ok=true
    len=<decoded byte count>
    sha=<first 8 hex of SHA-256 of the decoded bytes>

or the sole line ``ok=false`` on any decode-time throw. The Java side is
``oracle/probes/RunLengthDecodeFuzzProbe.java``; ``_py_dump`` reproduces the
same fingerprint on the pypdfbox side.

Outcome of this wave: pypdfbox's ``RunLengthDecode`` is already at
byte-for-byte parity with upstream across every RunLength-specific edge case
probed here. Upstream's ``decode`` (confirmed via ``javap`` of
``RunLengthDecodeFilter``) treats EOF anywhere -- before a length byte, mid
literal run, or before a repeat byte -- as a clean stop and returns whatever
was decoded so far; pypdfbox mirrors that exactly. No production change was
needed; these cases pin that parity so a future refactor cannot silently
regress the codec's malformed-input behaviour. The projection is pinned EXACT
(ok + len + sha) because both engines share the same decode algorithm, so
byte-equality is the correct bar.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import tempfile

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.filter import FilterFactory
from tests.oracle.harness import requires_oracle, run_probe_text

EOD = 128


# ---------------------------------------------------------------------------
# deterministic corpus: (name, encoded_bytes)
# ---------------------------------------------------------------------------
_Case = tuple[str, bytes]


def _build_corpus() -> list[_Case]:
    out: list[_Case] = []

    def add(name: str, body: bytes) -> None:
        out.append((name, body))

    # -- structural / empty edges ----------------------------------------
    add("empty", b"")
    add("eod_first", bytes([EOD]))
    add("all_eod", bytes([EOD, EOD, EOD]))
    add("lone_len0", bytes([0]))  # literal-1 length byte, no payload
    add("lone_len5", bytes([5]))  # promises 6 bytes, none follow
    add("lone_len127", bytes([127]))  # max literal length byte, no payload
    add("lone_repeat_no_byte", bytes([129]))  # repeat op, no byte follows
    add("lone_repeat255_no_byte", bytes([255]))

    # -- literal runs -----------------------------------------------------
    add("literal1", bytes([0, 0x41, EOD]))  # copy 1 byte: 'A'
    add("literal3", bytes([2, 0x41, 0x42, 0x43, EOD]))  # copy 3 bytes
    add("literal_no_eod", bytes([2, 0x41, 0x42, 0x43]))  # missing trailing EOD
    add("literal_overrun", bytes([5, 0x41, 0x42]))  # promise 6, give 2
    add("literal_overrun_eod", bytes([5, 0x41, 0x42, EOD]))  # EOD as a payload byte
    add("literal127_full", bytes([127, *range(128), EOD]))  # max 128-byte literal
    add("literal127_short", bytes([127, 0x41, 0x42, 0x43]))  # max len, truncated

    # -- repeat runs ------------------------------------------------------
    add("repeat_min255", bytes([255, 0x5A, EOD]))  # 257-255 = 2 copies
    add("repeat_129_max", bytes([129, 0x58, EOD]))  # 257-129 = 128 copies
    add("repeat_200", bytes([200, 0x42, EOD]))  # 257-200 = 57 copies
    add("repeat_no_eod", bytes([200, 0x42]))  # repeat then EOF (no EOD)
    add("repeat_then_garbage", bytes([255, 0x5A, 200, 0x42]))  # two repeats, no EOD

    # -- EOD placement ----------------------------------------------------
    add("data_after_eod", bytes([0, 0x41, EOD, 2, 0x42, 0x43, 0x44]))  # must stop
    add("eod_then_eod", bytes([0, 0x41, EOD, EOD]))
    add("literal_then_eod_then_repeat", bytes([1, 0x41, 0x42, EOD, 255, 0x43]))

    # -- interleaved literal + repeat runs -------------------------------
    add(
        "interleaved",
        bytes([2, 0x41, 0x42, 0x43, 255, 0x44, 1, 0x45, 0x46, 200, 0x47, EOD]),
    )
    add(
        "repeat_literal_repeat",
        bytes([254, 0x30, 0, 0x31, 129, 0x32, EOD]),  # 3x'0', 1x'1', 128x'2'
    )

    # -- length byte 128 boundary as repeat boundary ---------------------
    # 128 is EOD, so the smallest repeat opcode is 129; verify nearby ops.
    add("literal_max_then_repeat_min", bytes([127, *range(128), 255, 0x99, EOD]))

    # -- all-bytes literal stress (no EOD, full 256-value sweep) ----------
    sweep = bytearray()
    for chunk_start in range(0, 256, 128):
        block = bytes(range(chunk_start, min(chunk_start + 128, 256)))
        sweep.append(len(block) - 1)
        sweep.extend(block)
    sweep.append(EOD)
    add("full_byte_sweep", bytes(sweep))
    add("full_byte_sweep_no_eod", bytes(sweep[:-1]))

    return out


_CORPUS = _build_corpus()
_CORPUS_IDS = [c[0] for c in _CORPUS]


# ---------------------------------------------------------------------------
# projection helpers (mirror RunLengthDecodeFuzzProbe exactly)
# ---------------------------------------------------------------------------
def _sha_prefix(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:8]


def _build_stream_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Filter"), COSName.get_pdf_name("RunLengthDecode"))
    return d


def _py_dump(encoded: bytes) -> str:
    try:
        flt = FilterFactory.get("RunLengthDecode")
        out = io.BytesIO()
        flt.decode(io.BytesIO(encoded), out, _build_stream_dict(), 0)
        decoded = out.getvalue()
    except Exception:
        return "ok=false\n"
    return f"ok=true\nlen={len(decoded)}\nsha={_sha_prefix(decoded)}\n"


def _java_dump(encoded: bytes) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".bin")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(encoded)
        return run_probe_text("RunLengthDecodeFuzzProbe", tmp)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# Differential parity: every crafted stream produces the identical projection.
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.parametrize(("name", "encoded"), _CORPUS, ids=_CORPUS_IDS)
def test_run_length_decode_fuzz_parity(name: str, encoded: bytes) -> None:
    java = _java_dump(encoded)
    py = _py_dump(encoded)
    assert py == java, (
        f"RunLength decode divergence on {name!r}:\n java={java!r}\n  py={py!r}"
    )


# ---------------------------------------------------------------------------
# Sanity: crafted "valid" streams really decode to the expected bytes, so a
# corpus-build regression cannot turn every case into a vacuous ok=true|len=0.
# ---------------------------------------------------------------------------
def test_crafted_valid_streams_decode_expected() -> None:
    cases = {
        "literal3": b"ABC",
        "repeat_min255": b"ZZ",
        "repeat_129_max": b"X" * 128,
        "interleaved": b"ABC" + b"D" * 2 + b"EF" + b"G" * 57,
        "data_after_eod": b"A",  # decode stops at EOD; trailing data ignored
        "repeat_literal_repeat": b"0" * 3 + b"1" + b"2" * 128,
    }
    body_by_name = {c[0]: c[1] for c in _CORPUS}
    for name, expected in cases.items():
        enc = body_by_name[name]
        out = io.BytesIO()
        FilterFactory.get("RunLengthDecode").decode(
            io.BytesIO(enc), out, _build_stream_dict(), 0
        )
        assert out.getvalue() == expected, name
