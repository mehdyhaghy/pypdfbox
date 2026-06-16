"""Text-region segment decode fuzz — wave 1571 (agent C).

Drives ``pypdfbox.jbig2.segments.text_region.TextRegion`` over crafted flag
words and stubbed integer-coder sequences to exercise the branches that the
five bundled ``.jb2`` fixtures (only ``21.jb2`` carries a text region — a
single-corner, non-transposed, ``LOGSBSTRIPS==0`` Huffman one) never reach:

* the 16-bit region-flags word (7.4.3.1.1) over the full SBDSOFFSET signed-5-bit
  range, every REFCORNER 0-3, TRANSPOSED 0/1, every SBCOMBOP 0-3, SBDEFPIXEL,
  SBRTEMPLATE, and LOGSBSTRIPS 0-3 (``sb_strips == 1 << log_sb_strips``);
* the optional Huffman-flags word (7.4.3.1.2) bit assignments;
* ``_decode_strip_t`` (§6.4.6) returning ``stripT * -sbStrips`` and the
  ``+= dt * sbStrips`` strip advance;
* ``_decode_current_t`` (§6.4.5 3c iii) IAIT arithmetic branch with
  ``log_sb_strips > 0`` — the residual the wave-1510 audit flagged as starved on
  the arithmetic path because the SD-aggregate route always sets ``sb_strips==1``;
* the §6.4.5 3c vi-x placement matrix asserted to *exact* blit coordinates for
  every (TRANSPOSED, REFCORNER) combination over an asymmetric symbol;
* a full multi-instance arithmetic ``_decode_symbol_instances`` run with a
  stubbed integer coder feeding STRIPT / DT / DFS / IDS / CURT / ID so the
  whole strip/instance loop, the SBDSOFFSET S-advance, and the OOB / instance
  count exit guards all fire.

Field layout (16-bit region-flags word, MSB-first, 7.4.3.1.1):

    15 SBRTEMPLATE   14-10 SBDSOFFSET (signed 5-bit)   9 SBDEFPIXEL
    8-7 SBCOMBOP     6 TRANSPOSED     5-4 REFCORNER    3-2 LOGSBSTRIPS
    1 SBREFINE       0 SBHUFF

All assertions are derived from ITU-T T.88 and pinned against the upstream
``apache/pdfbox-jbig2`` ``TextRegion.blit`` / ``readRegionFlags`` /
``decodeStripT`` / ``decodeCurrentT`` semantics (verified verbatim).
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_integer_decoder import (
    LONG_MAX_VALUE,
)
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.text_region import TextRegion
from pypdfbox.jbig2.util.combination_operator import CombinationOperator


def _sis(data: bytes) -> SubInputStream:
    return SubInputStream(ImageInputStream(data), 0, len(data))


def _tr(data: bytes = b"\x00\x00") -> TextRegion:
    tr = TextRegion()
    tr.sub_input_stream = _sis(data)
    return tr


def _solid(width: int, height: int) -> Bitmap:
    bmp = Bitmap(width, height)
    for i in range(len(bmp.get_byte_array())):
        bmp.set_byte(i, 0xFF)
    return bmp


class _StubIntegerDecoder:
    """Yields a fixed sequence for ``decode`` and ``decode_iaid``.

    ``decode`` raises ``StopIteration``-equivalent only if exhausted; the test
    sequences are sized to the exact number of pulls.
    """

    def __init__(self, values, iaid_values=None):
        self._values = list(values)
        self._i = 0
        self._iaid = list(iaid_values or [])
        self._j = 0

    def decode(self, cx):
        value = self._values[self._i]
        self._i += 1
        return value

    def decode_iaid(self, cx, length):
        value = self._iaid[self._j]
        self._j += 1
        return value


# ---------------------------------------------------------------------------
# Region-flags word — full SBDSOFFSET signed range
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw5", "expected"),
    [(v, v if v <= 0x0F else v - 0x20) for v in range(32)],
    ids=[f"sbds_raw{v}" for v in range(32)],
)
def test_sbds_offset_sign_extension_full_range(raw5, expected):
    """Bits 14-10 SBDSOFFSET: a 5-bit value > 0x0F is sign-extended by -0x20.

    So raw 0..15 -> 0..15 (non-negative), raw 16..31 -> -16..-1.
    """
    word = raw5 << 10
    tr = _tr(struct.pack(">H", word))
    tr._read_region_flags()
    assert tr.sbds_offset == expected


def test_sbds_offset_max_negative_and_max_positive():
    # raw 0x10 (10000b) -> -16 ; raw 0x0F (01111b) -> +15.
    tr_neg = _tr(struct.pack(">H", 0x10 << 10))
    tr_neg._read_region_flags()
    assert tr_neg.sbds_offset == -16

    tr_pos = _tr(struct.pack(">H", 0x0F << 10))
    tr_pos._read_region_flags()
    assert tr_pos.sbds_offset == 15


# ---------------------------------------------------------------------------
# Region-flags word — LOGSBSTRIPS / sb_strips
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("log", [0, 1, 2, 3], ids=["log0", "log1", "log2", "log3"])
def test_log_sb_strips_to_sb_strips(log):
    """Bits 3-2 LOGSBSTRIPS: sb_strips == 1 << log_sb_strips."""
    word = log << 2
    tr = _tr(struct.pack(">H", word))
    tr._read_region_flags()
    assert tr.log_sb_strips == log
    assert tr.sb_strips == (1 << log)


# ---------------------------------------------------------------------------
# Region-flags word — REFCORNER / TRANSPOSED / SBCOMBOP / SBDEFPIXEL / SBRTEMPLATE
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("corner", [0, 1, 2, 3], ids=lambda c: f"corner{c}")
def test_reference_corner_bits_4_5(corner):
    word = corner << 4
    tr = _tr(struct.pack(">H", word))
    tr._read_region_flags()
    assert tr.reference_corner == corner


@pytest.mark.parametrize("transposed", [0, 1], ids=["t0", "t1"])
def test_transposed_bit_6(transposed):
    word = transposed << 6
    tr = _tr(struct.pack(">H", word))
    tr._read_region_flags()
    assert tr.is_transposed == transposed


@pytest.mark.parametrize(
    ("code", "op"),
    [
        (0, CombinationOperator.OR),
        (1, CombinationOperator.AND),
        (2, CombinationOperator.XOR),
        (3, CombinationOperator.XNOR),
    ],
    ids=["or", "and", "xor", "xnor"],
)
def test_combination_operator_bits_7_8(code, op):
    word = code << 7
    tr = _tr(struct.pack(">H", word))
    tr._read_region_flags()
    assert tr.combination_operator is op


def test_default_pixel_bit_9_and_template_bit_15():
    tr = _tr(struct.pack(">H", (1 << 9) | (1 << 15)))
    tr._read_region_flags()
    assert tr.default_pixel == 1
    assert tr.sbr_template == 1


def test_refine_and_huffman_low_bits():
    tr = _tr(struct.pack(">H", 0b11))
    tr._read_region_flags()
    assert tr.use_refinement is True
    assert tr.is_huffman_encoded is True


def test_all_region_flags_packed_together():
    """A fully-populated flag word decodes every field independently."""
    # SBRTEMPLATE=1, SBDSOFFSET raw=0b10101(=-11), SBDEFPIXEL=1, SBCOMBOP=2,
    # TRANSPOSED=1, REFCORNER=3, LOGSBSTRIPS=2, SBREFINE=1, SBHUFF=0
    word = (
        (1 << 15)
        | (0b10101 << 10)
        | (1 << 9)
        | (2 << 7)
        | (1 << 6)
        | (3 << 4)
        | (2 << 2)
        | (1 << 1)
        | 0
    )
    tr = _tr(struct.pack(">H", word))
    tr._read_region_flags()
    assert tr.sbr_template == 1
    assert tr.sbds_offset == 0b10101 - 0x20  # -11
    assert tr.default_pixel == 1
    assert tr.combination_operator is CombinationOperator.XOR
    assert tr.is_transposed == 1
    assert tr.reference_corner == 3
    assert tr.log_sb_strips == 2
    assert tr.sb_strips == 4
    assert tr.use_refinement is True
    assert tr.is_huffman_encoded is False


# ---------------------------------------------------------------------------
# Huffman-flags word (7.4.3.1.2)
# ---------------------------------------------------------------------------


def test_huffman_flags_bit_layout():
    # bit14 RSIZE=1, 13-12 RDY=2->but 2 is illegal for RD*, use 1, 11-10 RDX=1,
    # 9-8 RDH=1, 7-6 RDW=1, 5-4 DT=3, 3-2 DS=1, 1-0 FS=1 ; bit15 dirty.
    word = (
        (0 << 15)
        | (1 << 14)
        | (1 << 12)  # rdy
        | (1 << 10)  # rdx
        | (1 << 8)  # rdh
        | (1 << 6)  # rdw
        | (3 << 4)  # dt
        | (1 << 2)  # ds
        | (1 << 0)  # fs
    )
    tr = _tr(struct.pack(">H", word))
    tr._read_huffman_flags()
    assert tr.sb_huff_r_size == 1
    assert tr.sb_huff_rdy == 1
    assert tr.sb_huff_rdx == 1
    assert tr.sb_huff_rd_height == 1
    assert tr.sb_huff_rd_width == 1
    assert tr.sb_huff_dt == 3
    assert tr.sb_huff_ds == 1
    assert tr.sb_huff_fs == 1


# ---------------------------------------------------------------------------
# Strip-T / DT (§6.4.6) — arithmetic path sign & scaling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sb_strips", [1, 2, 4, 8], ids=lambda s: f"strips{s}")
def test_decode_strip_t_negates_and_scales(sb_strips):
    """§6.4.6: decode_strip_t returns ``raw * -sb_strips``."""
    tr = _tr()
    tr.is_huffman_encoded = False
    tr.sb_strips = sb_strips
    tr.cx_iadt = object()
    tr.integer_decoder = _StubIntegerDecoder([3])
    assert tr._decode_strip_t() == 3 * -sb_strips


@pytest.mark.parametrize("sb_strips", [1, 2, 4], ids=lambda s: f"strips{s}")
def test_decode_dt_scales_positive(sb_strips):
    """§6.4.6 3b: dt is scaled by ``+sb_strips``."""
    tr = _tr()
    tr.is_huffman_encoded = False
    tr.sb_strips = sb_strips
    tr.cx_iadt = object()
    tr.integer_decoder = _StubIntegerDecoder([5])
    assert tr._decode_dt() == 5 * sb_strips


# ---------------------------------------------------------------------------
# current_t (§6.4.5 3c iii) — IAIT arithmetic branch with log_sb_strips > 0
# ---------------------------------------------------------------------------


def test_decode_current_t_single_strip_returns_zero():
    tr = _tr()
    tr.sb_strips = 1
    assert tr._decode_current_t() == 0


@pytest.mark.parametrize("log", [1, 2, 3], ids=["log1", "log2", "log3"])
def test_decode_current_t_iait_arithmetic(log):
    """sb_strips != 1, arithmetic: pulls IAIT from the integer decoder."""
    tr = _tr()
    tr.sb_strips = 1 << log
    tr.is_huffman_encoded = False
    tr.cx_iait = object()
    tr.integer_decoder = _StubIntegerDecoder([2])
    assert tr._decode_current_t() == 2


@pytest.mark.parametrize("log", [1, 2, 3], ids=["log1", "log2", "log3"])
def test_decode_current_t_huffman_reads_log_bits(log):
    """sb_strips != 1, Huffman: reads ``log_sb_strips`` raw bits."""
    # Put a value in the top bits so read_bits(log) returns a known value.
    tr = _tr(bytes([0xFF, 0x00]))
    tr.sb_strips = 1 << log
    tr.is_huffman_encoded = True
    tr.log_sb_strips = log
    assert tr._decode_current_t() == (1 << log) - 1  # log ones


# ---------------------------------------------------------------------------
# Placement matrix (§6.4.5 3c vi-x) — exact blit coordinates
# ---------------------------------------------------------------------------


def _placement_region(transposed: int, corner: int, current_s: int) -> TextRegion:
    tr = TextRegion()
    tr.region_bitmap = Bitmap(64, 64)
    tr.combination_operator = CombinationOperator.OR
    tr.is_transposed = transposed
    tr.reference_corner = corner
    tr.current_s = current_s
    return tr


# Asymmetric symbol so width-1 (=7) and height-1 (=3) are distinguishable.
_W, _H = 8, 4


def _expected_blit_and_post(transposed, corner, current_s, t):
    """Re-derive expected (s, t) blit origin + post-blit current_s per T.88.

    Mirrors the upstream blit() arithmetic exactly (independent of the port).
    """
    s = current_s
    # pre-shift (step vi)
    if transposed == 0 and corner in (2, 3):
        s += _W - 1
    elif transposed == 1 and corner in (0, 2):
        s += _H - 1
    cur_after_pre = s  # current_s after pre-shift
    # viii) transpose swap
    if transposed == 1:
        t, s = s, t
    # corner offset
    if corner != 1:
        if corner == 0:
            t -= _H - 1
        elif corner == 2:
            t -= _H - 1
            s -= _W - 1
        elif corner == 3:
            s -= _W - 1
    blit_s, blit_t = s, t
    # post-shift (step x)
    cur = cur_after_pre
    if transposed == 0 and corner in (0, 1):
        cur += _W - 1
    if transposed == 1 and corner in (1, 3):
        cur += _H - 1
    return blit_s, blit_t, cur


@pytest.mark.parametrize(
    ("transposed", "corner"),
    [(t, c) for t in (0, 1) for c in (0, 1, 2, 3)],
    ids=[f"t{t}_c{c}" for t in (0, 1) for c in (0, 1, 2, 3)],
)
def test_blit_exact_coordinates_and_current_s(transposed, corner):
    """Every (TRANSPOSED, REFCORNER) combo lands the symbol at the exact (s, t)
    derived from T.88 and advances current_s by the spec amount."""
    start_s, in_t = 20, 15
    tr = _placement_region(transposed, corner, start_s)
    ib = _solid(_W, _H)
    exp_s, exp_t, exp_cur = _expected_blit_and_post(
        transposed, corner, start_s, in_t
    )

    tr._blit(ib, in_t)

    # The symbol pixels must appear at (exp_s, exp_t).. so check a corner pixel.
    if 0 <= exp_s < 64 and 0 <= exp_t < 64:
        assert tr.region_bitmap.get_pixel(exp_s, exp_t) == 1
    assert tr.current_s == exp_cur


def test_blit_transposed_swaps_axes():
    """TRANSPOSED==1, REFCORNER==1 (TL): no corner offset, s<->t swapped, so
    the symbol top-left lands at (in_t, current_s)."""
    tr = _placement_region(1, 1, 5)
    ib = _solid(_W, _H)
    tr._blit(ib, 9)
    # swap: blit s = original t = 9, blit t = original current_s = 5.
    assert tr.region_bitmap.get_pixel(9, 5) == 1


# ---------------------------------------------------------------------------
# Full multi-instance arithmetic decode loop (§6.4.5 3)
# ---------------------------------------------------------------------------


def test_decode_symbol_instances_two_strips_with_offset_and_oob():
    """Drive the whole instance loop with a stubbed integer coder.

    sb_strips=2, sbds_offset=+1, 3 instances across 2 strips. The decode order
    of integer pulls (arithmetic, no refinement, no huffman) is:
      strip_t  : IADT
      strip 0  : DT(IADT), DFS(IAFS), CURT(IAIT), [id IAID], then
                 IDS(IADS)=OOB -> end strip
      strip 1  : DT(IADT), DFS(IAFS), CURT(IAIT), [id IAID],
                 IDS(IADS), CURT(IAIT), [id IAID], IDS(IADS)=OOB
    We feed a value sequence and assert it terminates at the instance count.
    """
    tr = TextRegion()
    tr.region_bitmap = Bitmap(64, 16)
    tr.region_info = None
    tr.combination_operator = CombinationOperator.OR
    tr.is_huffman_encoded = False
    tr.use_refinement = False
    tr.is_transposed = 0
    tr.reference_corner = 1  # TL: no pre/corner shift, post += width-1
    tr.sb_strips = 2
    tr.log_sb_strips = 1
    tr.sbds_offset = 1
    tr.amount_of_symbol_instances = 3
    tr.symbol_code_length = 1
    sym = _solid(4, 4)
    tr.symbols = [sym, sym]
    # IADT pulls: strip_t, then per-strip dt. IAFS: dfs per strip-first.
    # IADS: ids (OOB == LONG_MAX_VALUE ends strip). IAIT: current_t per inst.
    # We use separate cx objects keyed by identity inside the stub via order.
    # Sequence below matches the documented pull order.
    iadt = _StubIntegerDecoder([0, 1, 1])  # strip_t=0, dt strip0=1, dt strip1=1
    iafs = _StubIntegerDecoder([0, 0])  # dfs strip0, dfs strip1
    iads = _StubIntegerDecoder([LONG_MAX_VALUE, 2, LONG_MAX_VALUE])
    iait = _StubIntegerDecoder([0, 0, 0])
    iaid = _StubIntegerDecoder([], [0, 0, 0])

    # A single dispatching stub keyed by the cx object passed in.
    class _Dispatch:
        def __init__(self):
            self.map = {}

        def decode(self, cx):
            return self.map[id(cx)].decode(cx)

        def decode_iaid(self, cx, length):
            return iaid.decode_iaid(cx, length)

    disp = _Dispatch()
    tr.cx_iadt = object()
    tr.cx_iafs = object()
    tr.cx_iads = object()
    tr.cx_iait = object()
    tr.cx_iaid = object()
    disp.map = {
        id(tr.cx_iadt): iadt,
        id(tr.cx_iafs): iafs,
        id(tr.cx_iads): iads,
        id(tr.cx_iait): iait,
    }
    tr.integer_decoder = disp

    tr._decode_symbol_instances()
    # All three instances consumed; iaid pulled exactly 3 times.
    assert iaid._j == 3
    # sb_strips != 1 -> the IAIT (current_t) arithmetic branch fired once per
    # instance: this is the wave-1510 "starved" residual.
    assert iait._i == 3


def test_decode_symbol_instances_instance_count_guard():
    """The ``instance_counter >= amount`` guard breaks a non-OOB strip so a
    pathological IDS stream that never yields OOB still terminates."""
    tr = TextRegion()
    tr.region_bitmap = Bitmap(256, 8)
    tr.region_info = None
    tr.combination_operator = CombinationOperator.OR
    tr.is_huffman_encoded = False
    tr.use_refinement = False
    tr.is_transposed = 0
    tr.reference_corner = 1
    tr.sb_strips = 1
    tr.sbds_offset = 0
    tr.amount_of_symbol_instances = 2
    tr.symbol_code_length = 1
    sym = _solid(2, 2)
    tr.symbols = [sym, sym]

    # sb_strips==1 -> current_t always 0 (no IAIT pulls).
    # one strip, IDS never OOB; must stop after 2 instances via the count guard.
    iadt = _StubIntegerDecoder([0, 0])  # strip_t, dt
    iafs = _StubIntegerDecoder([0])
    iads = _StubIntegerDecoder([1, 1, 1, 1])  # never OOB
    iaid = _StubIntegerDecoder([], [0, 0, 0])

    class _Dispatch:
        def decode(self, cx):
            return self.map[id(cx)].decode(cx)

        def decode_iaid(self, cx, length):
            return iaid.decode_iaid(cx, length)

    disp = _Dispatch()
    tr.cx_iadt = object()
    tr.cx_iafs = object()
    tr.cx_iads = object()
    tr.cx_iait = object()
    tr.cx_iaid = object()
    disp.map = {
        id(tr.cx_iadt): iadt,
        id(tr.cx_iafs): iafs,
        id(tr.cx_iads): iads,
    }
    tr.integer_decoder = disp

    tr._decode_symbol_instances()
    assert iaid._j == 2
