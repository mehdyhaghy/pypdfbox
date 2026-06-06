"""Template-0 optimized-blit shift / AT-override decode branches — wave 1494.

The §6.3.5.6 template-0 optimized byte-blit (``_decode_template`` and
``_decode_typical_predicted_line_template0``) has several reference-shift and
AT-override sub-branches that none of the bundled ``.jb2`` fixtures (and none of
the wave-1493 oracle cases) exercise, because they require either a *wide*
reference bitmap (so ``mod_ref_byte_idx > 1``), a non-zero ``referenceDX`` (so
the context-shift offset leaves the nominal ``+6`` band), or active AT-pixel
overrides. These are reachable arithmetic paths, so this module drives the
procedure directly with crafted reference bitmaps + AT parameters, mirroring the
direct-driving approach in ``test_generic_refinement_region``.

Parity scope (matching the wave-1493 oracle rationale):

* ``dx == 8`` over a 24-px reference hits the ``shift_offset == 6 and
  mod_ref_byte_idx > 1`` multi-byte band and is a non-negative-dx path the
  bundled 3.0.7 jar shares with the refactored upstream pypdfbox ports — the
  byte pin is therefore jar-faithful.
* ``dx == -7`` hits the ``shift_offset < 0`` (negative-remainder) ``else`` band.
  This is the refactored-upstream branch; the 3.0.7 jar's inlined decoder
  diverges here (the same divergence pinned by the strict-xfail in
  ``test_generic_refinement_region_oracle``), so the pin is Python-deterministic.
* AT-override (RA1 / RA2) drives ``_override_at_template0``, including the
  ``gr_at_y[0] == 0`` result-bit branch whose Java ``>>`` shift-count masking
  the port now mirrors (a negative ``7 - (minor_x + gr_at_x[0])`` shifts by
  ``count & 0x1F`` instead of raising). Pinned Python-deterministically.
* TPGRON-on template-0 with an active override drives the typical-predicted
  override path; the 3.0.7 jar NPEs on the first SLTP under TPGRON (see the
  wave-1493 note), so this too is Python-deterministic.
"""

from __future__ import annotations

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import ArithmeticDecoder
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.decoder.generic_refinement_region_decoding_procedure import (
    GenericRefinementRegionDecodingProcedure,
)

_Proc = GenericRefinementRegionDecodingProcedure


class _MemoryImageInputStream:
    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        self._pos = 0

    def get_stream_position(self) -> int:
        return self._pos

    def read(self) -> int:
        if self._pos >= len(self._data):
            return -1
        value = self._data[self._pos]
        self._pos += 1
        return value

    def seek(self, pos: int) -> None:
        self._pos = pos


def _make_reference(width: int, height: int, hexbytes: str) -> Bitmap:
    bmp = Bitmap(width, height)
    raw = bytes.fromhex(hexbytes)
    n = min(len(bmp.bitmap_bytes), len(raw))
    bmp.bitmap_bytes[:n] = raw[:n]
    return bmp


def _decode(
    *,
    width: int,
    height: int,
    ref_w: int,
    ref_h: int,
    dx: int,
    dy: int,
    tpgr: bool,
    ref_hex: str,
    coded_hex: str,
    at_x: list[int] | None = None,
    at_y: list[int] | None = None,
) -> Bitmap:
    reference = _make_reference(ref_w, ref_h, ref_hex)
    decoder = ArithmeticDecoder(_MemoryImageInputStream(bytes.fromhex(coded_hex)))
    cx = CX(8192, 1)
    return GenericRefinementRegionDecodingProcedure.decode(
        decoder,
        cx,
        width,
        height,
        0,  # template 0
        tpgr,
        reference,
        dx,
        dy,
        at_x if at_x is not None else [-1, -1],
        at_y if at_y is not None else [-1, -1],
    )


_REF_24 = "aabbccddeeff00112233445566778899"
_REF_16 = "aabbccddeeff0011"
_CODED = "84c73b00ff12abcd5566778899aabbcc"


def test_template0_positive_dx8_multibyte_shift_band():
    """dx=8 over a 24-px reference: shift_offset==6 with mod_ref_byte_idx>1."""
    bmp = _decode(
        width=24, height=4, ref_w=24, ref_h=4, dx=8, dy=0, tpgr=False,
        ref_hex=_REF_24, coded_hex=_CODED,
    )
    # Non-negative dx: bundled 3.0.7 jar agrees with the refactored procedure.
    assert bytes(bmp.get_byte_array()).hex() == "1d214cb04c2e3288645fe564"


def test_template0_negative_dx8_multibyte_band():
    """dx=-8 over a 32-px reference: shift_offset==6 with mod_ref_byte_idx>1.

    The negative reference start-column pushes the reference byte index past the
    nominal band, exercising the per-current-line two-bytes-back reads inside the
    ``shift_offset == 6 and mod_ref_byte_idx > 1`` branch. Negative-dx =
    refactored-upstream path (jar diverges), pinned deterministically.
    """
    bmp = _decode(
        width=32, height=4, ref_w=32, ref_h=4, dx=-8, dy=0, tpgr=False,
        ref_hex=(
            "aabbccddeeff00112233445566778899"
            "aabbccddeeff00112233445566778899"
        ),
        coded_hex="84c73b00ff12abcd5566778899aabbccaabbccddeeff0011",
    )
    assert (
        bytes(bmp.get_byte_array()).hex()
        == "1d33106487933e5326b88a0e301e3025"
    )


def test_template0_negative_dx6_shift_offset_zero_band():
    """dx=-6: shift_offset==0 band (the ``w1=w2=w3=0`` reload sub-branch).

    Negative-dx refactored-upstream path (jar diverges), pinned deterministically.
    """
    bmp = _decode(
        width=24, height=4, ref_w=24, ref_h=4, dx=-6, dy=0, tpgr=False,
        ref_hex=_REF_24, coded_hex=_CODED,
    )
    assert bytes(bmp.get_byte_array()).hex() == "1d0c80b660208916103e6780"


def test_template0_negative_dx7_else_shift_band():
    """dx=-7: shift_offset<0 (negative-remainder) else band.

    Refactored-upstream branch; the 3.0.7 jar's inlined decoder diverges here
    (same divergence as the strict-xfail oracle pin), so this is deterministic.
    """
    bmp = _decode(
        width=24, height=4, ref_w=24, ref_h=4, dx=-7, dy=0, tpgr=False,
        ref_hex=_REF_24, coded_hex=_CODED,
    )
    assert bytes(bmp.get_byte_array()).hex() == "1d0c687121f89c0e0860cd91"


def test_template0_at_override_ra1_result_bit_branch():
    """AT RA1 with gr_at_y[0]==0 drives the result-bit override branch.

    gr_at_x[0]=3 makes 7-(minor_x+3) go negative for minor_x>4, exercising the
    Java >>-shift-count masking the port now mirrors (no more negative-shift
    ValueError).
    """
    bmp = _decode(
        width=16, height=4, ref_w=16, ref_h=4, dx=0, dy=0, tpgr=False,
        ref_hex=_REF_16, coded_hex=_CODED, at_x=[3, -1], at_y=[0, -1],
    )
    assert bytes(bmp.get_byte_array()).hex() == "1d285c1e8950928e"


def test_template0_at_override_ra1_and_ra2():
    """Both AT pixels override: RA1 reference-bitmap branch + RA2."""
    bmp = _decode(
        width=16, height=4, ref_w=16, ref_h=4, dx=0, dy=0, tpgr=False,
        ref_hex=_REF_16, coded_hex=_CODED, at_x=[2, 5], at_y=[-1, 2],
    )
    assert bytes(bmp.get_byte_array()).hex() == "1d2f7e83bd9d8a5d"


def test_template0_tpgron_with_override():
    """TPGRON-on template-0 with active override: optimized (LTP=0) override path.

    The 3.0.7 jar NPEs on the first SLTP under TPGRON, so this is pinned
    Python-deterministically (refactored-upstream behaviour real readers ship).
    """
    bmp = _decode(
        width=16, height=4, ref_w=16, ref_h=4, dx=0, dy=0, tpgr=True,
        ref_hex=_REF_16, coded_hex=_CODED, at_x=[2, 5], at_y=[1, 2],
    )
    assert bytes(bmp.get_byte_array()).hex() == "3b867eb8332189e8"


def test_template0_tpgron_typical_predicted_line_override():
    """TPGRON-on template-0 where a line's LTP flips to 1: the typical-predicted
    (``_decode_typical_predicted_line_template0``) override branch.

    This coded stream's per-line SLTP bit flips ``is_line_typical_predicted`` to
    1, routing a line through the typical-predicted byte-blit with the AT
    override active. Jar-unreachable (TPGRON SLTP NPE), pinned deterministically.
    """
    bmp = _decode(
        width=16, height=4, ref_w=16, ref_h=4, dx=0, dy=0, tpgr=True,
        ref_hex=_REF_16, coded_hex="ff00ff00ffffff00", at_x=[2, 5], at_y=[1, 2],
    )
    assert bytes(bmp.get_byte_array()).hex() == "f0427f0659381816"


def test_template0_tpgron_typical_predicted_line_short_reference():
    """TPGRON-on template-0, region taller than the reference: the
    typical-predicted line's out-of-bounds reference-line guards (``current_line``
    past the reference height yields a zero reference line).

    Jar-unreachable (TPGRON SLTP NPE), pinned deterministically.
    """
    bmp = _decode(
        width=16, height=6, ref_w=16, ref_h=2, dx=0, dy=0, tpgr=True,
        ref_hex=_REF_16, coded_hex="ff00ff00ffffff00",
    )
    assert bytes(bmp.get_byte_array()).hex() == "f0427f06593a22340000fddd"


def _bare_proc() -> _Proc:
    # Construction is private (callers use decode()); the defensive
    # _update_override guards below are only reachable by driving the instance
    # directly, since decode() validates AT arrays before _update_override runs.
    return _Proc(None, None)


def test_update_override_returns_when_at_arrays_none():
    """§ updateOverride guard: gr_at_x / gr_at_y None -> early return, no override."""
    proc = _bare_proc()
    proc.template_id = 0
    proc.gr_at_x = None
    proc.gr_at_y = None
    proc._update_override()
    assert proc.override is False
    assert proc.gr_at_override is None


def test_update_override_returns_when_at_array_lengths_differ():
    """§ updateOverride guard: len(gr_at_x) != len(gr_at_y) -> early return."""
    proc = _bare_proc()
    proc.template_id = 0
    proc.gr_at_x = [-1, -1]
    proc.gr_at_y = [-1]
    proc._update_override()
    assert proc.override is False
    assert proc.gr_at_override is None
