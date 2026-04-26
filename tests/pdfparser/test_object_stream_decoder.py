"""Tests for the compressed-object loader (PDF 32000-1 §7.5.7).

Synthesises a tiny PDF whose payload objects live inside an ObjStm
(``/Type /ObjStm``) and are referenced from an xref stream via type-2
entries. End-to-end this exercises the cluster-#4 wiring:

  xref-stream record (type 2) → COSObject loader →
    PDFParser._load_compressed_object → ObjStm header parse →
      single-object COSParser slice
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSObjectKey, COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser
from pypdfbox.pdfparser.parse_error import PDFParseError


# --------------------------------------------------------------- helpers


def _pack_record(type_byte: int, field2: int, field3: int, w2: int = 4, w3: int = 2) -> bytes:
    return (
        type_byte.to_bytes(1, "big")
        + field2.to_bytes(w2, "big")
        + field3.to_bytes(w3, "big")
    )


def _build_objstm_body(items: list[tuple[int, bytes]]) -> tuple[bytes, int]:
    """Pack a list of ``(obj_num, body_bytes)`` into an ObjStm payload.

    Returns ``(decoded_body, first_offset)`` where ``first_offset`` is the
    byte index of the first packed object inside ``decoded_body`` (i.e.
    the value to emit as ``/First`` in the dict).
    """
    # Two passes — first compute byte_offsets within the payload region,
    # then emit "<obj_num> <byte_offset> ..." header + payload.
    payload = bytearray()
    pairs: list[tuple[int, int]] = []
    for obj_num, body in items:
        pairs.append((obj_num, len(payload)))
        payload += body + b" "
    header = b" ".join(
        f"{obj_num} {offset}".encode("ascii") for obj_num, offset in pairs
    ) + b" "
    first = len(header)
    return bytes(header) + bytes(payload), first


def _build_pdf_with_objstm(objstm_items: list[tuple[int, bytes]]) -> bytes:
    """Build a tiny PDF where an ObjStm (object 1) holds the payload
    objects and a PDF 1.5 xref stream registers them as type-2
    compressed entries.

    The xref stream's ``/Index`` is hand-built so each compressed entry
    sits at the object number requested in ``objstm_items`` — the
    cluster-#4 decoder splices the right (obj_num, inner_index) pairs
    into the resolver from there.
    """
    out = bytearray(b"%PDF-1.5\n")
    objstm_body, first = _build_objstm_body(objstm_items)
    objstm_off = len(out)
    n_packed = len(objstm_items)
    out += (
        f"1 0 obj\n<< /Type /ObjStm /N {n_packed} /First {first}"
        f" /Length {len(objstm_body)} >>\nstream\n".encode("ascii")
        + objstm_body
        + b"\nendstream\nendobj\n"
    )
    # The xref-stream object lives at the next free number > max(obj_num
    # in objstm) and > 1 (the ObjStm). Pick a number above every payload
    # object so /Index can place each compressed entry in its own
    # single-element section without overlap.
    highest_payload = max((n for n, _ in objstm_items), default=1)
    xref_obj_num = max(highest_payload, 1) + 1
    # /Index sections — one per slot we need:
    #   [0 1]                — object 0 free
    #   [1 1]                — object 1 (ObjStm) uncompressed
    #   [obj_num 1] x N      — payload objects, compressed
    #   [xref_obj_num 1]     — the xref stream itself
    index_sections: list[tuple[int, int]] = [(0, 1), (1, 1)]
    for obj_num, _ in objstm_items:
        index_sections.append((obj_num, 1))
    index_sections.append((xref_obj_num, 1))
    # Pack records in the same order as /Index.
    records = bytearray()
    records += _pack_record(0, 0, 65535)
    records += _pack_record(1, objstm_off, 0)
    for index, (_obj_num, _body) in enumerate(objstm_items):
        records += _pack_record(2, 1, index)
    records += _pack_record(1, 0, 0)  # placeholder offset for xref stream
    size = xref_obj_num + 1
    index_text = b"[ " + b" ".join(
        f"{first} {count}".encode("ascii") for first, count in index_sections
    ) + b" ]"
    xref_off = len(out)
    out += (
        f"{xref_obj_num} 0 obj\n<< /Type /XRef /Size {size}".encode("ascii")
        + b" /Index " + index_text
        + f" /W [ 1 4 2 ] /Length {len(records)} >>\nstream\n".encode("ascii")
        + bytes(records)
        + b"\nendstream\nendobj\n"
    )
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    return bytes(out)


# --------------------------------------------------------------- tests


def test_objstm_three_compressed_objects_round_trip() -> None:
    """An ObjStm holding three direct objects of three different shapes
    (integer, string, dictionary). All three must be retrievable by their
    own (obj_num, 0) keys."""
    items = [
        (10, b"42"),
        (11, b"(hello)"),
        (12, b"<< /Type /Page /Count 1 >>"),
    ]
    pdf = _build_pdf_with_objstm(items)
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    assert doc.has_object(COSObjectKey(10, 0))
    assert doc.has_object(COSObjectKey(11, 0))
    assert doc.has_object(COSObjectKey(12, 0))
    body10 = doc.get_object_from_pool(COSObjectKey(10, 0)).get_object()
    body11 = doc.get_object_from_pool(COSObjectKey(11, 0)).get_object()
    body12 = doc.get_object_from_pool(COSObjectKey(12, 0)).get_object()
    assert isinstance(body10, COSInteger) and body10.value == 42
    assert isinstance(body11, COSString) and body11.get_bytes() == b"hello"
    assert isinstance(body12, COSDictionary)
    assert body12.get_name("Type") == "Page"
    assert body12.get_int("Count") == 1


def test_objstm_index_lookup_uses_inner_offset_not_obj_num() -> None:
    """The ``inner_index`` stored in the xref entry is the position
    inside the ObjStm header, *not* the object's own number. Verify a
    case where the object numbers are non-contiguous and out of order."""
    items = [
        (50, b"(first)"),
        (3, b"(second)"),
        (99, b"(third)"),
    ]
    pdf = _build_pdf_with_objstm(items)
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    body50 = doc.get_object_from_pool(COSObjectKey(50, 0)).get_object()
    body3 = doc.get_object_from_pool(COSObjectKey(3, 0)).get_object()
    body99 = doc.get_object_from_pool(COSObjectKey(99, 0)).get_object()
    assert isinstance(body50, COSString) and body50.get_bytes() == b"first"
    assert isinstance(body3, COSString) and body3.get_bytes() == b"second"
    assert isinstance(body99, COSString) and body99.get_bytes() == b"third"


def test_objstm_loader_failure_when_n_or_first_missing() -> None:
    """Compressed lookups against a malformed ObjStm (missing /N or
    /First) should raise PDFParseError rather than silently returning."""
    # Hand-build an ObjStm with no /N or /First. The xref stream points
    # at object 5 (a compressed entry) so the loader has to touch the
    # malformed container.
    out = bytearray(b"%PDF-1.5\n")
    objstm_body = b"5 0 (whatever) "
    objstm_off = len(out)
    out += (
        f"1 0 obj\n<< /Type /ObjStm /Length {len(objstm_body)} >>\nstream\n".encode(
            "ascii"
        )
        + objstm_body
        + b"\nendstream\nendobj\n"
    )
    records = (
        _pack_record(0, 0, 65535)
        + _pack_record(1, objstm_off, 0)
        + _pack_record(2, 1, 0)  # object 5 is at index 0 in container 1
        + _pack_record(1, 0, 0)
    )
    xref_off = len(out)
    out += (
        b"2 0 obj\n<< /Type /XRef /Size 6 /Index [ 0 2 5 1 2 1 ]"
        b" /W [ 1 4 2 ] /Length "
        + str(len(records)).encode("ascii")
        + b" >>\nstream\n"
        + records
        + b"\nendstream\nendobj\n"
    )
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    obj5 = doc.get_object_from_pool(COSObjectKey(5, 0))
    with pytest.raises(PDFParseError):
        obj5.get_object()


def test_objstm_index_out_of_range_raises() -> None:
    """If a type-2 xref entry points to ``inner_index >= /N`` the loader
    must surface the contradiction as a parse error rather than silently
    truncating."""
    items = [(7, b"(one)")]  # only one packed object → /N == 1
    out = bytearray(b"%PDF-1.5\n")
    objstm_body, first = _build_objstm_body(items)
    objstm_off = len(out)
    out += (
        f"1 0 obj\n<< /Type /ObjStm /N 1 /First {first}"
        f" /Length {len(objstm_body)} >>\nstream\n".encode("ascii")
        + objstm_body
        + b"\nendstream\nendobj\n"
    )
    # Reference inner_index 5 — well beyond /N == 1.
    records = (
        _pack_record(0, 0, 65535)
        + _pack_record(1, objstm_off, 0)
        + _pack_record(2, 1, 5)  # bogus inner index
        + _pack_record(1, 0, 0)
    )
    xref_off = len(out)
    out += (
        b"3 0 obj\n<< /Type /XRef /Size 4 /Index [ 0 2 7 1 3 1 ]"
        b" /W [ 1 4 2 ] /Length "
        + str(len(records)).encode("ascii")
        + b" >>\nstream\n"
        + records
        + b"\nendstream\nendobj\n"
    )
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    obj7 = doc.get_object_from_pool(COSObjectKey(7, 0))
    with pytest.raises(PDFParseError):
        obj7.get_object()


def test_objstm_indirect_refs_inside_compressed_object_resolve() -> None:
    """A compressed direct object containing an indirect reference (e.g.
    a Page dict with ``/Parent 1 0 R``) must yield a normal ``COSObject``
    placeholder that resolves through the document pool."""
    items = [
        (4, b"<< /Type /Page /Parent 1 0 R >>"),
    ]
    pdf = _build_pdf_with_objstm(items)
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    body4 = doc.get_object_from_pool(COSObjectKey(4, 0)).get_object()
    assert isinstance(body4, COSDictionary)
    parent = body4.get_item("Parent")
    # Parent is an indirect reference — its resolved object is the ObjStm.
    from pypdfbox.cos import COSObject  # noqa: PLC0415

    assert isinstance(parent, COSObject)
    assert parent.object_number == 1
    # Resolve it — it's the ObjStm itself.
    resolved = parent.get_object()
    assert isinstance(resolved, COSDictionary)
    assert resolved.get_name(COSName.TYPE) == "ObjStm"  # type: ignore[attr-defined]
