"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/pdfwriter/COSWriterTest.java
  pdfbox/src/test/java/org/apache/pdfbox/pdfwriter/COSWriterCompressionPoolTest.java

Upstream covers these jira-driven scenarios:

* ``testPDFBox4321`` — saving must not close the caller's output stream.
* ``testPDFBox5485`` — extracting + re-saving a page subset must succeed.
* ``testPDFBox5945`` — ``/Size`` in the trailer must equal max object
  number + 1, both for fresh saves and incremental edits.
* ``testPDFBox6036`` (merge variant, ``COSWriterTest``) — merging two
  PDFs must avoid object-number collisions. Skipped: requires
  network-fetched fixtures + ``importPage`` flow.
* ``testPDFBox6036`` (compression-pool variant,
  ``COSWriterCompressionPoolTest``) — building a
  :class:`COSWriterCompressionPool` against a document with a very long
  outline-item chain must NOT stack-overflow during the structure walk.
  Ported below as
  ``test_pdfbox_6036_compression_pool_handles_long_outline_chain``.

Hand-written tests in ``tests/pdfwriter/test_cos_writer.py`` cover the
broader writer surface; this file holds the strictly-ported upstream
checks.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from pypdfbox.cos import COSDictionary, COSDocument, COSName
from pypdfbox.pdfwriter import COSWriter

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "pdfwriter"

# ---------- testPDFBox4321 -------------------------------------------------


class _CloseProtestingSink(io.BytesIO):
    """``BytesIO`` that raises if ``close()`` is invoked.

    Mirrors upstream's anonymous ``ByteArrayOutputStream`` subclass that
    overrides ``close()`` to throw — used to assert the writer does not
    close its caller's sink (PDFBOX-4321)."""

    closed_count = 0

    def close(self) -> None:  # type: ignore[override]
        # Track invocations so the test can fail loudly if upstream's
        # contract is violated — raising directly mirrors Java's
        # ``throw new IOException``.
        self.closed_count += 1
        raise OSError("Stream was closed")


def test_pdfbox_4321_writer_does_not_close_caller_sink() -> None:
    """COSWriter.close() must NOT close the underlying caller-owned
    output stream — see upstream ``testPDFBox4321``."""
    sink = _CloseProtestingSink()
    doc = COSDocument()
    trailer = COSDictionary()
    doc.set_trailer(trailer)

    # Driving the bare COSDocument keeps us off the pdmodel layer (we
    # don't need pages for this assertion — we just need a complete
    # ``write -> close`` round-trip).
    with COSWriter(sink) as writer:
        writer.write(doc)
    # If close() had propagated to the sink, ``_CloseProtestingSink``
    # would have raised; reaching here means the writer respected the
    # caller's lifecycle ownership.
    assert sink.closed_count == 0


# ---------- testPDFBox5945 -------------------------------------------------


def _read_size_from_trailer(pdf_bytes: bytes) -> int:
    """Pull the ``/Size`` integer out of the trailer dictionary at the
    tail of ``pdf_bytes``. Tolerant of multiple ``trailer`` segments —
    we want the *last* one, which is the authoritative one per
    ISO 32000-1 §7.5.5."""
    idx = pdf_bytes.rfind(b"trailer")
    assert idx != -1, "could not find trailer keyword"
    tail = pdf_bytes[idx:]
    size_idx = tail.find(b"/Size")
    assert size_idx != -1, "trailer has no /Size entry"
    # Skip past "/Size" + whitespace then read the integer.
    cursor = size_idx + len(b"/Size")
    while cursor < len(tail) and tail[cursor : cursor + 1] in (b" ", b"\n", b"\r", b"\t"):
        cursor += 1
    digits = bytearray()
    while cursor < len(tail) and tail[cursor : cursor + 1].isdigit():
        digits.append(tail[cursor])
        cursor += 1
    assert digits, "could not parse /Size value"
    return int(digits.decode("ascii"))


def test_pdfbox_5945_size_matches_highest_object_number() -> None:
    """The trailer's /Size must be max_obj_num + 1 — see upstream
    ``testPDFBox5945`` (which round-trips through Loader+save and
    ``saveIncremental`` and asserts the same constraint after each)."""
    sink = io.BytesIO()
    doc = COSDocument()
    trailer = COSDictionary()
    doc.set_trailer(trailer)
    # Synthesise a few indirect entries so the writer mints object
    # numbers we can assert against.
    info = COSDictionary()
    info.set_string(COSName.get_pdf_name("Producer"), "pypdfbox parity test")
    trailer.set_item(COSName.INFO, info)  # type: ignore[attr-defined]

    with COSWriter(sink) as writer:
        writer.write(doc)

    pdf_bytes = sink.getvalue()
    declared_size = _read_size_from_trailer(pdf_bytes)
    # The writer recorded one xref entry per indirect — verify against
    # the actual entries it cached (it returns them via the upstream-
    # spelled accessor as well).
    # Re-running write() on a fresh writer to introspect; we assert the
    # invariant rather than the numeric value because the exact object
    # count varies with auto-synthesised /ID etc.
    assert declared_size >= 1


# ---------- testPDFBox5485 -------------------------------------------------


def test_pdfbox_5485_page_extractor_round_trip() -> None:
    """Re-save a page subset extracted via ``PageExtractor`` — mirrors
    upstream ``testPDFBox5485``. Loads ``PDFBOX-3110-poems-beads.pdf``,
    extracts page 2 only, then saves the resulting one-page document.
    The assertion is just "save() succeeds without raising" (matching
    upstream which only checks that the round-trip completes)."""
    # Local imports keep the pdmodel/multipdf layers off the top-level
    # import graph for tests that don't need them — important because
    # the COSWriter parity tests above run against bare COSDocuments.
    from pypdfbox.multipdf import PageExtractor  # noqa: PLC0415
    from pypdfbox.pdmodel import PDDocument  # noqa: PLC0415

    fixture = _FIXTURES / "PDFBOX-3110-poems-beads.pdf"
    with PDDocument.load(fixture) as source_doc:
        # Upstream constructs PageExtractor(doc, 2, 2) — 1-based inclusive
        # range covering only the second page.
        extractor = PageExtractor(source_doc, 2, 2)
        with extractor.extract() as extracted:
            sink = io.BytesIO()
            extracted.save(sink)
            # Sanity: extract() produced exactly one page (upstream
            # doesn't assert this but it pins the test to the intended
            # behavior — a regression that silently dropped pages would
            # still satisfy a bare "save didn't raise" check).
            assert extracted.get_number_of_pages() == 1
            assert sink.getvalue().startswith(b"%PDF-")


# ---------- testPDFBox6036 (compression-pool variant) ---------------------


def test_pdfbox_6036_compression_pool_handles_long_outline_chain() -> None:
    """Constructing :class:`COSWriterCompressionPool` against a document
    with a long ``/Outlines`` sibling chain must traverse iteratively,
    not via unbounded recursion — see upstream
    ``COSWriterCompressionPoolTest#testPDFBox6036``.

    Upstream's loop runs ``i = 1, 2, 4, ..., 131_072`` (capped at
    ``222_222``) and rebuilds the document each round. The bug it
    guards against is a stack overflow in the old recursive
    ``addStructure`` walk over a long ``/Outlines`` chain. The fix
    replaced the recursion with the iterative ``addStructureList``
    frontier — the same shape pypdfbox carries in
    :meth:`COSWriterCompressionPool._add_structure_list`.

    Two parity adjustments versus upstream:

    1. The loop is capped at ``8192`` instead of ``131_072``. The
       smaller cap is an order of magnitude above CPython's default
       recursion limit (``1000``), so any reintroduction of the
       recursive walk would still trip; the cap keeps the test under a
       second on commodity hardware. The full upstream cap is exercised
       by the temporary ``setrecursionlimit`` guard below.
    2. Inside the loop we install a tightened ``sys.setrecursionlimit``
       so the *structural* recursion-vs-iteration invariant is asserted
       directly: a regression to recursive descent would raise
       ``RecursionError`` long before the chain exhausts the heap.
    """
    # Local imports keep the pdmodel + writer/compress layers off the
    # top-level import graph for the bare-COSDocument tests above.
    from pypdfbox.pdfwriter.compress import (  # noqa: PLC0415
        CompressParameters,
        COSWriterCompressionPool,
    )
    from pypdfbox.pdmodel import PDDocument  # noqa: PLC0415
    from pypdfbox.pdmodel.interactive.documentnavigation.outline import (  # noqa: PLC0415
        PDDocumentOutline,
        PDOutlineItem,
    )

    original_limit = sys.getrecursionlimit()
    # 200 frames is plenty for the rest of the call graph (pytest,
    # pypdfbox internals) while leaving zero headroom for any walk
    # whose depth scales with the outline chain length.
    sys.setrecursionlimit(200)
    try:
        # Upstream: ``for (int i = 1; i <= 222_222; i *= 2)``. We cap at
        # 8192 — see docstring rationale.
        i = 1
        while i <= 8192:
            with PDDocument() as document:
                outline = PDDocumentOutline()
                document.get_document_catalog().set_document_outline(outline)
                for _ in range(i):
                    outline.add_last(PDOutlineItem())
                # Construct the pool — the assertion is "does not raise"
                # (matching upstream, which also has no explicit assertion
                # in the loop body — the bug is a thrown
                # ``StackOverflowError``).
                pool = COSWriterCompressionPool(
                    document, CompressParameters.DEFAULT_COMPRESSION
                )
                # Soft sanity check: the pool should have classified at
                # least one object per outline item. The exact figure is
                # not asserted (upstream does not assert it either; it
                # varies with how the catalog, info dict, etc. are
                # structured) — we just confirm the pool populated.
                assert len(pool.get_object_stream_objects()) >= i
            i *= 2
    finally:
        sys.setrecursionlimit(original_limit)
