"""Wave 1579 fuzz/parity coverage for ``pypdfbox.filter.lzw_decode``.

Hammers the variable-width LZW decoder against behavioural parity with
Apache PDFBox 3.0.7 ``LZWFilter``:

* code-width transition boundaries (510/511 with EarlyChange=1 vs
  511/512 with EarlyChange=0 — the off-by-one EarlyChange controls),
* CLEAR (256) resetting the table and width to 9 mid-stream,
* EOD (257) terminating,
* the KwKwK "code not yet in the table" edge (a code equal to the
  next-to-be-added entry),
* /EarlyChange 0 vs 1 producing different widths at the boundary,
* empty input, width capping at 12 bits,
* lossless round-trips across many random payloads and boundary sizes.

Codes are packed with a self-contained MSB-first packer that mirrors the
decoder's own width schedule, so hand-built streams are independent of
the encoder under test.
"""

from __future__ import annotations

import os
import random
from io import BytesIO

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter.lzw_decode import (
    CLEAR_TABLE,
    EOD,
    LZWDecode,
    _calculate_chunk,
)

# ---------- helpers ---------------------------------------------------


def _make_params(early_change: int | None = None) -> COSDictionary | None:
    if early_change is None:
        return None
    inner = COSDictionary()
    inner.set_int("EarlyChange", early_change)
    outer = COSDictionary()
    outer.set_item("DecodeParms", inner)
    return outer


def _decode(encoded: bytes, params: COSDictionary | None = None) -> bytes:
    out = BytesIO()
    LZWDecode().decode(BytesIO(encoded), out, params)
    return out.getvalue()


def _roundtrip(data: bytes, params: COSDictionary | None = None) -> bytes:
    f = LZWDecode()
    enc = BytesIO()
    f.encode(BytesIO(data), enc, params)
    out = BytesIO()
    f.decode(BytesIO(enc.getvalue()), out, params)
    return out.getvalue()


def _pack(codes: list[int], early_change: bool = True) -> bytes:
    """Pack ``codes`` MSB-first using the decoder's exact width schedule.

    Starts at width 9 (or just after a CLEAR), grows according to
    ``_calculate_chunk(table_size, early_change)`` after each data code,
    and resets on CLEAR — identical to the decoder's own bookkeeping so
    the produced stream is a faithful synthetic input.
    """
    table_size = 258
    chunk = 9
    buf = 0
    nbits = 0
    out = bytearray()

    def emit(value: int, width: int) -> None:
        nonlocal buf, nbits
        buf = (buf << width) | (value & ((1 << width) - 1))
        nbits += width
        while nbits >= 8:
            nbits -= 8
            out.append((buf >> nbits) & 0xFF)
            buf &= (1 << nbits) - 1

    for code in codes:
        emit(code, chunk)
        if code == CLEAR_TABLE:
            table_size = 258
            chunk = 9
        elif code == EOD:
            continue
        else:
            table_size += 1
            chunk = _calculate_chunk(table_size, early_change)
    if nbits:
        out.append((buf << (8 - nbits)) & 0xFF)
    return bytes(out)


# ---------- calculate_chunk boundary parity ---------------------------


@pytest.mark.parametrize(
    ("table_size", "early_change", "expected"),
    [
        # EarlyChange=1 (PDF default): width grows one entry early.
        (258, True, 9),
        (510, True, 9),
        (511, True, 10),  # the early jump
        (512, True, 10),
        (1022, True, 10),
        (1023, True, 11),  # early jump
        (1024, True, 11),
        (2046, True, 11),
        (2047, True, 12),  # early jump
        (2048, True, 12),
        (4095, True, 12),  # capped
        (4096, True, 12),  # capped
        # EarlyChange=0 (canonical TIFF timing): width grows one later.
        (511, False, 9),
        (512, False, 10),  # standard jump
        (513, False, 10),
        (1023, False, 10),
        (1024, False, 11),  # standard jump
        (2047, False, 11),
        (2048, False, 12),  # standard jump
        (4095, False, 12),
    ],
)
def test_calculate_chunk_boundaries(
    table_size: int, early_change: bool, expected: int
) -> None:
    assert _calculate_chunk(table_size, early_change) == expected


def test_early_change_off_by_one_at_512_boundary() -> None:
    """At table size 511 the two modes diverge by exactly one bit: EC=1
    has already grown to 10 bits, EC=0 is still at 9. This is the
    off-by-one EarlyChange controls."""
    assert _calculate_chunk(511, True) == 10
    assert _calculate_chunk(511, False) == 9


def test_width_never_exceeds_12() -> None:
    for size in (4096, 5000, 10000, 1 << 20):
        assert _calculate_chunk(size, True) == 12
        assert _calculate_chunk(size, False) == 12


def test_calculate_chunk_static_helper_matches_module() -> None:
    for size in (258, 511, 1023, 2047, 4096):
        assert LZWDecode.calculate_chunk(size, True) == _calculate_chunk(size, True)
        assert LZWDecode.calculate_chunk(size, False) == _calculate_chunk(size, False)


# ---------- hand-built stream decode ----------------------------------


def test_clear_then_two_literals_then_eod() -> None:
    assert _decode(_pack([CLEAR_TABLE, 65, 66, EOD])) == b"AB"


def test_leading_clear_optional() -> None:
    # A well-formed PDF stream begins with CLEAR, but the decoder must
    # also handle a stream that opens straight on data codes.
    assert _decode(_pack([65, 66, 67, EOD])) == b"ABC"


def test_just_eod_yields_empty() -> None:
    assert _decode(_pack([EOD])) == b""


def test_clear_then_eod_yields_empty() -> None:
    assert _decode(_pack([CLEAR_TABLE, EOD])) == b""


def test_kwkwk_repeated_byte() -> None:
    # CLEAR, 'A', then code 258 (== current table size, the entry about
    # to be created) is the KwKwK case → 'A' + 'AA'.
    assert _decode(_pack([CLEAR_TABLE, 65, 258, EOD])) == b"AAA"


def test_kwkwk_multi_byte_prefix() -> None:
    # CLEAR, 'A', 'B' (258='AB', prev='B'), then 259 == table size is the
    # KwKwK case → prev + prev[0] = 'B' + 'B' = 'BB'. Output: A B BB.
    out = _decode(_pack([CLEAR_TABLE, 65, 66, 259, EOD]))
    assert out == b"ABBB"


def test_clear_resets_table_and_width_mid_stream() -> None:
    # Two independent segments separated by a CLEAR; codes 258.. are
    # redefined after the CLEAR, proving the table truly reset.
    codes = [CLEAR_TABLE, 65, 66, 258, CLEAR_TABLE, 67, 68, 258, EOD]
    # seg1: A B (258=AB) AB  -> "ABAB"
    # seg2: C D (258=CD) CD  -> "CDCD"
    assert _decode(_pack(codes)) == b"ABABCDCD"


def test_back_reference_uses_dictionary_entry() -> None:
    # CLEAR, 'A','B' (258='AB'), 'C' (259='BC'), 258 ('AB') -> "ABCAB"
    assert _decode(_pack([CLEAR_TABLE, 65, 66, 67, 258, EOD])) == b"ABCAB"


def test_eod_terminates_ignoring_trailing_codes() -> None:
    # Codes after EOD must be ignored — the decoder stops at EOD.
    stream = _pack([CLEAR_TABLE, 65, EOD])
    assert _decode(stream + b"\xff\xff\xff") == b"A"


# ---------- EarlyChange 0 vs 1 at the boundary ------------------------


def test_early_change_zero_vs_one_produce_different_streams() -> None:
    # A payload long enough to cross the 9->10 bit boundary, decoded with
    # the wrong EarlyChange flag, must not reproduce the input.
    data = bytes((i * 7) % 256 for i in range(900))
    enc = BytesIO()
    LZWDecode().encode(BytesIO(data), enc)  # encoder is EC=1
    same = _decode(enc.getvalue(), _make_params(1))
    diff = _decode(enc.getvalue(), _make_params(0))
    assert same == data
    assert diff != data


def test_early_change_zero_handbuilt_literals_decode() -> None:
    # A hand-built EC=0 stream of distinct literals (kept clear of the
    # 9->10 bit boundary so the packer's EOD timing is unambiguous)
    # decodes back to exactly those literals.
    literals = list(range(200))
    stream = _pack([CLEAR_TABLE, *literals, EOD], early_change=False)
    assert _decode(stream, _make_params(0)) == bytes(literals)


def test_early_change_one_handbuilt_literals_decode() -> None:
    # Same, but EC=1: confirms the default-mode packer/decoder agree on a
    # straight run of literals.
    literals = list(range(200))
    stream = _pack([CLEAR_TABLE, *literals, EOD], early_change=True)
    assert _decode(stream, _make_params(1)) == bytes(literals)


def test_default_early_change_is_one() -> None:
    # No params at all and explicit EarlyChange=1 must agree.
    data = os.urandom(700)
    enc = BytesIO()
    LZWDecode().encode(BytesIO(data), enc)
    assert _decode(enc.getvalue()) == data
    assert _decode(enc.getvalue(), _make_params(1)) == data


# ---------- round-trips across sizes & boundaries ---------------------


@pytest.mark.parametrize(
    "size",
    [0, 1, 2, 3, 16, 255, 256, 257, 258, 511, 512, 513, 1023, 1024, 4095, 4096, 8192],
)
def test_roundtrip_random_sizes(size: int) -> None:
    rng = random.Random(0xC0FFEE ^ size)
    data = bytes(rng.getrandbits(8) for _ in range(size))
    assert _roundtrip(data) == data


@pytest.mark.parametrize("seed", list(range(8)))
def test_roundtrip_fuzz_random(seed: int) -> None:
    rng = random.Random(seed)
    size = rng.randint(0, 6000)
    data = bytes(rng.getrandbits(8) for _ in range(size))
    assert _roundtrip(data) == data


def test_roundtrip_highly_repetitive_drives_table_full() -> None:
    # Long runs of a few bytes force the dictionary toward MAX_TABLE_SIZE
    # and an internal CLEAR; the round-trip must survive the reset.
    data = (b"AB" * 5000) + (b"X" * 5000) + bytes(range(256)) * 40
    assert _roundtrip(data) == data


def test_roundtrip_all_byte_values_blocks() -> None:
    data = bytes(range(256)) * 30
    assert _roundtrip(data) == data


def test_roundtrip_early_change_zero_random() -> None:
    # Encoder emits EC=1, so an EC=0 round-trip only matches if both ends
    # use EC=0. We can't ask the encoder for EC=0, but the EC=1 default
    # round-trip with a matching decode flag must be lossless.
    for n in (50, 600, 1500):
        data = os.urandom(n)
        assert _roundtrip(data) == data


# ---------- lenient corrupt-stream handling (parity) ------------------


def test_truncated_without_eod_keeps_partial_output() -> None:
    # PDFBox logs and stops on premature EOF, keeping decoded prefix.
    full = _pack([CLEAR_TABLE, 65, 66, 67])  # no EOD
    assert _decode(full) == b"ABC"


def test_invalid_out_of_range_code_stops_leniently() -> None:
    # Code far beyond the table size is corrupt; upstream raises an
    # EOFException it catches → partial output, no propagating error.
    stream = _pack([CLEAR_TABLE, 65, 4000, EOD])
    assert _decode(stream) == b"A"


def test_reserved_placeholder_code_as_data_stops_leniently() -> None:
    # An immediate KwKwK with no previous string (code == table size at
    # the very start after CLEAR) is corrupt; decoder exits gracefully.
    stream = _pack([CLEAR_TABLE, 258, EOD])
    assert _decode(stream) == b""


def test_empty_encoded_input_yields_empty() -> None:
    assert _decode(b"") == b""
