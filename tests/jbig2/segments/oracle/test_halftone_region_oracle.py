"""Live differential oracle for the JBIG2 halftone-region decoder.

Drives the upstream Apache PDFBox ``HalftoneRegion`` via
``oracle/probes/HalftoneRegionProbe.java`` on crafted halftone-region
segment-data buffers and asserts that pypdfbox's ``HalftoneRegion`` produces the
IDENTICAL rendered bitmap (width, height, row stride, and every packed byte).

This is the gold-standard parity check for the §6.6.5 procedure: the grayscale
image is decoded from ``bitsPerValue`` arithmetic generic-region bit planes,
XOR-combined into a Gray code (Annex C.5), reduced to per-cell grayscale values,
and each cell's value indexes a dictionary pattern that is blitted onto the
region bitmap at the grid position computed from HGX/HGY and the HRX/HRY vector.
Because the MQ arithmetic decoder is deterministic for a given coded byte
string, feeding the same crafted bytes to both decoders and comparing the
rendered bitmaps verifies the Gray-code plane combination, the grayscale-value
computation, ``computeX``/``computeY`` placement and the ``blit`` compositing
are bit-exact.

A standalone halftone-region segment normally resolves its patterns through a
referred-to pattern-dictionary segment (``segmentHeader.getRtSegments()``),
which is awkward to fabricate via reflection. Both the probe and this test
therefore decode the patterns from a pattern-dictionary segment-data buffer and
inject them directly into the halftone region (the probe sets the private
``patterns`` field; pypdfbox sets ``hr.patterns``), isolating the
grayscale-decode + placement path for the diff.

Version note — oracle cases are deliberately restricted to placements where the
pinned-newer upstream source (the port target, ``apache/pdfbox-jbig2``) and the
bundled 3.0.7 oracle jar agree. The 3.0.7 jar predates two upstream fixes that
the ported source already contains:

* ``HalftoneRegion.renderPattern`` in 3.0.7 blits at ``(x + HGX, y + HGY)``
  even though ``computeX``/``computeY`` already fold HGX/HGY into the grid
  formula — a double-add the newer source removed. Cases therefore use
  ``HGX == HGY == 0`` so the double-add is a no-op.
* 3.0.7's ``Bitmaps.blit`` lacks the ``blitByPixel`` slow path (PDFBOX-6156);
  the newer source routes non-byte-aligned / padded composites through it.
  Cases therefore use 8-pixel-wide patterns (padding 0) placed at byte-aligned
  x, so both versions take the identical (un)shifted byte path.

The divergent (HGX/HGY-offset, 4-wide-pattern, overlapping) placements are
covered bit-exactly by the hand-written unit tests against the ported behaviour,
and the divergence is recorded in CHANGES.md.
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.halftone_region import HalftoneRegion
from pypdfbox.jbig2.segments.pattern_dictionary import PatternDictionary
from tests.jbig2.segments.test_halftone_region import ht_data
from tests.jbig2.segments.test_pattern_dictionary import pd_data
from tests.oracle.harness import requires_oracle, run_probe_text


def _py_patterns(pattern_dict_data: bytes):
    iis = ImageInputStream(pattern_dict_data)
    sis = SubInputStream(iis, 0, len(pattern_dict_data))
    pd = PatternDictionary()
    pd.init(None, sis)
    return pd.get_dictionary()


def _py_decode(pattern_dict_data: bytes, halftone_data: bytes) -> str:
    """Decode with pypdfbox, formatted like the probe: 'w h stride hexbytes'."""
    patterns = _py_patterns(pattern_dict_data)
    iis = ImageInputStream(halftone_data)
    sis = SubInputStream(iis, 0, len(halftone_data))
    hr = HalftoneRegion()
    hr.init(None, sis)
    hr.patterns = patterns
    bitmap = hr.get_region_bitmap()
    return (
        f"{bitmap.get_width()} {bitmap.get_height()} {bitmap.get_row_stride()} "
        f"{bytes(bitmap.get_byte_array()).hex()}"
    )


# Pattern dictionary used for every case: 4 patterns of 8x8 (graymax 3 ->
# bitsPerValue 2). 8-wide patterns have zero padding, so byte-aligned
# placements take the identical (un)shifted byte path in both versions (no
# blitByPixel divergence).
_PD = lambda: pd_data(8, 8, 3, template=0)  # noqa: E731

# All cases keep HGX == HGY == 0 (no 3.0.7 double-add) and HRX a multiple of
# 8*256 (patterns land at byte-aligned x). See the module docstring.
# (name, pattern_dict_factory, halftone_factory)
_CASES = [
    (
        "grid2x2_8wide",
        _PD,
        lambda: ht_data(rw=16, rh=16, hgw=2, hgh=2, hgx=0, hgy=0, hrx=8 * 256, hry=0),
    ),
    (
        "grid3x2_8wide",
        _PD,
        lambda: ht_data(rw=24, rh=16, hgw=3, hgh=2, hgx=0, hgy=0, hrx=8 * 256, hry=0),
    ),
    (
        "grid2x2_xor_8wide",
        _PD,
        lambda: ht_data(
            rw=16, rh=16, hgw=2, hgh=2, hgx=0, hgy=0, hrx=8 * 256, hry=0, combop=2
        ),
    ),
    (
        "grid2x2_defpixel_8wide",
        _PD,
        lambda: ht_data(
            rw=16, rh=16, hgw=2, hgh=2, hgx=0, hgy=0, hrx=8 * 256, hry=0, defpix=1
        ),
    ),
    (
        # Wide grid (> 8 columns) exercises the multi-byte grayscale-plane path.
        "grid10x1_8wide",
        _PD,
        lambda: ht_data(rw=80, rh=8, hgw=10, hgh=1, hgx=0, hgy=0, hrx=8 * 256, hry=0),
    ),
]


@requires_oracle
@pytest.mark.parametrize(
    ("name", "pd_factory", "ht_factory"), _CASES, ids=[c[0] for c in _CASES]
)
def test_halftone_region_matches_pdfbox(name, pd_factory, ht_factory):
    pattern_dict_data = pd_factory()
    halftone_data = ht_factory()
    java = run_probe_text(
        "HalftoneRegionProbe", pattern_dict_data.hex(), halftone_data.hex()
    ).strip()
    py = _py_decode(pattern_dict_data, halftone_data)
    assert py == java
