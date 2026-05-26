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
**template 0, TPGRON off, AT pixels either both-nominal (-1,-1) or with neither
coordinate equal to -1**. The diverging paths are covered by hand-written unit
tests; full bit-exact coverage of TPGRON / template 1 lands when the pipeline is
wired against a refactored-version jar (refinement is also exercised via
symbol-dictionary / text-region segments later).
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
