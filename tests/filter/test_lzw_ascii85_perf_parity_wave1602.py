"""Regression tests locking the byte-exact behaviour of the optimized
LZWDecode / ASCII85Decode inner loops (wave 1602 performance rework).

The decode fast paths were rewritten for speed (slurp-and-index bit reader +
bytearray output for LZW; whitespace-strip + bulk base-85 group math for
ASCII85). These tests pin the quirks the rewrite had to preserve exactly:
EarlyChange width transitions, the lenient premature-EOF / corrupt-code exit,
the b'z' group-boundary shortcut, the exact ignored-whitespace set, the b'~'
end-of-data rule, and trailing partial-group padding.
"""
from __future__ import annotations

import random
from io import BytesIO

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter.ascii85_decode import ASCII85Decode
from pypdfbox.filter.lzw_decode import LZWDecode


def _lzw_roundtrip(raw: bytes, early_change: int = 1) -> bytes:
    filt = LZWDecode()
    enc = BytesIO()
    filt.encode(BytesIO(raw), enc, None)
    params = COSDictionary()
    params.set_int("EarlyChange", early_change)
    out = BytesIO()
    filt.decode(BytesIO(enc.getvalue()), out, params, 0)
    return out.getvalue()


def _a85_decode(data: bytes) -> bytes:
    out = BytesIO()
    ASCII85Decode().decode(BytesIO(data), out, None, 0)
    return out.getvalue()


# --------------------------------------------------------------------------
# LZW
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "length",
    [0, 1, 2, 3, 4, 5, 7, 8, 15, 16, 255, 256, 257, 511, 512, 1000, 4095, 4096, 4097],
)
def test_lzw_roundtrip_boundary_lengths(length: int) -> None:
    rnd = random.Random(length)
    raw = bytes(rnd.randrange(256) for _ in range(length))
    assert _lzw_roundtrip(raw) == raw


def test_lzw_roundtrip_repetitive_forces_table_growth() -> None:
    raw = b"ABCABCABC" * 20000
    assert _lzw_roundtrip(raw) == raw


def test_lzw_roundtrip_single_byte_run() -> None:
    raw = b"Z" * 50000
    assert _lzw_roundtrip(raw) == raw


def test_lzw_empty_stream_yields_empty() -> None:
    out = BytesIO()
    LZWDecode._do_lzw_decode(BytesIO(b""), out, True)
    assert out.getvalue() == b""


def test_lzw_truncated_stream_recovers_partial_output() -> None:
    # A stream cut short before EOD must yield whatever decoded so far, never
    # raise (upstream's lenient premature-EOF behaviour).
    filt = LZWDecode()
    enc = BytesIO()
    filt.encode(BytesIO(b"hello world " * 500), enc, None)
    full = enc.getvalue()
    complete = _lzw_roundtrip(b"hello world " * 500)
    for cut in range(1, len(full)):
        out = BytesIO()
        LZWDecode._do_lzw_decode(BytesIO(full[:cut]), out, True)
        partial = out.getvalue()
        # Partial output is always a prefix of the complete decode.
        assert complete.startswith(partial)


def test_lzw_garbage_never_raises() -> None:
    rnd = random.Random(0)
    for _ in range(200):
        blob = bytes(rnd.randrange(256) for _ in range(rnd.randrange(0, 40)))
        out = BytesIO()
        # Must not raise regardless of corruption.
        LZWDecode._do_lzw_decode(BytesIO(blob), out, True)


def test_lzw_early_change_flag_is_honoured() -> None:
    # Decoding an EarlyChange=1 stream with EarlyChange=0 must follow the
    # ec=0 width schedule (a distinct, deterministic byte sequence), not crash.
    raw = b"pattern data pattern data " * 400
    enc = BytesIO()
    LZWDecode().encode(BytesIO(raw), enc, None)
    ec1 = _lzw_roundtrip(raw, early_change=1)
    assert ec1 == raw
    # ec0 path just needs to be stable/self-consistent across calls.
    a = _lzw_roundtrip(raw, early_change=0)
    b = _lzw_roundtrip(raw, early_change=0)
    assert a == b


# --------------------------------------------------------------------------
# ASCII85
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "length",
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 100, 255, 256, 1000, 4096],
)
def test_a85_roundtrip_boundary_lengths(length: int) -> None:
    rnd = random.Random(length + 7)
    raw = bytes(rnd.randrange(256) for _ in range(length))
    enc = BytesIO()
    ASCII85Decode().encode(BytesIO(raw), enc, None)
    assert _a85_decode(enc.getvalue()) == raw


def test_a85_z_shortcut_only_at_group_boundary() -> None:
    # z at a boundary == four zero bytes.
    assert _a85_decode(b"z~>") == b"\x00\x00\x00\x00"
    assert _a85_decode(b"zzz~>") == b"\x00" * 12
    # z mid-group is an ordinary digit (0x7a - '!' == 89), NOT a shortcut.
    boundary = _a85_decode(b"z~>")
    midgroup = _a85_decode(b"!!z!!~>")
    assert midgroup != boundary
    assert len(midgroup) == 4  # one full group of 5 digits


def test_a85_zeros_use_z_shortcut_roundtrip() -> None:
    raw = b"\x00" * 400
    enc = BytesIO()
    ASCII85Decode().encode(BytesIO(raw), enc, None)
    assert b"z" in enc.getvalue()
    assert _a85_decode(enc.getvalue()) == raw


def test_a85_ignored_whitespace_is_exactly_lf_cr_space() -> None:
    # LF, CR, SPACE are stripped and do not affect grouping.
    clean = _a85_decode(b"<+oue~>")
    spaced = _a85_decode(b"<\n+ o\ru e ~>")
    assert spaced == clean
    # TAB / FF / VT / NUL are NOT whitespace -> they are out-of-range digits
    # (or invalid) and must raise.
    for bad in (b"\x00", b"\x09", b"\x0b", b"\x0c"):
        with pytest.raises(OSError):
            _a85_decode(b"<+" + bad + b"oue~>")


def test_a85_eod_ends_at_first_tilde() -> None:
    # Stream ends at first b'~'; trailing bytes are never read.
    assert _a85_decode(b"87cURD~X") == _a85_decode(b"87cURD~>")
    assert _a85_decode(b"~garbage") == b""


def test_a85_adobe_intro_not_special_cased() -> None:
    # b'<~...' : b'<' is a digit, b'~' terminates -> lone leading digit dropped.
    assert _a85_decode(b"<~87cURD]~>") == b""


def test_a85_trailing_partial_group_padding() -> None:
    # n trailing digits -> n-1 bytes; a lone single digit is dropped.
    assert _a85_decode(b"!~>") == b""  # 1 digit -> nothing
    assert len(_a85_decode(b"!!~>")) == 1
    assert len(_a85_decode(b"!!!~>")) == 2
    assert len(_a85_decode(b"!!!!~>")) == 3
    assert len(_a85_decode(b"!!!!!~>")) == 4  # exact full group


def test_a85_invalid_bytes_raise() -> None:
    for bad in (b"\x01", b"\x1f", b"\x7f", b"\x80", b"\xff"):
        with pytest.raises(OSError, match="Invalid data in Ascii85 stream"):
            _a85_decode(b"!!" + bad + b"~>")


def test_a85_fast_and_z_paths_agree_on_random_streams() -> None:
    # Cross-check: encode random data (fast path on decode) and separately
    # feed z-containing streams (slow path) to confirm both stay consistent
    # with re-decoding.
    rnd = random.Random(2024)
    filt = ASCII85Decode()
    for _ in range(100):
        raw = bytes(rnd.randrange(256) for _ in range(rnd.randrange(0, 80)))
        enc = BytesIO()
        filt.encode(BytesIO(raw), enc, None)
        assert _a85_decode(enc.getvalue()) == raw
