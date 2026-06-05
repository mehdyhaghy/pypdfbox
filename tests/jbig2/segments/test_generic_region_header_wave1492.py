"""Header-parse + SLTP-context parity for ``GenericRegion`` (wave 1492).

Drives ``GenericRegion.init`` off a crafted region-info + generic-region-flags
header (7.4.6.2 / 7.4.6.3) and pins the parsed flags, the AT-pixel arrays (whose
count depends on GBTEMPLATE / EXTTEMPLATE), and the segment-data offsets. The
``_decode_sltp`` typical-prediction context value per GBTEMPLATE (6.2.5.7 step
3b, the magic 0x9B25 / 0x0795 / 0x00E5 / 0x0195 constants) is pinned against a
stub arithmetic decoder so the per-template constants stay exact.

Generic-region-flags byte (8 bits, read MSB first):

    7-5 reserved   4 EXTTEMPLATE   3 TPGDON   2-1 GBTEMPLATE   0 MMR
"""

from __future__ import annotations

import struct

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.generic_region import GenericRegion


class _FakeHeader:
    def get_rt_segments(self):
        return None


def _region_info(width: int, height: int) -> bytes:
    # w, h, x, y (4 bytes each) + 1 flags byte = 17 bytes.
    return struct.pack(">IIII", width, height, 0, 0) + b"\x00"


def _sis(data: bytes) -> SubInputStream:
    return SubInputStream(ImageInputStream(data), 0, len(data))


def _init(width, height, flag_byte, at_pixels=b"", trailer=b"") -> GenericRegion:
    data = _region_info(width, height) + bytes([flag_byte]) + at_pixels + trailer
    gr = GenericRegion()
    gr.init(_FakeHeader(), _sis(data))
    return gr


# --------------------------------------------------------------------------
# Flags byte
# --------------------------------------------------------------------------


def test_template0_reads_four_at_pairs():
    # flags 0x00 -> arithmetic, GBTEMPLATE 0, no ext -> 4 AT pairs (8 bytes).
    at = struct.pack(">bbbbbbbb", 3, -1, -3, -1, 2, -2, -2, -2)
    gr = _init(8, 2, 0x00, at_pixels=at)
    assert gr.is_mmr_encoded is False
    assert gr.gb_template == 0
    assert gr.use_ext_templates is False
    assert gr.is_tpgdon is False
    assert gr.gb_at_x == [3, -3, 2, -2]
    assert gr.gb_at_y == [-1, -1, -2, -2]


def test_template1_reads_one_at_pair():
    # GBTEMPLATE 1 -> bits 2-1 == 01 -> 0x02. 1 AT pair.
    at = struct.pack(">bb", 3, -1)
    gr = _init(8, 2, 0x02, at_pixels=at)
    assert gr.gb_template == 1
    assert gr.gb_at_x == [3]
    assert gr.gb_at_y == [-1]


def test_tpgdon_bit_set():
    # TPGDON bit3 -> 0x08, GBTEMPLATE 0.
    at = struct.pack(">bbbbbbbb", 0, 0, 0, 0, 0, 0, 0, 0)
    gr = _init(8, 2, 0x08, at_pixels=at)
    assert gr.is_tpgdon is True


def test_ext_templates_reads_twelve_at_pairs():
    # EXTTEMPLATE bit4 -> 0x10 with GBTEMPLATE 0 -> 12 AT pairs (24 bytes).
    at = bytes(24)
    gr = _init(8, 2, 0x10, at_pixels=at)
    assert gr.use_ext_templates is True
    assert len(gr.gb_at_x) == 12
    assert len(gr.gb_at_y) == 12


def test_mmr_skips_at_pixels():
    # MMR bit0 -> 0x01. No AT pixels are read.
    gr = _init(8, 2, 0x01, at_pixels=b"")
    assert gr.is_mmr_encoded is True
    assert gr.gb_at_x is None
    assert gr.gb_at_y is None


def test_data_structure_offsets_after_header():
    at = bytes(8)
    trailer = b"\xde\xad\xbe\xef"
    gr = _init(8, 2, 0x00, at_pixels=at, trailer=trailer)
    # header = 17 (region info) + 1 (flags) + 8 (AT) == 26 bytes.
    assert gr.data_offset == 26
    assert gr.data_header_length == 26
    assert gr.data_length == len(trailer)


def test_region_info_dimensions_parsed():
    gr = _init(13, 7, 0x01)
    assert gr.region_info.get_bitmap_width() == 13
    assert gr.region_info.get_bitmap_height() == 7


# --------------------------------------------------------------------------
# _decode_sltp context constants (one per GBTEMPLATE)
# --------------------------------------------------------------------------


class _StubCX:
    def __init__(self):
        self.last_index = None

    def set_index(self, idx):
        self.last_index = idx


class _StubArith:
    def decode(self, cx):
        return 1


def _sltp_index(template: int) -> int:
    gr = GenericRegion()
    gr.gb_template = template
    gr.cx = _StubCX()
    gr.arith_decoder = _StubArith()
    bit = gr._decode_sltp()
    assert bit == 1
    return gr.cx.last_index


def test_sltp_context_constants_per_template():
    assert _sltp_index(0) == 0x9B25
    assert _sltp_index(1) == 0x0795
    assert _sltp_index(2) == 0x00E5
    assert _sltp_index(3) == 0x0195
