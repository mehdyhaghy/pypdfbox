"""Reachable error / None-return decode branches — wave 1510 (agent B).

The final JBIG2 coverage audit (wave 1510) closed the bulk of the
``text_region`` / ``symbol_dictionary`` user-table selection branches with the
encoder-built live-oracle differential
(``tests/jbig2/segments/oracle/test_huffman_user_table_oracle_wave1510.py``).

A handful of *reachable* branches are error or None-return arms that no valid
encoder-built stream reaches (a well-formed stream never overruns its own
refinement byte budget and always supplies the referred-to table). They are
exercised here directly — these are deterministic guards (not oracle-driven):

* ``TextRegion._decode_ib`` §6.4.11 step 7 — the OSError raised when the
  refinement bitmap reads more bytes than ``symInRefSize`` budgets.
* ``TextRegion._get_user_table`` / ``SymbolDictionary._get_user_table`` — the
  ``None`` return when no referred-to type-53 table matches the requested
  position.
* ``SymbolDictionary._validate_context_values`` — the
  ``InvalidHeaderValueException`` raised when a coding-context-reuse dictionary's
  configuration does not match the referred-to dictionary.
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import ArithmeticDecoder
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.err.invalid_header_value_exception import (
    InvalidHeaderValueException,
)
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.symbol_dictionary import SymbolDictionary
from pypdfbox.jbig2.segments.text_region import TextRegion


class _FakeRef:
    def __init__(self, segment_type: int) -> None:
        self._segment_type = segment_type

    def get_segment_type(self) -> int:
        return self._segment_type


class _FakeHeader:
    def __init__(self, refs: list[_FakeRef]) -> None:
        self._refs = refs

    def get_rt_segments(self) -> list[_FakeRef]:
        return self._refs


def _symbol(width: int, height: int, hexbytes: str) -> Bitmap:
    bitmap = Bitmap(width, height)
    for i, byte in enumerate(bytes.fromhex(hexbytes)):
        bitmap.set_byte(i, byte)
    return bitmap


def _huffman_refining_region(sym_in_ref_size: int) -> TextRegion:
    tr = TextRegion()
    data = bytes.fromhex("84c73b00ff12abcd5566778899")
    tr.sub_input_stream = SubInputStream(ImageInputStream(data), 0, len(data))
    tr.arithmetic_decoder = ArithmeticDecoder(tr.sub_input_stream)
    tr.is_huffman_encoded = True
    tr.use_refinement = True
    tr.sbr_template = 0
    tr.sbr_at_x = [-1, -1]
    tr.sbr_at_y = [-1, -1]
    tr.cx = CX(65536, 1)
    tr.symbols = [_symbol(8, 4, "8040c030")]
    # Stub the per-field Huffman decodes so the refined size stays valid; the
    # too-small symInRefSize forces the step-7 overrun check.
    tr._decode_rdw = lambda: 2
    tr._decode_rdh = lambda: 2
    tr._decode_rdx = lambda: 0
    tr._decode_rdy = lambda: 0
    tr._decode_sym_in_ref_size = lambda: sym_in_ref_size
    return tr


def test_text_region_refinement_overrun_raises():
    """symInRefSize smaller than the bytes consumed -> OSError (§6.4.11 step 7)."""
    tr = _huffman_refining_region(sym_in_ref_size=0)
    with pytest.raises(OSError, match="Refinement bitmap bytes expected"):
        tr._decode_ib(1, 0)


def test_text_region_get_user_table_returns_none_when_absent():
    tr = TextRegion()
    tr.segment_header = _FakeHeader([_FakeRef(0)])  # symbol dict only, no type-53
    assert tr._get_user_table(0) is None


def test_symbol_dictionary_get_user_table_returns_none_when_absent():
    sd = SymbolDictionary()
    sd.segment_header = _FakeHeader([_FakeRef(0)])  # no type-53 table referred
    assert sd._get_user_table(0) is None


def test_symbol_dictionary_validate_context_values_mismatch_raises():
    sd = SymbolDictionary()
    sd.is_huffman_encoded = False
    sd.use_refinement_aggregation = False
    sd.sd_template = 0
    sd.sdr_template = 0
    sd.sd_at_x = [1, 2]
    sd.sd_at_y = [3, 4]
    sd.sdr_at_x = None
    sd.sdr_at_y = None

    other = SymbolDictionary()
    other.is_huffman_encoded = False
    other.use_refinement_aggregation = False
    other.sd_template = 0
    other.sdr_template = 0
    other.sd_at_x = [9, 9]  # mismatched AT pixels
    other.sd_at_y = [3, 4]
    other.sdr_at_x = None
    other.sdr_at_y = None

    with pytest.raises(InvalidHeaderValueException, match="reuse values don't match"):
        sd._validate_context_values(other)
