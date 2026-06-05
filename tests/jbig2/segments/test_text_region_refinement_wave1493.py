"""Text-region per-instance refinement decode body — wave 1493.

None of the five bundled ``.jb2`` fixtures place a *refined* symbol instance in a
text region: ``21.jb2``'s text region is Huffman-coded with refinement off (only
the ``r == 0`` "use the symbol bitmap as-is" branch fires), and the other four
fixtures contain no text regions. A full refinement text-region stream cannot be
crafted minimally because the arithmetic-decoded RDW/RDH almost always come out
negative for short hand-made payloads (yielding an invalid sub-zero refined
size).

So this module exercises the §6.4.11 refined-instance branch of
``TextRegion._decode_ib`` (``r == 1``) directly, with the integer coder stubbed
to feed controlled RDW/RDH/RDX/RDY values. That drives the real refinement
plumbing — the reference-offset computation ``(RDW >> 1) + RDX`` /
``(RDH >> 1) + RDY``, the lazy ``ArithmeticDecoder`` / ``CX`` creation, and the
delegation to ``GenericRefinementRegionDecodingProcedure.decode`` — over a real
coded payload. The inner procedure is bit-exact against the live PDFBox 3.0.7 jar
(see ``test_generic_refinement_region_oracle``); here we pin the text-region-side
wiring deterministically.
"""

from __future__ import annotations

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import ArithmeticDecoder
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.text_region import TextRegion


class _StubIntegerDecoder:
    """Returns a fixed sequence — used to feed controlled RDW/RDH/RDX/RDY."""

    def __init__(self, values):
        self._values = list(values)
        self._i = 0

    def decode(self, cx):
        value = self._values[self._i]
        self._i += 1
        return value


def _symbol(width: int, height: int, hexbytes: str) -> Bitmap:
    bitmap = Bitmap(width, height)
    for i, byte in enumerate(bytes.fromhex(hexbytes)):
        bitmap.set_byte(i, byte)
    return bitmap


def _refining_region(rdw, rdh, rdx, rdy) -> TextRegion:
    tr = TextRegion()
    data = bytes.fromhex("84c73b00ff12abcd5566778899")
    tr.sub_input_stream = SubInputStream(ImageInputStream(data), 0, len(data))
    tr.arithmetic_decoder = ArithmeticDecoder(tr.sub_input_stream)
    tr.integer_decoder = _StubIntegerDecoder([rdw, rdh, rdx, rdy])
    tr.is_huffman_encoded = False
    tr.use_refinement = True
    tr.sbr_template = 0
    tr.sbr_at_x = [-1, -1]
    tr.sbr_at_y = [-1, -1]
    tr.cx = CX(65536, 1)
    tr.symbols = [_symbol(8, 4, "8040c030")]
    return tr


def test_decode_ib_r0_returns_symbol_unchanged():
    tr = _refining_region(0, 0, 0, 0)
    symbol = tr.symbols[0]
    assert tr._decode_ib(0, 0) is symbol


def test_decode_ib_r1_refines_symbol():
    # RDW=2, RDH=2 -> refined instance is (8+2) x (4+2) = 10 x 6.
    tr = _refining_region(2, 2, 0, 0)
    ib = tr._decode_ib(1, 0)
    assert ib.get_width() == 10
    assert ib.get_height() == 6
    # Deterministic refinement output (refactored-upstream procedure).
    assert bytes(ib.get_byte_array()).hex() == "1dc0f6400e00db805c800200"


def test_decode_ib_r1_creates_arith_decoder_and_cx_lazily():
    tr = _refining_region(2, 2, 0, 0)
    tr.arithmetic_decoder = None
    tr.cx = None
    ib = tr._decode_ib(1, 0)
    assert tr.arithmetic_decoder is not None
    assert tr.cx is not None
    assert ib.get_width() == 10
    assert ib.get_height() == 6


def test_decode_ib_r1_reference_offset_uses_rdx_rdy():
    # (RDW >> 1) + RDX and (RDH >> 1) + RDY shift the reference within the
    # refined bitmap; a non-zero RDX/RDY yields a different (still valid) result
    # than the zero-offset refinement of the same RDW/RDH.
    zero_offset = _refining_region(2, 2, 0, 0)._decode_ib(1, 0)
    shifted = _refining_region(2, 2, 1, -1)._decode_ib(1, 0)
    assert shifted.get_width() == 10
    assert shifted.get_height() == 6
    assert bytes(shifted.get_byte_array()) != bytes(zero_offset.get_byte_array())
