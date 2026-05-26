"""Live differential oracle for the JBIG2 text-region decoder.

Drives the upstream Apache PDFBox ``TextRegion`` via
``oracle/probes/TextRegionProbe.java`` on the EXACT segment-data slices of a
real immediate text region (type 6) and its referred standalone symbol
dictionary (type 0), cut out of the upstream ``.jb2`` test fixtures, and asserts
that pypdfbox's ``TextRegion`` produces the IDENTICAL region bitmap (width,
height, row stride, and every packed byte).

This is the gold-standard parity check for the text-region procedure: because
the MQ arithmetic decoder is deterministic for a given coded byte string,
feeding the same dictionary + text-region bytes to both decoders and comparing
the full region bitmap verifies the strip / FIRSTS / CURS positioning loop, the
IADT / IAFS / IADS / IAIT integer decoding, the IAID symbol-code decoding, the
reference-corner / transposition placement geometry, and the combination-
operator blit are all bit-exact.

The probe reaches the package-private ``SymbolDictionary`` / ``TextRegion``
no-arg constructors and ``init(SegmentHeader, SubInputStream)`` via reflection,
and synthesises the ``SegmentHeader`` graph (a text-region header whose single
referred-to segment is a type-0 dictionary header carrying the decoded symbol
dictionary), matching the stub-header graph the Python side decodes with.

The fixtures here are arithmetic-coded, non-refinement text regions; the Huffman
and per-instance refinement paths are not present in these fixtures.
"""

from __future__ import annotations

import pytest

from tests.jbig2.segments.test_text_region import (
    _FIXTURES,
    _decode_text_region,
    _symbol_dict_and_text_region_slices,
)
from tests.oracle.harness import requires_oracle, run_probe_text


def _py_decode(sd_blob: bytes, tr_blob: bytes) -> str:
    """Decode with pypdfbox, formatted exactly like the probe output."""
    b = _decode_text_region(sd_blob, tr_blob)
    return (
        f"{b.get_width()} {b.get_height()} {b.get_row_stride()} "
        f"{bytes(b.get_byte_array()).hex()}"
    )


_ORACLE_CASES = ["003.jb2", "005.jb2"]


@requires_oracle
@pytest.mark.parametrize("fixture", _ORACLE_CASES)
def test_arithmetic_matches_pdfbox(fixture):
    sd_blob, tr_blob = _symbol_dict_and_text_region_slices(_FIXTURES / fixture)
    java = run_probe_text(
        "TextRegionProbe",
        sd_blob.hex(),
        tr_blob.hex(),
    ).strip()
    assert _py_decode(sd_blob, tr_blob) == java
