"""Live differential oracle for the JBIG2 generic-region decoder.

Drives the upstream Apache PDFBox ``GenericRegion`` via
``oracle/probes/GenericRegionProbe.java`` on crafted generic-region
segment-data buffers and asserts that pypdfbox's ``GenericRegion`` produces the
IDENTICAL decoded bitmap (width, height, row stride, and every packed byte).

This is the gold-standard parity check for the generic-region procedure: it
exercises the arithmetic context computation for templates 0-3, the TPGDON
typical-prediction LTP toggling, the AT-pixel override paths, and the MMR
(CCITT Group-4) decode path. Because the MQ arithmetic decoder is deterministic
for a given coded byte string, feeding the same crafted bytes to both decoders
and comparing the bitmaps verifies the GB template bit-ordering and masking are
bit-exact.

The crafted buffer is the EXACT segment-data part of an immediate
generic-region segment (region segment information field + generic-region flags
+ AT pixels + coded data). The probe reaches ``GenericRegion``'s package-private
no-arg constructor and ``init(SegmentHeader, SubInputStream)`` via reflection
and passes a ``null`` header (which a generic region never dereferences).
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.generic_region import GenericRegion
from tests.jbig2.segments.test_generic_region import (
    CODED,
    NOMINAL_AT,
    _at,
    _g4_strip,
    _gen_flags,
    _region_info,
)
from tests.oracle.harness import requires_oracle, run_probe_text


def _py_decode(segment_data: bytes) -> str:
    """Decode with pypdfbox, formatted like the probe: 'w h stride hexbytes'."""
    iis = ImageInputStream(segment_data)
    sis = SubInputStream(iis, 0, len(segment_data))
    region = GenericRegion()
    region.init(None, sis)
    bitmap = region.get_region_bitmap()
    return (
        f"{bitmap.get_width()} {bitmap.get_height()} {bitmap.get_row_stride()} "
        f"{bytes(bitmap.get_byte_array()).hex()}"
    )


def _arith_case(template, pairs, width, height):
    return _region_info(width, height) + _gen_flags(template=template) + _at(pairs) + CODED


def _tpgdon_case(template, width, height):
    return (
        _region_info(width, height)
        + _gen_flags(template=template, tpgdon=1)
        + _at(NOMINAL_AT[template])
        + CODED
    )


# (name, segment_data_factory)
_ARITH_CASES = [
    ("template0_nominal", lambda: _arith_case(0, NOMINAL_AT[0], 13, 6)),
    ("template1_nominal", lambda: _arith_case(1, NOMINAL_AT[1], 13, 6)),
    ("template2_nominal", lambda: _arith_case(2, NOMINAL_AT[2], 13, 6)),
    ("template3_nominal", lambda: _arith_case(3, NOMINAL_AT[3], 13, 6)),
    ("template0_byte_aligned", lambda: _arith_case(0, NOMINAL_AT[0], 16, 8)),
    (
        "template0_at_override",
        lambda: _arith_case(0, [(4, -1), (-3, -1), (2, -2), (-2, -2)], 12, 4),
    ),
    ("template1_at_override", lambda: _arith_case(1, [(2, -1)], 9, 4)),
    ("template2_at_override", lambda: _arith_case(2, [(3, -1)], 9, 4)),
    ("template3_at_override", lambda: _arith_case(3, [(3, -1)], 9, 4)),
    ("template0_tpgdon", lambda: _tpgdon_case(0, 10, 5)),
    ("template1_tpgdon", lambda: _tpgdon_case(1, 10, 5)),
    ("template2_tpgdon", lambda: _tpgdon_case(2, 10, 5)),
    ("template3_tpgdon", lambda: _tpgdon_case(3, 10, 5)),
]


@requires_oracle
@pytest.mark.parametrize(
    ("name", "factory"), _ARITH_CASES, ids=[c[0] for c in _ARITH_CASES]
)
def test_arithmetic_matches_pdfbox(name, factory):
    segment_data = factory()
    java = run_probe_text("GenericRegionProbe", segment_data.hex()).strip()
    assert _py_decode(segment_data) == java


_MMR_CASES = [
    ("rect16x8", 16, 8, lambda: [(x, y) for y in range(2, 6) for x in range(4, 12)]),
    ("stripes13x5", 13, 5, lambda: [(x, y) for y in range(5) for x in range(0, 13, 2)]),
    ("diag12x12", 12, 12, lambda: [(i, i) for i in range(12)]),
]


@requires_oracle
@pytest.mark.parametrize(
    ("name", "width", "height", "black_factory"),
    _MMR_CASES,
    ids=[c[0] for c in _MMR_CASES],
)
def test_mmr_matches_pdfbox(name, width, height, black_factory):
    g4 = _g4_strip(width, height, black_factory())
    segment_data = _region_info(width, height) + _gen_flags(mmr=1) + g4
    java = run_probe_text("GenericRegionProbe", segment_data.hex()).strip()
    assert _py_decode(segment_data) == java
