"""Live differential oracle for the JBIG2 generic-refinement-region decoder.

Drives the upstream Apache PDFBox ``GenericRefinementRegion`` via
``oracle/probes/RefinementProbe.java`` — building a reference ``Bitmap`` from a
crafted hex pixel pattern, then invoking the (protected) ``setParameters`` entry
point with a fresh ``ArithmeticDecoder`` over crafted coded bytes and a fresh
``CX`` — and asserts pypdfbox's ``GenericRefinementRegionDecodingProcedure``
produces the IDENTICAL refined bitmap (every packed byte).

This is the gold-standard parity check for the §6.3.5.6 context computation:
because the MQ arithmetic decoder is deterministic for a given coded byte
string, feeding the same crafted bytes + reference bitmap to both decoders and
comparing the refined bitmaps verifies the refinement template bit-ordering,
the reference/region pixel sampling, the sliding-window byte registers, and the
AT-pixel override masking are bit-exact.

Scope note — bundled jar version (PDFBox 3.0.7) vs ported upstream:
The pinned ``pdfbox-app-3.0.7.jar`` carries the OLDER ``GenericRefinementRegion``
where the decode logic is inlined. The refactored upstream we ported (which
extracted ``GenericRefinementRegionDecodingProcedure``) fixed three behaviours
the 3.0.7 version got wrong:

* TPGRON crashes in 3.0.7 (``template`` field is null on the first SLTP), so the
  oracle cannot exercise the typical-prediction path at all;
* template 1 is routed through a different code path in the refactor;
* ``updateOverride`` activates AT override unless BOTH coords == -1 (3.0.7
  skipped override if EITHER coord == -1), and AT2 no longer has a
  ``grAtY[1] == 0`` special case.

So this oracle is restricted to the paths where the two versions agree:
**template 0 (any referenceDX) and template 1 with referenceDX >= 0, TPGRON off,
AT pixels either both-nominal (-1,-1) or with neither coordinate equal to -1**.

Wave-1493 update — the historical claim that "template 1 routes through a
different code path" turned out to be only HALF true. The 3.0.7 jar's inlined
``decodeTemplate`` and the refactored ``GenericRefinementRegionDecodingProcedure``
agree byte-for-byte for template 1 as long as ``referenceDX >= 0`` (verified live
against the jar via ``RefinementProbe`` for dx in {0, +1} and several reference
shapes). They DIVERGE only for ``referenceDX < 0`` template 1 (the refactor fixed
the negative-remainder shift in ``(2 - modReferenceDX) % 8`` / the AT-window
advance), which is pinned as a strict-xfail divergence below. The TPGRON path is
still uncoverable here because the 3.0.7 jar's ``setParameters`` entry leaves the
``template`` field null, so the first SLTP throws ``NullPointerException`` before
any pixel is decoded; TPGRON template 0/1 are pinned Python-deterministically in
``tests/jbig2/segments/test_generic_refinement_region.py``.
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import ArithmeticDecoder
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.decoder.generic_refinement_region_decoding_procedure import (
    GenericRefinementRegionDecodingProcedure,
)
from tests.jbig2.segments.test_generic_refinement_region import (
    MemoryImageInputStream,
    _make_reference,
)
from tests.oracle.harness import requires_oracle, run_probe_text

# (id, gr_template, w, h, ref_w, ref_h, dx, dy, ref_hex, coded_hex, at_x, at_y)
_CASES = [
    ("basic_8x4", 0, 8, 4, 8, 4, 0, 0, "8040c030", "84c73b00ff12abcd",
     [-1, -1], [-1, -1]),
    ("zero_ref", 0, 8, 4, 8, 4, 0, 0, "00000000", "00000000",
     [-1, -1], [-1, -1]),
    ("multibyte_24x8", 0, 24, 8, 24, 8, 0, 0,
     "8040c030aa5511220ff0a1b2c3d4e5f60718293a", "84c73b00ff12abcd5566778899",
     [-1, -1], [-1, -1]),
    ("ref_offset", 0, 12, 6, 12, 6, 1, -1, "8040c030aa5511220ff0",
     "84c73b00ff12abcd", [-1, -1], [-1, -1]),
    ("at_override", 0, 10, 4, 10, 4, 0, 0, "8040c030aa55", "84c73b00ff12",
     [-2, 2], [-2, 1]),
    ("at_nominal", 0, 10, 4, 10, 4, 0, 0, "8040c030aa55", "84c73b00ff12",
     [-1, -1], [-1, -1]),
    # Template-0, negative referenceDX (exercises the < 0 shiftOffset branch of
    # decodeTemplate — c1/c2/c3 from (w << 1) | (w >>> 7)). Both versions agree.
    ("t0_neg_ref_dx", 0, 12, 6, 12, 6, -2, 1, "8040c030aa5511220ff0",
     "84c73b00ff12abcd", [-1, -1], [-1, -1]),
    ("t0_neg_ref_dx_dy0", 0, 12, 6, 12, 6, -2, 0, "8040c030aa5511220ff0",
     "84c73b00ff12abcd", [-1, -1], [-1, -1]),
    ("t0_wide_offset_36x10", 0, 36, 10, 36, 10, 3, 2,
     "8040c030aa5511220ff0a1b2c3d4e5f607182939",
     "84c73b00ff12abcd5566778899aa", [-1, -1], [-1, -1]),
    # Template-1, referenceDX >= 0 — agrees with the 3.0.7 jar (the bit-formation
    # mask of Figure 15 plus the optimized byte-blit advance).
    ("t1_basic_8x4", 1, 8, 4, 8, 4, 0, 0, "8040c030", "84c73b00ff12abcd",
     [-1, -1], [-1, -1]),
    ("t1_zero_ref", 1, 8, 4, 8, 4, 0, 0, "00000000", "00000000",
     [-1, -1], [-1, -1]),
    ("t1_multibyte_24x8", 1, 24, 8, 24, 8, 0, 0,
     "8040c030aa5511220ff0a1b2c3d4e5f60718293a",
     "84c73b00ff12abcd5566778899", [-1, -1], [-1, -1]),
    ("t1_ref_offset_pos", 1, 12, 6, 12, 6, 1, -1, "8040c030aa5511220ff0",
     "84c73b00ff12abcd", [-1, -1], [-1, -1]),
    ("t1_pos_ref_dx_dy0", 1, 12, 6, 12, 6, 1, 0, "8040c030aa5511220ff0",
     "84c73b00ff12abcd", [-1, -1], [-1, -1]),
]


def _py_decode(gr_template, w, h, ref_w, ref_h, dx, dy, ref_hex, coded_hex,
               at_x, at_y) -> str:
    reference = _make_reference(ref_w, ref_h, ref_hex)
    decoder = ArithmeticDecoder(MemoryImageInputStream(bytes.fromhex(coded_hex)))
    cx = CX(8192, 1)
    result = GenericRefinementRegionDecodingProcedure.decode(
        decoder, cx, w, h, gr_template, False, reference, dx, dy, at_x, at_y
    )
    return result.bitmap_bytes.hex()


@requires_oracle
@pytest.mark.parametrize(
    ("case_id", "gr_template", "w", "h", "ref_w", "ref_h", "dx", "dy",
     "ref_hex", "coded_hex", "at_x", "at_y"),
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_refinement_matches_pdfbox(
    case_id, gr_template, w, h, ref_w, ref_h, dx, dy, ref_hex, coded_hex, at_x, at_y
):
    args = [
        str(gr_template), str(w), str(h), str(ref_w), str(ref_h),
        str(dx), str(dy), "0", ref_hex, coded_hex,
        str(at_x[0]), str(at_y[0]), str(at_x[1]), str(at_y[1]),
    ]
    java_hex = run_probe_text("RefinementProbe", *args).strip()

    py_hex = _py_decode(
        gr_template, w, h, ref_w, ref_h, dx, dy, ref_hex, coded_hex, at_x, at_y
    )

    assert py_hex == java_hex


# --------------------------------------------------------------------------
# Documented version divergence: template-1 refinement with referenceDX < 0.
# --------------------------------------------------------------------------
# The pinned 3.0.7 jar's inlined GenericRefinementRegion.decodeTemplate and the
# refactored GenericRefinementRegionDecodingProcedure (which pypdfbox ports)
# produce DIFFERENT bytes for template 1 once referenceDX is negative. The
# refactor corrected the negative-remainder handling in the optimized byte-blit
# (Java truncated `(2 - modReferenceDX) % 8` shift + the AT-window read at the
# `(x - referenceDX) % 8 == 5` boundary); the 3.0.7 inlined copy applied the
# Python/positive-remainder form. pypdfbox follows the refactored upstream (the
# behaviour real readers ship today), so we deliberately do NOT match the 3.0.7
# jar here. This strict-xfail pins the divergence on BOTH sides so a future jar
# bump (or a regression) flips it loudly.

_T1_NEG_DX_CASE = (1, 12, 6, 12, 6, -2, 0, "8040c030aa5511220ff0",
                   "84c73b00ff12abcd", [-1, -1], [-1, -1])


@requires_oracle
@pytest.mark.xfail(
    reason="template-1 referenceDX<0: 3.0.7 jar inlined decoder diverges from "
    "the refactored procedure pypdfbox ports (negative-remainder shift fix)",
    strict=True,
)
def test_template1_negative_ref_dx_diverges_from_3_0_7_jar():
    gr_template, w, h, ref_w, ref_h, dx, dy, ref_hex, coded_hex, at_x, at_y = (
        _T1_NEG_DX_CASE
    )
    java_hex = run_probe_text(
        "RefinementProbe", str(gr_template), str(w), str(h), str(ref_w),
        str(ref_h), str(dx), str(dy), "0", ref_hex, coded_hex,
        str(at_x[0]), str(at_y[0]), str(at_x[1]), str(at_y[1]),
    ).strip()
    py_hex = _py_decode(
        gr_template, w, h, ref_w, ref_h, dx, dy, ref_hex, coded_hex, at_x, at_y
    )
    # Strict-xfail: this assertion is EXPECTED to fail (the two versions differ).
    assert py_hex == java_hex


def test_template1_negative_ref_dx_python_is_stable():
    """The refactored-upstream byte output pypdfbox commits to (oracle-free).

    Pins the exact bytes pypdfbox produces for the divergent case so a
    regression in the negative-referenceDX template-1 path is caught even on a
    machine without Java.
    """
    gr_template, w, h, dx, dy, ref_hex, coded_hex = (
        1, 12, 6, -2, 0, "8040c030aa5511220ff0", "84c73b00ff12abcd"
    )
    py_hex = _py_decode(
        gr_template, w, h, 12, 6, dx, dy, ref_hex, coded_hex, [-1, -1], [-1, -1]
    )
    assert py_hex == "00601fc02980ac805e30b670"
