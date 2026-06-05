"""Parameter validation + template/context parity for the generic refinement
region decoding procedure (§6.3.5.6) — wave 1492.

The live page oracle (``test_jbig2_page_oracle``) already drives the *template-0*
refinement path bit-exact through ``20123110001.jb2``. This module pins the
parts the oracle's fixtures don't reach:

* the public ``decode`` parameter-validation contract (null guards, template
  range, the template-0 AT-array length requirement, positive dimensions);
* ``_java_mod`` — Java truncated remainder, whose sign differs from Python's
  ``%`` for a negative dividend (the ``referenceDX % 8`` branch selection);
* the per-template context-bit formation (``Template.form``) and SLTP context
  index (``Template.set_index``) constants from Figures 14/15;
* the §6.3.5.2 out-of-bounds pixel rule (all pixels outside a bitmap read as 0)
  via ``_get_pixel_safe`` / ``_get_reference_bit`` and the template-1 context
  builder;
* the template-1 explicit-decode loop fills the region bitmap from the
  arithmetic decoder, pixel by pixel.
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.decoder.generic_refinement_region_decoding_procedure import (
    T0,
    T1,
    _java_mod,
)
from pypdfbox.jbig2.decoder.generic_refinement_region_decoding_procedure import (
    GenericRefinementRegionDecodingProcedure as GRRDP,
)


class _StubArith:
    """Arithmetic-decoder stub returning a fixed sequence (or a constant)."""

    def __init__(self, bits=None, constant=0):
        self._bits = list(bits) if bits is not None else None
        self._constant = constant
        self._i = 0

    def decode(self, cx):
        if self._bits is None:
            return self._constant
        bit = self._bits[self._i]
        self._i += 1
        return bit


def _proc(arith=None, cx=None) -> GRRDP:
    return GRRDP(arith or _StubArith(), cx or CX(8192, 1))


# --------------------------------------------------------------------------
# decode() parameter-validation contract
# --------------------------------------------------------------------------


def test_decode_rejects_null_arith_decoder():
    ref = Bitmap(4, 4)
    with pytest.raises(ValueError, match="arithDecoder"):
        GRRDP.decode(None, CX(8192, 1), 4, 4, 1, False, ref, 0, 0, None, None)


def test_decode_rejects_null_cx():
    ref = Bitmap(4, 4)
    with pytest.raises(ValueError, match="cx"):
        GRRDP.decode(_StubArith(), None, 4, 4, 1, False, ref, 0, 0, None, None)


def test_decode_rejects_null_reference_bitmap():
    with pytest.raises(ValueError, match="referenceBitmap"):
        GRRDP.decode(_StubArith(), CX(8192, 1), 4, 4, 1, False, None, 0, 0, None, None)


def test_decode_rejects_bad_template():
    ref = Bitmap(4, 4)
    with pytest.raises(ValueError, match="grTemplate must be 0 or 1"):
        GRRDP.decode(_StubArith(), CX(8192, 1), 4, 4, 2, False, ref, 0, 0, None, None)


def test_decode_template0_requires_at_arrays_of_length_two():
    ref = Bitmap(4, 4)
    with pytest.raises(ValueError, match="length 2 for template 0"):
        GRRDP.decode(_StubArith(), CX(8192, 1), 4, 4, 0, False, ref, 0, 0, [0], [0])
    with pytest.raises(ValueError, match="length 2 for template 0"):
        GRRDP.decode(_StubArith(), CX(8192, 1), 4, 4, 0, False, ref, 0, 0, None, None)


def test_decode_rejects_non_positive_dimensions():
    ref = Bitmap(4, 4)
    with pytest.raises(ValueError, match="must be > 0"):
        GRRDP.decode(_StubArith(), CX(8192, 1), 0, 4, 1, False, ref, 0, 0, None, None)
    with pytest.raises(ValueError, match="must be > 0"):
        GRRDP.decode(_StubArith(), CX(8192, 1), 4, -1, 1, False, ref, 0, 0, None, None)


# --------------------------------------------------------------------------
# _java_mod — Java truncated remainder (sign of dividend)
# --------------------------------------------------------------------------


def test_java_mod_matches_java_truncated_remainder():
    assert _java_mod(-1, 8) == -1          # Python -1 % 8 == 7
    assert _java_mod(-9, 8) == -1
    assert _java_mod(9, 8) == 1
    assert _java_mod(0, 8) == 0
    assert _java_mod(8, 8) == 0
    assert _java_mod(-16, 8) == 0


# --------------------------------------------------------------------------
# Template context formation + SLTP index (Figures 14/15)
# --------------------------------------------------------------------------


def test_template0_form_packs_five_context_bits():
    # (c1<<10)|(c2<<7)|(c3<<4)|(c4<<1)|c5
    assert T0.form(1, 0, 0, 0, 0) == (1 << 10)
    assert T0.form(0, 1, 0, 0, 0) == (1 << 7)
    assert T0.form(1, 1, 1, 1, 1) == ((1 << 10) | (1 << 7) | (1 << 4) | (1 << 1) | 1)


def test_template1_form_masks_per_figure15():
    # ((c1&2)<<8)|(c2<<6)|((c3&3)<<4)|(c4<<1)|c5
    assert T1.form(2, 0, 0, 0, 0) == (2 << 8)
    assert T1.form(1, 0, 0, 0, 0) == 0          # c1 & 2 == 0
    assert T1.form(0, 1, 3, 1, 1) == ((1 << 6) | (3 << 4) | (1 << 1) | 1)


def test_template_sltp_context_indices():
    cx0 = CX(8192, 1)
    T0.set_index(cx0)
    assert cx0.index == 0x100
    cx1 = CX(8192, 1)
    T1.set_index(cx1)
    assert cx1.index == 0x008


# --------------------------------------------------------------------------
# §6.3.5.2 out-of-bounds rule + template-1 context builder
# --------------------------------------------------------------------------


def test_get_pixel_safe_treats_outside_as_zero():
    proc = _proc()
    bm = Bitmap(2, 2)
    bm.set_pixel(0, 0, 1)
    bm.set_pixel(1, 1, 1)
    assert proc._get_pixel_safe(bm, 0, 0) == 1
    assert proc._get_pixel_safe(bm, 1, 1) == 1
    assert proc._get_pixel_safe(bm, -1, 0) == 0
    assert proc._get_pixel_safe(bm, 0, -1) == 0
    assert proc._get_pixel_safe(bm, 2, 0) == 0   # x >= width
    assert proc._get_pixel_safe(bm, 0, 2) == 0   # y >= height


def test_get_reference_bit_applies_reference_offset():
    proc = _proc()
    proc.reference_bitmap = Bitmap(2, 2)
    proc.reference_bitmap.set_pixel(0, 0, 1)
    proc.reference_dx = 1
    proc.reference_dy = 1
    # reference bit at (x,y) reads ref(x-dx, y-dy); (1,1) -> ref(0,0) == 1.
    assert proc._get_reference_bit(1, 1) == 1
    assert proc._get_reference_bit(0, 0) == 0   # ref(-1,-1) -> outside -> 0


def test_build_context_t1_collects_neighbourhood_bits():
    proc = _proc()
    proc.region_bitmap = Bitmap(3, 3)
    proc.reference_bitmap = Bitmap(3, 3)
    proc.reference_dx = 0
    proc.reference_dy = 0
    # set the region bit at (x, y-1) -> contributes bit 8.
    proc.region_bitmap.set_pixel(1, 0, 1)
    # set the reference centre (x, y) -> contributes bit 3.
    proc.reference_bitmap.set_pixel(1, 1, 1)
    ctx = proc._build_context_t1(1, 1)
    assert ctx & (1 << 8)
    assert ctx & (1 << 3)
    # an unset neighbour contributes nothing.
    assert not (ctx & (1 << 9))  # region(0,0) is unset


# --------------------------------------------------------------------------
# Template-1 explicit decode loop fills the region bitmap
# --------------------------------------------------------------------------


def test_explicit_template1_fills_region_from_decoder():
    # An arith stub that always returns 1 -> every pixel set; verify the loop
    # visits every pixel of the line.
    proc = _proc(arith=_StubArith(constant=1))
    proc.template_id = 1
    proc.template = T1
    proc.region_bitmap = Bitmap(5, 1)
    proc.reference_bitmap = Bitmap(5, 1)
    proc.reference_dx = 0
    proc.reference_dy = 0
    proc._decode_line_explicit_t1(0, 5)
    assert all(proc.region_bitmap.get_pixel(x, 0) == 1 for x in range(5))


def test_tpgr_template1_uniform_neighbourhood_copies_reference():
    # All-zero reference: every 3x3 neighbourhood is uniform (centre 0), so the
    # TPGR line copies the reference centre (0) without touching the decoder.
    # A decoder that would explode if called proves the typical-prediction path.
    class _Boom:
        def decode(self, cx):
            raise AssertionError("decoder must not be called for a uniform line")

    proc = _proc(arith=_Boom())
    proc.template_id = 1
    proc.template = T1
    proc.region_bitmap = Bitmap(6, 1)
    proc.reference_bitmap = Bitmap(6, 3)  # all zero
    proc.reference_dx = 0
    proc.reference_dy = 0
    proc._decode_line_tpgr_t1(0, 6)
    assert all(proc.region_bitmap.get_pixel(x, 0) == 0 for x in range(6))
