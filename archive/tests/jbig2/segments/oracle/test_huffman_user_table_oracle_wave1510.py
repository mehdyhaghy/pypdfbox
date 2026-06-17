"""Live differential oracle for JBIG2 Huffman user-table decode branches.

Wave 1510 (agent B) final coverage audit of
``pypdfbox/jbig2/segments/{text_region,symbol_dictionary}.py``. Waves 1503-1506
broke the Huffman/arithmetic fixture famine with the test-only encoder
(:mod:`tests.jbig2.helpers.jb2_encoder`) but a band of *user-supplied custom
Huffman table* (segment type 53) selection branches — the ``SBHUFF*`` / ``SDHUFF*``
``== 3`` arms with their per-selector ``*_nr`` table-ordinal accumulators, plus the
``_get_user_table`` non-zero ``table_counter`` increment arm — stayed uncovered
because wave 1504 only drove a single-table SBHUFFFS==3 case.

This wave extends the encoder to emit *multiple* referred-to type-53 tables and
build regions that select user tables for several fields at once, so every
remaining user-table branch is exercised and pinned bit-exact vs the bundled
PDFBox 3.0.7 jar (each stream fed identically to the jar via the reflection
probes and to pypdfbox).

Covers:

* ``TextRegion`` SBHUFFFS/DS/DT == 3 user tables (and the ``ds_nr``/``dt_nr``
  accumulators) — :func:`huffman_text_region_multi_user_table_data`.
* ``TextRegion`` SBHUFFRDW/RDH/RDX/RDY == 3 and SBHUFFRSIZE == 1 user tables
  (and the ``rdh_nr``/``rdx_nr``/``rdy_nr``/``r_size_nr`` accumulators) —
  :func:`huffman_text_region_refine_user_table_data`.
* ``SymbolDictionary`` SDHUFFDH/DW == 3 and SDHUFFBMSIZE == 1 user tables
  (and ``_huff_decode_bm_size``) — :func:`huffman_sd_user_table_data`.
* ``TextRegion._get_user_table`` / ``SymbolDictionary._get_user_table`` non-zero
  ``table_counter`` increment arm — exercised by every multi-table stream above.
"""

from __future__ import annotations

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.jbig2_document import JBIG2Document
from tests.jbig2.helpers.jb2_encoder import (
    assemble,
    huffman_sd_alt_standard_table_data,
    huffman_sd_data,
    huffman_sd_user_table_data,
    huffman_text_region_data,
    huffman_text_region_multi_user_table_data,
    huffman_text_region_refine_user_table_data,
    page_info_segment_data,
    table_segment_data,
    wide_table_segment_data,
)
from tests.oracle.harness import requires_oracle, run_probe_text


def _py_page(stream: bytes) -> str:
    doc = JBIG2Document(ImageInputStream(stream))
    bm = doc.get_page(1).get_bitmap()
    return (
        f"{bm.get_width()} {bm.get_height()} {bm.get_row_stride()} "
        f"{bytes(bm.get_byte_array()).hex()}"
    )


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


@requires_oracle
def test_text_region_multi_user_table_matches_pdfbox():
    """SBHUFFFS/DS/DT all == 3, two instances, three referred type-53 tables."""
    sd = huffman_sd_data([(8, 10)])
    tab = table_segment_data()
    tr = huffman_text_region_multi_user_table_data(32, 16, [(8, 10)])
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(32, 16)),
            (1, 0, [], 1, sd),
            (2, 53, [], 1, tab),  # FS table (table 0)
            (3, 53, [], 1, tab),  # DS table (table 1)
            (4, 53, [], 1, tab),  # DT table (table 2)
            (5, 6, [1, 2, 3, 4], 1, tr),
            (6, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2PageProbe", stream.hex()).strip()
    py = _py_page(stream)
    assert py == java
    # Golden pin: two instances of symbol 0 at S==0 and S==7.
    assert py == (
        "32 16 4 8100000000000000000000000000000000000000000000000000000000000000"
        "0000000001020000000000000000000000000000000000000000000000000000"
    )


@requires_oracle
def test_text_region_refine_user_table_matches_pdfbox():
    """Every selector (FS/DS/DT/RDW/RDH/RDX/RDY == 3, RSIZE == 1) a user table.

    Eight referred type-53 tables drive every user-table branch and every
    per-selector ``*_nr`` ordinal accumulator in the refinement decode.
    """
    refine_bytes = 16
    sd = huffman_sd_data([(8, 10)])
    tab = table_segment_data()
    wide, _range_len = wide_table_segment_data(256)
    tr, _ = huffman_text_region_refine_user_table_data(32, 16, [(8, 10)], refine_bytes)
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(32, 16)),
            (1, 0, [], 1, sd),
            (2, 53, [], 1, tab),  # FS table (table 0)
            (3, 53, [], 1, tab),  # DS table (table 1)
            (4, 53, [], 1, tab),  # DT table (table 2)
            (5, 53, [], 1, tab),  # RDW table (table 3)
            (6, 53, [], 1, tab),  # RDH table (table 4)
            (7, 53, [], 1, tab),  # RDX table (table 5)
            (8, 53, [], 1, tab),  # RDY table (table 6)
            (9, 53, [], 1, wide),  # RSIZE table (table 7)
            (10, 6, [1, 2, 3, 4, 5, 6, 7, 8, 9], 1, tr),  # immediate text region
            (11, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2PageProbe", stream.hex()).strip()
    py = _py_page(stream)
    assert py == java
    # Golden pin: RDW/RDH/RDX/RDY == 0 refines symbol 0 against a refinement
    # bitmap decoded from the 16-byte (zeroed) refinement-region payload.
    assert py == (
        "32 16 4 68000000fe000000d20000002c000000a00000001b00000051000000d00000"
        "00a7000000fb000000000000000000000000000000000000000000000000000000"
    )


@requires_oracle
def test_symbol_dictionary_user_table_matches_pdfbox():
    """SDHUFFDH/DW == 3 + SDHUFFBMSIZE == 1; three referred wide tables."""
    wide, _range_len = wide_table_segment_data(256)
    sd = huffman_sd_user_table_data([(8, 10)], _range_len)
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(32, 16)),
            (1, 53, [], 1, wide),  # DH table (table 0)
            (2, 53, [], 1, wide),  # DW table (table 1)
            (3, 53, [], 1, wide),  # BMSIZE table (table 2)
            (4, 0, [1, 2, 3], 1, sd),
            (5, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2SymbolDictByNrProbe", stream.hex(), "4").strip()
    py = _py_symbols(stream, 4)
    assert py == java
    # Golden pin: one 8x10 symbol, top-left + bottom-right pixels set.
    assert py == "1\n0 8 10 1 80000000000000000001"


@requires_oracle
def test_symbol_dictionary_alt_standard_tables_matches_pdfbox():
    """SDHUFFDH==1 (B5) and SDHUFFDW==1 (B3) alternate standard tables."""
    sd = huffman_sd_alt_standard_table_data([(8, 10)])
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(32, 16)),
            (1, 0, [], 1, sd),
            (2, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2SymbolDictByNrProbe", stream.hex(), "1").strip()
    py = _py_symbols(stream, 1)
    assert py == java
    assert py == "1\n0 8 10 1 80000000000000000001"


@requires_oracle
def test_text_region_default_pixel_matches_pdfbox():
    """SBDEFPIXEL==1 pre-fills the region bitmap with 1s before compositing."""
    sd = huffman_sd_data([(8, 10)])
    tr = huffman_text_region_data(32, 16, [(8, 10)], [(0, 0, 0)], default_pixel=1)
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(32, 16)),
            (1, 0, [], 1, sd),
            (2, 6, [1], 1, tr),
            (3, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2PageProbe", stream.hex()).strip()
    py = _py_page(stream)
    assert py == java
    # Golden pin: the whole region pre-filled with 1s (OR-blit of the symbol is
    # invisible against the all-ones default).
    assert py == "32 16 4 " + "ff" * 64
