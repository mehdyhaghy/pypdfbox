"""Live differential oracle for the JBIG2 symbol-dictionary decoder.

Drives the upstream Apache PDFBox ``SymbolDictionary`` via
``oracle/probes/SymbolDictProbe.java`` on the EXACT segment-data slices of real
standalone (no referred-to segments) symbol-dictionary segments cut out of the
upstream ``.jb2`` test fixtures, and asserts that pypdfbox's
``SymbolDictionary`` produces the IDENTICAL exported symbol list (count, then
each symbol's width, height, row stride, and every packed byte).

This is the gold-standard parity check for the symbol-dictionary procedure:
because the MQ arithmetic decoder is deterministic for a given coded byte
string, feeding the same bytes to both decoders and comparing the full exported
symbol set verifies the height-class / delta-width loop, the IADH / IADW /
IAEX integer decoding, the direct generic-region symbol decoding (6.5.8.1), and
the export-flag run-length expansion (6.5.10) are all bit-exact.

The probe reaches ``SymbolDictionary``'s package-private no-arg constructor and
``init(SegmentHeader, SubInputStream)`` via reflection, and allocates a
``SegmentHeader`` without running its constructor (so ``rtSegments`` stays
``null`` ⇒ no imported symbols), matching the standalone-dictionary case the
Python side decodes with a stub header.

The fixtures here are arithmetic-coded, non-refinement, SDTEMPLATE 0. The
Huffman and refinement/aggregate paths are not present in these standalone
dictionaries.
"""

from __future__ import annotations

import pytest

from tests.jbig2.segments.test_symbol_dictionary import (
    _FIXTURES,
    _decode,
    _first_standalone_symbol_dict,
)
from tests.oracle.harness import requires_oracle, run_probe_text


def _py_decode(blob: bytes) -> str:
    """Decode with pypdfbox, formatted exactly like the probe output."""
    sd = _decode(blob)
    symbols = sd.get_dictionary()
    parts = [str(len(symbols))]
    for b in symbols:
        parts.append(
            f"{b.get_width()} {b.get_height()} {b.get_row_stride()} "
            f"{bytes(b.get_byte_array()).hex()}"
        )
    return " ; ".join(parts)


_ORACLE_CASES = ["003.jb2", "005.jb2"]


@requires_oracle
@pytest.mark.parametrize("fixture", _ORACLE_CASES)
def test_arithmetic_matches_pdfbox(fixture):
    blob = _first_standalone_symbol_dict(_FIXTURES / fixture)
    java = run_probe_text(
        "SymbolDictProbe",
        blob.hex(),
    ).strip()
    assert _py_decode(blob) == java
