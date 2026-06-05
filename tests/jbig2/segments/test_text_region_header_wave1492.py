"""Header-flag parsing + validation parity for ``TextRegion`` (wave 1492).

The text-region segment-flags word (7.4.3.1.1), the optional Huffman-flags word
(7.4.3.1.2), the refinement-AT byte reads (7.4.3.1.3), the symbol-instance count
sanity clamp (7.4.3.1.4) and the ``_check_input`` validation / normalisation
(7.4.3.1.7) are driven directly off a crafted ``SubInputStream``. Each case pins
an observed parse field, the clamped instance count, or the raised
``InvalidHeaderValueException`` — mirroring upstream ``TextRegionSegment``.

Region-segment-flags bit layout consumed by ``_read_region_flags`` (16 bits):

    15 SBRTEMPLATE   14-10 SBDSOFFSET (signed 5-bit)   9 SBDEFPIXEL
    8-7 SBCOMBOP     6 TRANSPOSED     5-4 REFCORNER    3-2 LOGSBSTRIPS
    1 SBREFINE       0 SBHUFF
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.text_region import (
    InvalidHeaderValueException,
    TextRegion,
)
from pypdfbox.jbig2.util.combination_operator import CombinationOperator


def _sis(data: bytes) -> SubInputStream:
    return SubInputStream(ImageInputStream(data), 0, len(data))


def _tr(data: bytes) -> TextRegion:
    tr = TextRegion()
    tr.sub_input_stream = _sis(data)
    return tr


# --------------------------------------------------------------------------
# Region flags word
# --------------------------------------------------------------------------


def test_region_flags_defaults_all_zero():
    tr = _tr(struct.pack(">H", 0x0000))
    tr._read_region_flags()
    assert tr.sbr_template == 0
    assert tr.sbds_offset == 0
    assert tr.default_pixel == 0
    assert tr.combination_operator is CombinationOperator.OR  # code 0
    assert tr.is_transposed == 0
    assert tr.reference_corner == 0
    assert tr.log_sb_strips == 0
    assert tr.sb_strips == 1
    assert tr.use_refinement is False
    assert tr.is_huffman_encoded is False


def test_region_flags_huffman_and_refine_bits():
    # bit0 (SBHUFF) and bit1 (SBREFINE) set -> 0x0003.
    tr = _tr(struct.pack(">H", 0x0003))
    tr._read_region_flags()
    assert tr.is_huffman_encoded is True
    assert tr.use_refinement is True


def test_region_flags_signed_sbds_offset_negative():
    # SBDSOFFSET is bits 14-10, signed 5-bit. Put 0x1F (== -1) there.
    # bits 14-10 == 11111 -> value 0x1F << 10 == 0x7C00.
    tr = _tr(struct.pack(">H", 0x7C00))
    tr._read_region_flags()
    assert tr.sbds_offset == -1


def test_region_flags_log_sb_strips_and_strips():
    # LOGSBSTRIPS bits 3-2 == 11 -> 0x000C, sb_strips == 1 << 3 == 8.
    tr = _tr(struct.pack(">H", 0x000C))
    tr._read_region_flags()
    assert tr.log_sb_strips == 3
    assert tr.sb_strips == 8


def test_region_flags_combination_operator_and_template():
    # SBRTEMPLATE bit15 == 1 -> 0x8000 ; SBCOMBOP bits 8-7 == 10 -> 0x0100.
    # combination code 2 == XOR.
    tr = _tr(struct.pack(">H", 0x8000 | 0x0100))
    tr._read_region_flags()
    assert tr.sbr_template == 1
    assert tr.combination_operator is CombinationOperator.XOR


# --------------------------------------------------------------------------
# Huffman flags word
# --------------------------------------------------------------------------


def test_huffman_flags_fields():
    # SBHUFFFS bits 1-0 == 01 -> 0x0001 ; SBHUFFDS bits 3-2 == 01 -> 0x0004.
    tr = _tr(struct.pack(">H", 0x0001 | 0x0004))
    tr._read_huffman_flags()
    assert tr.sb_huff_fs == 1
    assert tr.sb_huff_ds == 1


def test_huffman_flags_rsize_bit():
    # SBHUFFRSIZE bit 14 -> 0x4000.
    tr = _tr(struct.pack(">H", 0x4000))
    tr._read_huffman_flags()
    assert tr.sb_huff_r_size == 1


# --------------------------------------------------------------------------
# Refinement AT pixels
# --------------------------------------------------------------------------


def test_use_refinement_reads_four_at_bytes():
    tr = _tr(struct.pack(">bbbb", -1, -1, -1, -1))
    tr.use_refinement = True
    tr.sbr_template = 0
    tr._read_use_refinement()
    assert tr.sbr_at_x == [-1, -1]
    assert tr.sbr_at_y == [-1, -1]


def test_use_refinement_skipped_when_template_one():
    tr = _tr(b"")  # no bytes consumed
    tr.use_refinement = True
    tr.sbr_template = 1
    tr._read_use_refinement()
    assert tr.sbr_at_x is None


# --------------------------------------------------------------------------
# Symbol-instance count clamp
# --------------------------------------------------------------------------


class _FakeRegionInfo:
    def __init__(self, w, h):
        self._w, self._h = w, h

    def get_bitmap_width(self):
        return self._w

    def get_bitmap_height(self):
        return self._h


def test_amount_of_symbol_instances_clamped_to_pixel_count():
    # 4-byte count of 1_000_000 over a 10x10 region -> clamped to 100 pixels.
    tr = _tr(struct.pack(">I", 1_000_000))
    tr.region_info = _FakeRegionInfo(10, 10)
    tr._read_amount_of_symbol_instances()
    assert tr.amount_of_symbol_instances == 100


def test_amount_of_symbol_instances_below_pixel_count_unchanged():
    tr = _tr(struct.pack(">I", 42))
    tr.region_info = _FakeRegionInfo(10, 10)
    tr._read_amount_of_symbol_instances()
    assert tr.amount_of_symbol_instances == 42


# --------------------------------------------------------------------------
# _check_input validation / normalisation
# --------------------------------------------------------------------------


def test_check_input_forbidden_huffman_value_raises():
    tr = TextRegion()
    tr.sb_huff_fs = 2  # value 2 is reserved/forbidden for SBHUFFFS
    with pytest.raises(InvalidHeaderValueException, match="not permitted"):
        tr._check_input()


def test_check_input_clears_refine_fields_without_refinement():
    tr = TextRegion()
    tr.use_refinement = False
    tr.sb_huff_r_size = 1
    tr.sb_huff_rdy = 1
    tr.sb_huff_rdx = 1
    tr.sb_huff_rd_width = 1
    tr.sb_huff_rd_height = 1
    tr._check_input()
    assert tr.sb_huff_r_size == 0
    assert tr.sb_huff_rdy == 0
    assert tr.sb_huff_rdx == 0
    assert tr.sb_huff_rd_width == 0
    assert tr.sb_huff_rd_height == 0


def test_check_input_resets_sbr_template_without_refinement():
    tr = TextRegion()
    tr.use_refinement = False
    tr.sbr_template = 1
    tr._check_input()
    assert tr.sbr_template == 0
