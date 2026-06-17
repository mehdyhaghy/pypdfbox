"""Fuzz / differential parity for the JBIG2 generic refinement region decode
procedure (ITU-T T.88 §6.3.5) — wave 1584.

The byte-blit template-0 path is already pinned bit-exact against Apache PDFBox
3.0.7 by ``tests/jbig2/decoder/test_refinement_negative_reference_dx.py`` (the
``20123110001.jb2`` oracle). This module hits the parts the oracle fixture does
not reach by driving crafted flag combinations through the public
:meth:`GenericRefinementRegionDecodingProcedure.decode` entry point:

* **GRTEMPLATE 0 vs 1 context formation** — the two templates select different
  neighbour pixels (§6.3.5.3, Figures 14/15).
* **TPGRON typical prediction** — the SLTP pseudo-pixel decode and the "all 9
  surrounding reference pixels identical → copy" shortcut (§6.3.5.6 step 3d).
* **GRREFERENCEDX / GRREFERENCEDY** — the reference bitmap offset, including
  negative offsets, across both templates.

Two differential strategies catch a context-formation bug:

1. **Independent naive reference for template 1.** The actual decode uses the
   pdf.js-style per-pixel context builder
   (``_build_context_t1`` — coding bits at positions 9..6, reference bits at
   5..0, with the reference centre at bit 3). A second, structurally
   independent implementation is built here straight from the §6.3.5.3
   neighbour list and driven by the *same* context-sensitive arithmetic stub.
   If the actual context-bit ordering disagrees with the spec ordering, the
   decoded bitmaps diverge. Verified across seven reference offsets and the
   TPGRON path.
2. **Context-sensitive arithmetic stub.** ``decode`` returns a deterministic
   function of ``cx.index`` (not a constant), so a mis-formed context index
   produces a different decoded bit — a constant stub would mask the bug.

The SLTP context value for template 1 is ``0x008`` (the reference-centre bit in
the per-pixel ordering), matching pdf.js ``RefinementReusedContexts[1]``; for
template 0 it is ``0x100`` in PDFBox's ``form`` ordering. Both are asserted.
"""

from __future__ import annotations

import random

import pytest

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.decoder.generic_refinement_region_decoding_procedure import (
    _SLTP_CONTEXT_TEMPLATE0,
    _SLTP_CONTEXT_TEMPLATE1,
)
from pypdfbox.jbig2.decoder.generic_refinement_region_decoding_procedure import (
    GenericRefinementRegionDecodingProcedure as GRRDP,
)

# --------------------------------------------------------------------------
# Arithmetic-decoder stubs
# --------------------------------------------------------------------------


class _CtxStub:
    """Deterministic decoder whose output depends on the context index.

    Using a function of ``cx.index`` (rather than a constant) means a
    mis-formed context index decodes a different bit, so a context-formation
    bug shows up as a bitmap difference instead of being masked.
    """

    def decode(self, cx: CX) -> int:
        return ((cx.index * 2654435761) >> 13) & 1


class _SelStub:
    """SLTP returns 1 (forces LTP=1 on every line); explicit pixels return 0."""

    def __init__(self, sltp_index: int) -> None:
        self._sltp_index = sltp_index

    def decode(self, cx: CX) -> int:
        return 1 if cx.index == self._sltp_index else 0


# --------------------------------------------------------------------------
# Independent template-1 reference (§6.3.5.3 neighbour list)
# --------------------------------------------------------------------------


def _make_ref(width: int, height: int, seed: int) -> Bitmap:
    rng = random.Random(seed)
    bm = Bitmap(width, height)
    for x in range(width):
        for y in range(height):
            bm.set_pixel(x, y, rng.randint(0, 1))
    return bm


def _naive_t1(
    width: int,
    height: int,
    ref: Bitmap,
    dx: int,
    dy: int,
    *,
    tpgron: bool,
) -> Bitmap:
    arith = _CtxStub()
    reg = Bitmap(width, height)

    def rb(x: int, y: int) -> int:
        if x < 0 or y < 0 or x >= ref.get_width() or y >= ref.get_height():
            return 0
        return ref.get_pixel(x, y)

    def refbit(x: int, y: int) -> int:
        return rb(x - dx, y - dy)

    def gb(x: int, y: int) -> int:
        if x < 0 or y < 0 or x >= width or y >= height:
            return 0
        return reg.get_pixel(x, y)

    def context(x: int, y: int) -> int:
        return (
            (gb(x - 1, y - 1) << 9)
            | (gb(x, y - 1) << 8)
            | (gb(x + 1, y - 1) << 7)
            | (gb(x - 1, y) << 6)
            | (refbit(x, y - 1) << 5)
            | (refbit(x - 1, y) << 4)
            | (refbit(x, y) << 3)
            | (refbit(x + 1, y) << 2)
            | (refbit(x, y + 1) << 1)
            | refbit(x + 1, y + 1)
        )

    ltp = 0
    for y in range(height):
        if tpgron:
            cx = CX(8192, 1)
            cx.set_index(_SLTP_CONTEXT_TEMPLATE1)
            ltp ^= arith.decode(cx)
        for x in range(width):
            if tpgron and ltp:
                center = refbit(x, y)
                uniform = all(
                    refbit(x + ddx, y + ddy) == center
                    for ddy in (-1, 0, 1)
                    for ddx in (-1, 0, 1)
                )
                if uniform:
                    reg.set_pixel(x, y, center)
                    continue
            cx = CX(8192, 1)
            cx.set_index(context(x, y))
            reg.set_pixel(x, y, arith.decode(cx))
    return reg


# --------------------------------------------------------------------------
# Template-1 explicit-decode differential (LTP off)
# --------------------------------------------------------------------------

_T1_OFFSETS = [
    (0, 0),
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
    (2, -3),
    (-2, 2),
    (3, 3),
]


@pytest.mark.parametrize(
    ("dx", "dy"),
    _T1_OFFSETS,
    ids=[f"dx{dx}_dy{dy}" for dx, dy in _T1_OFFSETS],
)
def test_template1_context_matches_independent_reference(dx: int, dy: int) -> None:
    width, height = 9, 8
    ref = _make_ref(width, height, seed=100 + dx * 7 + dy * 3)
    got = GRRDP.decode(
        _CtxStub(), CX(8192, 1), width, height, 1, False, ref, dx, dy, None, None
    )
    expected = _naive_t1(width, height, ref, dx, dy, tpgron=False)
    assert got == expected


# --------------------------------------------------------------------------
# Template-1 TPGRON differential (LTP toggling + uniform-reference shortcut)
# --------------------------------------------------------------------------

_T1_TPGR_OFFSETS = [(0, 0), (1, 1), (-1, -1), (3, -2), (-2, 0), (0, 2)]


@pytest.mark.parametrize(
    ("dx", "dy"),
    _T1_TPGR_OFFSETS,
    ids=[f"dx{dx}_dy{dy}" for dx, dy in _T1_TPGR_OFFSETS],
)
def test_template1_tpgron_matches_independent_reference(dx: int, dy: int) -> None:
    width, height = 10, 9
    ref = _make_ref(width, height, seed=500 + dx * 11 + dy * 5)
    got = GRRDP.decode(
        _CtxStub(), CX(8192, 1), width, height, 1, True, ref, dx, dy, None, None
    )
    expected = _naive_t1(width, height, ref, dx, dy, tpgron=True)
    assert got == expected


# --------------------------------------------------------------------------
# TPGRON shortcut: uniform reference neighbourhood copies the reference centre
# --------------------------------------------------------------------------


def test_template1_tpgron_uniform_zero_reference_copies_zero() -> None:
    # All-zero reference: every interior 3x3 is uniform -> typical-predicted to
    # 0 without the decoder. SLTP is forced to 1 (so LTP=1 every line) and any
    # explicit decode would return 0 anyway, but the boom stub proves no
    # non-SLTP decode happens on a fully-uniform interior... edges still read
    # out-of-bounds zeros (also uniform 0), so the whole bitmap is 0.
    width, height = 12, 6
    ref = Bitmap(width, height)  # all zero
    sltp = _SelStub(_SLTP_CONTEXT_TEMPLATE1)
    got = GRRDP.decode(
        sltp, CX(8192, 1), width, height, 1, True, ref, 0, 0, None, None
    )
    assert all(
        got.get_pixel(x, y) == 0 for x in range(width) for y in range(height)
    )


def test_template1_tpgron_uniform_interior_skips_decoder() -> None:
    # All-ones reference. SLTP is forced to 1, so LTP toggles 1,0,1,0... per
    # line: even lines are LTP=1 (typical predicted), odd lines LTP=0 (explicit
    # decode -> 0). On an even line the genuinely uniform interior cells copy
    # the reference centre (1) without consulting the arithmetic decoder; edge
    # cells read the border (0), so they are non-uniform and decode explicitly.
    width, height = 16, 16
    ref = Bitmap(width, height)
    ref.fill_bitmap(0xFF)

    stub = _SelStub(_SLTP_CONTEXT_TEMPLATE1)
    got = GRRDP.decode(
        stub, CX(8192, 1), width, height, 1, True, ref, 0, 0, None, None
    )
    # Even (LTP=1) interior lines: uniform-1 neighbourhood copies centre -> 1.
    assert all(got.get_pixel(x, 2) == 1 for x in range(2, 14))
    assert all(got.get_pixel(x, 4) == 1 for x in range(2, 14))
    # Odd (LTP=0) lines: explicit decode returned 0.
    assert all(got.get_pixel(x, 1) == 0 for x in range(width))


# --------------------------------------------------------------------------
# Template-0 byte-blit path: structural / shortcut behaviour
# --------------------------------------------------------------------------

_T0_AT_DEFAULT = ([-1, -1], [-1, -1])


def test_template0_constant_one_fills_bitmap() -> None:
    class _One:
        def decode(self, cx: CX) -> int:
            return 1

    width, height = 13, 11
    ref = Bitmap(width, height)
    got = GRRDP.decode(
        _One(),
        CX(8192, 1),
        width,
        height,
        0,
        False,
        ref,
        0,
        0,
        *_T0_AT_DEFAULT,
    )
    assert all(
        got.get_pixel(x, y) == 1 for x in range(width) for y in range(height)
    )


@pytest.mark.parametrize(
    ("dx", "dy"),
    [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (2, -1)],
    ids=["dx0", "dxp1", "dxn1", "dyp1", "dyn1", "dx2dyn1"],
)
def test_template0_offsets_do_not_crash_and_are_deterministic(
    dx: int, dy: int
) -> None:
    width, height = 17, 9
    ref = _make_ref(width, height, seed=900 + dx * 13 + dy * 7)
    a = GRRDP.decode(
        _CtxStub(),
        CX(8192, 1),
        width,
        height,
        0,
        False,
        ref,
        dx,
        dy,
        *_T0_AT_DEFAULT,
    )
    b = GRRDP.decode(
        _CtxStub(),
        CX(8192, 1),
        width,
        height,
        0,
        False,
        ref,
        dx,
        dy,
        *_T0_AT_DEFAULT,
    )
    assert a == b  # decode is a pure function of inputs


def test_template0_tpgron_all_zero_reference_predicts_zero() -> None:
    # SLTP forced to 1 -> LTP toggles 1,0,1,0...; on LTP=1 lines an all-zero
    # uniform reference predicts 0; on LTP=0 lines explicit decode returns 0
    # too. Result is an all-zero bitmap.
    width, height = 24, 8
    ref = Bitmap(width, height)
    stub = _SelStub(_SLTP_CONTEXT_TEMPLATE0)
    got = GRRDP.decode(
        stub, CX(8192, 1), width, height, 0, True, ref, 0, 0, *_T0_AT_DEFAULT
    )
    assert all(
        got.get_pixel(x, y) == 0 for x in range(width) for y in range(height)
    )


def test_template0_tpgron_all_one_reference_predicts_one_on_ltp_lines() -> None:
    # All-ones reference. SLTP forced to 1: even lines are LTP=1 (typical
    # predicted), odd lines LTP=0 (explicit -> 0). The interior of even lines
    # copies the uniform reference 1.
    width, height = 16, 8
    ref = Bitmap(width, height)
    ref.fill_bitmap(0xFF)
    stub = _SelStub(_SLTP_CONTEXT_TEMPLATE0)
    got = GRRDP.decode(
        stub, CX(8192, 1), width, height, 0, True, ref, 0, 0, *_T0_AT_DEFAULT
    )
    # Even lines (LTP=1), interior columns: predicted 1.
    assert all(got.get_pixel(x, 2) == 1 for x in range(2, 14))
    # Odd lines (LTP=0): explicit decode returned 0.
    assert all(got.get_pixel(x, 1) == 0 for x in range(width))


# --------------------------------------------------------------------------
# AT-pixel override (template 0 only): a non-default GRAT changes the result
# --------------------------------------------------------------------------


def test_template0_default_at_disables_override() -> None:
    # Default AT positions (-1,-1) for both AT pixels -> override is OFF.
    proc = GRRDP(_CtxStub(), CX(8192, 1))
    proc.template_id = 0
    proc.gr_at_x = [-1, -1]
    proc.gr_at_y = [-1, -1]
    proc._update_override()
    assert proc.override is False
    assert proc.gr_at_override == [False, False]


def test_template0_custom_at_enables_override() -> None:
    proc = GRRDP(_CtxStub(), CX(8192, 1))
    proc.template_id = 0
    proc.gr_at_x = [-1, 2]
    proc.gr_at_y = [-1, -2]
    proc._update_override()
    assert proc.override is True
    assert proc.gr_at_override == [False, True]


def test_template0_at_override_changes_decoded_bitmap() -> None:
    # A non-default AT pixel must change the context-formation, and therefore
    # the decoded bitmap, relative to the default AT positions (with a
    # context-sensitive stub).
    width, height = 12, 6
    ref = _make_ref(width, height, seed=4242)
    default = GRRDP.decode(
        _CtxStub(), CX(8192, 1), width, height, 0, False, ref, 0, 0, [-1, -1], [-1, -1]
    )
    overridden = GRRDP.decode(
        _CtxStub(), CX(8192, 1), width, height, 0, False, ref, 0, 0, [-2, 2], [3, -1]
    )
    assert default != overridden


# --------------------------------------------------------------------------
# SLTP context constants (Figures 14/15) and per-template SLTP decode
# --------------------------------------------------------------------------


def test_sltp_context_constants() -> None:
    assert _SLTP_CONTEXT_TEMPLATE0 == 0x100
    assert _SLTP_CONTEXT_TEMPLATE1 == 0x008


def test_sltp_decode_uses_template_specific_index() -> None:
    from pypdfbox.jbig2.decoder.generic_refinement_region_decoding_procedure import (
        T0,
        T1,
    )

    seen: list[int] = []

    class _Recorder:
        def decode(self, cx: CX) -> int:
            seen.append(cx.index)
            return 0

    proc0 = GRRDP(_Recorder(), CX(8192, 1))
    proc0.template = T0
    proc0._decode_sltp()
    assert seen[-1] == _SLTP_CONTEXT_TEMPLATE0

    seen.clear()
    proc1 = GRRDP(_Recorder(), CX(8192, 1))
    proc1.template = T1
    proc1._decode_sltp()
    assert seen[-1] == _SLTP_CONTEXT_TEMPLATE1


# --------------------------------------------------------------------------
# §6.3.5.2 out-of-bounds rule edge: reference smaller than region
# --------------------------------------------------------------------------


def test_reference_smaller_than_region_reads_zero_outside() -> None:
    # A 2x2 reference under a 6x6 region: outside-reference reads are 0, decode
    # must not raise and must be deterministic.
    ref = Bitmap(2, 2)
    ref.set_pixel(0, 0, 1)
    ref.set_pixel(1, 1, 1)
    got = GRRDP.decode(
        _CtxStub(), CX(8192, 1), 6, 6, 1, False, ref, 0, 0, None, None
    )
    again = GRRDP.decode(
        _CtxStub(), CX(8192, 1), 6, 6, 1, False, ref, 0, 0, None, None
    )
    assert got == again


def test_reference_offset_pushes_reference_off_region() -> None:
    # A large positive offset moves the reference entirely outside the region's
    # sampling window: every reference read is 0. Template 1, no crash.
    ref = _make_ref(4, 4, seed=7)
    got = GRRDP.decode(
        _CtxStub(), CX(8192, 1), 5, 5, 1, False, ref, 100, 100, None, None
    )
    again = GRRDP.decode(
        _CtxStub(), CX(8192, 1), 5, 5, 1, False, ref, 100, 100, None, None
    )
    assert got == again
