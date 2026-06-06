"""Live differential oracle for JBIG2 Huffman segment-graph decode paths.

Wave 1503 (agent C) broke the fixture famine with a test-only minimal JBIG2
encoder (:mod:`tests.jbig2.helpers.jb2_encoder`) and pinned the SDHUFF/SBHUFF
collective-bitmap, text-region and refinement bodies bit-exact vs the bundled
PDFBox 3.0.7 jar. Two referred-to-segment arcs stayed fixture-starved; wave 1504
(agent B) extends the encoder to reach them and pins each bit-exact vs the jar:

* **Import-symbols across SD segments** — a base symbol dictionary exporting two
  symbols, then a second SD that refers to it, imports both, adds one new
  directly-coded symbol and re-exports all three. Exercises
  ``SymbolDictionary._retrieve_import_symbols`` /
  ``amount_of_imported_symbols`` and the export-flag run over a mix of imported
  and new symbols.
* **User-supplied custom Huffman table (segment type 53)** — a text region with
  ``SBHUFFFS == 3`` that reads the first-S coordinate from a referred-to
  type-53 code-table segment. Exercises ``TextRegion._get_user_table`` /
  ``fs_table`` and the ``EncodedTable`` / ``Table`` segment parse.

Both streams are built by the encoder and fed IDENTICALLY to the bundled jar
(via the reflection probes) and pypdfbox; the assertions are exact-output golden
pins so an accidental regression on either side trips the test.
"""

from __future__ import annotations

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.jbig2_document import JBIG2Document
from tests.jbig2.helpers.jb2_encoder import (
    assemble,
    huffman_sd_data,
    huffman_sd_import_chain_data,
    huffman_text_region_user_fs_data,
    page_info_segment_data,
    table_segment_data,
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
def test_huffman_sd_import_chain_matches_pdfbox():
    """A second SD imports two symbols from a base SD and re-exports all three."""
    base = huffman_sd_data([(8, 10), (12, 10)])
    chain = huffman_sd_import_chain_data((16, 10), 2)
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(64, 16)),
            (1, 0, [], 1, base),
            (2, 0, [1], 1, chain),
            (3, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2SymbolDictByNrProbe", stream.hex(), "2").strip()
    py = _py_symbols(stream, 2)
    assert py == java
    # Golden pin: two imported symbols + one new, all re-exported.
    assert py == (
        "3\n"
        "0 8 10 1 80000000000000000001\n"
        "1 12 10 2 8000000000000000000000000000000000000010\n"
        "2 16 10 2 8000000000000000000000000000000000000001"
    )


@requires_oracle
def test_huffman_text_region_user_table_matches_pdfbox():
    """SBHUFFFS==3 reads the first-S coordinate from a type-53 user table."""
    sd = huffman_sd_data([(8, 10)])
    tab = table_segment_data()
    tr = huffman_text_region_user_fs_data(32, 16, [(8, 10)])
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(32, 16)),
            (1, 0, [], 1, sd),
            (2, 53, [], 1, tab),
            (4, 6, [1, 2], 1, tr),
            (5, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2PageProbe", stream.hex()).strip()
    py = _py_page(stream)
    assert py == java
    # Golden pin: symbol 0 placed at S==0 (top-left pixel of a 32x16 page).
    assert py == (
        "32 16 4 8000000000000000000000000000000000000000000000000000000000000000"
        "0000000001000000000000000000000000000000000000000000000000000000"
    )
