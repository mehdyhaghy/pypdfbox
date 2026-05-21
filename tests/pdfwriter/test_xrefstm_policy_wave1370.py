"""Wave 1370 — /XRefStm policy + xref-table vs xref-stream selection.

PDF 32000-1 carries three xref tail styles:

* §7.5.4 — traditional ``xref`` table + ``trailer`` (default, PDF 1.0+),
* §7.5.8 — pure ``/Type /XRef`` stream (PDF 1.5+),
* §7.5.8.4 — hybrid layout: traditional table + a parallel ``/Type /XRef``
  stream announced via ``/XRefStm`` in the trailer dict.

The selection follows the constructor flags:

* default → traditional table only.
* ``xref_stream=True`` → pure stream (no traditional table, no /XRefStm).
* ``hybrid_xref=True`` → both, /XRefStm announces the parallel stream.
"""

from __future__ import annotations

import io
import re

from pypdfbox.cos import COSDictionary, COSDocument, COSName, COSObject
from pypdfbox.pdfwriter import COSWriter


def _make_doc() -> COSDocument:
    doc = COSDocument()
    doc.set_version(1.6)
    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    catalog_obj = COSObject(1, 0, resolved=catalog)
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, catalog_obj)  # type: ignore[attr-defined]
    doc.set_trailer(trailer)
    return doc


def _write(*, xref_stream: bool = False, hybrid_xref: bool = False) -> bytes:
    sink = io.BytesIO()
    with COSWriter(
        sink, xref_stream=xref_stream, hybrid_xref=hybrid_xref
    ) as w:
        w.write(_make_doc())
    return sink.getvalue()


# ---------- default: traditional table only -------------------------------


def test_default_uses_traditional_table_only() -> None:
    out = _write()
    # Traditional ``xref`` keyword + ``trailer`` keyword both present.
    assert b"\nxref\n" in out
    assert b"\ntrailer\n" in out
    # No /Type /XRef stream emitted.
    assert b"/Type /XRef" not in out and b"/Type/XRef" not in out
    # No /XRefStm in trailer.
    assert b"/XRefStm" not in out


# ---------- pure xref-stream: no traditional table, no /XRefStm -----------


def test_xref_stream_only_drops_traditional_table_and_xrefstm() -> None:
    out = _write(xref_stream=True)
    # The ``trailer`` keyword is gone — its entries live inside the
    # xref stream dict.
    assert b"\ntrailer\n" not in out
    # The traditional ``xref\n`` table keyword is gone.
    assert b"\nxref\n" not in out
    # No /XRefStm — that's a hybrid-only concept.
    assert b"/XRefStm" not in out
    # But a /Type /XRef stream IS present.
    assert b"/Type /XRef" in out or b"/Type/XRef" in out


# ---------- hybrid: both table and stream, trailer announces /XRefStm -----


def test_hybrid_emits_table_and_stream_with_xrefstm_announce() -> None:
    out = _write(hybrid_xref=True)
    # Traditional table keyword stays.
    assert b"\nxref\n" in out
    assert b"\ntrailer\n" in out
    # /Type /XRef stream also emitted.
    assert b"/Type /XRef" in out or b"/Type/XRef" in out
    # Trailer must carry /XRefStm with an integer offset.
    match = re.search(rb"/XRefStm\s+(\d+)", out)
    assert match is not None, "trailer missing /XRefStm"
    offset = int(match.group(1))
    # The announced offset must land on an indirect-object frame
    # (the parallel /Type /XRef stream).
    assert offset < len(out)
    assert re.match(rb"\d+\s+\d+\s+obj", out[offset:])


# ---------- /XRefStm value in source trailer is NOT echoed unless hybrid ---


def test_source_xrefstm_entry_is_not_carried_through_default_save() -> None:
    """When the parsed source trailer happens to carry /XRefStm but we
    do a vanilla (traditional-table) save, the new trailer must NOT echo
    /XRefStm — the value was a position pointer to the parsed source,
    not a re-serialisable entry."""
    doc = _make_doc()
    trailer = doc.get_trailer()
    assert trailer is not None
    # Spoof a leftover /XRefStm — the writer must strip it on the
    # full-save tail.
    trailer.set_int(COSName.get_pdf_name("XRefStm"), 9999)
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.write(doc)
    out = sink.getvalue()
    # If /XRefStm appears at all, it's only because the writer chose
    # to emit it (hybrid mode) — in a default save it must not.
    assert b"/XRefStm" not in out


# ---------- mutual exclusivity guards -------------------------------------


def test_hybrid_supersedes_pure_stream_when_both_flags_set() -> None:
    """Setting BOTH ``xref_stream`` and ``hybrid_xref`` is upgraded to
    hybrid — the strict superset wins. Verify the output still has a
    traditional table (the hybrid signature)."""
    sink = io.BytesIO()
    with COSWriter(sink, xref_stream=True, hybrid_xref=True) as w:
        w.write(_make_doc())
    out = sink.getvalue()
    assert b"\nxref\n" in out
    assert b"\ntrailer\n" in out
    assert b"/XRefStm" in out


def test_startxref_points_at_traditional_table_in_hybrid() -> None:
    """In hybrid mode the startxref offset must point at the *traditional*
    table, not at the /Type /XRef stream. Old PDF-1.4 readers locate the
    table via startxref; modern readers see /XRefStm and use the stream."""
    out = _write(hybrid_xref=True)
    startxref_idx = out.rindex(b"startxref\n")
    line_start = startxref_idx + len(b"startxref\n")
    line_end = out.index(b"\n", line_start)
    declared = int(out[line_start:line_end].strip())
    # The byte at the declared offset must be the start of an ``xref``
    # keyword (traditional table).
    assert out[declared:declared + 4] == b"xref"


def test_startxref_points_at_xref_stream_in_pure_stream_mode() -> None:
    """Inverse of the hybrid case: pure xref-stream mode must land
    startxref on the indirect-object frame of the /Type /XRef stream."""
    out = _write(xref_stream=True)
    startxref_idx = out.rindex(b"startxref\n")
    line_start = startxref_idx + len(b"startxref\n")
    line_end = out.index(b"\n", line_start)
    declared = int(out[line_start:line_end].strip())
    # An indirect-object frame begins with "<num> <gen> obj".
    assert re.match(rb"\d+\s+\d+\s+obj", out[declared:])
