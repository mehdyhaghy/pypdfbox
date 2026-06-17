"""Live differential oracle for the Huffman + refinement/aggregation JBIG2 paths.

No bundled or upstream ``.jb2`` fixture exercises the Huffman symbol-dictionary,
Huffman text-region or refinement decode bodies (DEFERRED.md). These tests build
complete, valid multi-segment JBIG2 streams with the test-only minimal encoder
(:mod:`tests.jbig2.helpers.jb2_encoder`) and feed the IDENTICAL bytes to both the
bundled PDFBox 3.0.7 jar (via the reflection probes) and pypdfbox, asserting
byte-for-byte parity of the decoded symbols / page bitmap.

Three paths are bit-exact vs the jar:

* SDHUFF=1, SDREFAGG=0 symbol dictionary (collective bitmap + export flags),
* SBHUFF=1, REFINE=0 text region (symbol-ID run-code table + strip placement),
* SBHUFF=1, REFINE=1 text region (one refined instance via the generic
  refinement region procedure, symInRefSize bound + seek).

One path DIVERGES and is pinned both-sides: the SDHUFF=1, SDREFAGG=1 *aggregate*
route (naggInst>1 -> a one-strip TextRegion decoded from inside the dictionary)
with two instances overlapping at the aggregate-region edge. pypdfbox places the
second instance at column width-1 (clipped), yielding byte-1 ``0x81``; the
bundled jar yields ``0x80``. Both decoders consume the identical bits and arrive
at the same stream position; the difference is in the byte-shifted blit clipping
at the region edge.

ROOT CAUSE (wave 1504, agent B) — this is a *jar bug fixed upstream*, identical
in shape to the template-1 ``referenceDX < 0`` precedent in
``test_generic_refinement_region_oracle.py``. The aggregate symbol's second
instance lands at a non-byte-aligned column that runs past the region's right
edge, so ``Bitmaps.blit`` takes a shifted-and-clipped path. The bundled 3.0.7
jar's ``org.apache.pdfbox.jbig2.image.Bitmaps`` (verified by ``javap -c`` on the
jar: ``blit`` dispatches *only* to ``blitUnshifted`` / ``blitSpecialShifted`` /
``blitShifted`` — there is **no** ``blitByPixel`` method) carries the pre-fix
shifted-blit arithmetic, which mis-clips and drops the edge pixel (``0x80``). The
standalone ``apache/pdfbox-jbig2`` repo later added the PDFBOX-6156 guard
(Bitmaps.java: "do it the hard way until the other methods are fixed") that
diverts every non-byte-aligned / edge-overhanging blit to a correct per-pixel
``blitByPixel`` fallback. pypdfbox ports the *fixed* upstream, so its ``0x81`` is
the correct value. There is no pypdfbox bug to fix; we follow the corrected
upstream and pin the jar's stale output as a documented divergence. Exotic
SD-aggregate-overlap edge with no known real-world trigger; pinned here so the
reproduction is never lost.
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.jbig2_document import JBIG2Document
from tests.jbig2.helpers.jb2_encoder import (
    assemble,
    huffman_sd_data,
    huffman_sd_refagg_aggregate_data,
    huffman_text_region_data,
    huffman_text_region_refine_data,
    page_info_segment_data,
)
from tests.oracle.harness import requires_oracle, run_probe_text


def _py_symbols(stream: bytes, segment_nr: int) -> str:
    doc = JBIG2Document(ImageInputStream(stream))
    dictionary = (
        doc.get_page(1).get_segment(segment_nr).get_segment_data().get_dictionary()
    )
    parts = [str(len(dictionary))]
    for i, b in enumerate(dictionary):
        parts.append(
            f"{i} {b.get_width()} {b.get_height()} {b.get_row_stride()} "
            f"{bytes(b.get_byte_array()).hex()}"
        )
    return "\n".join(parts)


def _py_page(stream: bytes) -> str:
    doc = JBIG2Document(ImageInputStream(stream))
    bm = doc.get_page(1).get_bitmap()
    return (
        f"{bm.get_width()} {bm.get_height()} {bm.get_row_stride()} "
        f"{bytes(bm.get_byte_array()).hex()}"
    )


@requires_oracle
def test_huffman_symbol_dictionary_matches_pdfbox():
    sd = huffman_sd_data([(8, 10), (12, 10)])
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(64, 16)),
            (1, 0, [], 1, sd),
            (2, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2SymbolDictProbe", stream.hex()).strip()
    assert _py_symbols(stream, 1) == java


@requires_oracle
def test_huffman_text_region_matches_pdfbox():
    sd = huffman_sd_data([(8, 10), (12, 10)])
    tr = huffman_text_region_data(
        64, 16, [(8, 10), (12, 10)], [(0, 0, 0), (1, 20, 0)]
    )
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(64, 16)),
            (1, 0, [], 1, sd),
            (4, 6, [1], 1, tr),
            (5, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2PageProbe", stream.hex()).strip()
    assert _py_page(stream) == java


@requires_oracle
@pytest.mark.parametrize("refine_bytes", [16, 24])
def test_huffman_text_region_refinement_matches_pdfbox(refine_bytes):
    sd = huffman_sd_data([(8, 10)])
    trr = huffman_text_region_refine_data(32, 16, [(8, 10)], refine_bytes)
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(32, 16)),
            (1, 0, [], 1, sd),
            (4, 6, [1], 1, trr),
            (5, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2PageProbe", stream.hex()).strip()
    assert _py_page(stream) == java


@requires_oracle
def test_huffman_sd_refinement_aggregate_diverges_from_pdfbox():
    """Pinned both-sides divergence: aggregate-route symbol byte-1 0x81 vs 0x80.

    pypdfbox and the bundled jar agree on the symbol count and the imported
    symbol but differ on byte-1 of the aggregate symbol decoded through the
    SD-internal one-strip text region (two overlapping instances at the region
    edge). Root cause (module docstring): the bundled 3.0.7 jar's pre-PDFBOX-6156
    shifted-blit mis-clips the edge pixel (``0x80``); pypdfbox ports the fixed
    upstream per-pixel fallback (``0x81``, correct). Asserting the EXACT outputs
    of both sides documents the divergence; if a future change accidentally
    reconciles or worsens it, this test will flag it.
    """
    base = huffman_sd_data([(8, 10)])
    agg = huffman_sd_refagg_aggregate_data(8, 10, 2)
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(64, 16)),
            (1, 0, [], 1, base),
            (2, 0, [1], 1, agg),
            (3, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2SymbolDictByNrProbe", stream.hex(), "2").strip()
    py = _py_symbols(stream, 2)

    # Both decode 2 symbols; the imported symbol matches.
    assert java == (
        "2\n0 8 10 1 80000000000000000001\n1 8 10 1 80000000000000000001"
    )
    assert py == (
        "2\n0 8 10 1 80000000000000000001\n1 8 10 1 81000000000000000001"
    )
    # The aggregate symbol (#1) is where they diverge.
    assert java != py
