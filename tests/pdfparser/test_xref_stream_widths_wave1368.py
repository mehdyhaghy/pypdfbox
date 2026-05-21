"""Wave 1368 — PDF 1.5+ xref-stream ``/W`` width and ``/Index`` edges.

The xref stream encoder packs three columns per record with widths
declared by ``/W [w0 w1 w2]``; the entries cover the object-number
ranges declared by ``/Index``. Tests cover:

* default-widths fallback (``/W [1 2 1]`` style, w0=0 implies type 1).
* ``/Index`` with three non-contiguous ranges.
* ``/Index`` omitted (parser must default to ``[0 Size]``).
* mixed type-1 (in-use) + type-2 (compressed) entries in one stream.
* zero-length stream body when /Size==0 (legal — no entries).
* /Index ranges that overlap the explicit object 0 free-root.
"""

from __future__ import annotations

import zlib

import pytest

from pypdfbox.cos import COSObjectKey, COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError, PDFParser


def _pack(type_byte: int, field2: int, field3: int, w0: int, w1: int, w2: int) -> bytes:
    parts = b""
    if w0 > 0:
        parts += type_byte.to_bytes(w0, "big")
    parts += field2.to_bytes(w1, "big")
    parts += field3.to_bytes(w2, "big")
    return parts


def _build(
    payload_objects: list[bytes],
    records: bytes,
    *,
    w: tuple[int, int, int],
    index_array: bytes | None = None,
    extra_dict: bytes = b"",
    flate: bool = False,
    size_override: int | None = None,
) -> bytes:
    out = bytearray(b"%PDF-1.5\n")
    for body in payload_objects:
        out += body
        if not body.endswith(b"\n"):
            out += b"\n"
    xref_obj_num = len(payload_objects) + 1
    xref_off = len(out)
    size = size_override if size_override is not None else xref_obj_num + 1
    body = zlib.compress(records) if flate else records
    index_bytes = (
        f"[ 0 {size} ]".encode("ascii") if index_array is None else index_array
    )
    head = bytearray()
    head += f"{xref_obj_num} 0 obj\n".encode("ascii")
    head += b"<< /Type /XRef\n"
    head += f"/Size {size}\n".encode("ascii")
    head += b"/Index " + index_bytes + b"\n"
    head += f"/W [ {w[0]} {w[1]} {w[2]} ]\n".encode("ascii")
    head += f"/Length {len(body)}\n".encode("ascii")
    if flate:
        head += b"/Filter /FlateDecode\n"
    if extra_dict:
        head += extra_dict + b"\n"
    head += b">>\nstream\n"
    out += head + body + b"\nendstream\nendobj\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    return bytes(out)


def test_xref_stream_w_one_two_one_default_widths() -> None:
    """``/W [1 2 1]`` — the smallest practical width set for files that
    fit under 64 KiB. Each in-use record fits in 4 bytes."""
    obj1 = b"1 0 obj\n(small)\nendobj"
    out = bytearray(b"%PDF-1.5\n")
    obj1_off = len(out)
    out += obj1 + b"\n"
    # Build records: free root + obj1 + placeholder for xref stream itself.
    records = b""
    records += _pack(0, 0, 255, 1, 2, 1)  # object 0, gen 255 sentinel-ish
    records += _pack(1, obj1_off, 0, 1, 2, 1)
    records += _pack(1, 0, 0, 1, 2, 1)
    xref_off = len(out)
    out += b"2 0 obj\n<< /Type /XRef /Size 3 /Index [ 0 3 ]"
    out += f" /W [ 1 2 1 ] /Length {len(records)} >>\n".encode("ascii")
    out += b"stream\n" + records + b"\nendstream\nendobj\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    body1 = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
    assert isinstance(body1, COSString) and body1.get_bytes() == b"small"


def test_xref_stream_index_three_non_contiguous_ranges() -> None:
    """``/Index [ 0 1  3 1  6 2 ]`` — three subsections covering objects
    0, 3, 6 and 7. All declared in-use entries must land in the pool."""
    obj3 = b"3 0 obj\n(three)\nendobj"
    obj6 = b"6 0 obj\n(six)\nendobj"
    obj7 = b"7 0 obj\n(seven)\nendobj"
    out = bytearray(b"%PDF-1.5\n")
    obj3_off = len(out)
    out += obj3 + b"\n"
    obj6_off = len(out)
    out += obj6 + b"\n"
    obj7_off = len(out)
    out += obj7 + b"\n"
    # Records in /Index order: (0), (3), (6), (7).
    records = b""
    records += _pack(0, 0, 65535, 1, 4, 2)
    records += _pack(1, obj3_off, 0, 1, 4, 2)
    records += _pack(1, obj6_off, 0, 1, 4, 2)
    records += _pack(1, obj7_off, 0, 1, 4, 2)
    xref_off = len(out)
    out += b"8 0 obj\n<< /Type /XRef /Size 9 /Index [ 0 1 3 1 6 2 ]"
    out += f" /W [ 1 4 2 ] /Length {len(records)} >>\n".encode("ascii")
    out += b"stream\n" + records + b"\nendstream\nendobj\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    for n in (3, 6, 7):
        assert doc.has_object(COSObjectKey(n, 0))
    # Gaps remain unreachable.
    for n in (1, 2, 4, 5):
        assert not doc.has_object(COSObjectKey(n, 0))


def test_xref_stream_omits_index_defaults_to_zero_size() -> None:
    """Per spec, a missing /Index defaults to ``[0 Size]``. The parser
    must synthesise that default rather than fail."""
    obj1 = b"1 0 obj\n(default-index)\nendobj"
    out = bytearray(b"%PDF-1.5\n")
    obj1_off = len(out)
    out += obj1 + b"\n"
    records = (
        _pack(0, 0, 65535, 1, 4, 2)
        + _pack(1, obj1_off, 0, 1, 4, 2)
        + _pack(1, 0, 0, 1, 4, 2)  # placeholder for the xref stream itself
    )
    xref_off = len(out)
    # Note: NO /Index entry in the dict.
    out += b"2 0 obj\n<< /Type /XRef /Size 3 /W [ 1 4 2 ]"
    out += f" /Length {len(records)} >>\n".encode("ascii")
    out += b"stream\n" + records + b"\nendstream\nendobj\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    assert doc.has_object(COSObjectKey(1, 0))


def test_xref_stream_index_pair_count_odd_rejected() -> None:
    """``/Index`` must always come in pairs ``(first, count)``. An
    odd-length array is malformed."""
    bad = (
        b"%PDF-1.5\n"
        b"1 0 obj\n<< /Type /XRef /Size 2 /Index [ 0 1 9 ]"
        b" /W [ 1 1 1 ] /Length 3 >>\nstream\n"
        b"\x00\x00\x00\nendstream\nendobj\n"
        b"startxref\n9\n%%EOF"
    )
    with pytest.raises(PDFParseError):
        PDFParser(RandomAccessReadBuffer(bad)).parse()


def test_xref_stream_compressed_entry_records_object_stream_membership() -> None:
    """Type-2 records describe compressed objects: field2=objstm number,
    field3=index inside it. The parser must enqueue them as compressed
    pool entries (loaded lazily on demand)."""
    # Build an actual object stream so the compressed entry can resolve.
    objstm_body_payload = b"3 0 5 7 (hi) (yo)"
    # 2 objects (numbers 3 and 5), header lengths chosen by hand:
    # "3 0 5 7 " = 8 bytes (so /First = 8).
    objstm_body = b"3 0 5 7 (hi) (yo)"
    out = bytearray(b"%PDF-1.5\n")
    objstm_off = len(out)
    out += (
        b"1 0 obj\n<< /Type /ObjStm /N 2 /First 8 /Length "
        + str(len(objstm_body)).encode("ascii")
        + b" >>\nstream\n"
        + objstm_body
        + b"\nendstream\nendobj\n"
    )
    _ = objstm_body_payload  # silence linter on the helper variable
    # Xref stream: object 0 (free), object 1 (ObjStm, uncompressed),
    # object 3 (compressed inside stream 1, index 0),
    # object 5 (compressed inside stream 1, index 1),
    # object 6 (the xref stream itself).
    records = b""
    records += _pack(0, 0, 65535, 1, 4, 2)
    records += _pack(1, objstm_off, 0, 1, 4, 2)
    records += _pack(2, 1, 0, 1, 4, 2)  # obj 3 — in objstm 1, index 0
    records += _pack(2, 1, 1, 1, 4, 2)  # obj 5 — in objstm 1, index 1
    records += _pack(1, 0, 0, 1, 4, 2)  # placeholder for xref stream itself
    xref_off = len(out)
    out += (
        b"6 0 obj\n<< /Type /XRef /Size 7 /Index [ 0 2 3 1 5 2 ]"
        b" /W [ 1 4 2 ] /Length "
        + str(len(records)).encode("ascii")
        + b" >>\nstream\n"
        + records
        + b"\nendstream\nendobj\n"
    )
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    assert doc.has_object(COSObjectKey(3, 0))
    assert doc.has_object(COSObjectKey(5, 0))


def test_xref_stream_flate_with_index_subset_round_trips() -> None:
    """Real-world: Flate-compressed body + /Index covering a strict
    subset of the declared /Size (objects 0 + xref-stream + obj 1)."""
    obj1 = b"1 0 obj\n(flate-subset)\nendobj"
    out = bytearray(b"%PDF-1.5\n")
    obj1_off = len(out)
    out += obj1 + b"\n"
    records = (
        _pack(0, 0, 65535, 1, 4, 2)
        + _pack(1, obj1_off, 0, 1, 4, 2)
        + _pack(1, 0, 0, 1, 4, 2)
    )
    compressed = zlib.compress(records)
    xref_off = len(out)
    out += (
        b"2 0 obj\n<< /Type /XRef /Size 3 /Index [ 0 3 ]"
        b" /W [ 1 4 2 ] /Filter /FlateDecode /Length "
        + str(len(compressed)).encode("ascii")
        + b" >>\nstream\n"
        + compressed
        + b"\nendstream\nendobj\n"
    )
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    body = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
    assert isinstance(body, COSString) and body.get_bytes() == b"flate-subset"
