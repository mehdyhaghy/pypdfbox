"""Tests for hybrid xref output (PDF 32000-1 §7.5.8.4) added to
``COSWriter``.

In a hybrid layout the writer emits BOTH a traditional ``xref`` table
(found by legacy PDF-1.4 readers via ``startxref``) AND a parallel
``/Type /XRef`` stream announced from the trailer via ``/XRefStm``.
Modern readers prefer the stream; legacy readers use the table.

Three layers of coverage:

1. constructor / setter / getter surface,
2. wire-format assertions on the emitted bytes — both the ``xref``
   keyword and the ``/Type /XRef`` stream and ``/XRefStm`` in the
   trailer must be present together,
3. round-trip via the parser (which may pick either form),
4. regression: without the flag, no /XRefStm appears.
"""

from __future__ import annotations

import io
import re

from pypdfbox.cos import (
    COSDictionary,
    COSDocument,
    COSName,
    COSObject,
)
from pypdfbox.loader import Loader
from pypdfbox.pdfwriter import COSWriter

# ---------- helpers ---------------------------------------------------------


def _make_doc(catalog_dict: COSDictionary | None = None) -> COSDocument:
    """Mirror the fixture from ``test_xref_stream_output.py`` — minimal
    trailer + catalog #1, suitable for both traditional, xref-stream,
    and hybrid output paths."""
    doc = COSDocument()
    doc.set_version(1.5)
    catalog = catalog_dict if catalog_dict is not None else COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    catalog_obj = COSObject(1, 0, resolved=catalog)
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, catalog_obj)  # type: ignore[attr-defined]
    doc.set_trailer(trailer)
    return doc


def _write_hybrid(doc: COSDocument) -> bytes:
    sink = io.BytesIO()
    with COSWriter(sink, hybrid_xref=True) as w:
        w.write(doc)
    return sink.getvalue()


def _write_traditional(doc: COSDocument) -> bytes:
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.write(doc)
    return sink.getvalue()


# ---------- constructor / setter / getter surface --------------------------


def test_default_hybrid_flag_off() -> None:
    sink = io.BytesIO()
    w = COSWriter(sink)
    assert w.is_hybrid_xref_output() is False


def test_hybrid_setter_round_trip() -> None:
    sink = io.BytesIO()
    w = COSWriter(sink)
    w.set_hybrid_xref(True)
    assert w.is_hybrid_xref_output() is True
    w.set_hybrid_xref(False)
    assert w.is_hybrid_xref_output() is False


def test_hybrid_constructor_flag_propagates() -> None:
    sink = io.BytesIO()
    with COSWriter(sink, hybrid_xref=True) as w:
        assert w.is_hybrid_xref_output() is True


def test_hybrid_wins_when_both_set() -> None:
    """``hybrid_xref=True`` overrides ``xref_stream=True`` because hybrid
    is a strict superset behaviorally — the output still carries the
    stream AND adds the traditional table on top."""
    out_sink = io.BytesIO()
    with COSWriter(out_sink, xref_stream=True, hybrid_xref=True) as w:
        w.write(_make_doc())
    saved = out_sink.getvalue()
    # Must have both the legacy keyword and the XRef stream marker.
    assert b"\nxref\n" in saved
    assert b"/Type /XRef" in saved or b"/Type/XRef" in saved


# ---------- wire-format assertions -----------------------------------------


def test_hybrid_emits_both_xref_keyword_and_xref_stream() -> None:
    out = _write_hybrid(_make_doc())
    # Traditional xref keyword.
    assert b"\nxref\n" in out
    # Parallel /Type /XRef stream object.
    assert b"/Type /XRef" in out or b"/Type/XRef" in out
    # Traditional ``trailer`` keyword still present (hybrid keeps both).
    assert b"\ntrailer\n" in out


def test_hybrid_trailer_contains_xref_stm_pointing_at_stream() -> None:
    out = _write_hybrid(_make_doc())

    # Find the trailer block.
    trailer_idx = out.rindex(b"\ntrailer\n")
    startxref_idx = out.rindex(b"startxref\n")
    trailer_blob = out[trailer_idx:startxref_idx]

    # /XRefStm <offset> must be in the trailer dict.
    match = re.search(rb"/XRefStm\s+(\d+)", trailer_blob)
    assert match is not None, "trailer is missing /XRefStm key"
    xref_stm_offset = int(match.group(1))

    # That offset must land on an indirect-object frame whose dict
    # contains /Type /XRef (this IS the parallel xref stream).
    window = out[xref_stm_offset:xref_stm_offset + 4096]
    assert b" obj" in window, (
        "/XRefStm offset doesn't land on an indirect object frame"
    )
    assert b"/Type /XRef" in window or b"/Type/XRef" in window, (
        "/XRefStm offset doesn't land on the /Type /XRef stream"
    )


def test_hybrid_startxref_points_at_traditional_table() -> None:
    out = _write_hybrid(_make_doc())

    startxref_idx = out.rindex(b"startxref\n")
    line_start = startxref_idx + len(b"startxref\n")
    line_end = out.index(b"\n", line_start)
    declared = int(out[line_start:line_end].strip())

    # The traditional xref table starts with the bytes ``xref\n``.
    assert out[declared:declared + 5] == b"xref\n", (
        "startxref offset must point at the traditional ``xref`` keyword "
        "in hybrid mode (legacy readers depend on it)"
    )


def test_hybrid_xref_table_includes_xref_stream_entry() -> None:
    """The traditional xref table covers ALL objects, including the xref
    stream itself — confirm the entry count matches the highest object
    number (catalog #1 + xref stream #2 + free-list head ⇒ 3 entries)."""
    out = _write_hybrid(_make_doc())

    # Locate the table.
    startxref_idx = out.rindex(b"startxref\n")
    line_start = startxref_idx + len(b"startxref\n")
    line_end = out.index(b"\n", line_start)
    table_offset = int(out[line_start:line_end].strip())

    table_blob = out[table_offset:startxref_idx]
    # First subsection header is the line right after ``xref\n``.
    header_match = re.search(rb"xref\s*\n(\d+)\s+(\d+)\s*\n", table_blob)
    assert header_match is not None
    first, count = (int(g) for g in header_match.groups())
    # Catalog (#1) and xref stream (#2) on top of the free-list head (#0)
    # yields a single subsection ``0 3``.
    assert first == 0
    assert count >= 3, (
        f"traditional xref must include the xref stream entry; saw count={count}"
    )


# ---------- round-trip via parser ------------------------------------------


def test_hybrid_round_trip_via_parser() -> None:
    catalog = COSDictionary()
    catalog.set_int(COSName.get_pdf_name("Marker"), 7)
    doc = _make_doc(catalog)
    out = _write_hybrid(doc)

    parsed = Loader.load_pdf(out)
    try:
        cat = parsed.get_catalog()
        assert cat is not None
        assert cat.get_name(COSName.TYPE) == "Catalog"  # type: ignore[attr-defined]
        assert cat.get_int(COSName.get_pdf_name("Marker")) == 7
    finally:
        parsed.close()


# ---------- regression: default save has no /XRefStm -----------------------


def test_default_save_has_no_xrefstm_key_in_trailer() -> None:
    out = _write_traditional(_make_doc())
    assert b"\nxref\n" in out
    assert b"\ntrailer\n" in out
    # Without hybrid mode the trailer must NOT carry /XRefStm — adding
    # it would mislead conforming readers into hunting for a parallel
    # stream that doesn't exist.
    assert b"/XRefStm" not in out
