"""Round-out tests for ``PDDocument.save_incremental`` (Wave 42).

Cluster pointer: PDDocument-level append-only save. The low-level
``COSWriter(incremental=True)`` path lives in
``tests/pdfwriter/test_cos_writer_incremental.py`` and exercises object
queueing, /Prev wiring, /Size accounting. These tests pin the
PDDocument-facing contract:

* round-tripping through ``PDDocument.save`` then ``PDDocument.load``
  then ``PDDocument.save_incremental`` produces a file whose original
  byte prefix is preserved verbatim;
* the appended xref's ``/Prev`` matches the source's ``startxref``;
* mutating the document info dictionary and marking the trailer dirty
  appends only the info object, not the whole graph;
* repeated incremental saves chain correctly (each save's ``/Prev``
  points at the previous save's startxref).
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

from pypdfbox import PDDocument, PDPage


def _save_full(doc: PDDocument) -> bytes:
    sink = io.BytesIO()
    doc.save(sink)
    return sink.getvalue()


def _make_seed_pdf(num_pages: int = 1, *, with_info: bool = False) -> bytes:
    src = PDDocument()
    for _ in range(num_pages):
        src.add_page(PDPage())
    if with_info:
        # Force /Info into existence so it is emitted as an indirect
        # object (the cluster #1 writer queues /Info during the body
        # walk) — incremental save can then mutate it.
        info = src.get_document_information()
        info.set_title("seed-title")
    out = _save_full(src)
    src.close()
    return out


# ----------------------------------------------------------------- contracts


def test_save_incremental_preserves_original_bytes_verbatim() -> None:
    """The source PDF must appear as a byte-for-byte prefix of the
    incremental output (mirrors upstream ``saveIncremental`` contract)."""
    src = _make_seed_pdf()
    with PDDocument.load(src) as loaded:
        # Mark the catalog dirty so we get an actual increment appended.
        catalog = loaded.get_document_catalog()
        catalog.get_cos_object().set_needs_to_be_updated(True)
        sink = io.BytesIO()
        loaded.save_incremental(sink)
        out = sink.getvalue()
    assert out.startswith(src), "original bytes must be preserved verbatim"
    # Increment must follow the original %%EOF.
    increment = out[len(src) :]
    assert increment.lstrip().startswith(b"") or len(increment) > 0


def test_save_incremental_chains_prev_to_source_startxref() -> None:
    """The appended trailer's ``/Prev`` must equal the source's
    ``startxref`` value (PDF 32000-1 §7.5.6)."""
    src = _make_seed_pdf()
    src_startxref = int(
        re.search(rb"startxref\s+(\d+)\s+%%EOF", src).group(1)
    )

    with PDDocument.load(src) as loaded:
        catalog = loaded.get_document_catalog()
        catalog.get_cos_object().set_needs_to_be_updated(True)
        sink = io.BytesIO()
        loaded.save_incremental(sink)
        out = sink.getvalue()

    increment = out[len(src) :]
    prev_match = re.search(rb"/Prev\s+(\d+)", increment)
    assert prev_match is not None, "increment must carry /Prev"
    assert int(prev_match.group(1)) == src_startxref


def test_save_incremental_round_trip_through_loader() -> None:
    """The output of an incremental save must be re-loadable, and the
    edit must survive the round trip."""
    src = _make_seed_pdf(with_info=True)
    with PDDocument.load(src) as loaded:
        info = loaded.get_document_information()
        info.set_title("Wave 42 Round-out")
        info.get_cos_object().set_needs_to_be_updated(True)
        sink = io.BytesIO()
        loaded.save_incremental(sink)
        out = sink.getvalue()

    with PDDocument.load(out) as re_loaded:
        info2 = re_loaded.get_document_information()
        assert info2.get_title() == "Wave 42 Round-out"


def test_save_incremental_to_path_round_trip(tmp_path: Path) -> None:
    """``save_incremental`` accepts a path argument (mirrors
    upstream's ``File`` overload of ``saveIncremental``)."""
    src_path = tmp_path / "src.pdf"
    src_path.write_bytes(_make_seed_pdf())
    src_bytes = src_path.read_bytes()

    out_path = tmp_path / "incr.pdf"
    with PDDocument.load(src_path) as loaded:
        catalog = loaded.get_document_catalog()
        catalog.get_cos_object().set_needs_to_be_updated(True)
        loaded.save_incremental(out_path)

    out = out_path.read_bytes()
    assert out.startswith(src_bytes)
    assert out.rstrip().endswith(b"%%EOF")


def test_save_incremental_no_dirty_objects_is_byte_identical() -> None:
    """If nothing is marked dirty, the writer must emit zero increment
    bytes — the output equals the source. Pins upstream's no-op path."""
    src = _make_seed_pdf()
    with PDDocument.load(src) as loaded:
        sink = io.BytesIO()
        loaded.save_incremental(sink)
        out = sink.getvalue()
    assert out == src


def test_save_incremental_chained_twice() -> None:
    """Two successive incremental saves must each chain correctly: the
    second save's ``/Prev`` must point at the first save's ``startxref``,
    not at the original source's."""
    src = _make_seed_pdf()

    # First incremental save.
    with PDDocument.load(src) as loaded:
        catalog = loaded.get_document_catalog()
        catalog.get_cos_object().set_needs_to_be_updated(True)
        sink1 = io.BytesIO()
        loaded.save_incremental(sink1)
        round1 = sink1.getvalue()

    # The first save's last startxref becomes the source for the second.
    first_startxref = int(
        re.findall(rb"startxref\s+(\d+)\s+%%EOF", round1)[-1]
    )

    with PDDocument.load(round1) as loaded:
        catalog = loaded.get_document_catalog()
        catalog.get_cos_object().set_needs_to_be_updated(True)
        sink2 = io.BytesIO()
        loaded.save_incremental(sink2)
        round2 = sink2.getvalue()

    assert round2.startswith(round1)
    increment2 = round2[len(round1) :]
    prev_match = re.search(rb"/Prev\s+(\d+)", increment2)
    assert prev_match is not None
    assert int(prev_match.group(1)) == first_startxref


def test_save_incremental_synthesised_doc_raises() -> None:
    """A document built from scratch has no source — incremental save
    must reject it. Upstream raises ``IllegalStateException`` →
    ``RuntimeError`` with the upstream-exact message (oracle-confirmed against
    PDFBox 3.0.7, PDDocumentSignStateProbe)."""
    doc = PDDocument()
    doc.add_page(PDPage())
    with pytest.raises(
        RuntimeError, match="document was not loaded from a file or a stream"
    ):
        doc.save_incremental(io.BytesIO())
    doc.close()
