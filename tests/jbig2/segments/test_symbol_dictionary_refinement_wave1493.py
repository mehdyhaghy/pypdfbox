"""Symbol-dictionary refinement / refinement-aggregation decode bodies — wave 1493.

None of the five bundled ``.jb2`` fixtures exercise a refinement-aggregation
symbol dictionary (§6.5.8.2): ``21.jb2`` is a Huffman dictionary without
refinement, and ``003/005/006/20123110001`` carry no symbol dictionaries at all.
Crafting a complete multi-segment refinement-aggregation dictionary stream by
hand is impractical, so this module drives the two reachable refinement decode
bodies directly with prepared decoder state, mirroring how
``test_generic_refinement_region`` drives the underlying procedure:

* ``_decode_new_symbols`` (Table 18) — the §6.5.8.2.2 single-symbol refinement
  that delegates to ``GenericRefinementRegionDecodingProcedure.decode``;
* ``_decode_refined_symbol`` (arithmetic branch, §6.5.8.2 steps 2-7) — decodes
  the refinement ID / RDX / RDY via the integer coder, then refines.

The refinement procedure itself is bit-exact against the live PDFBox 3.0.7 jar
(see ``tests/jbig2/segments/oracle/test_generic_refinement_region_oracle.py``);
the new-symbol byte vectors pinned here equal that proven output (the basic
template-0 refinement of an ``8040c030`` reference over the ``84c73b00ff12abcd``
coded payload is ``1d0671d1`` on both decoders), so these pins are anchored to
oracle-verified bytes rather than to a hand-computed expectation.
"""

from __future__ import annotations

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import ArithmeticDecoder
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_integer_decoder import (
    ArithmeticIntegerDecoder,
)
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.symbol_dictionary import SymbolDictionary


def _reference(width: int, height: int, hexbytes: str) -> Bitmap:
    bitmap = Bitmap(width, height)
    for i, byte in enumerate(bytes.fromhex(hexbytes)):
        bitmap.set_byte(i, byte)
    return bitmap


def _arith_sd(coded_hex: str) -> SymbolDictionary:
    sd = SymbolDictionary()
    data = bytes.fromhex(coded_hex)
    sd.sub_input_stream = SubInputStream(ImageInputStream(data), 0, len(data))
    sd.arithmetic_decoder = ArithmeticDecoder(sd.sub_input_stream)
    sd.i_decoder = ArithmeticIntegerDecoder(sd.arithmetic_decoder)
    sd.cx = CX(65536, 1)
    sd.is_huffman_encoded = False
    sd.sdr_template = 0
    sd.sdr_at_x = [-1, -1]
    sd.sdr_at_y = [-1, -1]
    return sd


def test_decode_new_symbols_refines_via_procedure():
    """Table 18 single-symbol refinement matches the oracle-proven bytes."""
    sd = _arith_sd("84c73b00ff12abcd")
    sd.new_symbols = [None]
    sd.sb_symbols = []
    sd.amount_of_decoded_symbols = 0

    ibo = _reference(8, 4, "8040c030")
    sd._decode_new_symbols(8, 4, ibo, 0, 0)

    # Identical to the live-oracle template-0 basic refinement vector.
    assert bytes(sd.new_symbols[0].get_byte_array()).hex() == "1d0671d1"
    assert sd.sb_symbols == [sd.new_symbols[0]]


def test_decode_new_symbols_requires_initialized_cx():
    sd = _arith_sd("84c73b00ff12abcd")
    sd.cx = None
    sd.new_symbols = [None]
    sd.sb_symbols = []
    sd.amount_of_decoded_symbols = 0
    try:
        sd._decode_new_symbols(8, 4, _reference(8, 4, "8040c030"), 0, 0)
    except RuntimeError as exc:
        assert "CX not initialized" in str(exc)
    else:  # pragma: no cover - guard must raise
        raise AssertionError("expected RuntimeError for uninitialized CX")


def test_decode_refined_symbol_arithmetic_branch():
    """§6.5.8.2 steps 2-7 (arithmetic): decode ID/RDX/RDY then refine.

    Drives the whole arithmetic refined-symbol path: the integer coder reads the
    symbol id + RDX + RDY from the same arithmetic stream, then the referenced
    symbol is refined into a new bitmap. Pins the byte output so a regression in
    the id/RDX/RDY plumbing (not just the inner procedure) is caught.
    """
    sd = _arith_sd("84c73b00ff12abcd5566778899")
    sd.sb_sym_code_len = 1
    sd.cx_iaid = CX(2, 1)
    sd.cx_iardx = CX(512, 1)
    sd.cx_iardy = CX(512, 1)

    ibo = _reference(8, 4, "8040c030")
    sd.import_symbols = [ibo]
    sd.sb_symbols = [ibo]
    sd.new_symbols = [None]
    sd.amount_of_decoded_symbols = 0

    sd._decode_refined_symbol(8, 4)

    assert sd.new_symbols[0] is not None
    assert sd.new_symbols[0].get_width() == 8
    assert sd.new_symbols[0].get_height() == 4
    assert bytes(sd.new_symbols[0].get_byte_array()).hex() == "42231088"
    assert sd.sb_symbols[-1] is sd.new_symbols[0]
