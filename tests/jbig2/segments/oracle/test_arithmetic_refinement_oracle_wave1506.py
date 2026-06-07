"""Live differential oracle for the JBIG2 arithmetic refinement/aggregation and
coding-context-reuse symbol-dictionary paths.

Wave 1505 (agent B) added the MQ-arithmetic encoder
(:mod:`tests.jbig2.helpers.mq_encoder`) and pinned the plain SDHUFF=0 arithmetic
dictionary + the arithmetic import-chain bit-exact vs the bundled jar. Three arcs
stayed open (DEFERRED.md):

* the coding-context-reuse arc (SDCONTEXTUSED=1, adopt a referred-to SD's
  retained bitmap CX) — blocked by a production weakref bug;
* the SDHUFF=0, SDREFAGG=1 single-instance refinement
  (``_decode_refined_symbol`` -> IAID/IARDX/IARDY + GenericRefinementRegion);
* the SDHUFF=0, SDREFAGG=1 ``n_inst > 1`` aggregate route
  (``_decode_through_text_region``).

Wave 1506 (agent A) closes all three. The weakref bug
(``SegmentHeader._segment_data`` held the decoded segment data by ``weakref``,
which Python drops the instant no strong reference survives — far more aggressive
than upstream's ``SoftReference``, so a retained coding context could be GC'd
mid-decode) is fixed by holding a strong reference, mirroring the practical
``SoftReference`` lifetime. The MQ encoder is extended with a template-1
refinement-region encoder (``encode_refinement_region_template1``) so the
refinement + aggregate bodies can be built and fed identically to the jar and
pypdfbox.

Two arcs are bit-exact vs the jar (single-instance refinement; aggregate route
with in-bounds placements). The coding-context-reuse arc is golden-pinned on the
pypdfbox side only: the bundled 3.0.7 jar CANNOT decode it through ANY access
shape — both the cold by-number probe and a base-first-then-target probe fault
with ``ArrayIndexOutOfBoundsException`` in ``getToExportFlags`` (the jar
mis-decodes the export-flag run lengths under the context-adoption arc; the
export-bounds guard upstream added is absent from the bundled jar). pypdfbox
decodes it correctly (imported + new symbols bit-exact), so we pin pypdfbox's
output and document the jar fault both-sides, same precedent as the SDHUFF=1
aggregate edge-clip divergence in ``test_huffman_refinement_oracle_wave1503.py``.
"""

from __future__ import annotations

from subprocess import CalledProcessError

import pytest

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.jbig2_document import JBIG2Document
from tests.jbig2.helpers.jb2_encoder import (
    _encode_arithmetic_sd_body,
    _new_cx,
    arithmetic_sd_data,
    arithmetic_sd_header,
    arithmetic_sd_refagg_aggregate_data,
    arithmetic_sd_refagg_single_data,
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


def _corner(width: int, height: int) -> list[list[int]]:
    rows = [[0] * width for _ in range(height)]
    rows[0][0] = 1
    rows[height - 1][width - 1] = 1
    return rows


def _checkerboard(width: int, height: int) -> list[list[int]]:
    return [[(x + y) & 1 for x in range(width)] for y in range(height)]


# ---------------------------------------------------------------------------
# Single-instance refinement (SDHUFF=0, SDREFAGG=1, IAAI == 1)
# ---------------------------------------------------------------------------


@requires_oracle
def test_arithmetic_refagg_single_identity_matches_pdfbox():
    """A refinement SD refines an imported symbol with RDX=RDY=0 and an
    identical target -> reproduces the reference bitmap. Exercises the arithmetic
    ``_decode_refined_symbol`` (IAID/IARDX/IARDY) + GenericRefinementRegion
    template-1 path."""
    base = [(8, 8, _corner(8, 8))]
    base_data = arithmetic_sd_data(base)
    ref_data = arithmetic_sd_refagg_single_data(
        8, 8, _corner(8, 8), 0, base, imported_count=1, rdx=0, rdy=0
    )
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(32, 16)),
            (1, 0, [], 1, base_data),
            (2, 0, [1], 1, ref_data),
            (3, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2SymbolDictByNrProbe", stream.hex(), "2").strip()
    py = _py_symbols(stream, 2)
    assert py == java
    # Golden pin: 1 imported corner + 1 refined corner (identical).
    assert py == (
        "2\n"
        "0 8 8 1 8000000000000001\n"
        "1 8 8 1 8000000000000001"
    )


@requires_oracle
def test_arithmetic_refagg_single_changed_target_matches_pdfbox():
    """The refined symbol differs from its reference (corner -> checkerboard):
    the refinement-region arithmetic codes the per-pixel delta over the
    reference, decoded bit-exact by both decoders."""
    base = [(8, 8, _corner(8, 8))]
    base_data = arithmetic_sd_data(base)
    ref_data = arithmetic_sd_refagg_single_data(
        8, 8, _checkerboard(8, 8), 0, base, imported_count=1, rdx=0, rdy=0
    )
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(32, 16)),
            (1, 0, [], 1, base_data),
            (2, 0, [1], 1, ref_data),
            (3, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2SymbolDictByNrProbe", stream.hex(), "2").strip()
    py = _py_symbols(stream, 2)
    assert py == java
    assert py == (
        "2\n"
        "0 8 8 1 8000000000000001\n"
        "1 8 8 1 55aa55aa55aa55aa"
    )


# ---------------------------------------------------------------------------
# Aggregate route (SDHUFF=0, SDREFAGG=1, IAAI > 1 -> one-strip TextRegion)
# ---------------------------------------------------------------------------


@requires_oracle
def test_arithmetic_refagg_aggregate_matches_pdfbox():
    """The single new symbol is composed by a one-strip arithmetic TextRegion
    placing the imported symbol twice (in-bounds, no edge clipping). Exercises
    ``_decode_through_text_region`` + the SD-internal TextRegion arithmetic
    instance placement (IADT/IAFS/IADS/IAID/IARI)."""
    base = [(3, 8, _corner(3, 8))]
    base_data = arithmetic_sd_data(base)
    placements = [(0, 0, 0), (0, 8, 0)]
    agg_data = arithmetic_sd_refagg_aggregate_data(
        16, 8, placements, base, imported_count=1
    )
    stream = assemble(
        [
            (0, 48, [], 1, page_info_segment_data(64, 16)),
            (1, 0, [], 1, base_data),
            (2, 0, [1], 1, agg_data),
            (3, 49, [], 1, b""),
        ]
    )
    java = run_probe_text("Jbig2SymbolDictByNrProbe", stream.hex(), "2").strip()
    py = _py_symbols(stream, 2)
    assert py == java
    # Golden pin: 1 imported 3x8 corner + 1 new 16x8 aggregate (corner placed at
    # x=0 and x=8).
    assert py == (
        "2\n"
        "0 3 8 1 8000000000000020\n"
        "1 16 8 2 80800000000000000000000000002020"
    )


# ---------------------------------------------------------------------------
# Coding-context-reuse arc (SDHUFF=0, SDCONTEXTUSED=1) — jar faults both-sides
# ---------------------------------------------------------------------------


def _context_reuse_stream() -> bytes:
    """Two arithmetic SDs: base #1 retains its bitmap CX, #2 adopts it.

    #2 sets SDCONTEXTUSED, refers to #1, imports its 2 symbols and adds 2 new
    ones whose bitmaps are arithmetic-coded continuing from a copy of #1's
    trained bitmap context (mirroring ``adoptRetainedCodingContexts`` ->
    ``cx = base.cx.copy()``).
    """
    base_syms = [(8, 8, _corner(8, 8)), (8, 8, _checkerboard(8, 8))]
    base_header = arithmetic_sd_header(2, 2, retain_context=True, use_context=False)
    base_cx = _new_cx(65536, 1)
    base_body, _ = _encode_arithmetic_sd_body(base_syms, base_cx)
    base_data = base_header + base_body

    header2 = arithmetic_sd_header(4, 2, retain_context=False, use_context=True)
    adopted = base_cx.copy()
    body2, _ = _encode_arithmetic_sd_body(
        [(8, 8, _checkerboard(8, 8)), (8, 8, _corner(8, 8))],
        adopted,
        amount_imported=2,
    )
    reuse_data = header2 + body2

    return assemble(
        [
            (0, 48, [], 1, page_info_segment_data(64, 32)),
            (1, 0, [], 1, base_data),
            (2, 0, [1], 1, reuse_data),
            (3, 49, [], 1, b""),
        ]
    )


def test_arithmetic_context_reuse_decodes_in_pypdfbox():
    """pypdfbox decodes the context-reuse SD bit-exact (regression pin for the
    SegmentHeader strong-reference fix)."""
    stream = _context_reuse_stream()
    py = _py_symbols(stream, 2)
    # 2 imported (corner, checkerboard) + 2 new (checkerboard, corner).
    assert py == (
        "4\n"
        "0 8 8 1 8000000000000001\n"
        "1 8 8 1 55aa55aa55aa55aa\n"
        "2 8 8 1 55aa55aa55aa55aa\n"
        "3 8 8 1 8000000000000001"
    )


@requires_oracle
def test_arithmetic_context_reuse_jar_faults_by_number():
    """The bundled 3.0.7 jar cannot decode the context-reuse SD cold by-number:
    it throws ArrayIndexOutOfBoundsException in getToExportFlags (mis-decoded
    export-run lengths under context adoption). Pinned both-sides so the jar
    fault is documented and the divergence reproduction is never lost."""
    stream = _context_reuse_stream()
    with pytest.raises(CalledProcessError) as exc:
        run_probe_text("Jbig2SymbolDictByNrProbe", stream.hex(), "2")
    stderr = (exc.value.stderr or b"").decode("utf-8", "replace")
    assert "getToExportFlags" in stderr or "ArrayIndexOutOfBounds" in stderr


@requires_oracle
def test_arithmetic_context_reuse_jar_faults_base_first():
    """Even with the base SD decoded first (its retained CX trained) the jar
    still faults identically — the context-reuse arc is undecodable by the
    bundled jar through any access shape, so pypdfbox's correct output is
    golden-pinned (test_arithmetic_context_reuse_decodes_in_pypdfbox)."""
    stream = _context_reuse_stream()
    with pytest.raises(CalledProcessError) as exc:
        run_probe_text("Jbig2SymbolDictReuseProbe", stream.hex(), "2")
    stderr = (exc.value.stderr or b"").decode("utf-8", "replace")
    assert "getToExportFlags" in stderr or "ArrayIndexOutOfBounds" in stderr
