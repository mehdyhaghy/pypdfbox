"""Live differential oracle for the JBIG2 arithmetic (SDHUFF=0) decode path.

Waves 1503-1504 (agents C/B) broke the JBIG2 fixture famine with a test-only
*Huffman* encoder. The arithmetic (SDHUFF=0) symbol-dictionary bodies stayed
fixture-starved because no MQ-arithmetic *encoder* existed (Apache PDFBox only
decodes). Wave 1505 (agent B) adds one — :mod:`tests.jbig2.helpers.mq_encoder`,
a faithful inverse of the production ``ArithmeticDecoder`` /
``ArithmeticIntegerDecoder`` (round-trip-pinned in
``tests/jbig2/helpers/test_mq_encoder.py``) — and a template-0 generic-region
bitmap encoder. :func:`jb2_encoder.arithmetic_sd_data` assembles those into a
complete SDHUFF=0, SDREFAGG=0 symbol dictionary.

Each stream is fed IDENTICALLY to the bundled PDFBox 3.0.7 jar (via the
``Jbig2SymbolDictByNrProbe`` reflection probe) and to pypdfbox; the assertions
are exact-output golden pins so a regression on either side trips the test.
"""

from __future__ import annotations

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.jbig2_document import JBIG2Document
from tests.jbig2.helpers.jb2_encoder import (
    _encode_arithmetic_sd_body,
    _new_cx,
    arithmetic_sd_data,
    arithmetic_sd_header,
    assemble,
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


def _checkerboard(width: int, height: int) -> list[list[int]]:
    return [[(x + y) & 1 for x in range(width)] for y in range(height)]


def _corner(width: int, height: int) -> list[list[int]]:
    rows = [[0] * width for _ in range(height)]
    rows[0][0] = 1
    rows[height - 1][width - 1] = 1
    return rows


@requires_oracle
def test_arithmetic_sd_single_symbol_matches_pdfbox():
    rows = _corner(8, 8)
    sd = arithmetic_sd_data([(8, 8, rows)])
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
    # Golden pin: a single 8x8 symbol with the two corner pixels set.
    assert py == "1\n0 8 8 1 8000000000000001"


@requires_oracle
def test_arithmetic_sd_multi_symbol_same_height_matches_pdfbox():
    syms = [
        (8, 8, _corner(8, 8)),
        (12, 8, _checkerboard(12, 8)),
        (5, 8, _corner(5, 8)),
    ]
    sd = arithmetic_sd_data(syms)
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(64, 16)),
            (1, 0, [], 1, sd),
            (2, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2SymbolDictByNrProbe", stream.hex(), "1").strip()
    py = _py_symbols(stream, 1)
    assert py == java


@requires_oracle
def test_arithmetic_sd_import_chain_matches_pdfbox():
    """A second arithmetic SD imports a base SD's symbols and re-exports all.

    Exercises ``SymbolDictionary._retrieve_import_symbols`` /
    ``amount_of_imported_symbols`` and the IAEX export-flag run over a mix of
    imported and new symbols on the arithmetic (SDHUFF=0) path — the import arc
    that the wave-1504 Huffman builder only reached for SDHUFF=1.
    """
    base_data = arithmetic_sd_data([(8, 8, _corner(8, 8)), (8, 8, _checkerboard(8, 8))])
    # Second SD: fresh CX, imports 2, adds 2 new, exports all 4.
    header = arithmetic_sd_header(4, 2, retain_context=False, use_context=False)
    body, _ = _encode_arithmetic_sd_body(
        [(8, 8, _checkerboard(8, 8)), (8, 8, _corner(8, 8))],
        _new_cx(65536, 1),
        amount_imported=2,
    )
    reuse_data = header + body
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(64, 32)),
            (1, 0, [], 1, base_data),
            (2, 0, [1], 1, reuse_data),
            (3, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2SymbolDictByNrProbe", stream.hex(), "2").strip()
    py = _py_symbols(stream, 2)
    assert py == java
    # Golden pin: 2 imported (corner, checkerboard) + 2 new (checkerboard, corner).
    assert py == (
        "4\n"
        "0 8 8 1 8000000000000001\n"
        "1 8 8 1 55aa55aa55aa55aa\n"
        "2 8 8 1 55aa55aa55aa55aa\n"
        "3 8 8 1 8000000000000001"
    )


@requires_oracle
def test_arithmetic_sd_multi_height_classes_matches_pdfbox():
    syms = [
        (8, 6, _checkerboard(8, 6)),
        (8, 10, _corner(8, 10)),
        (6, 6, _corner(6, 6)),
        (10, 10, _checkerboard(10, 10)),
    ]
    sd = arithmetic_sd_data(syms)
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(64, 32)),
            (1, 0, [], 1, sd),
            (2, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2SymbolDictByNrProbe", stream.hex(), "1").strip()
    py = _py_symbols(stream, 1)
    assert py == java
