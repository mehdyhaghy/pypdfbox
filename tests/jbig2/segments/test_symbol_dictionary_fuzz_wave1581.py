"""Symbol-dictionary decode-body fuzz / branch coverage — wave 1581.

The arithmetic-direct (SDHUFF=0, SDREFAGG=0) path is already pinned bit-exact by
``test_symbol_dictionary.py`` against the bundled ``.jb2`` fixtures, and the
header/flag-word + ``_check_input`` normalisation by
``test_symbol_dictionary_header_wave1492.py``. The remaining ~16 % of
``pypdfbox/jbig2/segments/symbol_dictionary.py`` lives in branches that no
standalone arithmetic fixture reaches:

* the Huffman direct path (§6.5.5 4d): height-class collective bitmap (both the
  uncompressed ``BMSIZE==0`` byte-copy and the ``BMSIZE!=0`` generic-region
  variant), the per-symbol slice ``_decode_height_class_bitmap``, and the
  standard-table / alternate-standard-table / user-table selectors of
  ``_decode_height_class_delta_height_with_huffman`` / ``_decode_difference_width``
  / ``_huff_decode_bm_size`` (SDHUFFDH/DW/BMSIZE ``== 0 / 1 / 3``);
* the refinement-aggregation path (§6.5.8.2): the IAID/IARDX/IARDY integer-coder
  reset (``_reset_integer_coder_statistics`` with SDREFAGG on), the
  single-instance ``_decode_refined_symbol`` and the aggregate
  ``_decode_through_text_region`` (IAAI ``> 1``);
* the imported-symbol import counting (``_retrieve_import_symbols``), the
  retained-coding-context adoption (``_adopt_retained_coding_contexts`` /
  ``_validate_context_values`` success path), and the ``_get_user_table``
  table-counter increment arm.

This module drives those branches deterministically (no live oracle) by building
full decodable SD data parts with the test-only encoder
(:mod:`tests.jbig2.helpers.jb2_encoder`, itself verified bit-exact vs the bundled
PDFBox 3.0.7 jar) and a fake ``SegmentHeader`` that supplies referred-to type-0
(symbol dictionary) and type-53 (custom Huffman table) segments. Expected values
are read from the T.88 spec semantics (symbol counts, exported widths/heights,
the toggling EXFLAGS run sense) rather than re-hashing decoder output, so a sense
or ordinal-accumulation regression is caught.
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.err.invalid_header_value_exception import (
    InvalidHeaderValueException,
)
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.symbol_dictionary import (
    SymbolDictionary as _SymbolDictionary,
)
from pypdfbox.jbig2.segments.symbol_dictionary import (
    _to_signed_int32,
)
from pypdfbox.jbig2.segments.table import Table
from tests.jbig2.helpers.jb2_encoder import (
    arithmetic_sd_data,
    arithmetic_sd_refagg_aggregate_data,
    arithmetic_sd_refagg_single_data,
    huffman_sd_alt_standard_table_data,
    huffman_sd_data,
    huffman_sd_import_chain_data,
    huffman_sd_user_table_data,
    table_segment_data,
    wide_table_segment_data,
)

# ---------------------------------------------------------------------------
# Fake segment-header / referred-segment scaffolding
# ---------------------------------------------------------------------------


class _FakeRef:
    """A referred-to segment: exposes ``get_segment_type`` / ``get_segment_data``."""

    def __init__(self, segment_type: int, data: object) -> None:
        self._segment_type = segment_type
        self._data = data

    def get_segment_type(self) -> int:
        return self._segment_type

    def get_segment_data(self) -> object:
        return self._data


class _FakeHeader:
    def __init__(self, refs: list[_FakeRef] | None = None) -> None:
        self._refs = refs

    def get_rt_segments(self) -> list[_FakeRef] | None:
        return self._refs


def _sis(data: bytes) -> SubInputStream:
    return SubInputStream(ImageInputStream(data), 0, len(data))


def _decode(data: bytes, refs: list[_FakeRef] | None = None) -> _SymbolDictionary:
    sd = _SymbolDictionary()
    sd.init(_FakeHeader(refs), _sis(data))
    return sd


def _table_segment(data: bytes) -> Table:
    """Build a real ``Table`` (type-53 segment data) so ``_get_user_table`` can
    wrap it in an ``EncodedTable``."""
    t = Table()
    t.init(_FakeHeader(), _sis(data))
    return t


# ---------------------------------------------------------------------------
# Huffman direct path — standard tables (SDHUFFDH/DW/BMSIZE == 0), collective
# bitmap uncompressed, per-symbol slice, export runs.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "symbols",
    [
        [(8, 10)],
        [(8, 10), (16, 10)],
        [(3, 7), (5, 7), (9, 7)],
        [(1, 1)],
    ],
    ids=["single", "two_same_hc", "three_same_hc", "tiny"],
)
def test_huffman_standard_table_dictionary_decodes(symbols):
    sd = _decode(huffman_sd_data(symbols))
    assert sd.is_huffman_encoded is True
    assert sd.use_refinement_aggregation is False
    # Standard-table selectors stay 0.
    assert sd.sd_huff_decode_height_selection == 0
    assert sd.sd_huff_decode_width_selection == 0
    assert sd.sd_huff_bm_size_selection == 0

    out = sd.get_dictionary()
    # All symbols exported (encoder exports every symbol).
    assert len(out) == len(symbols)
    for bitmap, (w, h) in zip(out, symbols, strict=True):
        assert bitmap.get_width() == w
        assert bitmap.get_height() == h


def test_huffman_dictionary_top_left_pixel_set():
    # The encoder sets the top-left pixel of each symbol; confirm the collective
    # bitmap slice (_decode_height_class_bitmap) lands the pixel at (0, 0).
    sd = _decode(huffman_sd_data([(8, 4)]))
    out = sd.get_dictionary()
    assert out[0].get_pixel(0, 0) == 1


def test_huffman_amount_fields_and_no_at_pixels():
    sd = _decode(huffman_sd_data([(8, 10), (16, 10)]))
    assert sd.amount_of_new_symbols == 2
    assert sd.amount_of_export_symbolss == 2
    # Huffman skips the direct AT-pixel reads entirely (7.4.2.1.2).
    assert sd.sd_at_x is None
    assert sd.sd_at_y is None


# ---------------------------------------------------------------------------
# Huffman direct path — alternate standard tables (SDHUFFDH==1 -> B5,
# SDHUFFDW==1 -> B3). Exercises the `selection == 1` arms.
# ---------------------------------------------------------------------------


def test_huffman_alt_standard_tables_decode():
    symbols = [(8, 9), (12, 9)]
    sd = _decode(huffman_sd_alt_standard_table_data(symbols))
    assert sd.sd_huff_decode_height_selection == 1
    assert sd.sd_huff_decode_width_selection == 1
    out = sd.get_dictionary()
    assert [(b.get_width(), b.get_height()) for b in out] == symbols


# ---------------------------------------------------------------------------
# Huffman direct path — user (type-53) tables for SDHUFFDH/DW (== 3) and
# SDHUFFBMSIZE (== 1). Exercises _get_user_table's table-counter increment
# (the DW table is ordinal 1, BMSIZE ordinal 2) and the *_nr accumulators.
# ---------------------------------------------------------------------------


def test_huffman_user_table_dictionary_decodes():
    symbols = [(8, 6), (10, 6)]
    wide_table, range_len = wide_table_segment_data(256)
    data = huffman_sd_user_table_data(symbols, range_len)
    # Three referred-to type-53 tables in DH, DW, BMSIZE order.
    refs = [_FakeRef(53, _table_segment(wide_table)) for _ in range(3)]
    sd = _decode(data, refs)
    assert sd.sd_huff_decode_height_selection == 3
    assert sd.sd_huff_decode_width_selection == 3
    assert sd.sd_huff_bm_size_selection == 1
    out = sd.get_dictionary()
    assert [(b.get_width(), b.get_height()) for b in out] == symbols


def test_get_user_table_table_counter_increments():
    # Two type-53 tables; position 1 must select the SECOND, exercising the
    # else: table_counter += 1 increment arm.
    t0 = _table_segment(table_segment_data())
    t1 = _table_segment(table_segment_data())
    sd = _SymbolDictionary()
    sd.segment_header = _FakeHeader([_FakeRef(53, t0), _FakeRef(53, t1)])
    assert sd._get_user_table(0) is not None
    assert sd._get_user_table(1) is not None
    # Position 2 has no matching table -> None.
    assert sd._get_user_table(2) is None


def test_get_user_table_skips_non_table_segments():
    # A non-type-53 segment between tables must not advance the counter.
    other = _SymbolDictionary()
    t0 = _table_segment(table_segment_data())
    sd = _SymbolDictionary()
    sd.segment_header = _FakeHeader([_FakeRef(0, other), _FakeRef(53, t0)])
    assert sd._get_user_table(0) is not None


# ---------------------------------------------------------------------------
# Huffman import chain — _retrieve_import_symbols + amount_of_imported_symbols,
# export runs over a mix of imported + new symbols.
# ---------------------------------------------------------------------------


def test_huffman_import_chain_counts_imported_symbols():
    base_symbols = [(8, 10), (16, 10)]
    base = _decode(huffman_sd_data(base_symbols))
    # Pre-decode the base so it has a cached dictionary + export count.
    assert len(base.get_dictionary()) == 2
    assert base.amount_of_export_symbolss == 2

    importing = huffman_sd_import_chain_data((6, 5), imported_count=2)
    sd = _decode(importing, [_FakeRef(0, base)])
    out = sd.get_dictionary()
    assert sd.amount_of_imported_symbols == 2
    assert sd.amount_of_new_symbols == 1
    # All imported + new symbols re-exported (imported_count + 1).
    assert len(out) == 3
    # First two exported are the imported bitmaps, third is the new symbol.
    assert (out[2].get_width(), out[2].get_height()) == (6, 5)


# ---------------------------------------------------------------------------
# Arithmetic direct path with a generic-region collective-bitmap reference
# (sanity for the already-pinned path under the encoder helper).
# ---------------------------------------------------------------------------


def test_arithmetic_direct_dictionary_decodes():
    symbols = [
        (4, 4, [[1, 0, 0, 1], [0, 1, 1, 0], [0, 1, 1, 0], [1, 0, 0, 1]]),
        (4, 5, [[1, 1, 1, 1]] + [[1, 0, 0, 1]] * 4),
    ]
    sd = _decode(arithmetic_sd_data(symbols))
    assert sd.is_huffman_encoded is False
    out = sd.get_dictionary()
    assert len(out) == 2
    # Encoder sorts by height; both heights present.
    assert {b.get_height() for b in out} == {4, 5}


# ---------------------------------------------------------------------------
# Refinement-aggregation: single-instance refined symbol (IAAI == 1) — exercises
# _reset_integer_coder_statistics (IAID/IARDX/IARDY), _decode_aggregate ->
# _decode_refined_symbol, _decode_new_symbols, _get_sb_sym_code_len.
# ---------------------------------------------------------------------------


def test_refagg_single_instance_refined_symbol():
    # Base SD provides two imported symbols; the refining SD adds one new symbol
    # refined from imported symbol 1.
    base_pixels = [
        (8, 4, [[1, 0, 0, 0, 0, 0, 0, 1]] + [[0] * 8] * 2 + [[1, 0, 0, 0, 0, 0, 0, 1]]),
        (8, 4, [[1, 1, 1, 1, 1, 1, 1, 1]] + [[0] * 8] * 3),
    ]
    base = _decode(arithmetic_sd_data(base_pixels))
    assert len(base.get_dictionary()) == 2

    target_rows = [[1, 0, 0, 0, 0, 0, 0, 1]] + [[0] * 8] * 2 + [[1] * 8]
    data = arithmetic_sd_refagg_single_data(
        8,
        4,
        target_rows,
        ref_id=1,
        ref_symbols=base_pixels,
        imported_count=2,
    )
    sd = _decode(data, [_FakeRef(0, base)])
    assert sd.use_refinement_aggregation is True
    assert sd.is_huffman_encoded is False
    out = sd.get_dictionary()
    assert sd.amount_of_imported_symbols == 2
    assert sd.amount_of_new_symbols == 1
    # imported_count + new == 3, all exported.
    assert len(out) == 3
    assert (out[2].get_width(), out[2].get_height()) == (8, 4)
    # The refinement integer-coder contexts were allocated (SDREFAGG path).
    assert sd.cx_iaid is not None
    assert sd.cx_iardx is not None
    assert sd.cx_iardy is not None


# ---------------------------------------------------------------------------
# Refinement-aggregation: aggregate via one-strip TextRegion (IAAI > 1) —
# exercises _decode_through_text_region.
# ---------------------------------------------------------------------------


def test_refagg_aggregate_text_region_symbol():
    base_pixels = [
        (4, 4, [[1, 1, 1, 1]] + [[1, 0, 0, 1]] * 2 + [[1, 1, 1, 1]]),
        (4, 4, [[0, 1, 1, 0]] * 4),
    ]
    base = _decode(arithmetic_sd_data(base_pixels))
    assert len(base.get_dictionary()) == 2

    # Compose the new 12x4 symbol from two instances of imported symbols.
    placements = [(0, 0, 0), (1, 6, 0)]
    data = arithmetic_sd_refagg_aggregate_data(
        12,
        4,
        placements,
        ref_symbols=base_pixels,
        imported_count=2,
    )
    sd = _decode(data, [_FakeRef(0, base)])
    out = sd.get_dictionary()
    assert sd.use_refinement_aggregation is True
    assert len(out) == 3
    new_symbol = out[2]
    assert (new_symbol.get_width(), new_symbol.get_height()) == (12, 4)
    # The aggregate path constructed a one-strip TextRegion.
    assert sd.text_region is not None


# ---------------------------------------------------------------------------
# Retained-coding-context adoption (§7.4.2.2) — _adopt_retained_coding_contexts
# + _validate_context_values success path + the get_dictionary adopt branch.
# ---------------------------------------------------------------------------


def test_adopt_retained_coding_contexts_copies_cx():
    prev = _SymbolDictionary()
    prev.cx = CX(65536, 1)
    prev.cx.set_index(5)
    prev.cx.set_cx(7)  # mark a context value at index 5
    sd = _SymbolDictionary()
    sd._adopt_retained_coding_contexts(prev)
    assert sd.cx is not prev.cx  # a copy, not the same object
    sd.cx.set_index(5)
    assert sd.cx.cx() == 7


def test_validate_context_values_matching_passes():
    sd = _SymbolDictionary()
    sd.is_huffman_encoded = False
    sd.use_refinement_aggregation = False
    sd.sd_template = 0
    sd.sdr_template = 0
    sd.sd_at_x = [3, -3, 2, -2]
    sd.sd_at_y = [-1, -1, -2, -2]
    sd.sdr_at_x = None
    sd.sdr_at_y = None

    other = _SymbolDictionary()
    other.is_huffman_encoded = False
    other.use_refinement_aggregation = False
    other.sd_template = 0
    other.sdr_template = 0
    other.sd_at_x = [3, -3, 2, -2]
    other.sd_at_y = [-1, -1, -2, -2]
    other.sdr_at_x = None
    other.sdr_at_y = None
    # Matching config -> no exception.
    sd._validate_context_values(other)


def test_context_used_with_retaining_dict_adopts_cx():
    # A base SD that decodes and *retains* its bitmap CX; a second SD whose
    # header requests context-use must adopt (copy) the base's CX rather than
    # resetting it (§7.4.2.2 step 4 -> get_dictionary's adopt branch, line 330).
    # No new symbols (amount_of_new_symbols == 0) so the height-class loop is
    # skipped and the decode does not depend on a hand-encoded bitmap body.
    base_pixels = [(4, 4, [[1, 0, 0, 1]] * 4)]
    base = _decode(arithmetic_sd_data(base_pixels))
    base.get_dictionary()  # populate base.cx with adapted statistics
    base.is_coding_context_retained = True
    base_cx_snapshot = base.cx.copy()

    from tests.jbig2.helpers.jb2_encoder import (
        _encode_arithmetic_sd_body,
        _new_cx,
        arithmetic_sd_header,
    )

    # base exports 1 symbol -> import count 1. New symbols 0; re-export the 1
    # imported. The body carries only the IAEX export runs (no height classes),
    # so the decode does not depend on a hand-encoded bitmap.
    header = arithmetic_sd_header(1, 0, retain_context=False, use_context=True)
    body, _ = _encode_arithmetic_sd_body([], _new_cx(65536, 1), amount_imported=1)
    data = header + body
    sd = _decode(data, [_FakeRef(0, base)])
    assert sd.is_coding_context_used is True
    out = sd.get_dictionary()
    # The single imported symbol is re-exported.
    assert len(out) == 1
    # CX adopted as a COPY of base's adapted statistics (not the reset 65536/1).
    assert sd.cx is not None
    assert sd.cx is not base.cx
    sd.cx.set_index(0)
    base_cx_snapshot.set_index(0)
    assert sd.cx.cx() == base_cx_snapshot.cx()


# ---------------------------------------------------------------------------
# _decode_height_class_collective_bitmap BMSIZE != 0 (generic-region variant).
# Driven directly: a generic-region-coded collective bitmap.
# ---------------------------------------------------------------------------


def test_collective_bitmap_uncompressed_byte_copy():
    # BMSIZE == 0 path: collective bitmap is read byte-for-byte from the stream.
    sd = _SymbolDictionary()
    payload = bytes([0xFF, 0x0F])  # 2 bytes -> 2x8? width 9 height 1 -> stride 2
    sd.sub_input_stream = _sis(payload)
    bitmap = sd._decode_height_class_collective_bitmap(0, 1, 9)
    assert bitmap.get_width() == 9
    assert bitmap.get_height() == 1
    assert bitmap.get_pixel(0, 0) == 1  # 0xFF top bit set
    assert bitmap.get_pixel(8, 0) == 0  # 0x0F top bit (bit 8) clear


def test_collective_bitmap_generic_region_plumbing(monkeypatch):
    # BMSIZE != 0 path (§6.5.9): the collective bitmap is MMR-coded and decoded
    # via a GenericRegion configured with is_mmr_encoded=True, data_length=bm_size
    # and the height-class height / total width. The MMR decode itself is covered
    # by the GenericRegion MMR tests; here we pin the SD-side parameter plumbing
    # (751-763) by capturing what the SD hands to set_parameters. generic_region
    # starts None so the lazy-construct arm (752) runs.
    import pypdfbox.jbig2.segments.symbol_dictionary as sd_module

    sentinel = Bitmap(20, 6)
    captured = {}

    class _StubGenericRegion:
        def __init__(self, _sis):
            pass

        def set_parameters(self, is_mmr_encoded, **kwargs):
            captured["is_mmr_encoded"] = is_mmr_encoded
            captured.update(kwargs)

        def get_region_bitmap(self):
            return sentinel

    monkeypatch.setattr(sd_module, "GenericRegion", _StubGenericRegion)

    sd = _SymbolDictionary()
    sd.sub_input_stream = _sis(b"\x00\x01\x02\x03\x04\x05\x06\x07")
    assert sd.generic_region is None
    result = sd._decode_height_class_collective_bitmap(5, 6, 20)
    assert result is sentinel
    assert sd.generic_region is not None  # lazily constructed
    assert captured["is_mmr_encoded"] is True
    assert captured["data_length"] == 5
    assert captured["gbh"] == 6
    assert captured["gbw"] == 20
    assert captured["variant"] == "dict_simple"
    # data_offset is the stream position at the time of the call (start, 0).
    assert captured["data_offset"] == 0


# ---------------------------------------------------------------------------
# Huffman single-instance refined symbol (§6.5.8.2 steps 2-7, Huffman branch):
# id via read_bits, RDX/RDY via Table B15, SYMINREFSIZE via Table B1, then the
# refinement bitmap arithmetic-decoded on the same stream + the byte-budget
# check / seek (584-624).
# ---------------------------------------------------------------------------


def _huffman_refined_symbol_stream(sym_in_ref_size: int) -> bytes:
    from tests.jbig2.helpers.jb2_encoder import BitWriter, write_huffman

    bw = BitWriter()
    bw.write_bit(0)  # id (sb_sym_code_len == 1) -> symbol 0
    write_huffman(bw, 15, 0)  # RDX == 0 (B15)
    write_huffman(bw, 15, 0)  # RDY == 0 (B15)
    write_huffman(bw, 1, sym_in_ref_size)  # SYMINREFSIZE (B1)
    bw.align()  # skip_bits before the arithmetic refinement bitmap
    # Oracle-proven template-0 refinement payload (see wave 1493).
    return bw.to_bytes() + bytes.fromhex("84c73b00ff12abcd")


def _prepare_huffman_refining_sd(sym_in_ref_size: int) -> _SymbolDictionary:
    sd = _SymbolDictionary()
    data = _huffman_refined_symbol_stream(sym_in_ref_size)
    sd.sub_input_stream = _sis(data)
    sd.is_huffman_encoded = True
    sd.sb_sym_code_len = 1
    sd.sdr_template = 0
    sd.sdr_at_x = [-1, -1]
    sd.sdr_at_y = [-1, -1]
    sd.cx = CX(65536, 1)
    ibo = _bitmap(8, 4, "8040c030")
    sd.import_symbols = [ibo]
    sd.sb_symbols = [ibo]
    sd.new_symbols = [None]
    sd.amount_of_decoded_symbols = 0
    return sd


def test_huffman_decode_refined_symbol():
    # Refinement payload is 8 bytes; a generous SYMINREFSIZE lets the decode
    # complete, then the SD seeks to stream_position0 + sym_in_ref_size.
    sd = _prepare_huffman_refining_sd(sym_in_ref_size=8)
    sd._decode_refined_symbol(8, 4)
    assert sd.new_symbols[0] is not None
    assert (sd.new_symbols[0].get_width(), sd.new_symbols[0].get_height()) == (8, 4)
    # Same oracle-proven refinement bytes as the arithmetic branch (wave 1493).
    assert bytes(sd.new_symbols[0].get_byte_array()).hex() == "1d0671d1"
    assert sd.sb_symbols[-1] is sd.new_symbols[0]


def test_huffman_decode_refined_symbol_overrun_raises():
    # SYMINREFSIZE smaller than the bytes the refinement decode consumes -> the
    # step-7 budget check raises (614-622).
    sd = _prepare_huffman_refining_sd(sym_in_ref_size=0)
    with pytest.raises(OSError, match="Refinement bitmap bytes expected"):
        sd._decode_refined_symbol(8, 4)


# ---------------------------------------------------------------------------
# Huffman ref/agg instance count via a user (type-53) AGGINST table
# (SDHUFFAGGINST == 1, _huff_decode_ref_agg_n_inst selection==1, 501-514).
# ---------------------------------------------------------------------------


def test_huff_decode_ref_agg_n_inst_user_table():
    # SDHUFFAGGINST == 1 -> AGGINST decoded from a user table. With DH/DW/BMSIZE
    # all == 3 the AGGINST ordinal is 3 (it follows those three user tables); a
    # smaller config lowers the ordinal. Here only AGGINST is a user table, so
    # its ordinal is 0.
    from tests.jbig2.helpers.jb2_encoder import BitWriter

    wide_table, range_len = wide_table_segment_data(16)
    sd = _SymbolDictionary()
    sd.is_huffman_encoded = True
    sd.use_refinement_aggregation = True
    sd.sd_huff_agg_instance_selection = 1
    sd.sd_huff_decode_height_selection = 0
    sd.sd_huff_decode_width_selection = 0
    sd.sd_huff_bm_size_selection = 0
    sd.segment_header = _FakeHeader([_FakeRef(53, _table_segment(wide_table))])

    bw = BitWriter()
    bw.write_bit(0)  # canonical prefix of the wide table's single normal line
    bw.write_bits(5, range_len)  # value 5
    sd.sub_input_stream = _sis(bw.to_bytes())
    assert sd._huff_decode_ref_agg_n_inst() == 5
    # The ordinal-0 user table was cached.
    assert sd.agg_inst_table is not None


def test_huff_decode_ref_agg_n_inst_user_table_ordinal_three():
    # DH/DW/BMSIZE all == 3 (each a user table) -> AGGINST's ordinal is 3, so it
    # is the FOURTH referred type-53 table (506/508/510 accumulators all fire).
    from tests.jbig2.helpers.jb2_encoder import BitWriter

    wide_table, range_len = wide_table_segment_data(16)
    # Tables 0-2 (DH/DW/BMSIZE) plus table 3 (AGGINST, the one actually decoded).
    refs = [_FakeRef(53, _table_segment(wide_table)) for _ in range(4)]
    sd = _SymbolDictionary()
    sd.is_huffman_encoded = True
    sd.use_refinement_aggregation = True
    sd.sd_huff_agg_instance_selection = 1
    sd.sd_huff_decode_height_selection = 3
    sd.sd_huff_decode_width_selection = 3
    sd.sd_huff_bm_size_selection = 3
    sd.segment_header = _FakeHeader(refs)

    bw = BitWriter()
    bw.write_bit(0)
    bw.write_bits(7, range_len)  # value 7 from the 4th (ordinal-3) table
    sd.sub_input_stream = _sis(bw.to_bytes())
    assert sd._huff_decode_ref_agg_n_inst() == 7


def test_huff_decode_ref_agg_n_inst_standard_table():
    # SDHUFFAGGINST == 0 -> standard Table B1.
    from tests.jbig2.helpers.jb2_encoder import BitWriter, write_huffman

    sd = _SymbolDictionary()
    sd.is_huffman_encoded = True
    sd.sd_huff_agg_instance_selection = 0
    bw = BitWriter()
    write_huffman(bw, 1, 3)
    sd.sub_input_stream = _sis(bw.to_bytes())
    assert sd._huff_decode_ref_agg_n_inst() == 3


# ---------------------------------------------------------------------------
# Export-flag run-length toggling sense (6.5.10): first run is NOT exported,
# alternating thereafter — a sense regression flips these.
# ---------------------------------------------------------------------------


class _ScriptedIntDecoder:
    def __init__(self, values):
        self._values = list(values)

    def decode(self, _cx):
        return self._values.pop(0)


@pytest.mark.parametrize(
    ("runs", "imported", "new", "expected"),
    [
        # first run (0) starts NOT exported, toggles to exported.
        ([1, 4], 0, 5, [0, 1, 1, 1, 1]),
        ([0, 3, 0, 2], 0, 5, [1, 1, 1, 1, 1]),
        ([2, 1, 2], 0, 5, [0, 0, 1, 0, 0]),
        ([0, 6], 2, 4, [1, 1, 1, 1, 1, 1]),
    ],
    ids=["one_unexported_head", "all_exported_then_unexported", "alternating", "mix"],
)
def test_export_flag_run_toggle_sense(runs, imported, new, expected):
    sd = _SymbolDictionary()
    sd.is_huffman_encoded = False
    sd.amount_of_imported_symbols = imported
    sd.amount_of_new_symbols = new
    sd.i_decoder = _ScriptedIntDecoder(runs)
    assert sd._get_to_export_flags() == expected


def test_export_flag_run_overlong_rejected():
    sd = _SymbolDictionary()
    sd.is_huffman_encoded = False
    sd.amount_of_imported_symbols = 0
    sd.amount_of_new_symbols = 3
    sd.i_decoder = _ScriptedIntDecoder([4])  # one past total
    with pytest.raises(InvalidHeaderValueException, match="EXRUNLENGTH"):
        sd._get_to_export_flags()


def test_set_exported_symbols_mixes_imported_and_new():
    sd = _SymbolDictionary()
    sd.amount_of_imported_symbols = 2
    sd.amount_of_new_symbols = 3
    sd.import_symbols = ["i0", "i1"]
    sd.new_symbols = ["n0", "n1", "n2"]
    # export imported[0], new[1] and new[2].
    sd._set_exported_symbols([1, 0, 0, 1, 1])
    assert sd.export_symbols == ["i0", "n1", "n2"]


# ---------------------------------------------------------------------------
# _to_signed_int32 overflow-detection helper (Java signed-int masking).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, 0),
        (1, 1),
        (0x7FFFFFFF, 0x7FFFFFFF),
        (0x80000000, -0x80000000),
        (0xFFFFFFFF, -1),
        (0x100000005, 5),  # wraps the low 32 bits
    ],
)
def test_to_signed_int32(raw, expected):
    assert _to_signed_int32(raw) == expected


def test_negative_amount_field_rejected_in_export_flags():
    # A 32-bit count with bit 31 set sign-extends to negative and is caught.
    sd = _SymbolDictionary()
    sd.amount_of_imported_symbols = 0
    sd.amount_of_new_symbols = _to_signed_int32(0x80000000)
    assert sd.amount_of_new_symbols < 0
    with pytest.raises(InvalidHeaderValueException, match="Invalid number of symbols"):
        sd._get_to_export_flags()


# ---------------------------------------------------------------------------
# AT-pixel parsing: signed bytes (7.4.2.1.2 / 7.4.2.1.3).
# ---------------------------------------------------------------------------


def test_at_pixels_signed_parse_template0():
    sd = _SymbolDictionary()
    # 4 AT pairs, signed bytes (0x80 -> -128, 0x7F -> 127).
    sd.sub_input_stream = _sis(bytes([0x80, 0x7F, 0xFF, 0x01, 0x00, 0x00, 0x02, 0xFE]))
    sd._read_at_pixels(4)
    assert sd.sd_at_x == [-128, -1, 0, 2]
    assert sd.sd_at_y == [127, 1, 0, -2]


def test_refinement_at_pixels_signed_parse():
    sd = _SymbolDictionary()
    sd.sub_input_stream = _sis(bytes([0xFF, 0xFF, 0x01, 0x02]))
    sd._read_refinement_at_pixels(2)
    assert sd.sdr_at_x == [-1, 1]
    assert sd.sdr_at_y == [-1, 2]


def test_set_refinement_at_pixels_only_when_refagg_and_template0():
    # refagg off -> no refinement AT read regardless of sdr_template.
    sd = _SymbolDictionary()
    sd.use_refinement_aggregation = False
    sd.sdr_template = 0
    sd.sub_input_stream = _sis(b"\xff\xff\xff\xff")
    sd._set_refinement_at_pixels()
    assert sd.sdr_at_x is None
    # refagg on + sdr_template 1 -> still no refinement AT (template 1 carries none).
    sd2 = _SymbolDictionary()
    sd2.use_refinement_aggregation = True
    sd2.sdr_template = 1
    sd2.sub_input_stream = _sis(b"\xff\xff\xff\xff")
    sd2._set_refinement_at_pixels()
    assert sd2.sdr_at_x is None


def _bitmap(width: int, height: int, hexbytes: str) -> Bitmap:
    bitmap = Bitmap(width, height)
    for i, byte in enumerate(bytes.fromhex(hexbytes)):
        bitmap.set_byte(i, byte)
    return bitmap


def test_decode_height_class_bitmap_slices_by_width():
    # Two 4-wide symbols side by side in a 8x2 collective bitmap; the slice must
    # split them at the cumulative width boundary.
    sd = _SymbolDictionary()
    sd.new_symbols = [None, None]
    sd.sb_symbols = []
    sd.amount_of_decoded_symbols = 2
    collective = _bitmap(8, 2, "f00f")  # row0=0xF0, row1=0x0F
    sd._decode_height_class_bitmap(collective, 0, 2, [4, 4])
    assert sd.new_symbols[0].get_width() == 4
    assert sd.new_symbols[1].get_width() == 4
    # Symbol 0 carries the left nibble of row 0 (all ones), symbol 1 the right.
    assert sd.new_symbols[0].get_pixel(0, 0) == 1
    assert sd.new_symbols[1].get_pixel(3, 1) == 1
    assert sd.sb_symbols == [sd.new_symbols[0], sd.new_symbols[1]]
