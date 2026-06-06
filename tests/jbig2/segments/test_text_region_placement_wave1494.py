"""Text-region arithmetic-reachable wiring not exercised by bundled fixtures —
wave 1494.

These three surfaces are reachable on the *arithmetic* decode path but are not
hit by any of the five bundled ``.jb2`` fixtures (whose only text region —
``21.jb2`` — is Huffman-coded, non-transposed, single reference corner) nor by
the wave-1493 refinement tests (which construct a bare ``TextRegion()`` and call
``_decode_ib`` directly):

* ``_blit`` (§6.4.5 step 3 c) vi-x) symbol-instance placement — every
  ``is_transposed`` x ``reference_corner`` combination shifts ``current_s`` and
  the blit origin differently; the bundled fixture only ever takes one combo.
* ``set_contexts`` / ``set_parameters`` (Table 31 / 34 parameter wiring) — only
  invoked by the symbol-dictionary refinement-aggregation path
  (``_decode_through_text_region``), which no fixture exercises.
* The ``__init__(sub_input_stream)`` branch that builds a
  ``RegionSegmentInformation`` (the refinement tests pass no stream).

All are pure state wiring (no arithmetic-stream output), so they are driven
directly and asserted structurally.
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.text_region import TextRegion
from pypdfbox.jbig2.util.combination_operator import CombinationOperator


def _solid(width: int, height: int) -> Bitmap:
    bmp = Bitmap(width, height)
    for i in range(len(bmp.bitmap_bytes)):
        bmp.set_byte(i, 0xFF)
    return bmp


def _placement_region() -> TextRegion:
    tr = TextRegion()
    tr.region_bitmap = Bitmap(32, 32)
    tr.combination_operator = CombinationOperator.OR
    return tr


@pytest.mark.parametrize(
    ("transposed", "corner"),
    [(t, c) for t in (0, 1) for c in (0, 1, 2, 3)],
    ids=[f"t{t}_corner{c}" for t in (0, 1) for c in (0, 1, 2, 3)],
)
def test_blit_placement_all_transposed_corner_combos(transposed, corner):
    """§6.4.5 3c vi-x: each transposed x reference-corner combo shifts current_s
    and the blit origin per the spec; all eight must run without error."""
    tr = _placement_region()
    tr.is_transposed = transposed
    tr.reference_corner = corner
    tr.current_s = 10
    ib = _solid(8, 4)
    tr._blit(ib, 5)
    # current_s advanced by (width-1) or (height-1) on the pre/post-blit shifts
    # depending on the combo; in every combo it moved off the starting 10.
    assert tr.current_s in (13, 17)


def test_blit_non_transposed_right_corner_pre_shift():
    """Non-transposed + BR/TR corner pre-shifts current_s by width-1 (step vi)."""
    tr = _placement_region()
    tr.is_transposed = 0
    tr.reference_corner = 2  # BR
    tr.current_s = 0
    ib = _solid(8, 4)
    tr._blit(ib, 3)
    # +7 (pre-shift width-1); BR takes no post-shift.
    assert tr.current_s == 7


def test_set_contexts_and_parameters_wire_state():
    """Table 31 / 34 wiring: set_contexts + set_parameters populate the decode
    state used by the refinement-aggregation TextRegion path."""
    sis = SubInputStream(ImageInputStream(bytes(20)), 0, 20)
    tr = TextRegion(sis)
    assert tr.region_info is not None  # __init__ stream branch

    iaid = CX(2, 1)
    tr.set_contexts(
        CX(2, 1), CX(512, 1), CX(512, 1), CX(512, 1), CX(512, 1),
        iaid, CX(512, 1), CX(512, 1), CX(512, 1), CX(512, 1),
    )
    assert tr.cx_iaid is iaid

    syms = [_solid(8, 4)]
    tr.set_parameters(
        None, None, False, True, 16, 8, 2, 1, 4, 0, 0, 0, 1, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, [-1, -1], [-1, -1], syms, 1,
    )
    assert tr.region_info.get_bitmap_width() == 16
    assert tr.region_info.get_bitmap_height() == 8
    assert tr.amount_of_symbol_instances == 2
    assert tr.use_refinement is True
    assert tr.is_transposed == 0
    assert tr.reference_corner == 1
    assert tr.symbols is syms
    assert tr.symbol_code_length == 1
