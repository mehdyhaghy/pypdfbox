"""Live differential oracle for the JBIG2 pattern-dictionary decoder.

Drives the upstream Apache PDFBox ``PatternDictionary`` via
``oracle/probes/PatternDictionaryProbe.java`` on crafted pattern-dictionary
segment-data buffers and asserts that pypdfbox's ``PatternDictionary`` decodes
the IDENTICAL list of patterns (count, then each pattern's width, height, row
stride, and every packed byte).

This is the gold-standard parity check for the §6.7.5 procedure: the collective
bitmap is decoded by an internal generic region (arithmetic templates 0-3 with
the pattern-dictionary AT-pixel placement, or the MMR path) and then sliced
left-to-right into the dictionary patterns. Because the MQ arithmetic decoder is
deterministic for a given coded byte string, feeding the same crafted bytes to
both decoders and comparing the patterns verifies the AT-pixel placement, the
collective-bitmap width ``(GRAYMAX + 1) * HDPW`` and the slicing are bit-exact.

The crafted buffer is the EXACT segment-data part of a pattern-dictionary
segment (flags + HDPW + HDPH + GRAYMAX + coded collective bitmap). The probe
reaches ``PatternDictionary``'s package-private no-arg constructor and
``init(SegmentHeader, SubInputStream)`` via reflection and passes a ``null``
header (which the pattern-dictionary parse path never dereferences).
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.pattern_dictionary import PatternDictionary
from tests.jbig2.segments.test_pattern_dictionary import pd_data
from tests.oracle.harness import requires_oracle, run_probe_text


def _py_decode(segment_data: bytes) -> str:
    """Decode with pypdfbox, formatted like the probe.

    ``"<count>|<w> <h> <stride> <hex>|..."``.
    """
    iis = ImageInputStream(segment_data)
    sis = SubInputStream(iis, 0, len(segment_data))
    pd = PatternDictionary()
    pd.init(None, sis)
    patterns = pd.get_dictionary()
    parts = [str(len(patterns))]
    for b in patterns:
        parts.append(
            f"{b.get_width()} {b.get_height()} {b.get_row_stride()} "
            f"{bytes(b.get_byte_array()).hex()}"
        )
    return "|".join(parts)


# (name, segment_data_factory)
_CASES = [
    ("template0_4x4_graymax3", lambda: pd_data(4, 4, 3, template=0)),
    ("template0_6x3_graymax0", lambda: pd_data(6, 3, 0, template=0)),
    ("template1_5x4_graymax1", lambda: pd_data(5, 4, 1, template=1)),
    ("template2_8x8_graymax2", lambda: pd_data(8, 8, 2, template=2)),
    ("template3_4x4_graymax3", lambda: pd_data(4, 4, 3, template=3)),
    ("template0_wide_graymax7", lambda: pd_data(3, 3, 7, template=0)),
]


@requires_oracle
@pytest.mark.parametrize(
    ("name", "factory"), _CASES, ids=[c[0] for c in _CASES]
)
def test_pattern_dictionary_matches_pdfbox(name, factory):
    segment_data = factory()
    java = run_probe_text("PatternDictionaryProbe", segment_data.hex()).strip()
    py = _py_decode(segment_data)
    assert py == java
