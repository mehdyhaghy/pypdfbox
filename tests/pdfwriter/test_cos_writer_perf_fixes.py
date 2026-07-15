"""Regression tests for the cos_writer performance fixes.

Covers three optimisations that must preserve behaviour exactly:

1. ``_WriteQueue`` — the O(1) duplicate-enqueue guard (parallel ``id()`` set)
   must stay in lockstep with the deque across append / popleft / pop / clear.
2. The ``is_dereferenced()`` gate in ``_prepare_increment`` /
   ``_enqueue_dirty_objects`` must produce byte-identical incremental output
   when it actually skips never-dereferenced (lazy) pool objects.
3. The running-index xref subsection emission must be byte-identical to the
   O(ranges x entries) filter it replaced (exercised indirectly by the
   round-trip below and the wider suite).
"""
from __future__ import annotations

import io
import os
import tempfile

from pypdfbox.cos import COSDictionary
from pypdfbox.pdfwriter import COSWriter
from pypdfbox.pdfwriter.compress import CompressParameters
from pypdfbox.pdfwriter.cos_writer import _WriteQueue
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


def _build(n: int) -> PDDocument:
    doc = PDDocument()
    font = PDType1Font()
    for i in range(n):
        page = PDPage()
        doc.add_page(page)
        cs = PDPageContentStream(doc, page)
        cs.begin_text()
        cs.set_font(font, 12)
        cs.new_line_at_offset(50, 700)
        cs.show_text(f"Page {i}")
        cs.end_text()
        cs.close()
    return doc


# ---- fix 1: _WriteQueue id-set stays in lockstep --------------------------

def test_write_queue_ids_track_append_and_popleft() -> None:
    q = _WriteQueue()
    a, b = COSDictionary(), COSDictionary()
    q.append(a)
    q.append(b)
    assert q.ids == {id(a), id(b)}
    assert q.popleft() is a
    assert q.ids == {id(b)}
    q.appendleft(a)
    assert q.ids == {id(a), id(b)}
    assert q.pop() is b
    assert q.ids == {id(a)}
    q.clear()
    assert q.ids == set()
    assert len(q) == 0


def test_write_queue_dedup_guard_via_direct_append() -> None:
    # A direct append (as internal call sites do) must update ``ids`` so the
    # O(1) duplicate-enqueue guard in ``_add_object_to_write`` sees it.
    obj = COSDictionary()
    with COSWriter(io.BytesIO()) as writer:
        writer._objects_to_write.append(obj)
        writer._add_object_to_write(obj)
        assert list(writer._objects_to_write) == [obj]


# ---- fix 2: is_dereferenced gate is byte-identical when it skips ----------

def test_incremental_gate_byte_identical_when_skipping_lazy_objects(
    monkeypatch,
) -> None:
    # The incremental /ID[1] is a SHA-256 over time.time_ns() + secrets; pin
    # both so the only variable across the two saves is the is_dereferenced()
    # gate itself.
    import pypdfbox.pdfwriter.cos_writer as cw

    monkeypatch.setattr(cw.secrets, "token_bytes", lambda n: b"\xab" * n)
    monkeypatch.setattr(cw.time, "time_ns", lambda: 1234567890)
    monkeypatch.setattr(cw.time, "time", lambda: 1234567.0)

    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        doc = _build(60)
        doc.save(path, CompressParameters.NO_COMPRESSION)
        doc.close()

        def incr(force_deref: bool) -> bytes:
            d = PDDocument.load(path)
            cos = d.get_document()
            d.get_page(0).get_cos_object().set_needs_to_be_updated(True)
            if force_deref:
                # Dereference every pool object so the gate condition is always
                # False -> equivalent to the pre-fix (un-gated) code path.
                for o in cos.get_objects():
                    o.get_object()
            sink = io.BytesIO()
            # allow_signing_placeholders bypasses the byterange scan, so lazy
            # objects genuinely stay lazy and the gate actually skips them.
            with COSWriter(
                sink, incremental=True, allow_signing_placeholders=True
            ) as w:
                w.write(cos)
            d.close()
            return sink.getvalue()

        assert incr(force_deref=False) == incr(force_deref=True)
    finally:
        os.unlink(path)


# ---- fix 3: xref running-index round-trips cleanly ------------------------

def test_uncompressed_save_reloads_intact() -> None:
    doc = _build(40)
    buf = io.BytesIO()
    doc.save(buf, CompressParameters.NO_COMPRESSION)
    doc.close()
    buf.seek(0)
    reloaded = PDDocument.load(buf.getvalue())
    try:
        assert reloaded.get_number_of_pages() == 40
    finally:
        reloaded.close()
