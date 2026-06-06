"""Hand-written pins for the Huffman + refinement/aggregation JBIG2 paths.

These cover the long-fixture-starved Huffman symbol-dictionary, Huffman
text-region and refinement decode bodies (DEFERRED.md). The streams are built
by :mod:`tests.jbig2.helpers.jb2_encoder` (a test-only minimal JBIG2 encoder)
and were verified bit-exact against the bundled PDFBox 3.0.7 jar — see
``tests/jbig2/segments/oracle/test_huffman_refinement_oracle_wave1503.py`` for
the live differential checks. Here we pin pypdfbox's decoded output as frozen
golden bytes so the paths stay exercised even when the Java oracle is absent.
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


def _symbols_repr(dictionary) -> str:
    parts = [str(len(dictionary))]
    for i, b in enumerate(dictionary):
        parts.append(
            f"{i} {b.get_width()} {b.get_height()} {b.get_row_stride()} "
            f"{bytes(b.get_byte_array()).hex()}"
        )
    return " ; ".join(parts)


def _bitmap_repr(bm) -> str:
    return (
        f"{bm.get_width()} {bm.get_height()} {bm.get_row_stride()} "
        f"{bytes(bm.get_byte_array()).hex()}"
    )


def test_huffman_symbol_dictionary_decodes():
    """SDHUFF=1, SDREFAGG=0: height-class collective bitmap + export flags."""
    sd = huffman_sd_data([(8, 10), (12, 10)])
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(64, 16)),
            (1, 0, [], 1, sd),
            (2, 49, [], 1, b""),
        ]
    )
    doc = JBIG2Document(ImageInputStream(stream))
    dictionary = doc.get_page(1).get_segment(1).get_segment_data().get_dictionary()
    assert _symbols_repr(dictionary) == (
        "2 ; 0 8 10 1 80000000000000000001 ; "
        "1 12 10 2 8000000000000000000000000000000000000010"
    )


def test_huffman_text_region_decodes():
    """SBHUFF=1, REFINE=0: symbol-ID run-code table + strip placement."""
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
    doc = JBIG2Document(ImageInputStream(stream))
    bm = doc.get_page(1).get_bitmap()
    assert bm.get_width() == 64
    assert bm.get_height() == 16
    # Symbol 0's top-left pixel at page col 0, symbol 1's at page col 20.
    rep = _bitmap_repr(bm)
    assert rep.startswith("64 16 8 80")
    # symbol 1 marker (col 20 -> byte 2, bit 4 -> 0x08) on row 0.
    assert rep.split()[3][4:6] == "08"


def test_huffman_text_region_refinement_decodes():
    """SBHUFF=1, REFINE=1: one refined instance (RDW/RDH/RDX/RDY=0)."""
    sd = huffman_sd_data([(8, 10)])
    trr = huffman_text_region_refine_data(32, 16, [(8, 10)], 16)
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(32, 16)),
            (1, 0, [], 1, sd),
            (4, 6, [1], 1, trr),
            (5, 49, [], 1, b""),
        ]
    )
    doc = JBIG2Document(ImageInputStream(stream))
    bm = doc.get_page(1).get_bitmap()
    assert bm.get_width() == 32
    assert bm.get_height() == 16
    # The refinement region decoded a 8x10 bitmap from 16 zero arithmetic bytes;
    # frozen golden output (matches the bundled jar, see the oracle test).
    assert _bitmap_repr(bm) == (
        "32 16 4 "
        "68000000fe000000d20000002c000000a00000001b00000051000000d0000000a7000000"
        "fb000000000000000000000000000000000000000000000000000000"
    )


def test_huffman_sd_refinement_aggregate_decodes():
    """SDHUFF=1, SDREFAGG=1 aggregate route (naggInst>1 -> one-strip TextRegion).

    Exercises SymbolDictionary._decode_aggregate -> _decode_through_text_region
    and a Huffman TextRegion driven entirely from inside the dictionary. The
    decoded byte-1 of the aggregate symbol DIVERGES from the bundled PDFBox jar
    (pypdfbox 0x81 vs jar 0x80 for two overlapping instances at the region
    edge); the divergence is pinned both-sides in the oracle test. Here we pin
    pypdfbox's (spec-consistent) output.
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
    doc = JBIG2Document(ImageInputStream(stream))
    dictionary = doc.get_page(1).get_segment(2).get_segment_data().get_dictionary()
    assert _symbols_repr(dictionary) == (
        "2 ; 0 8 10 1 80000000000000000001 ; "
        "1 8 10 1 81000000000000000001"
    )


@pytest.mark.parametrize("refine_bytes", [16, 24])
def test_huffman_text_region_refinement_byte_counts(refine_bytes):
    """The refinement decode is stable for symInRefSize >= the bytes consumed."""
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
    doc = JBIG2Document(ImageInputStream(stream))
    bm = doc.get_page(1).get_bitmap()
    assert bm.get_width() == 32
    assert _bitmap_repr(bm).startswith("32 16 4 68000000fe")
