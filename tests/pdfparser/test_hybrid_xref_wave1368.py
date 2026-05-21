"""Wave 1368 — hybrid xref layout (PDF 1.5 ``/XRefStm`` + traditional table).

PDF 32000-1 §7.5.8.4: a PDF 1.4 file can carry an *additional* xref
stream describing compressed objects by linking ``/XRefStm`` from the
trailer of a traditional xref table. PDF 1.4 readers ignore the
``/XRefStm`` key and see only uncompressed objects; PDF 1.5+ readers
merge the xref-stream's compressed entries into the same section,
overwriting the legacy table's free-list stubs for the same numbers.

These tests probe the merge:

* table + /XRefStm both present, stream introduces a new object number
  not in the table.
* document marker ``has_hybrid_xref`` flipped.
* /XRefStm key absent → no hybrid load attempted.
* /XRefStm value zero / missing offset → ignored.
* xref-stream object inside the file is also visible via its own
  uncompressed (table) entry.
"""

from __future__ import annotations

from pypdfbox.cos import COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser


def _pack(type_byte: int, field2: int, field3: int) -> bytes:
    """Pack one record under /W [1 4 2]."""
    return (
        type_byte.to_bytes(1, "big")
        + field2.to_bytes(4, "big")
        + field3.to_bytes(2, "big")
    )


def _build_hybrid_pdf() -> bytes:
    """A PDF with both a traditional xref TABLE describing the catalog
    and an /XRefStm whose body adds a (compressed-style record for the
    same) object stream entry. The merged view must see both."""
    out = bytearray(b"%PDF-1.5\n")
    # Object 1: the catalog.
    obj1_off = len(out)
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    # Object 2: an ObjStm containing object 3.
    objstm_payload = b"3 0 (compressed)"
    obj2_off = len(out)
    out += (
        b"2 0 obj\n<< /Type /ObjStm /N 1 /First 4 /Length "
        + str(len(objstm_payload)).encode("ascii")
        + b" >>\nstream\n"
        + objstm_payload
        + b"\nendstream\nendobj\n"
    )
    # Object 4: the supplementary xref stream. Its records cover
    # objects 0..3 — describing object 2 as in-use and object 3 as
    # compressed inside object 2. Use /Index [ 0 4 ] for the records.
    records = b""
    records += _pack(0, 0, 65535)  # object 0 (free root)
    records += _pack(1, obj1_off, 0)  # object 1 (in-use, redundant w/ table)
    records += _pack(1, obj2_off, 0)  # object 2 (in-use, ObjStm)
    records += _pack(2, 2, 0)  # object 3 (compressed inside objstm 2)
    xref_stm_off = len(out)
    out += (
        b"4 0 obj\n<< /Type /XRef /Size 4 /Index [ 0 4 ]"
        b" /W [ 1 4 2 ] /Length "
        + str(len(records)).encode("ascii")
        + b" >>\nstream\n"
        + records
        + b"\nendstream\nendobj\n"
    )
    # Traditional xref table — newest section. It describes objects
    # 0..2 (and 4 — the xref-stream object itself).
    table_off = len(out)
    out += b"xref\n0 3\n0000000000 65535 f \n"
    out += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    out += f"{obj2_off:010d} 00000 n \n".encode("ascii")
    out += b"4 1\n"
    out += f"{xref_stm_off:010d} 00000 n \n".encode("ascii")
    # Trailer links to /XRefStm so the parser pulls in object 3 too.
    out += (
        b"trailer\n<< /Size 5 /Root 1 0 R /XRefStm "
        + str(xref_stm_off).encode("ascii")
        + b" >>\n"
    )
    out += b"startxref\n" + str(table_off).encode("ascii") + b"\n%%EOF"
    return bytes(out)


def test_hybrid_xref_table_plus_xrefstm_merges_compressed_entry() -> None:
    """The table provides object 1/2; the /XRefStm supplements with the
    compressed object 3 entry. After parse both number ranges must be
    visible."""
    pdf = _build_hybrid_pdf()
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    assert doc.has_object(COSObjectKey(1, 0))
    assert doc.has_object(COSObjectKey(2, 0))
    # Object 3 only lives in the xref-stream's records — the hybrid
    # merge must surface it.
    assert doc.has_object(COSObjectKey(3, 0))


def test_hybrid_xref_marks_document_has_hybrid_xref() -> None:
    """When the merge path fires the document records the fact so
    downstream layers (incremental writer, in particular) can rewire."""
    pdf = _build_hybrid_pdf()
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    assert doc.has_hybrid_xref()


def test_without_xrefstm_in_trailer_no_hybrid_flag() -> None:
    """A plain traditional xref with no /XRefStm key must not flip the
    hybrid flag."""
    out = bytearray(b"%PDF-1.4\n")
    obj1_off = len(out)
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 2 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    assert not doc.has_hybrid_xref()


def test_hybrid_xrefstm_zero_offset_is_ignored() -> None:
    """``/XRefStm 0`` means "no supplementary xref stream" — the parser
    must not try to load anything at offset 0 (which is the PDF
    header)."""
    out = bytearray(b"%PDF-1.4\n")
    obj1_off = len(out)
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 2 /Root 1 0 R /XRefStm 0 >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    assert doc.has_object(COSObjectKey(1, 0))
    # No hybrid merge happened — the zero-offset short-circuit must hold.
    assert not doc.has_hybrid_xref()


def test_hybrid_resolved_xref_type_is_table() -> None:
    """The hybrid section's primary type stays TABLE — the xref-stream
    fragment is supplementary, not a replacement for the parsed
    section's identity."""
    from pypdfbox.pdfparser.xref_trailer_resolver import XrefType  # noqa: PLC0415

    pdf = _build_hybrid_pdf()
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    parser.parse()
    resolver = parser.get_xref_trailer_resolver()
    resolver.set_startxref(parser.get_xref_offset())
    assert resolver.get_xref_type() == XrefType.TABLE
