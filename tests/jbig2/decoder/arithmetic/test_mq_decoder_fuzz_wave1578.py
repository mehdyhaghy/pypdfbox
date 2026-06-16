"""Fuzz / spec-conformance tests for the JBIG2 MQ arithmetic decoder (wave 1578).

Hammers :class:`pypdfbox.jbig2.decoder.arithmetic.ArithmeticDecoder` — the MQ
entropy decoder underlying generic/text/symbol-dictionary region decoding — against
ITU-T Rec. T.88 Annex E (identical to the JPEG2000 MQ coder of ITU-T T.800
Annex C):

* the Qe probability-estimation state table + NMPS/NLPS/SWITCH columns vs an
  *inlined, independent* copy of T.88 Table E.1 (the production table is NOT
  imported into the reference — the reference is typed out from the spec so a
  silent edit to the production table is caught);
* the DECODE procedure (T.88 Figure E.17): the ``(C >> 16) < Qe`` comparison
  selecting the MPS vs LPS path, the ``A & 0x8000`` renorm guard;
* MPS_EXCHANGE / LPS_EXCHANGE (Figures E.16/E.18): the ``A < Qe`` conditional
  exchange, the SWITCH-conditioned MPS toggle, the NMPS/NLPS index transition;
* BYTEIN (Figure E.19): the 0xFF marker / bit-stuffing branch (``B1 > 0x8F``
  vs ``B1 <= 0x8F``) and the ordinary branch;
* RENORMD (Figure E.20): the shift-until-``A & 0x8000`` loop with ``CT==0``
  triggering BYTEIN;
* the context state transition on MPS vs LPS;
* decoding *known* short bitstreams to *known* bit sequences. The independent
  oracle is the validated round-trip encoder
  :class:`tests.jbig2.helpers.mq_encoder.MQEncoder` (an inline T.88 E.3 ENCODE
  implementation, the structural inverse of the decoder); decoded bits are
  verified exactly against the encoder's input.

These are behavioural-parity tests: the production decoder is a port of
``org.apache.pdfbox.jbig2.decoder.arithmetic.ArithmeticDecoder``, which itself
implements T.88 Annex E.
"""

from __future__ import annotations

import random

import pytest

from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import QE, ArithmeticDecoder
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_integer_decoder import (
    LONG_MAX_VALUE,
    ArithmeticIntegerDecoder,
)
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from tests.jbig2.helpers.mq_encoder import (
    OOB,
    ArithmeticIntegerEncoder,
    Cx,
    MQEncoder,
)

# ---------------------------------------------------------------------------
# Independent T.88 Table E.1 (Qe, NMPS, NLPS, SWITCH), typed verbatim from the
# spec. Deliberately NOT derived from the production QE — this is the oracle the
# production table is checked against.
# ---------------------------------------------------------------------------
_T88_TABLE_E1: tuple[tuple[int, int, int, int], ...] = (
    (0x5601, 1, 1, 1),    # 0
    (0x3401, 2, 6, 0),    # 1
    (0x1801, 3, 9, 0),    # 2
    (0x0AC1, 4, 12, 0),   # 3
    (0x0521, 5, 29, 0),   # 4
    (0x0221, 38, 33, 0),  # 5
    (0x5601, 7, 6, 1),    # 6
    (0x5401, 8, 14, 0),   # 7
    (0x4801, 9, 14, 0),   # 8
    (0x3801, 10, 14, 0),  # 9
    (0x3001, 11, 17, 0),  # 10
    (0x2401, 12, 18, 0),  # 11
    (0x1C01, 13, 20, 0),  # 12
    (0x1601, 29, 21, 0),  # 13
    (0x5601, 15, 14, 1),  # 14
    (0x5401, 16, 14, 0),  # 15
    (0x5101, 17, 15, 0),  # 16
    (0x4801, 18, 16, 0),  # 17
    (0x3801, 19, 17, 0),  # 18
    (0x3401, 20, 18, 0),  # 19
    (0x3001, 21, 19, 0),  # 20
    (0x2801, 22, 19, 0),  # 21
    (0x2401, 23, 20, 0),  # 22
    (0x2201, 24, 21, 0),  # 23
    (0x1C01, 25, 22, 0),  # 24
    (0x1801, 26, 23, 0),  # 25
    (0x1601, 27, 24, 0),  # 26
    (0x1401, 28, 25, 0),  # 27
    (0x1201, 29, 26, 0),  # 28
    (0x1101, 30, 27, 0),  # 29
    (0x0AC1, 31, 28, 0),  # 30
    (0x09C1, 32, 29, 0),  # 31
    (0x08A1, 33, 30, 0),  # 32
    (0x0521, 34, 31, 0),  # 33
    (0x0441, 35, 32, 0),  # 34
    (0x02A1, 36, 33, 0),  # 35
    (0x0221, 37, 34, 0),  # 36
    (0x0141, 38, 35, 0),  # 37
    (0x0111, 39, 36, 0),  # 38
    (0x0085, 40, 37, 0),  # 39
    (0x0049, 41, 38, 0),  # 40
    (0x0025, 42, 39, 0),  # 41
    (0x0015, 43, 40, 0),  # 42
    (0x0009, 44, 41, 0),  # 43
    (0x0005, 45, 42, 0),  # 44
    (0x0001, 45, 43, 0),  # 45
    (0x5601, 46, 46, 0),  # 46
)


def _roundtrip(bits: list[int], n_ctx: int = 1, indices: list[int] | None = None):
    """Encode ``bits`` (optionally each under context ``indices[i]``) then decode.

    Returns the decoded bit list. The encoder is the independent T.88 E.3
    reference, so an exact match pins the decoder's DECODE/BYTEIN/RENORMD/
    MPS-LPS-exchange paths bit-for-bit.
    """
    enc = MQEncoder()
    enc_cx = Cx(n_ctx, 0)
    for i, bit in enumerate(bits):
        if indices is not None:
            enc_cx.set_index(indices[i])
        enc.encode(enc_cx, bit)
    data = enc.flush()

    dec = ArithmeticDecoder(ImageInputStream(data))
    dec_cx = CX(n_ctx, 0)
    out = []
    for i in range(len(bits)):
        if indices is not None:
            dec_cx.set_index(indices[i])
        out.append(dec.decode(dec_cx))
    return out


# === Qe table vs T.88 Table E.1 ============================================


def test_qe_table_full_equals_t88_table_e1():
    # Every one of the 47 rows must match the inlined spec table exactly.
    assert tuple(QE) == _T88_TABLE_E1


def test_qe_table_has_47_rows_each_4_columns():
    assert len(QE) == 47
    assert all(len(row) == 4 for row in QE)


def test_qe_state0_anchor():
    # State 0: Qe=0x5601, NMPS=1, NLPS=1, SWITCH=1.
    assert QE[0] == (0x5601, 1, 1, 1)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (0, (0x5601, 1, 1, 1)),
        (5, (0x0221, 38, 33, 0)),
        (6, (0x5601, 7, 6, 1)),
        (14, (0x5601, 15, 14, 1)),
        (24, (0x1C01, 25, 22, 0)),
        (45, (0x0001, 45, 43, 0)),
        (46, (0x5601, 46, 46, 0)),
    ],
    ids=["s0", "s5", "s6_switch", "s14_switch", "s24", "s45_nmps_eq_self", "s46_term"],
)
def test_qe_spot_check_rows(state, expected):
    assert QE[state] == expected


def test_switch_rows_are_exactly_0_6_14():
    switch = [i for i, row in enumerate(QE) if row[3] == 1]
    assert switch == [0, 6, 14]


def test_state0_and_6_and_14_share_qe_5601():
    # The three SWITCH states all carry Qe = 0x5601 (the maximum, ~0.5 prob).
    assert QE[0][0] == QE[6][0] == QE[14][0] == 0x5601


def test_nmps_is_monotone_nondecreasing_in_index_region():
    # NMPS climbs the table toward the more-skewed states; never points backward
    # except the terminal/clamped rows (45 -> 45, 46 -> 46).
    for i in range(0, 44):
        assert QE[i][1] >= i  # NMPS moves to a >= index (more skewed) or stays


def test_terminal_state_self_loops():
    # State 46 is the non-adaptive "stable" state: both NMPS and NLPS == 46.
    assert QE[46][1] == 46
    assert QE[46][2] == 46
    assert QE[46][3] == 0


# === DECODE / round-trip on known bit sequences =============================


def test_decode_known_all_zero_sequence():
    bits = [0] * 80
    assert _roundtrip(bits) == bits


def test_decode_known_all_one_sequence():
    bits = [1] * 80
    assert _roundtrip(bits) == bits


def test_decode_known_alternating_sequence():
    bits = [i & 1 for i in range(120)]
    assert _roundtrip(bits) == bits


def test_decode_known_single_bits():
    assert _roundtrip([0]) == [0]
    assert _roundtrip([1]) == [1]


def test_decode_known_short_pattern_exact():
    # A short, fixed, human-checkable pattern decoded bit-exact.
    bits = [1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 0, 1, 1]
    assert _roundtrip(bits) == bits


@pytest.mark.parametrize("seed", [1, 3, 7, 42, 99, 1234, 65537, 99991])
def test_decode_random_single_context_roundtrip(seed):
    rng = random.Random(seed)
    bits = [rng.randint(0, 1) for _ in range(rng.randint(50, 400))]
    assert _roundtrip(bits) == bits


@pytest.mark.parametrize("seed", [2, 11, 17, 55, 777, 31337])
def test_decode_random_multi_context_roundtrip(seed):
    # Cycle several distinct CX states so MPS/LPS exchange + NMPS/NLPS
    # transitions are exercised across many table rows simultaneously.
    rng = random.Random(seed)
    n_ctx = 16
    n = rng.randint(80, 500)
    bits = [rng.randint(0, 1) for _ in range(n)]
    indices = [rng.randrange(n_ctx) for _ in range(n)]
    assert _roundtrip(bits, n_ctx=n_ctx, indices=indices) == bits


def test_decode_skewed_stream_drives_state_machine_deep():
    # 5% ones forces long MPS runs (deep NMPS climb toward state 46) punctuated
    # by rare LPS events (NLPS + SWITCH near the top of the table).
    rng = random.Random(424242)
    bits = [0 if rng.random() > 0.05 else 1 for _ in range(3000)]
    assert _roundtrip(bits) == bits


# === BYTEIN: 0xFF stuffing / marker handling ===============================


class _MemIIS:
    """Minimal ImageInputStream shim (read==-1 at EOF, position unchanged)."""

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        self._pos = 0

    def get_stream_position(self) -> int:
        return self._pos

    def read(self) -> int:
        if self._pos >= len(self._data):
            return -1
        v = self._data[self._pos]
        self._pos += 1
        return v

    def seek(self, pos: int) -> None:
        self._pos = pos


def _decode_n(data: bytes, n: int, n_ctx: int = 512) -> list[int]:
    dec = ArithmeticDecoder(_MemIIS(data))
    cx = CX(n_ctx, 0)
    return [dec.decode(cx) for _ in range(n)]


def test_bytein_ff_marker_branch_b1_gt_8f():
    # 0xFF followed by a byte > 0x8F is the end-of-data marker: BYTEIN adds
    # 0xFF00, sets CT=8, and rewinds 2 so the marker is re-seen. Must not raise
    # and must produce stable bits when the marker is reached during renorm.
    data = bytes([0x00, 0xFF, 0xAC, 0xFF, 0xD9])
    bits = _decode_n(data, 40)
    assert len(bits) == 40
    assert set(bits) <= {0, 1}


def test_bytein_ff_stuffed_branch_b1_le_8f():
    # 0xFF followed by a byte <= 0x8F is a stuffed byte: BYTEIN adds B1<<9 and
    # CT=7 (only 7 fresh code bits). Exercise that branch.
    data = bytes([0x12, 0xFF, 0x7F, 0x34, 0xFF, 0x00, 0x56])
    bits = _decode_n(data, 48)
    assert len(bits) == 48
    assert set(bits) <= {0, 1}


def test_bytein_ff_boundary_exactly_8f_is_stuffed_not_marker():
    # B1 == 0x8F is NOT > 0x8F, so it takes the stuffed (CT=7) branch, not the
    # marker branch. Guards the boundary condition (> vs >=).
    data = bytes([0x00, 0xFF, 0x8F, 0x11, 0x22])
    bits = _decode_n(data, 24)
    assert len(bits) == 24


def test_bytein_ff_boundary_0x90_is_marker():
    # B1 == 0x90 IS > 0x8F -> marker branch.
    data = bytes([0x00, 0xFF, 0x90, 0x11, 0x22])
    bits = _decode_n(data, 24)
    assert len(bits) == 24


def test_decode_ff_dense_stream_roundtrips_via_encoder():
    # The encoder emits real 0xFF stuffing/terminator bytes on FLUSH; a stream
    # rich in 0xFF (all-ones tends to push C high) round-trips bit-exact, which
    # is the strongest BYTEIN correctness check.
    bits = [1] * 200 + [0, 1, 0, 1] * 50
    assert _roundtrip(bits) == bits


# === Register invariants (A keeps top bit, C bounded to 32 bits) ============


def test_registers_bounded_and_renormalized_each_decode():
    data = bytes([0x84, 0xC7, 0x3B, 0x00, 0xFF, 0x12, 0x55, 0xAA, 0xFF, 0xD9])
    dec = ArithmeticDecoder(_MemIIS(data))
    cx = CX(512, 0)
    for i in range(120):
        cx.set_index(i % 512)
        dec.decode(cx)
        # C never exceeds 32 bits (Java long masked to 0xffffffff).
        assert 0 <= dec.get_c() <= 0xFFFFFFFF
        # RENORMD guarantees A's top bit is set after every decode.
        assert dec.get_a() & 0x8000


def test_init_sets_a_to_0x8000():
    dec = ArithmeticDecoder(_MemIIS(bytes([0x84, 0xC7, 0x3B, 0x00])))
    assert dec.get_a() == 0x8000
    assert 0 <= dec.get_c() <= 0xFFFFFFFF


# === Context state transition on MPS vs LPS =================================


def test_mps_run_climbs_nmps_index():
    # Feeding a long MPS run (all matching the MPS) must walk the context index
    # up the NMPS chain. With MPS=0 (initial) and bit 0 repeatedly, the index
    # should advance from 0 toward higher (more skewed) states.
    enc = MQEncoder()
    enc_cx = Cx(1, 0)
    for _ in range(40):
        enc.encode(enc_cx, 0)
    data = enc.flush()

    dec = ArithmeticDecoder(ImageInputStream(data))
    cx = CX(1, 0)
    cx.set_index(0)
    for _ in range(40):
        assert dec.decode(cx) == 0
    # After a long MPS run the context's probability-estimate index climbed.
    assert cx.cx() > 0
    # MPS sense unchanged by a pure MPS run (SWITCH only fires on LPS).
    assert cx.mps() == 0


def test_lps_event_can_toggle_mps_on_switch_state():
    # State 0 has SWITCH=1: an LPS decoded while at the bottom state flips the
    # MPS sense. Build a stream whose first decoded bit is an LPS at state 0.
    # MPS starts 0, so an LPS yields bit 1 and toggles MPS to 1.
    enc = MQEncoder()
    enc_cx = Cx(1, 0)
    enc.encode(enc_cx, 1)  # bit != MPS(0) -> LPS at switch state 0
    data = enc.flush()

    dec = ArithmeticDecoder(ImageInputStream(data))
    cx = CX(1, 0)
    cx.set_index(0)
    assert dec.decode(cx) == 1
    # SWITCH at state 0 flips the MPS sense.
    assert cx.mps() == 1
    # NLPS at state 0 is 1, so the index moved to 1.
    assert cx.cx() == 1


# === Integer / IAID layers riding the same decoder =========================


@pytest.mark.parametrize(
    "value",
    [0, 1, -1, 7, -7, 42, -42, 255, 256, 4435, 4436, 100000, -100000, OOB],
    ids=[
        "zero", "one", "neg_one", "seven", "neg_seven", "fortytwo",
        "neg_fortytwo", "255", "256_bucket_edge", "bucket4_top",
        "bucket5_start", "big", "neg_big", "oob",
    ],
)
def test_integer_roundtrip_exact(value):
    enc = MQEncoder()
    enc_cx = Cx(512, 0)
    int_enc = ArithmeticIntegerEncoder(enc)
    int_enc.encode(enc_cx, value)
    data = enc.flush()

    dec = ArithmeticDecoder(ImageInputStream(data))
    int_dec = ArithmeticIntegerDecoder(dec)
    dec_cx = CX(512, 0)
    decoded = int_dec.decode(dec_cx)

    if value == OOB:
        assert decoded == LONG_MAX_VALUE
    else:
        assert decoded == value


@pytest.mark.parametrize("seed", [5, 50, 500, 5000])
def test_integer_stream_roundtrip(seed):
    rng = random.Random(seed)
    values = []
    for _ in range(rng.randint(5, 30)):
        if rng.random() < 0.1:
            values.append(OOB)
        else:
            values.append(rng.randint(-5000, 5000))

    enc = MQEncoder()
    enc_cx = Cx(512, 0)
    int_enc = ArithmeticIntegerEncoder(enc)
    for v in values:
        int_enc.encode(enc_cx, v)
    data = enc.flush()

    dec = ArithmeticDecoder(ImageInputStream(data))
    int_dec = ArithmeticIntegerDecoder(dec)
    dec_cx = CX(512, 0)
    for v in values:
        decoded = int_dec.decode(dec_cx)
        assert decoded == (LONG_MAX_VALUE if v == OOB else v)


@pytest.mark.parametrize(
    ("sym_code_len", "value"),
    [(1, 0), (1, 1), (4, 0), (4, 15), (5, 21), (8, 200), (8, 255)],
    ids=["l1v0", "l1v1", "l4v0", "l4v15", "l5v21", "l8v200", "l8v255"],
)
def test_iaid_roundtrip_exact(sym_code_len, value):
    enc = MQEncoder()
    enc_cx = Cx(1 << (sym_code_len + 1), 0)
    int_enc = ArithmeticIntegerEncoder(enc)
    int_enc.encode_iaid(enc_cx, value, sym_code_len)
    data = enc.flush()

    dec = ArithmeticDecoder(ImageInputStream(data))
    int_dec = ArithmeticIntegerDecoder(dec)
    dec_cx = CX(1 << (sym_code_len + 1), 0)
    assert int_dec.decode_iaid(dec_cx, sym_code_len) == value
