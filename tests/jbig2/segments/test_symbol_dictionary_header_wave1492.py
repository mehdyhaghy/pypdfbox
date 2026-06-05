"""Header-parse + flag-validation parity for ``SymbolDictionary`` (wave 1492).

The symbol-dictionary *flags word* (7.4.2.1.1), the AT-pixel reads (7.4.2.1.2 /
7.4.2.1.3), the coding-context reuse validation (7.4.2.1.1 last paragraph) and
the ``_check_input`` flag-normalisation (the upstream sanity clamps applied to a
contradictory header) are exercised here directly: a crafted ``SubInputStream``
plus a minimal segment-header stub drives ``SymbolDictionary.init``.

Each case pins an observable parse outcome (the decoded flag fields, the AT
arrays, or the raised ``InvalidHeaderValueException``), matching the upstream
``SymbolDictionarySegment.parseHeader`` byte-for-byte.

Flag-word bit layout consumed by ``_read_region_flags`` (MSB first, 16 bits):

    15-13 reserved   12 SDRTEMPLATE   11-10 SDTEMPLATE     9 context-retained
    8 context-used   7 aggInstSel     6 bmSizeSel          5-4 huffDecodeWidth
    3-2 huffDecodeHeight              1 refAgg              0 huffman
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.symbol_dictionary import (
    InvalidHeaderValueException,
    SymbolDictionary,
)


class _FakeHeader:
    """Minimal stand-in for ``SegmentHeader`` (only ``get_rt_segments`` used)."""

    def __init__(self, rt_segments=None):
        self._rt = rt_segments

    def get_rt_segments(self):
        return self._rt


def _sis(data: bytes) -> SubInputStream:
    return SubInputStream(ImageInputStream(data), 0, len(data))


def _flags(flags: int, *, at_pairs=(), refagg_pairs=(),
           exported=0, new=0) -> bytes:
    """Build a symbol-dictionary header byte stream from its fields."""
    out = bytearray(struct.pack(">H", flags))
    for x, y in at_pairs:
        out += struct.pack(">bb", x, y)
    for x, y in refagg_pairs:
        out += struct.pack(">bb", x, y)
    out += struct.pack(">i", exported)
    out += struct.pack(">i", new)
    return bytes(out)


def _parse(data: bytes, header=None) -> SymbolDictionary:
    sd = SymbolDictionary()
    sd.init(header or _FakeHeader(), _sis(data))
    return sd


# --------------------------------------------------------------------------
# Arithmetic (non-Huffman) flag words + AT pixel reads
# --------------------------------------------------------------------------


def test_arith_template0_reads_four_at_pairs():
    # flags 0x0000 -> arithmetic, SDTEMPLATE 0 -> 4 AT pairs (8 bytes).
    data = _flags(0x0000, at_pairs=[(3, -1), (-3, -1), (2, -2), (-2, -2)],
                  exported=5, new=7)
    sd = _parse(data)
    assert sd.is_huffman_encoded is False
    assert sd.sd_template == 0
    assert sd.sd_at_x == [3, -3, 2, -2]
    assert sd.sd_at_y == [-1, -1, -2, -2]
    assert sd.amount_of_export_symbolss == 5
    assert sd.amount_of_new_symbols == 7


def test_arith_template1_reads_one_at_pair():
    # SDTEMPLATE 1 -> bits 11-10 == 01 -> flags 0x0400. 1 AT pair (2 bytes).
    data = _flags(0x0400, at_pairs=[(3, -1)], exported=1, new=2)
    sd = _parse(data)
    assert sd.sd_template == 1
    assert sd.sd_at_x == [3]
    assert sd.sd_at_y == [-1]


def test_refinement_aggregation_reads_refinement_at_pairs():
    # refAgg bit1 == 1 and SDRTEMPLATE bit12 == 0 -> 2 refinement AT pairs.
    # flags: bit1 set -> 0x0002. SDTEMPLATE 0 -> still 4 direct AT pairs.
    data = _flags(0x0002,
                  at_pairs=[(0, 0), (0, 0), (0, 0), (0, 0)],
                  refagg_pairs=[(-1, -1), (-1, -1)],
                  exported=0, new=0)
    sd = _parse(data)
    assert sd.use_refinement_aggregation is True
    assert sd.sdr_template == 0
    assert sd.sdr_at_x == [-1, -1]
    assert sd.sdr_at_y == [-1, -1]


def test_huffman_flag_skips_at_pixels():
    # huffman bit0 == 1 -> flags 0x0001. No AT pixels read at all.
    data = _flags(0x0001, exported=3, new=4)
    sd = _parse(data)
    assert sd.is_huffman_encoded is True
    assert sd.sd_at_x is None
    assert sd.sd_at_y is None
    assert sd.amount_of_export_symbolss == 3
    assert sd.amount_of_new_symbols == 4


# --------------------------------------------------------------------------
# Coding-context reuse validation
# --------------------------------------------------------------------------


def test_context_used_without_referred_dict_raises():
    # context-used bit8 == 1, no referred-to segments -> InvalidHeaderValue.
    data = _flags(0x0100, at_pairs=[(0, 0)] * 4, exported=0, new=0)
    with pytest.raises(InvalidHeaderValueException, match="no referred symbol"):
        _parse(data, header=_FakeHeader(rt_segments=None))


def test_context_used_referred_dict_not_retaining_raises():
    # A referred type-0 dictionary that does NOT retain context -> error message
    # about "does not retain coding context".
    prev = SymbolDictionary()
    prev.is_coding_context_retained = False
    # Already-decoded referred dictionary so get_dictionary() returns at once
    # (we only care about the context-retention validation branch here).
    prev.export_symbols = []
    prev.amount_of_export_symbolss = 0

    class _Ref:
        def get_segment_type(self):
            return 0

        def get_segment_data(self):
            return prev

    data = _flags(0x0100, at_pairs=[(0, 0)] * 4, exported=0, new=0)
    with pytest.raises(InvalidHeaderValueException, match="does not retain"):
        _parse(data, header=_FakeHeader(rt_segments=[_Ref()]))


# --------------------------------------------------------------------------
# _check_input flag normalisation (upstream clamps a contradictory header)
# --------------------------------------------------------------------------


def test_check_input_normalises_arith_huffman_selections():
    # Arithmetic header but huff selection bits set -> they are cleared.
    # bmSizeSel bit6, huffDecodeWidth bits5-4 == 11, huffDecodeHeight bits3-2 == 11
    # -> 0x0040 | 0x0030 | 0x000C == 0x007C. Arithmetic (bit0 == 0) so 4 AT pairs.
    data = _flags(0x007C, at_pairs=[(0, 0)] * 4, exported=0, new=0)
    sd = _parse(data)
    assert sd.is_huffman_encoded is False
    assert sd.sd_huff_bm_size_selection == 0
    assert sd.sd_huff_decode_width_selection == 0
    assert sd.sd_huff_decode_height_selection == 0


def test_check_input_huffman_clears_context_flags_without_refagg():
    # Huffman (bit0) + context-retained (bit9) but no refAgg -> retained cleared.
    # bit0 | bit9 == 0x0001 | 0x0200 == 0x0201.
    data = _flags(0x0201, exported=0, new=0)
    sd = _parse(data)
    assert sd.is_huffman_encoded is True
    assert sd.is_coding_context_retained is False


def test_sb_sym_code_len_arith_vs_huffman():
    sd = SymbolDictionary()
    sd.amount_of_imported_symbols = 0
    sd.amount_of_new_symbols = 4  # log2(4) == 2
    sd.is_huffman_encoded = False
    assert sd._get_sb_sym_code_len() == 2
    # huffman path takes max(.., 1); with a single symbol log2(1) == 0 -> 1.
    sd.amount_of_new_symbols = 1
    sd.is_huffman_encoded = True
    assert sd._get_sb_sym_code_len() == 1
